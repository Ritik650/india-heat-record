#!/usr/bin/env bash
# Install a pinned Grafana and the ClickHouse data source under ~/heat, inside WSL or any Linux host.
set -euo pipefail
HEAT_HOME="${HEAT_HOME:-$HOME/heat}"
VERSION=12.2.1
PLUGIN_VERSION=4.21.3
mkdir -p "$HEAT_HOME/download"
cd "$HEAT_HOME/download"
curl -fsSL -C - -o grafana.tar.gz "https://dl.grafana.com/oss/release/grafana-${VERSION}.linux-amd64.tar.gz"
rm -rf "$HEAT_HOME/grafana"
mkdir -p "$HEAT_HOME/grafana"
tar -xzf grafana.tar.gz --strip-components=1 -C "$HEAT_HOME/grafana"
rm -f grafana.tar.gz
cd "$HEAT_HOME/grafana"
./bin/grafana cli --pluginsDir "$HEAT_HOME/grafana/data/plugins" plugins install grafana-clickhouse-datasource "$PLUGIN_VERSION"
du -sh "$HEAT_HOME/grafana"
