SELECT station_id, year(date) AS year, count(*) FILTER (tempMax >= 400) AS days_40c, sum(tempMax) / count(*) FILTER (tempMax != 0) AS mean_tmax
FROM read_parquet('/root/heat/parquet/noaa_enriched.parquet', binary_as_string = true)
WHERE station_id LIKE 'IN%'
GROUP BY station_id, year(date);
