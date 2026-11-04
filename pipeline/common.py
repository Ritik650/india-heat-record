"""Paths, constants and the ClickHouse connection shared by every pipeline step."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL = ROOT / "sql"
RAW = ROOT / "data" / "raw"
GHCN = RAW / "ghcn"
BY_STATION = GHCN / "by_station"
MART = ROOT / "data" / "mart"
REFERENCE = ROOT / "data" / "reference"
DOCS = ROOT / "docs"
OUTPUTS = ROOT / "outputs"
CHARTS = OUTPUTS / "charts"

GHCN_BASE = "https://noaa-ghcn-pds.s3.amazonaws.com"
PARQUET_URL = "https://datasets-documentation.s3.eu-west-3.amazonaws.com/noaa/noaa_enriched.parquet"

# Read from the file's footer, so a partial download or load cannot pass unnoticed.
PARQUET_ROWS = 1_074_089_837
PARQUET_BYTES = 2_284_954_281

# NOAA's station names are decades old. Reports use the names people know today.
STATION_NAMES = {
    "BOMBAY/SANTACRUZ": "Mumbai",
    "CALCUTTA/DUM DUM": "Kolkata",
    "POONA": "Pune",
    "MADRAS/MINAMBAKKAM": "Chennai",
    "BANGALORE": "Bengaluru",
    "GAUHATI": "Guwahati",
    "BEGUMPET        OBSY": "Hyderabad",
    "SHOLAPUR": "Solapur",
    "BELGAUM/SAMBRA": "Belagavi",
    "GOA/PANJIM": "Panaji",
    "NEW DELHI/SAFDARJUN": "New Delhi",
    "AURANGABAD CHIKALTH": "Aurangabad",
    "PBO ANANTAPUR": "Anantapur",
    "MANGALORE/BAJPE": "Mangaluru",
    "BHUJ-RUDRAMATA": "Bhuj",
    "KOTA AERODROME": "Kota",
    "HISSAR": "Hisar",
    "M.O. AMINI": "Amini",
    "M.O. RANCHI": "Ranchi",
    "CHANDIGARH(IAFB)": "Chandigarh",
    "MUKTESHWAR KUMAON": "Mukteshwar",
    "CANNUR": "Kannur",
    "CALCUTTA/ALIPORE": "Kolkata (Alipore)",
    "VISHAKHAPATNAM": "Visakhapatnam",
}


def display_name(raw: str) -> str:
    return STATION_NAMES.get(raw, raw.split("/")[0].split("  ")[0].strip().title())


CH_HOST = os.environ.get("HEAT_CH_HOST", "127.0.0.1")
CH_PORT = int(os.environ.get("HEAT_CH_PORT", "8123"))
CH_DATABASE = "heat"


def client(database: str = CH_DATABASE, **settings):
    """A ClickHouse HTTP client. Long scans need the long timeouts."""
    import clickhouse_connect

    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        database=database,
        send_receive_timeout=3600,
        settings=settings or None,
    )


def run_sql_file(ch, path: Path) -> None:
    """Run each statement in a .sql file. Statements end with a semicolon at the end of a line."""
    text = "\n".join(line for line in path.read_text(encoding="utf8").splitlines() if not line.lstrip().startswith("--"))
    for statement in text.split(";\n"):
        statement = statement.strip().rstrip(";")
        if statement:
            ch.command(statement)
