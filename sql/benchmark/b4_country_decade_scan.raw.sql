SELECT substring(station_id, 1, 2) AS country, intDiv(toYear(date), 10) * 10 AS decade, count() AS station_days,
       sum(tempMax) / countIf(tempMax != 0) AS mean_tmax, countIf(tempMax >= 400) AS days_40c
FROM heat.noaa
GROUP BY country, decade
FORMAT Null
