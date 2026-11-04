-- Daily normals per station, 1991-2020, the period IMD now uses.
-- The plan's 1961-1990 cannot be built: no Indian station has 20 complete years in it.
-- A single calendar day gets about 25 readings, which is noisy, so each normal averages the
-- 15 days centred on it. A station needs 15 complete hot seasons in the window to get normals.
DROP TABLE IF EXISTS heat.station_normals;

CREATE TABLE heat.station_normals
(
    station_id   LowCardinality(String),
    doy          UInt16,
    normal_tmax  Float32 COMMENT 'tenths of a degree C',
    normal_tmin  Float32 COMMENT 'tenths of a degree C',
    readings     UInt32
)
ENGINE = MergeTree
ORDER BY (station_id, doy);

INSERT INTO heat.station_normals
SELECT
    station_id,
    toUInt16(((toInt32(t.doy) + window_offset - 1 + 366) % 366) + 1) AS doy_centre,
    avg(t.tmax),
    avg(t.tmin),
    count(t.tmax)
FROM heat.india_days AS t
ARRAY JOIN range(-7, 8) AS window_offset
WHERE t.year BETWEEN 1991 AND 2020
  AND (t.station_id, t.year) IN (
        SELECT station_id, year FROM heat.station_season
        WHERE hot_ok = 1 AND year BETWEEN 1991 AND 2020
  )
  AND t.station_id IN (
        SELECT station_id FROM heat.station_season
        WHERE hot_ok = 1 AND year BETWEEN 1991 AND 2020
        GROUP BY station_id
        HAVING count() >= 15
  )
GROUP BY station_id, doy_centre;
