SELECT substring(station_id, 1, 2) AS country, intDiv(year, 10) * 10 AS decade, sum(days_obs) AS station_days,
       sum(sum_tmax) / sum(tmax_days) AS mean_tmax, sum(days_40c) AS days_40c
FROM heat.station_year
GROUP BY country, decade
FORMAT Null
