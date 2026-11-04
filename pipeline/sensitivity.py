"""How much does the heatwave result depend on this project's own choices?

IMD's rule is implemented a second time here in plain Python and must reproduce ClickHouse's stored levels
exactly. Each scenario then changes one assumption and recomputes the change from 1982-89 to the 2010s.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import MART, client  # noqa: E402

HOT_SEASON_DAYS = 122
HOT_MONTHS = (3, 4, 5, 6)


def heat_level(tmax: np.ndarray, departure: np.ndarray, station_class: np.ndarray) -> np.ndarray:
    """IMD's rule, in tenths of a degree, independent of the SQL function."""
    floor = np.select([station_class == "plains", station_class == "coastal"], [400, 370], default=300)
    plains, coastal = station_class == "plains", station_class == "coastal"
    level = np.zeros(len(tmax), dtype=int)
    above = tmax >= floor
    level[above & coastal & (departure >= 45)] = 1
    inland = above & ~coastal
    level[inland & ((departure >= 45) | (plains & (tmax >= 450)))] = 1
    level[inland & ((departure > 64) | (plains & (tmax >= 470)))] = 2
    return level


def normals(days: pd.DataFrame, first: int, last: int, half_window: int = 7) -> pd.DataFrame:
    """Daily normals from qualifying seasons, averaged over a window centred on each day."""
    usable = days[days.year.between(first, last) & days.hot_ok.eq(1) & days.tmax.notna()]
    seasons = usable.groupby("station_id").year.nunique()
    usable = usable[usable.station_id.isin(seasons[seasons >= 15].index)]
    totals = usable.groupby(["station_id", "doy"], observed=True).tmax.agg(["sum", "count"]).reset_index()
    frames = []
    for offset in range(-half_window, half_window + 1):
        shifted = totals.copy()
        shifted["doy"] = (shifted.doy.astype(int) + offset - 1) % 366 + 1
        frames.append(shifted)
    combined = pd.concat(frames).groupby(["station_id", "doy"])[["sum", "count"]].sum().reset_index()
    combined["normal_tmax"] = combined["sum"] / combined["count"]
    return combined[["station_id", "doy", "normal_tmax"]]


def classify(stations: pd.DataFrame, hill_metres: float, coast_km: float) -> pd.Series:
    return np.select([stations.elevation >= hill_metres, stations.coast_km <= coast_km], ["hills", "coastal"], default="plains")


def panel_ids(seasons: pd.DataFrame, minimum: int) -> list[str]:
    bands = {"a": (1982, 1989), "b": (1990, 1999), "c": (2000, 2009), "d": (2010, 2019)}
    good = None
    for low, high in bands.values():
        counts = seasons[seasons.hot_ok.eq(1) & seasons.year.between(low, high)].groupby("station_id").size()
        ids = set(counts[counts >= minimum].index)
        good = ids if good is None else good & ids
    return sorted(good)


def outcome(days: pd.DataFrame, seasons: pd.DataFrame, ids: list[str], column: str = "level") -> dict:
    """Mean heatwave days per hot season, each station compared with itself."""
    hot = days[days.month.isin(HOT_MONTHS) & days.station_id.isin(ids) & days.tmax.notna()]
    observed = seasons[seasons.hot_ok.eq(1) & seasons.station_id.isin(ids)][["station_id", "year", "hot_tmax_days"]]
    flagged = hot[hot[column] > 0]
    counted = flagged.groupby(["station_id", "year"]).size().rename("days")
    clean = flagged[flagged.repeat_tmax == 0].groupby(["station_id", "year"]).size().rename("clean")
    frame = observed.merge(counted, on=["station_id", "year"], how="left").merge(clean, on=["station_id", "year"], how="left").fillna(0)
    frame["days"] *= HOT_SEASON_DAYS / frame.hot_tmax_days
    frame["clean"] *= HOT_SEASON_DAYS / frame.hot_tmax_days
    before = frame[frame.year.between(1982, 1989)].groupby("station_id")[["days", "clean"]].mean()
    after = frame[frame.year.between(2010, 2019)].groupby("station_id")[["days", "clean"]].mean()
    return {
        "stations": len(before),
        "before_recorded": round(before.days.mean(), 2),
        "after_recorded": round(after.days.mean(), 2),
        "change_recorded_pct": round(100 * (after.days.mean() / before.days.mean() - 1)),
        "before_no_repeat": round(before.clean.mean(), 2),
        "after_no_repeat": round(after.clean.mean(), 2),
        "change_no_repeat_pct": round(100 * (after.clean.mean() / before.clean.mean() - 1)),
    }


