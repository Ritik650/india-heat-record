-- Q4 check: the same stations, season by season, by NOAA's source flag. This is the water-balance test:
-- rainfall that halves and then doubles when the source changes is a reporting change, not the climate.
SELECT
    station_id,
    toYear(date) AS year,
    sflag AS source,
    count() AS reports,
    countIf(value = 0) AS zero_reports,
    countIf(value >= 25) AS rainy_days,
    countIf(value >= 1000) AS heavy_days,
    sum(value) / 10 AS season_mm
FROM heat.india_raw
WHERE element = 'PRCP'
  AND qflag = ''
  AND toMonth(date) BETWEEN 6 AND 9
GROUP BY station_id, year, source
ORDER BY station_id, year, source;
