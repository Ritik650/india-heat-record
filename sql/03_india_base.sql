-- The analysis base for Indian temperature. Missing readings become NULL here, so no later query
-- can mistake a reading that was never taken for 0.0 C.
--
-- The Parquet stops on 2022-09-07. NOAA's raw files carry the same source on to 2024-12-31. They
-- are not used past that date, because NOAA moved these stations to a different source in 2025.
DROP TABLE IF EXISTS heat.india_temp;

CREATE TABLE heat.india_temp
(
    station_id LowCardinality(String),
    date       Date32,
    year       UInt16,
    month      UInt8,
    doy        UInt16 COMMENT 'day of a leap-year calendar, so 1 March is always 61',
    tmax       Nullable(Int32) COMMENT 'tenths of a degree C',
    tmin       Nullable(Int32) COMMENT 'tenths of a degree C',
    origin     LowCardinality(String) COMMENT 'parquet, or noaa_raw after the Parquet ends'
)
ENGINE = MergeTree
ORDER BY (station_id, date);

INSERT INTO heat.india_temp
SELECT
    station_id,
    date,
    toYear(date),
    toMonth(date),
    toDayOfYear(makeDate(2020, toMonth(date), toDayOfMonth(date))),
    nullIf(tempMax, 0),
    nullIf(tempMin, 0),
    'parquet'
FROM heat.noaa
WHERE station_id LIKE 'IN%'
  AND (tempMax != 0 OR tempMin != 0);

INSERT INTO heat.india_temp
SELECT
    station_id,
    date,
    toYear(date),
    toMonth(date),
    toDayOfYear(makeDate(2020, toMonth(date), toDayOfMonth(date))),
    maxIfOrNull(value, element = 'TMAX'),
    maxIfOrNull(value, element = 'TMIN'),
    'noaa_raw'
FROM heat.india_raw
WHERE date BETWEEN '2022-09-08' AND '2024-12-31'
  AND element IN ('TMAX', 'TMIN')
  AND qflag = ''
  AND sflag = 'S'
GROUP BY station_id, date;

-- Flag a maximum or minimum identical to the day before's, to the tenth. A natural repeat covers about 4% of days.
-- For maximums only, whole groups of stations jump to 20-30%: see pipeline/repeat_groups.py.
-- Heat results are reported as recorded, with these days removed, and at stations never affected.
DROP TABLE IF EXISTS heat.india_days;

CREATE TABLE heat.india_days
ENGINE = MergeTree
ORDER BY (station_id, date)
AS
SELECT
    *,
    toUInt8(ifNull(lagInFrame(toNullable(date), 1) OVER w = date - 1 AND lagInFrame(tmax, 1) OVER w = tmax, 0)) AS repeat_tmax,
    toUInt8(ifNull(lagInFrame(toNullable(date), 1) OVER w = date - 1 AND lagInFrame(tmin, 1) OVER w = tmin, 0)) AS repeat_tmin
FROM heat.india_temp
WINDOW w AS (PARTITION BY station_id ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING);

-- How complete each station-year is. Hot season means March to June, 122 days.
DROP TABLE IF EXISTS heat.station_season;

CREATE TABLE heat.station_season
ENGINE = MergeTree
ORDER BY (station_id, year)
AS
SELECT
    station_id,
    year,
    count(tmax) AS tmax_days,
    count(tmin) AS tmin_days,
    countIf(tmax IS NOT NULL AND month BETWEEN 3 AND 6) AS hot_tmax_days,
    countIf(tmin IS NOT NULL AND month BETWEEN 3 AND 6) AS hot_tmin_days,
    countIf(tmax IS NOT NULL AND month BETWEEN 1 AND 6) AS firsthalf_tmax_days,
    toUInt8(year % 4 != 0 AND tmax_days >= 292 AND tmin_days >= 292 OR year % 4 = 0 AND tmax_days >= 293 AND tmin_days >= 293) AS year_ok,
    toUInt8(hot_tmax_days >= 98) AS hot_ok,
    toUInt8(firsthalf_tmax_days >= 145) AS firsthalf_ok
FROM heat.india_days
GROUP BY station_id, year;

-- IMD heat level for one station-day. Temperatures and departures are in tenths of a degree C.
-- Returns 0 for none, 1 for heatwave and 2 for severe. Source: IMD heat wave FAQ.
--   plains:  at least 40 C, with a departure of 4.5 or more, or at least 45 C outright; severe above 6.4 or from 47 C
--   hills:   at least 30 C, with the same departures
--   coastal: at least 37 C, with a departure of 4.5 or more; IMD defines no severe level for the coast
CREATE OR REPLACE FUNCTION imd_heat_level AS (tmax, departure, station_class) ->
    multiIf(
        tmax IS NULL OR departure IS NULL, 0,
        tmax < multiIf(station_class = 'plains', 400, station_class = 'coastal', 370, 300), 0,
        station_class = 'coastal', if(departure >= 45, 1, 0),
        departure > 64 OR (station_class = 'plains' AND tmax >= 470), 2,
        departure >= 45 OR (station_class = 'plains' AND tmax >= 450), 1,
        0
    );

-- IMD warm night: only when the day's maximum is at least 40 C, then by how far the minimum sits above normal.
-- Returns 0 for none, 1 for warm and 2 for very warm.
CREATE OR REPLACE FUNCTION imd_warm_night AS (tmax, tmin_departure) ->
    multiIf(
        tmax IS NULL OR tmin_departure IS NULL OR tmax < 400, 0,
        tmin_departure > 64, 2,
        tmin_departure >= 45, 1,
        0
    );
