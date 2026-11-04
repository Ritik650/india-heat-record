-- Data-quality checks. Each block starts with a header line that pipeline/quality.py parses:
--   check: ID | severity | action taken
-- and the next comment line describes it. Every query returns (station, n, detail). No rows, or n = 0, means it passed.

-- check: DQ01 | high | Not a defect in the file, but every query must treat 0 as missing. Reads go through heat.india_days, where 0 becomes NULL.
-- Missing readings are stored as 0. If so, exactly 0 is far more common than its neighbours, -0.1 and +0.1 C.
SELECT
    '' AS station,
    countIf(tempMax = 0) AS n,
    concat('India: tempMax = 0 on ', toString(countIf(tempMax = 0)), ' rows, against ', toString(countIf(tempMax = 1)), ' at +0.1 C and ', toString(countIf(tempMax = -1)), ' at -0.1 C') AS detail
FROM heat.noaa
WHERE station_id LIKE 'IN%';

-- check: DQ02 | high | Rain results use only stations and periods where reports are complete, never a zero on its own.
-- A zero in precipitation can mean dry or not reported. Compare the Parquet's zeros with NOAA's raw file for temperature stations.
SELECT
    '' AS station,
    toUInt64(n_rows - n_raw) AS n,
    concat('Rows on temperature stations 1982-2021: ', toString(n_rows), '. NOAA rain reports on those rows: ', toString(n_raw), '. The difference is rows where 0 rain was never reported.') AS detail
FROM
(
    SELECT
        (SELECT count() FROM heat.noaa WHERE station_id LIKE 'IN%' AND date BETWEEN '1982-01-01' AND '2021-12-31'
            AND station_id IN (SELECT DISTINCT station_id FROM heat.india_raw)) AS n_rows,
        (SELECT count() FROM heat.india_raw WHERE element = 'PRCP' AND qflag = '' AND date BETWEEN '1982-01-01' AND '2021-12-31') AS n_raw
);

-- check: DQ03 | low | None found, so no action was needed.
-- Duplicates: more than one row per station per date, for every Indian station.
SELECT
    station_id AS station,
    count() - uniqExact(date) AS n,
    'extra rows beyond one per station per date' AS detail
FROM heat.noaa
WHERE station_id LIKE 'IN%'
GROUP BY station_id
HAVING n > 0;

-- check: DQ04 | medium | Days where the minimum exceeds the maximum are dropped from temperature means and thresholds.
-- Plausibility: tempMin above tempMax on the same day.
SELECT
    station_id AS station,
    count() AS n,
    concat('largest gap ', toString(max(tmin - tmax) / 10), ' C') AS detail
FROM heat.india_days
WHERE tmin > tmax
GROUP BY station_id
ORDER BY n DESC;

-- check: DQ05 | low | The plan's -10 to 52 C bound suits the plains. Readings outside it are real in the hills, so only non-hill stations are flagged.
-- Plausibility: maximum or minimum outside -10 to 52 C at stations below 1,000 m.
SELECT
    d.station_id AS station,
    count() AS n,
    concat(any(c.name), ', ', toString(min(least(ifNull(d.tmax, 0), ifNull(d.tmin, 0))) / 10), ' to ', toString(max(greatest(ifNull(d.tmax, 0), ifNull(d.tmin, 0))) / 10), ' C') AS detail
FROM heat.india_days AS d
INNER JOIN heat.station_class AS c ON d.station_id = c.station_id
WHERE c.station_class != 'hills'
  AND (d.tmax > 520 OR d.tmin > 520 OR d.tmax < -100 OR d.tmin < -100)
GROUP BY d.station_id
ORDER BY n DESC;

-- check: DQ06 | info | Passes by construction: NOAA's source column has no negative rain, and the column cannot hold one.
-- Plausibility: negative rainfall, and any single day above India's 24-hour record of about 1,560 mm.
SELECT
    station_id AS station,
    count() AS n,
    concat('wettest ', toString(max(precipitation) / 10), ' mm on ', toString(argMax(date, precipitation))) AS detail
FROM heat.noaa
WHERE station_id LIKE 'IN%'
  AND precipitation > 15600
GROUP BY station_id
ORDER BY n DESC;

-- check: DQ07 | medium | Reported, not removed: long gaps are why stations need 80% coverage in each year they are used.
-- Gaps: longest run of days with no temperature reading, per station, between its first and last reading since 1982.
SELECT
    station_id AS station,
    toUInt64(arrayMax(steps) - 1) AS n,
    concat('longest gap in days, ending ', toString(toDate32(days[indexOf(steps, arrayMax(steps))]))) AS detail
FROM
(
    SELECT
        station_id,
        arraySort(groupArray(toInt32(date))) AS days,
        arrayDifference(days) AS steps
    FROM heat.india_days
    WHERE year >= 1982
    GROUP BY station_id
)
WHERE arrayMax(steps) >= 366
ORDER BY n DESC;

-- check: DQ08 | low | Kept. Every station flagged is a border or island location that the simplified outline clips, or an offshore pilot station.
-- Location: IN-prefix stations whose coordinates fall outside the outline of India.
SELECT
    station_id AS station,
    toUInt64(1) AS n,
    concat(name, ' (', toString(lat), ', ', toString(lon), '), ', toString(round(coast_km)), ' km from the coast') AS detail
