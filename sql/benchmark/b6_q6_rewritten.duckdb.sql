WITH months AS
(
    SELECT station_id, year(date) AS yr, month(date) AS mon,
           (sum(tempMax) / count(*) FILTER (tempMax != 0) + sum(tempMin) / count(*) FILTER (tempMin != 0)) / 20 AS mean_c
    FROM read_parquet('/root/heat/parquet/noaa_enriched.parquet', binary_as_string = true)
    WHERE date >= DATE '1982-01-01' AND date <= DATE '2021-12-31'
    GROUP BY station_id, yr, mon
    HAVING count(*) FILTER (tempMax != 0) >= 24 AND count(*) FILTER (tempMin != 0) >= 24
),
anomalies AS
(
    SELECT station_id, yr, mon, mean_c - avg(mean_c) OVER (PARTITION BY station_id, mon) AS anomaly
    FROM months
)
SELECT station_id, substring(station_id, 1, 2) AS country, count(*) AS months_used, min(yr) AS first_year, max(yr) AS last_year,
       regr_slope(anomaly, yr + (mon - 0.5) / 12) * 10 AS rate_per_decade
FROM anomalies
GROUP BY station_id
HAVING count(*) >= 180
   AND min(yr) <= 1990
   AND max(yr) >= 2015
   AND count(*) FILTER (yr < 1995) >= 24
   AND count(*) FILTER (yr >= 1995 AND yr < 2010) >= 24
   AND count(*) FILTER (yr >= 2010) >= 24;