def main() -> None:
    ch = client(max_threads=2)
    days = ch.query_df("SELECT station_id, year, month, doy, date, tmax, tmin, repeat_tmax FROM heat.india_days WHERE year BETWEEN 1982 AND 2024")
    seasons = ch.query_df("SELECT station_id, year, hot_ok, hot_tmax_days FROM heat.station_season")
    stations = ch.query_df("SELECT station_id, elevation, coast_km, station_class FROM heat.station_class")
    stored = ch.query_df("SELECT station_id, date, heat_level, tmax_departure FROM heat.heatwave_days WHERE year BETWEEN 1982 AND 2024")

    days = days.merge(seasons[["station_id", "year", "hot_ok"]], on=["station_id", "year"], how="left")
    days["tmax"] = pd.to_numeric(days.tmax, errors="coerce")
    days["doy"] = days.doy.astype(int)
    stations["station_id"] = stations.station_id.astype(str)

    base_normals = normals(days, 1991, 2020)
    base = days.merge(base_normals, on=["station_id", "doy"]).merge(stations[["station_id", "station_class"]], on="station_id")
    base = base[base.tmax.notna()].copy()
    base["departure"] = np.round(base.tmax - base.normal_tmax).astype(int)
    base["level"] = heat_level(base.tmax.to_numpy(), base.departure.to_numpy(), base.station_class.to_numpy())

    # The second implementation must agree with ClickHouse on every station-day before anything else is trusted.
    compare = base.merge(stored, on=["station_id", "date"], how="inner")
    mismatches = int((compare.level != compare.heat_level).sum())
    print(f"Python and ClickHouse compared on {len(compare):,} station-days: {mismatches} differ")
    if len(compare) != len(stored):
        raise SystemExit(f"Row counts differ: {len(compare):,} joined against {len(stored):,} stored")
    if mismatches:
        raise SystemExit("The two implementations of IMD's rule disagree")

    ids = panel_ids(seasons, 3)
    with_normals = set(base_normals.station_id)
    ids = [i for i in ids if i in with_normals]
    rows = [{"scenario": "This project's rule", **outcome(base, seasons, ids)}]

    def scenario(name: str, frame: pd.DataFrame, station_ids=None) -> None:
        rows.append({"scenario": name, **outcome(frame, seasons, station_ids if station_ids is not None else ids)})
        print(rows[-1])

    other = normals(days, 1981, 2010)
    usable = [i for i in ids if i in set(other.station_id)]
    frame = days.merge(other, on=["station_id", "doy"]).merge(stations[["station_id", "station_class"]], on="station_id")
    frame = frame[frame.tmax.notna()].copy()
    frame["level"] = heat_level(frame.tmax.to_numpy(), np.round(frame.tmax - frame.normal_tmax).astype(int).to_numpy(), frame.station_class.to_numpy())
    scenario("Normals from 1981-2010, not 1991-2020", frame, usable)

    raw_normals = normals(days, 1991, 2020, half_window=0)
    frame = days.merge(raw_normals, on=["station_id", "doy"]).merge(stations[["station_id", "station_class"]], on="station_id")
    frame = frame[frame.tmax.notna()].copy()
    frame["level"] = heat_level(frame.tmax.to_numpy(), np.round(frame.tmax - frame.normal_tmax).astype(int).to_numpy(), frame.station_class.to_numpy())
    scenario("Normals not smoothed across 15 days", frame)

    for label, hill, coast in [("Hills from 600 m, not 1,000 m", 600, 50), ("Coast within 25 km, not 50 km", 1000, 25), ("Coast within 100 km, not 50 km", 1000, 100)]:
        classes = pd.DataFrame({"station_id": stations.station_id, "cls": classify(stations, hill, coast)})
        frame = base.drop(columns=["station_class"]).merge(classes, on="station_id")
        frame["level"] = heat_level(frame.tmax.to_numpy(), frame.departure.to_numpy(), frame.cls.to_numpy())
        scenario(label, frame)

    frame = base.copy()
    frame["level"] = ((frame.tmax >= 400) & (frame.departure >= 45)).astype(int)
    scenario("The plan's simpler rule: 40 C and 4.5 C above normal, everywhere", frame)

    frame = base.sort_values(["station_id", "date"]).copy()
    frame["date"] = pd.to_datetime(frame.date)
    hot = frame.level > 0
    same_station = frame.station_id == frame.station_id.shift()
    consecutive_before = same_station & ((frame.date - frame.date.shift()) == pd.Timedelta(days=1))
    with_previous = hot & hot.shift(fill_value=False) & consecutive_before
    with_next = hot & hot.shift(-1, fill_value=False) & consecutive_before.shift(-1, fill_value=False)
    frame["level"] = (with_previous | with_next).astype(int)
    scenario("Counted only in runs of 2 or more days, as IMD declares", frame)

    for minimum in (2, 4):
        chosen = [i for i in panel_ids(seasons, minimum) if i in with_normals]
        scenario(f"Panel needs {minimum} seasons per period, not 3", base, chosen)

    groups = pd.read_csv(MART / "station_repeat_groups.csv").set_index("station_id").repeat_group
    scenario("Only stations repeats never affected", base, [i for i in ids if groups.get(i) == "clean"])
    scenario("Leaving out stations that stepped at 2011", base, [i for i in ids if groups.get(i) != "jumped"])

    table = pd.DataFrame(rows)
    table.to_csv(MART / "sensitivity.csv", index=False)
    print(table.to_string())


if __name__ == "__main__":
    main()
