#!/usr/bin/env bash
# Time one benchmark query, in seconds, under the same limits on each engine: 4 threads, 3 GB.
# Usage: timed_query.sh clickhouse|duckdb query.sql [cold]
set -euo pipefail
HEAT_HOME="${HEAT_HOME:-$HOME/heat}"
ENGINE="$1"; FILE="$2"; MODE="${3:-warm}"
if [ "$MODE" = "cold" ]; then
    "$HEAT_HOME/bin/clickhouse" client --query "SYSTEM DROP MARK CACHE"
    "$HEAT_HOME/bin/clickhouse" client --query "SYSTEM DROP QUERY CONDITION CACHE"
    sync
    # Clearing the OS page cache needs root. Without it the first run is only partly cold.
    { echo 3 > /proc/sys/vm/drop_caches; } 2>/dev/null || true
fi
START=$(date +%s.%N)
if [ "$ENGINE" = "clickhouse" ]; then
    "$HEAT_HOME/bin/clickhouse" client --max_threads=4 --max_memory_usage=3000000000 --log_comment="$(basename "$FILE")" --queries-file "$FILE" >/dev/null
else
    { echo "SET threads=4; SET memory_limit='3GB'; SET temp_directory='$HEAT_HOME/ch/tmp/duckdb';"; sed "s#/root/heat#$HEAT_HOME#g" "$FILE"; } | "$HEAT_HOME/bin/duckdb" -batch >/dev/null
fi
END=$(date +%s.%N)
awk -v a="$START" -v b="$END" 'BEGIN { printf "%.3f\n", b - a }'
