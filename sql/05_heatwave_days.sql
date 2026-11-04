-- One row per station-day that has normals, with IMD's heat and warm-night levels and the flags
-- that the artefact tests need.
DROP TABLE IF EXISTS heat.heatwave_days;

CREATE TABLE heat.heatwave_days
ENGINE = MergeTree
ORDER BY (station_id, date)
AS
WITH joined AS
(
    SELECT
        t.station_id AS station_id,
        t.date AS date,
        t.year AS year,
        t.month AS month,
        t.doy AS doy,
        t.tmax AS tmax,
        t.tmin AS tmin,
        t.origin AS origin,
        t.repeat_tmax AS repeat_tmax,
        t.repeat_tmin AS repeat_tmin,
        c.station_class AS station_class,
        toInt32(round(t.tmax - n.normal_tmax)) AS tmax_departure,
        toInt32(round(t.tmin - n.normal_tmin)) AS tmin_departure,
        imd_heat_level(t.tmax, tmax_departure, c.station_class) AS heat_level,
        imd_warm_night(t.tmax, tmin_departure) AS night_level,
        -- Rounding all years to whole degrees shows what the 1973-1981 rounding does to the counts.
        imd_heat_level(toInt32(round(t.tmax / 10)) * 10, toInt32(round((toInt32(round(t.tmax / 10)) * 10) - n.normal_tmax)), c.station_class) AS heat_level_rounded
    FROM heat.india_days AS t
    INNER JOIN heat.station_normals AS n ON t.station_id = n.station_id AND t.doy = n.doy
    INNER JOIN heat.station_class AS c ON t.station_id = c.station_id
    WHERE t.tmax IS NOT NULL
)
SELECT
    *,
    -- IMD declares on the second consecutive day, so this is the stricter count.
    toUInt8(heat_level > 0 AND (
        (lagInFrame(toNullable(date), 1) OVER w = date - 1 AND lagInFrame(heat_level, 1) OVER w > 0)
        OR (leadInFrame(toNullable(date), 1) OVER w = date + 1 AND leadInFrame(heat_level, 1) OVER w > 0)
    )) AS in_spell
FROM joined
WINDOW w AS (PARTITION BY station_id ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING);
