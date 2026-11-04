SELECT substring(station_id, 1, 2) AS country, (year(date) // 10) * 10 AS dcd, count(*) AS station_days,
       sum(tempMax) / count(*) FILTER (tempMax != 0) AS mean_tmax, count(*) FILTER (tempMax >= 400) AS days_40c
FROM read_parquet('/root/heat/parquet/noaa_enriched.parquet', binary_as_string = true)
GROUP BY 1, 2;
