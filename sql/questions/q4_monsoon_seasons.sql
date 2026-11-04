-- Q4: is monsoon rain getting more extreme? One row per Indian station and June-September season.
-- Rainy day is at least 2.5 mm, heavy day at least 100 mm, both in tenths of a mm in the source.
-- Reports means rows in the season. That equals days reported only for rain-only stations, because a
-- station that also reports temperature gets a row with precipitation 0 on days without a rain report.
SELECT
    station_id,
    toYear(date) AS year,
    count() AS reports,
    countIf(precipitation >= 25) AS rainy_days,
    countIf(precipitation >= 1000) AS heavy_days,
    sum(precipitation) / 10 AS season_mm,
    max(precipitation) / 10 AS wettest_day_mm,
    countIf(tempMax != 0 OR tempMin != 0) AS rows_with_temperature
FROM heat.noaa
WHERE station_id LIKE 'IN%'
  AND toMonth(date) BETWEEN 6 AND 9
GROUP BY station_id, year
ORDER BY station_id, year;
