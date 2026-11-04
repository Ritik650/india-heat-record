-- How the repeat problem looks at each station and year, for maximums and minimums alike.
-- A change in how the data was processed should hit both readings, and most stations, at the same time.
SELECT
    station_id,
    year,
    count(tmax) AS tmax_days,
    countIf(repeat_tmax = 1) AS tmax_repeats,
    count(tmin) AS tmin_days,
    countIf(repeat_tmin = 1) AS tmin_repeats
FROM heat.india_days
WHERE year BETWEEN 1982 AND 2024
GROUP BY station_id, year
ORDER BY station_id, year;