FROM heat.station_class
WHERE inside_india = 0
ORDER BY station;

-- check: DQ09 | low | Station list coordinates are used for maps, as the Parquet's copy is older.
-- Location: the Parquet's coordinates disagree with NOAA's current station list by more than 0.1 degree.
SELECT
    n.station_id AS station,
    count() AS n,
    concat('Parquet ', toString(round(any(n.location.2), 3)), ', ', toString(round(any(n.location.1), 3)), ' against list ', toString(any(c.lat)), ', ', toString(any(c.lon))) AS detail
FROM heat.noaa AS n
INNER JOIN heat.station_class AS c ON n.station_id = c.station_id
WHERE n.station_id LIKE 'IN%'
  AND (abs(n.location.2 - c.lat) > 0.1 OR abs(n.location.1 - c.lon) > 0.1)
GROUP BY n.station_id
ORDER BY n DESC;

-- check: DQ10 | high | Stations are grouped by when this affected them. Heat counts are reported as recorded, with repeats removed, and at stations never affected.
-- Repeated readings: maximum identical to the day before. Whole groups of stations jump well above a natural level near 4%.
SELECT
    '' AS station,
    toUInt64(countIf(repeat_tmax = 1)) AS n,
    concat('Share of days repeating the previous maximum: ', toString(round(100 * countIf(repeat_tmax = 1 AND year BETWEEN 1982 AND 1988) / countIf(tmax IS NOT NULL AND year BETWEEN 1982 AND 1988), 1)), '% in 1982-88, ', toString(round(100 * countIf(repeat_tmax = 1 AND year BETWEEN 2011 AND 2024) / countIf(tmax IS NOT NULL AND year BETWEEN 2011 AND 2024), 1)), '% in 2011-24') AS detail
FROM heat.india_days
WHERE year >= 1982;

-- check: DQ11 | high | Threshold questions start in 1982, and a sensitivity test rounds every year to whole degrees.
-- Rounding: every maximum from 1973 to 1981 is a whole degree, which moves values across a 40 C cut-off.
SELECT
    '' AS station,
    toUInt64(countIf(tmax % 10 = 0 AND year BETWEEN 1973 AND 1981)) AS n,
    concat('Whole-degree share of maximums: ', toString(round(100 * countIf(tmax % 10 = 0 AND year BETWEEN 1973 AND 1981) / countIf(tmax IS NOT NULL AND year BETWEEN 1973 AND 1981), 1)), '% in 1973-81, ', toString(round(100 * countIf(tmax % 10 = 0 AND year BETWEEN 1982 AND 2021) / countIf(tmax IS NOT NULL AND year BETWEEN 1982 AND 2021), 1)), '% in 1982-2021') AS detail
FROM heat.india_days;

-- check: DQ12 | high | The Parquet and NOAA's raw files are compared before the raw files extend the series past September 2022.
-- Reconciliation: Indian maximums in the Parquet that disagree with NOAA's raw files or are absent from them.
SELECT
    '' AS station,
    toUInt64(countIf(r.value IS NULL OR r.value != p.tmax)) AS n,
    concat(toString(count()), ' Parquet maximums compared; ', toString(countIf(r.value = p.tmax)), ' identical, ', toString(countIf(r.value != p.tmax)), ' differ, ', toString(countIf(r.value IS NULL)), ' not in the raw files') AS detail
FROM
(
    SELECT station_id, date, tmax
    FROM heat.india_days
    WHERE origin = 'parquet' AND tmax IS NOT NULL
) AS p
LEFT JOIN
(
    SELECT station_id, date, toNullable(value) AS value
    FROM heat.india_raw
    WHERE element = 'TMAX' AND qflag = ''
) AS r ON p.station_id = r.station_id AND p.date = r.date;

-- check: DQ13 | high | Temperature stops at December 2024. Later values come from a different source and are not spliced on.
-- Source break: NOAA moved Indian stations from its Summary of the Day source to a different one during 2025.
SELECT
    '' AS station,
    toUInt64(countIf(sflag != 'S' AND toYear(date) >= 2025)) AS n,
    concat('Maximums from a source other than S: ', toString(countIf(sflag != 'S' AND toYear(date) <= 2024)), ' through 2024, ', toString(countIf(sflag != 'S' AND toYear(date) >= 2025)), ' from 2025') AS detail
FROM heat.india_raw
WHERE element = 'TMAX' AND qflag = '';

-- check: DQ14 | medium | Annual trends use whole years, and 2022 comes from NOAA's raw files after 7 September.
-- Coverage: the Parquet stops on 7 September 2022, not at the end of 2022.
SELECT
    '' AS station,
    toUInt64(dateDiff('day', max(date), toDate32('2022-12-31'))) AS n,
    concat('Last date in the Parquet: ', toString(max(date)), '; days short of the end of 2022 are in n') AS detail
FROM heat.noaa
WHERE date >= '2022-01-01';

-- check: DQ15 | low | Station list elevations replace the missing values. Stations with no elevation at all count as plains.
-- Elevation: Indian stations whose elevation is the missing marker, -999.9.
SELECT
    station_id AS station,
    toUInt64(1) AS n,
    name AS detail
FROM heat.station_class
WHERE elevation < -900
ORDER BY station;
