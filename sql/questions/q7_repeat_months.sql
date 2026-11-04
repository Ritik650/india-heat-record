-- The repeat problem month by month around its start and end, for each station.
SELECT
    station_id,
    year,
    month,
    count(tmax) AS tmax_days,
    countIf(repeat_tmax = 1) AS tmax_repeats,
    count(tmin) AS tmin_days,
    countIf(repeat_tmin = 1) AS tmin_repeats
FROM heat.india_days
WHERE year BETWEEN 2009 AND 2017
GROUP BY station_id, year, month
ORDER BY station_id, year, month;
