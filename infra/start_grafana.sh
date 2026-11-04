#!/usr/bin/env bash
# Run Grafana in the foreground on http://127.0.0.1:3000 with the dashboard provisioned from this repository.
# Anonymous read-only access suits a laptop-only server, and nothing listens beyond loopback.
set -euo pipefail
HEAT_HOME="${HEAT_HOME:-$HOME/heat}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
GRAFANA="$HEAT_HOME/grafana"

# Grafana reads the outline from its own public folder.
mkdir -p "$GRAFANA/public/maps"
cp "$REPO/data/geo/india_states_2011.geojson" "$GRAFANA/public/maps/india_states.geojson"
# A blank tile keeps online basemaps, with their own borders and labels, off the map.
cp "$REPO/dashboard/blank_tile.png" "$GRAFANA/public/maps/blank_tile.png"

# Provisioning files need the repository's path, so copy them in with it filled.
PROVISIONING="$HEAT_HOME/grafana-provisioning"
rm -rf "$PROVISIONING"
mkdir -p "$PROVISIONING/datasources" "$PROVISIONING/dashboards" "$PROVISIONING/plugins" "$PROVISIONING/alerting"
cp "$REPO/dashboard/provisioning/datasources/clickhouse.yml" "$PROVISIONING/datasources/"
sed "s#__DASHBOARD_DIR__#$REPO/dashboard#" "$REPO/dashboard/provisioning/dashboards/dashboards.yml" > "$PROVISIONING/dashboards/dashboards.yml"

export GF_SERVER_HTTP_ADDR=127.0.0.1
export GF_SERVER_HTTP_PORT=3000
export GF_PATHS_PROVISIONING="$PROVISIONING"
export GF_PATHS_PLUGINS="$GRAFANA/data/plugins"
export GF_AUTH_ANONYMOUS_ENABLED=true
export GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
export GF_AUTH_DISABLE_LOGIN_FORM=false
export GF_USERS_DEFAULT_THEME=light
export GF_ANALYTICS_REPORTING_ENABLED=false
export GF_ANALYTICS_CHECK_FOR_UPDATES=false
export GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES=false
export GF_NEWS_NEWS_FEED_ENABLED=false
export GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH="$REPO/dashboard/india_heat.json"
cd "$GRAFANA"
exec ./bin/grafana server --homepath "$GRAFANA"
