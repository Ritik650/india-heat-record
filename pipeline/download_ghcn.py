"""Download NOAA's raw per-station files for every Indian station that ever reported temperature.

The ClickHouse Parquet dropped NOAA's flags and stores a missing reading as 0. These files keep
both, so they settle which zeros are real, which source each value came from, and what the
Parquet's quality filter removed.

Usage: python pipeline/download_ghcn.py
"""
from __future__ import annotations

import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import BY_STATION, GHCN, GHCN_BASE, RAW  # noqa: E402

TEMPERATURE = {"TMAX", "TMIN", "TAVG"}
METADATA = ["ghcnd-stations.txt", "ghcnd-inventory.txt", "ghcnd-version.txt", "readme.txt"]
COASTLINE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_coastline.geojson"


def temperature_stations() -> list[str]:
    stations = set()
    with open(GHCN / "ghcnd-inventory.txt", encoding="ascii") as inventory:
        for line in inventory:
            if line.startswith("IN") and line[31:35] in TEMPERATURE:
                stations.add(line[:11])
    return sorted(stations)


def fetch(station: str) -> int:
    target = BY_STATION / f"{station}.csv"
    if target.exists() and target.stat().st_size > 0:
        return target.stat().st_size
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"{GHCN_BASE}/csv/by_station/{station}.csv", timeout=120) as response:
                body = response.read()
            part = target.with_suffix(".part")
            part.write_bytes(body)
            part.replace(target)
            return len(body)
        except OSError:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    return 0


def fetch_url(url: str, target: Path) -> None:
    if target.exists() and target.stat().st_size > 0:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as response:
        target.write_bytes(response.read())


def main() -> None:
    BY_STATION.mkdir(parents=True, exist_ok=True)
    for name in METADATA:
        fetch_url(f"{GHCN_BASE}/{name}", GHCN / name)
    fetch_url(COASTLINE, RAW / "geo" / "ne_50m_coastline.geojson")
    stations = temperature_stations()
    with ThreadPoolExecutor(max_workers=6) as pool:
        sizes = list(pool.map(fetch, stations))
    print(f"{len(stations)} Indian temperature stations, {sum(sizes) / 1e6:.0f} MB in {BY_STATION}")


if __name__ == "__main__":
    main()
