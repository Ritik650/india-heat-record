#!/usr/bin/env bash
# Load the Parquet into heat.noaa on the server side. The server's memory cap then covers the
# Parquet reader too, and it loaded about four times faster than INSERT ... FROM INFILE on the client.
set -euo pipefail
HEAT_HOME="${HEAT_HOME:-$HOME/heat}"
mkdir -p "$HEAT_HOME/ch/data/user_files"
ln -sfn "$HEAT_HOME/parquet" "$HEAT_HOME/ch/data/user_files/parquet"
"$HEAT_HOME/bin/clickhouse" client --query "
INSERT INTO heat.noaa
SELECT * FROM file('parquet/noaa_enriched.parquet', Parquet)
SETTINGS max_threads = 2, max_insert_threads = 2,
         min_insert_block_size_rows = 1000000, min_insert_block_size_bytes = 0,
         input_format_parquet_max_block_size = 65536"
