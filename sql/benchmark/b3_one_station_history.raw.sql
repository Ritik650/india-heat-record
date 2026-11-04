SELECT toYear(date) AS year, max(tempMax) AS hottest, countIf(tempMax >= 400) AS days_40c
FROM heat.noaa
WHERE station_id = 'IN022021900'
GROUP BY year
FORMAT Null
