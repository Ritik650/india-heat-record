#!/usr/bin/env bash
# Install a pinned ClickHouse build under ~/heat, inside WSL or any Linux host.
# ClickHouse has no native Windows build, and its data belongs on a Linux filesystem.
set -euo pipefail
VERSION=26.8.34.13
HEAT_HOME="${HEAT_HOME:-$HOME/heat}"
BASE="https://github.com/ClickHouse/ClickHouse/releases/download/v${VERSION}-lts"
TGZ="clickhouse-common-static-${VERSION}-amd64.tgz"

mkdir -p "$HEAT_HOME/bin" "$HEAT_HOME/download"
cd "$HEAT_HOME/download"
curl -fsSL -C - -o "$TGZ" "$BASE/$TGZ"
curl -fsSL -o "$TGZ.sha512" "$BASE/$TGZ.sha512"
sha512sum -c "$TGZ.sha512"
tar -xzf "$TGZ" --strip-components=3 -C "$HEAT_HOME/bin" "clickhouse-common-static-${VERSION}/usr/bin/clickhouse"
rm -f "$TGZ" "$TGZ.sha512"
"$HEAT_HOME/bin/clickhouse" --version
