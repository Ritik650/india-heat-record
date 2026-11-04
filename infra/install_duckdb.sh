#!/usr/bin/env bash
# DuckDB's command line, for the benchmark. Same version as the Python package in requirements.txt.
set -euo pipefail
HEAT_HOME="${HEAT_HOME:-$HOME/heat}"
VERSION=1.3.2
cd "$HEAT_HOME/bin"
curl -fsSL -o duckdb.zip "https://github.com/duckdb/duckdb/releases/download/v${VERSION}/duckdb_cli-linux-amd64.zip"
python3 -c "import zipfile; zipfile.ZipFile('duckdb.zip').extractall('.')"
rm -f duckdb.zip
chmod +x duckdb
./duckdb --version
