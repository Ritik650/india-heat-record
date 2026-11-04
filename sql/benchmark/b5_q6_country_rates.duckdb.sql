WITH months AS
(
    SELECT station_id, year(date) AS yr, month(date) AS mon,
           (sum(tempMax) / count(*) FILTER (tempMax != 0) + sum(tempMin) / count(*) FILTER (tempMin != 0)) / 20 AS mean_c
    FROM read_parquet('/root/heat/parquet/noaa_enriched.parquet', binary_as_string = true)
    WHERE date >= DATE '1982-01-01' AND date <= DATE '2021-12-31'
    GROUP BY station_id, yr, mon
    HAVING count(*) FILTER (tempMax != 0) >= 24 AND count(*) FILTER (tempMin != 0) >= 24
),
usual AS
(
    SELECT station_id, mon, avg(mean_c) AS mean_usual
    FROM months
    GROUP BY station_id, mon
)
SELECT m.station_id, substring(m.station_id, 1, 2) AS country, count(*) AS months_used, min(m.yr) AS first_year, max(m.yr) AS last_year,
       regr_slope(m.mean_c - u.mean_usual, m.yr + (m.mon - 0.5) / 12) * 10 AS rate_per_decade
FROM months AS m
JOIN usual AS u ON m.station_id = u.station_id AND m.mon = u.mon
GROUP BY m.station_id
HAVING count(*) >= 180
   AND min(m.yr) <= 1990
   AND max(m.yr) >= 2015
   AND count(*) FILTER (m.yr < 1995) >= 24
   AND count(*) FILTER (m.yr >= 1995 AND m.yr < 2010) >= 24
   AND count(*) FILTER (m.yr >= 2010) >= 24;
