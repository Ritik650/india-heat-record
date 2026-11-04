"""Sort Indian stations into the plains, coastal and hill groups that IMD's heatwave rule needs.

IMD names the three groups but gives no numeric boundary for them, so these two cut-offs are this
project's assumptions. Both are tested in the sensitivity table.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import RAW, ROOT, client  # noqa: E402

HILL_METRES = 1000
COAST_KM = 50
EARTH_KM = 6371.0


def coast_points() -> list[tuple[float, float]]:
    """Coastline vertices near India, densified so gaps between them stay under about 5 km."""
    coast = json.loads((RAW / "geo" / "ne_50m_coastline.geojson").read_text(encoding="utf8"))
    points: list[tuple[float, float]] = []
    for feature in coast["features"]:
        geometry = feature["geometry"]
        lines = geometry["coordinates"] if geometry["type"] == "MultiLineString" else [geometry["coordinates"]]
        for line in lines:
            for (lon1, lat1), (lon2, lat2) in zip(line, line[1:]):
                if not (62 <= lon1 <= 100 and 2 <= lat1 <= 30):
                    continue
                steps = max(1, int(max(abs(lon2 - lon1), abs(lat2 - lat1)) / 0.05))
                for step in range(steps + 1):
                    points.append((lat1 + (lat2 - lat1) * step / steps, lon1 + (lon2 - lon1) * step / steps))
    return points


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def point_in_ring(lon: float, lat: float, ring: list) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def state_at(lon: float, lat: float, states: list) -> str | None:
    for feature in states:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        for polygon in polygons:
            if point_in_ring(lon, lat, polygon[0]) and not any(point_in_ring(lon, lat, hole) for hole in polygon[1:]):
                return next((str(v) for k, v in feature["properties"].items() if "name" in k.lower() or "state" in k.lower()), "")
    return None


def nearest_state(lon: float, lat: float, states: list) -> str:
    """The simplified outline clips some border and island stations, so name the closest state for them."""
    best, best_km = "", float("inf")
    for feature in states:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        for polygon in polygons:
            for p_lon, p_lat in polygon[0][::5]:
                distance = km(lat, lon, p_lat, p_lon)
                if distance < best_km:
                    best, best_km = next((str(v) for k, v in feature["properties"].items() if "name" in k.lower() or "state" in k.lower()), ""), distance
    return best


def classify(elevation: float, coast_km: float) -> str:
    if elevation >= HILL_METRES:
        return "hills"
    if coast_km <= COAST_KM:
        return "coastal"
    return "plains"


def main() -> None:
    ch = client()
    states = json.loads((ROOT / "data" / "geo" / "india_states_2011.geojson").read_text(encoding="utf8"))["features"]
    coast = coast_points()
    stations = ch.query("SELECT station_id, name, lat, lon, elevation FROM heat.stations WHERE country = 'IN'").result_rows
    rows = []
    for station_id, name, lat, lon, elevation in stations:
        coast_km = min(km(lat, lon, p_lat, p_lon) for p_lat, p_lon in coast)
        state = state_at(lon, lat, states)
        rows.append([station_id, name, lat, lon, float(elevation), round(coast_km, 1), classify(elevation, coast_km), state or nearest_state(lon, lat, states), 1 if state is not None else 0])
    ch.command(
        """CREATE TABLE IF NOT EXISTS heat.station_class
        (station_id LowCardinality(String), name String, lat Float64, lon Float64, elevation Float32, coast_km Float32,
         station_class LowCardinality(String), state String, inside_india UInt8)
        ENGINE = MergeTree ORDER BY station_id"""
    )
    ch.command("TRUNCATE TABLE heat.station_class")
    ch.insert("station_class", rows, column_names=["station_id", "name", "lat", "lon", "elevation", "coast_km", "station_class", "state", "inside_india"])
    print(f"{len(rows)} Indian stations classified")


if __name__ == "__main__":
    main()
