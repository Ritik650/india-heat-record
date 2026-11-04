SELECT station_id, toYear(date) AS year, countIf(tempMax >= 400) AS days_40c, sum(tempMax) / countIf(tempMax != 0) AS mean_tmax
FROM heat.noaa
WHERE substring(station_id, 1, 2) = 'IN'
GROUP BY station_id, year
FORMAT Null
