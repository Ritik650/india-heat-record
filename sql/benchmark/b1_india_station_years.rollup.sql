SELECT station_id, year, sum(days_40c) AS days_40c, sum(sum_tmax) / sum(tmax_days) AS mean_tmax
FROM heat.station_year
WHERE station_id LIKE 'IN%'
GROUP BY station_id, year
FORMAT Null
