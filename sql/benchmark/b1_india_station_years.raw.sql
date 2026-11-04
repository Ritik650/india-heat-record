SELECT station_id, toYear(date) AS year, countIf(tempMax >= 400) AS days_40c, sum(tempMax) / countIf(tempMax != 0) AS mean_tmax
FROM heat.noaa
WHERE station_id LIKE 'IN%'
GROUP BY station_id, year
FORMAT Null
