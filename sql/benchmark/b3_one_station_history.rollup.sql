SELECT year, sum(days_40c) AS days_40c
FROM heat.station_year
WHERE station_id = 'IN022021900'
GROUP BY year
FORMAT Null
