"""Load NOAA's station list, country list and raw Indian station files into ClickHouse."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import BY_STATION, GHCN, REFERENCE, SQL, client, run_sql_file  # noqa: E402

BATCH = 500_000
RAW_COLUMNS = ["station_id", "date", "element", "value", "mflag", "qflag", "sflag"]


def stations() -> list[list]:
    """Fixed-width fields as documented in NOAA's readme, section IV."""
    rows = []
    with open(GHCN / "ghcnd-stations.txt", encoding="ascii") as handle:
        for line in handle:
            rows.append([
                line[0:11], line[0:2], float(line[12:20]), float(line[21:30]), float(line[31:37]),
                line[38:40].strip(), line[41:71].strip(), line[80:85].strip(),
            ])
    return rows


def countries() -> list[list]:
    with open(REFERENCE / "ghcnd-countries.txt", encoding="ascii") as handle:
        return [[line[0:2], line[3:].strip()] for line in handle]


def raw_rows(path: Path):
    from datetime import date

    with open(path, newline="", encoding="ascii") as handle:
        for row in csv.DictReader(handle):
            day = row["DATE"]
            yield [row["ID"], date(int(day[:4]), int(day[4:6]), int(day[6:8])), row["ELEMENT"],
                   int(row["DATA_VALUE"]), row["M_FLAG"], row["Q_FLAG"], row["S_FLAG"]]


def main() -> None:
    ch = client()
    run_sql_file(ch, SQL / "02_reference.sql")
    for table in ("stations", "countries", "india_raw"):
        ch.command(f"TRUNCATE TABLE heat.{table}")
    ch.insert("stations", stations(), column_names=["station_id", "country", "lat", "lon", "elevation", "state", "name", "wmo_id"])
    ch.insert("countries", countries(), column_names=["country", "name"])

    wanted = {"TMAX", "TMIN", "PRCP"}
    batch: list[list] = []
    total = 0
    for path in sorted(BY_STATION.glob("*.csv")):
        for row in raw_rows(path):
            if row[2] in wanted:
                batch.append(row)
        if len(batch) >= BATCH:
            ch.insert("india_raw", batch, column_names=RAW_COLUMNS)
            total += len(batch)
            batch = []
    if batch:
        ch.insert("india_raw", batch, column_names=RAW_COLUMNS)
        total += len(batch)
    print(f"stations {ch.command('SELECT count() FROM heat.stations')}, countries {ch.command('SELECT count() FROM heat.countries')}, india_raw {total:,} rows")


if __name__ == "__main__":
    main()
