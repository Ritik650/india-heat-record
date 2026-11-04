#!/usr/bin/env bash
# Run ClickHouse in the foreground from ~/heat/ch, so the data stays on the Linux filesystem.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEAT_HOME="${HEAT_HOME:-$HOME/heat}"
mkdir -p "$HEAT_HOME/ch/log"
cp "$HERE/clickhouse_config.xml" "$HEAT_HOME/ch/config.xml"
cp "$HERE/users.xml" "$HEAT_HOME/ch/users.xml"
cd "$HEAT_HOME/ch"
exec "$HEAT_HOME/bin/clickhouse" server --config-file=config.xml
