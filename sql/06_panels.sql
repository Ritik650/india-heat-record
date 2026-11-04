-- Which stations pass the quality bar, and how many stations report at all.

-- Coverage of Indian stations per year, from every row in the raw table.
DROP TABLE IF EXISTS heat.coverage_by_year;

CREATE TABLE heat.coverage_by_year
ENGINE = MergeTree
ORDER BY year
AS
SELECT
    y.year AS year,
    any(y.stations_any) AS stations_any,
    any(y.stations_rain) AS stations_rain,
    any(y.stations_tmax) AS stations_tmax,
    countIf(s.year_ok = 1) AS stations_full_year,
    countIf(s.hot_ok = 1) AS stations_full_hot_season
FROM
(
    SELECT
        toUInt16(year) AS year,
        uniqExact(station_id) AS stations_any,
        uniqExactIf(station_id, sum_precip > 0) AS stations_rain,
        uniqExactIf(station_id, tmax_days > 0) AS stations_tmax
    FROM heat.station_year
    WHERE station_id LIKE 'IN%'
    GROUP BY year
) AS y
LEFT JOIN heat.station_season AS s ON y.year = s.year
GROUP BY y.year;

-- A hot season counts when at least 98 of its 122 days have a maximum.
-- has_normals: 15 such seasons in 1991-2020, the period IMD uses for normals.
-- in_heat_panel: has normals, and 3 such seasons in each of 1982-89, the 1990s, the 2000s and the 2010s, so
-- changes across decades are the same stations compared with themselves.
DROP TABLE IF EXISTS heat.passing_stations;

CREATE TABLE heat.passing_stations
ENGINE = MergeTree
ORDER BY station_id
AS
SELECT
    c.station_id AS station_id,
    c.name AS name,
    c.state AS state,
    c.station_class AS station_class,
    c.lat AS lat,
    c.lon AS lon,
    c.elevation AS elevation,
    c.coast_km AS coast_km,
    s.seasons_normal AS seasons_normal,
    s.seasons_1982_89 AS seasons_1982_89,
    s.seasons_1990s AS seasons_1990s,
    s.seasons_2000s AS seasons_2000s,
    s.seasons_2010s AS seasons_2010s,
    s.seasons_2020_24 AS seasons_2020_24,
    s.seasons_total AS seasons_total,
    s.years_ok AS years_ok,
    toUInt8(s.seasons_normal >= 15) AS has_normals,
    toUInt8(s.seasons_normal >= 15 AND s.seasons_1982_89 >= 3 AND s.seasons_1990s >= 3 AND s.seasons_2000s >= 3 AND s.seasons_2010s >= 3) AS in_heat_panel
FROM heat.station_class AS c
INNER JOIN
(
    SELECT
        station_id,
        countIf(hot_ok = 1 AND year BETWEEN 1991 AND 2020) AS seasons_normal,
        countIf(hot_ok = 1 AND year BETWEEN 1982 AND 1989) AS seasons_1982_89,
        countIf(hot_ok = 1 AND year BETWEEN 1990 AND 1999) AS seasons_1990s,
        countIf(hot_ok = 1 AND year BETWEEN 2000 AND 2009) AS seasons_2000s,
        countIf(hot_ok = 1 AND year BETWEEN 2010 AND 2019) AS seasons_2010s,
        countIf(hot_ok = 1 AND year BETWEEN 2020 AND 2024) AS seasons_2020_24,
        countIf(hot_ok = 1 AND year BETWEEN 1982 AND 2024) AS seasons_total,
        countIf(year_ok = 1 AND year BETWEEN 1982 AND 2024) AS years_ok
    FROM heat.station_season
    GROUP BY station_id
) AS s ON c.station_id = s.station_id;
