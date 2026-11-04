-- Station metadata and NOAA's raw readings for Indian temperature stations.
CREATE TABLE IF NOT EXISTS heat.stations
(
    station_id LowCardinality(String),
    country    LowCardinality(String),
    lat        Float64,
    lon        Float64,
    elevation  Float32,
    state      LowCardinality(String),
    name       String,
    wmo_id     String
)
ENGINE = MergeTree
ORDER BY station_id;

CREATE TABLE IF NOT EXISTS heat.countries
(
    country LowCardinality(String),
    name    String
)
ENGINE = MergeTree
ORDER BY country;

-- Long format with NOAA's flags kept: a reading that was never taken is simply absent here,
-- which is how these rows settle what the zeros in heat.noaa mean.
CREATE TABLE IF NOT EXISTS heat.india_raw
(
    station_id LowCardinality(String),
    date       Date32,
    element    LowCardinality(String),
    value      Int32,
    mflag      LowCardinality(String),
    qflag      LowCardinality(String),
    sflag      LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY intDiv(toYear(date), 10)
ORDER BY (station_id, element, date);
