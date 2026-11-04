SELECT year(date) AS year, max(tempMax) AS hottest, count(*) FILTER (tempMax >= 400) AS days_40c
FROM read_parquet('/root/heat/parquet/noaa_enriched.parquet', binary_as_string = true)
WHERE station_id = 'IN022021900'
GROUP BY year(date);
