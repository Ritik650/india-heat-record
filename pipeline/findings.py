"""Turn the saved query results into data/mart/findings.json.

Every figure in the brief, README and dashboard notes comes from this file, so nothing is typed by hand.
Uncertainty resamples stations rather than days: nearby days are not independent, and the question is
whether a pattern holds across stations or rests on a few.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import MART, PARQUET_BYTES, PARQUET_ROWS, REFERENCE, display_name  # noqa: E402
from repeat_groups import analyse as analyse_repeats  # noqa: E402

SEED = 20261105
BOOTSTRAPS = 10_000
HOT_SEASON_DAYS = 122
PERIODS = [(1982, 1989, "1982-89"), (1990, 1999, "1990s"), (2000, 2009, "2000s"), (2010, 2019, "2010s"), (2020, 2024, "2020-24")]
BEFORE, AFTER = "1982-89", "2010s"
RAIN_ERAS = [(1901, 1972, "1901-72"), (1973, 1981, "1973-81"), (1982, 1998, "1982-98"), (1999, 2005, "1999-2005"), (2006, 2015, "2006-15"), (2016, 2024, "2016-24")]

# Published figures this project is checked against. Sources are listed in docs/sources.md.
MEASUREMENTS_BEFORE_PIVOT = 2_679_264_563
IMD_103_STATIONS = {"1981-90": 413, "2001-10": 575, "2011-20": 600}
IMD_RECORDS = [
    {"station": "IN019100500", "name": "Churu", "date": "2019-06-01", "celsius": 50.8},
    {"station": "IN019100500", "name": "Churu", "date": "2024-05-28", "celsius": 50.5},
]


def period_of(year: int) -> str | None:
    for low, high, name in PERIODS:
        if low <= year <= high:
            return name
    return None


def bootstrap(values: np.ndarray, statistic, seed: int = SEED) -> tuple[float, float]:
    """95% interval for a statistic of one value per station."""
    rng = np.random.default_rng(seed)
    n = len(values)
    samples = [statistic(values[rng.integers(0, n, n)]) for _ in range(BOOTSTRAPS)]
    return float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def two_sided_sign_test(wins: int, total: int) -> float:
    """Chance of a split at least this lopsided if each station were a coin flip."""
    extreme = min(wins, total - wins)
    tail = sum(math.comb(total, k) for k in range(extreme + 1)) / 2**total
    return min(1.0, 2 * tail)


def fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Slope per decade, and a standard error widened for month-to-month autocorrelation."""
    slope, intercept = np.polyfit(x, y, 1)
    residual = y - (slope * x + intercept)
    n = len(x)
    rho = float(np.corrcoef(residual[:-1], residual[1:])[0, 1]) if n > 3 else 0.0
    rho = max(0.0, min(rho, 0.95))
    effective = max(3.0, n * (1 - rho) / (1 + rho))
    se = math.sqrt((residual**2).sum() / (effective - 2) / ((x - x.mean()) ** 2).sum())
    return float(slope * 10), float(se * 10), rho


def rounded(value, digits=2):
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else round(float(value), digits)


def doy_to_date(doy: float) -> str:
    """Day of a leap-year calendar, as written in the brief."""
    day = pd.Timestamp("2020-01-01") + pd.Timedelta(days=round(doy) - 1)
    return f"{day.day} {day.strftime('%B')}"


def heatwaves(passing: pd.DataFrame, groups: pd.Series) -> tuple[dict, pd.DataFrame]:
    seasons = pd.read_csv(MART / "q1_heatwave_seasons.csv")
    seasons["period"] = seasons.year.map(period_of)
    measures = ["heatwave_days", "severe_days", "heatwave_days_no_repeat", "severe_days_no_repeat", "spell_days", "heatwave_days_rounded"]
    for measure in measures:
        seasons[measure] = seasons[measure] * HOT_SEASON_DAYS / seasons.observed_days
    panel_ids = passing[passing.in_heat_panel == 1].station_id
    panel = seasons[seasons.station_id.isin(panel_ids)]
    per_period = panel.groupby(["station_id", "period"])[measures].mean().reset_index()
    per_period = per_period.merge(passing[["station_id", "name", "state", "station_class"]], on="station_id")
    per_period.to_csv(MART / "q1_station_periods.csv", index=False)

    def compare(measure: str, ids=None) -> dict:
        chosen = per_period if ids is None else per_period[per_period.station_id.isin(ids)]
        wide = chosen.pivot(index="station_id", columns="period", values=measure)
        before, after = wide[BEFORE].to_numpy(), wide[AFTER].to_numpy()
        change = after - before
        low, high = bootstrap(change, np.mean)
        pct_low, pct_high = bootstrap(np.arange(len(before)), lambda idx: 100 * (after[idx.astype(int)].mean() / before[idx.astype(int)].mean() - 1))
        rising = int((change > 0).sum())
        return {
            "before": rounded(before.mean()),
            "after": rounded(after.mean()),
            "change_days": rounded(change.mean()),
            "change_days_ci": [rounded(low), rounded(high)],
            "change_pct": rounded(100 * (after.mean() / before.mean() - 1), 0),
            "change_pct_ci": [rounded(pct_low, 0), rounded(pct_high, 0)],
            "stations_rising": rising,
            "stations_falling": int((change < 0).sum()),
            "stations": len(change),
            "sign_test_p": rounded(two_sided_sign_test(rising, int((change != 0).sum())), 3),
            "median_change": rounded(np.median(change)),
        }

    table = {
        name: {measure: rounded(per_period[per_period.period == name][measure].mean()) for measure in measures}
        | {"stations_with_seasons": int(panel[panel.period == name].station_id.nunique()), "seasons": int((panel.period == name).sum())}
        for _, _, name in PERIODS
    }
    recorded, cleaned = compare("heatwave_days"), compare("heatwave_days_no_repeat")
    in_panel = pd.Series(groups.reindex(panel_ids).to_numpy(), index=panel_ids.to_numpy())
    by_group = {}
    for key in ("clean", "jumped", "early"):
        ids = in_panel[in_panel == key].index
        by_group[key] = {"names": sorted(passing[passing.station_id.isin(ids)].name), "recorded": compare("heatwave_days", ids), "without_repeats": compare("heatwave_days_no_repeat", ids)}
    per_period.assign(repeat_group=per_period.station_id.map(in_panel)).groupby(["repeat_group", "period"])[["heatwave_days", "heatwave_days_no_repeat"]].mean().round(3).reset_index().to_csv(MART / "q1_group_periods.csv", index=False)
    raw_rise = recorded["after"] - recorded["before"]
    clean_rise = cleaned["after"] - cleaned["before"]

    # Repeats by year. Whole-year shares come from the issue log; this is the hot season at stations with normals.
    by_year = seasons.groupby("year").agg(stations=("station_id", "nunique"), repeat_days=("repeat_days", "sum"), observed=("observed_days", "sum"))
    by_year["repeat_pct"] = 100 * by_year.repeat_days / by_year.observed
    by_year.reset_index().to_csv(MART / "repeats_by_year.csv", index=False)
    window = lambda a, b: by_year[by_year.index.to_series().between(a, b)]  # noqa: E731
    share = lambda a, b: 100 * window(a, b).repeat_days.sum() / window(a, b).observed.sum()  # noqa: E731

    # The most recent hot seasons, each station against its own 1991-2020 average.
    usual = seasons[seasons.year.between(1991, 2020)].groupby("station_id")[["heatwave_days", "heatwave_days_no_repeat"]].mean()
    recent = {}
    for year in (2022, 2023, 2024):
        rows = seasons[seasons.year == year].merge(usual, left_on="station_id", right_index=True, suffixes=("", "_usual"))
        recent[str(year)] = {
            "stations": len(rows),
            "heatwave_days": rounded(rows.heatwave_days.mean()),
            "heatwave_days_usual": rounded(rows.heatwave_days_usual.mean()),
            "no_repeat": rounded(rows.heatwave_days_no_repeat.mean()),
            "no_repeat_usual": rounded(rows.heatwave_days_no_repeat_usual.mean()),
            "stations_above_usual": int((rows.heatwave_days_no_repeat > rows.heatwave_days_no_repeat_usual).sum()),
        }

    classes = per_period.groupby(["station_class", "period"])[["heatwave_days", "heatwave_days_no_repeat"]].mean().round(2)
    clean_wide = per_period.pivot(index="name", columns="period", values="heatwave_days_no_repeat")
    biggest_rises = (clean_wide[AFTER] - clean_wide[BEFORE]).sort_values(ascending=False)
    rarely_any = int(((clean_wide[BEFORE] < 1) & (clean_wide[AFTER] < 1)).sum())
    imd_change = 100 * (IMD_103_STATIONS["2011-20"] / IMD_103_STATIONS["1981-90"] - 1)
    return {
        "panel_stations": int(len(panel_ids)),
        "panel_by_class": passing[passing.in_heat_panel == 1].station_class.value_counts().to_dict(),
        "periods": table,
        "recorded": recorded,
        "without_repeats": cleaned,
        "by_repeat_group": by_group,
        "share_of_rise_from_repeats_pct": rounded(100 * (1 - clean_rise / raw_rise), 0),
        "stations_under_one_day_both_periods": rarely_any,
        "biggest_rises": biggest_rises.head(3).index.tolist(),
        "repeat_pct_2010": rounded(by_year.repeat_pct.get(2010), 1),
        "repeat_pct_2011": rounded(by_year.repeat_pct.get(2011), 1),
        "repeat_pct_1982_88": rounded(share(1982, 1988), 1),
        "repeat_pct_1991_2010": rounded(share(1991, 2010), 1),
        "repeat_pct_2011_2024": rounded(share(2011, 2024), 1),
        "stricter_two_day": {"before": table[BEFORE]["spell_days"], "after": table[AFTER]["spell_days"]},
        "severe": {
            "before": table[BEFORE]["severe_days"], "after": table[AFTER]["severe_days"],
            "before_no_repeat": table[BEFORE]["severe_days_no_repeat"], "after_no_repeat": table[AFTER]["severe_days_no_repeat"],
        },
        "rounded_to_whole_degrees": {"before": table[BEFORE]["heatwave_days_rounded"], "after": table[AFTER]["heatwave_days_rounded"]},
        "by_class": {f"{a}|{b}": row.to_dict() for (a, b), row in classes.iterrows()},
        "recent_seasons": recent,
        "imd_103_stations": IMD_103_STATIONS,
        "imd_change_pct": rounded(imd_change, 0),
        "imd_inside_our_range": bool(cleaned["change_pct"] <= imd_change <= recorded["change_pct"]),
    }, per_period


def warming(passing: pd.DataFrame, groups: pd.Series) -> tuple[dict, pd.DataFrame, dict]:
    months = pd.read_csv(MART / "q2_monthly_anomalies.csv")
    months["x"] = months.year + (months.month - 0.5) / 12
    rows = []
    for station_id, g in months.groupby("station_id"):
        y = g.year
        if len(g) < 180 or y.min() > 1990 or y.max() < 2015:
            continue
        if (y < 1995).sum() < 24 or ((y >= 1995) & (y < 2010)).sum() < 24 or (y >= 2010).sum() < 24:
            continue
        x = g.x.to_numpy()
        tmax, tmax_se, _ = fit(x, g.tmax_anomaly.to_numpy())
        tmin, tmin_se, _ = fit(x, g.tmin_anomaly.to_numpy())
        mean, mean_se, _ = fit(x, ((g.tmax_anomaly + g.tmin_anomaly) / 2).to_numpy())
        tmax_clean = fit(x, g.tmax_anomaly_no_repeat.to_numpy())[0]
        tmin_clean = fit(x, g.tmin_anomaly_no_repeat.to_numpy())[0]
        rows.append({
            "station_id": station_id, "months": len(g), "first_year": int(y.min()), "last_year": int(y.max()),
            "tmax_rate": tmax, "tmax_se": tmax_se, "tmin_rate": tmin, "tmin_se": tmin_se,
            "mean_rate": mean, "mean_se": mean_se, "tmax_rate_no_repeat": tmax_clean, "tmin_rate_no_repeat": tmin_clean,
        })
    rates = pd.DataFrame(rows).merge(passing[["station_id", "name", "state", "station_class", "lat", "lon", "elevation"]], on="station_id")
    rates["nights_faster"] = rates.tmin_rate > rates.tmax_rate
    # Day and night at one site should not move in opposite directions by this much. It usually means the
    # instrument or site changed, and GHCN-Daily does not adjust for that.
    rates["suspect"] = (rates.tmax_rate - rates.tmin_rate).abs() >= 0.5
    rates["ci_low"] = rates.mean_rate - 1.96 * rates.mean_se
    rates["ci_high"] = rates.mean_rate + 1.96 * rates.mean_se
    rates["repeat_group"] = rates.station_id.map(groups).fillna("unknown")
    rates = rates.sort_values("mean_rate", ascending=False)
    rates.to_csv(MART / "station_rates.csv", index=False)

    diff = (rates.tmin_rate - rates.tmax_rate).to_numpy()
    diff_clean = (rates.tmin_rate_no_repeat - rates.tmax_rate_no_repeat).to_numpy()
    nights = int((diff > 0).sum())

    nights_table = pd.read_csv(MART / "q2_warm_nights.csv")
    nights_table["period"] = nights_table.year.map(period_of)
    in_panel = nights_table[nights_table.station_id.isin(passing[passing.in_heat_panel == 1].station_id)]
    for column in ("warm_nights", "very_warm_nights", "warm_nights_no_repeat"):
        in_panel = in_panel.assign(**{column: in_panel[column] * HOT_SEASON_DAYS / in_panel.observed_days})
    per_station = in_panel.groupby(["station_id", "period"])[["warm_nights", "warm_nights_no_repeat"]].mean().reset_index()

    by_group = {}
    for key in ("clean", "jumped", "early"):
        part = rates[rates.repeat_group == key]
        by_group[key] = {
            "stations": len(part),
            "median_tmax_rate": rounded(part.tmax_rate.median(), 3),
            "median_tmin_rate": rounded(part.tmin_rate.median(), 3),
            "nights_faster": int(part.nights_faster.sum()),
            "median_rate": rounded(part.mean_rate.median(), 3),
        }
    q2 = {
        "stations": len(rates),
        "by_repeat_group": by_group,
        "median_tmax_rate": rounded(rates.tmax_rate.median(), 3),
        "median_tmax_rate_ci": [rounded(v, 3) for v in bootstrap(rates.tmax_rate.to_numpy(), np.median)],
        "median_tmin_rate": rounded(rates.tmin_rate.median(), 3),
        "median_tmin_rate_ci": [rounded(v, 3) for v in bootstrap(rates.tmin_rate.to_numpy(), np.median)],
        "median_difference": rounded(np.median(diff), 3),
        "median_difference_ci": [rounded(v, 3) for v in bootstrap(diff, np.median)],
        "nights_faster": nights,
        "days_faster": len(diff) - nights,
        "sign_test_p": rounded(two_sided_sign_test(nights, len(diff)), 3),
        "median_difference_no_repeat": rounded(np.median(diff_clean), 3),
        "nights_faster_no_repeat": int((diff_clean > 0).sum()),
        "warm_nights_per_season": {
            name: {
                "recorded": rounded(per_station[per_station.period == name].warm_nights.mean()),
                "without_repeats": rounded(per_station[per_station.period == name].warm_nights_no_repeat.mean()),
            }
            for _, _, name in PERIODS
        },
    }
    top = rates.head(5)[["name", "state", "mean_rate", "ci_low", "ci_high", "suspect"]]
    q5 = {
        "stations": len(rates),
        "median_rate": rounded(rates.mean_rate.median(), 3),
        "median_rate_ci": [rounded(v, 3) for v in bootstrap(rates.mean_rate.to_numpy(), np.median)],
        "warming": int((rates.mean_rate > 0).sum()),
        "clearly_warming": int((rates.ci_low > 0).sum()),
        "clearly_cooling": int((rates.ci_high < 0).sum()),
        "suspect": int(rates.suspect.sum()),
        "fastest": [{k: (rounded(v, 2) if isinstance(v, float) else (bool(v) if isinstance(v, (bool, np.bool_)) else v)) for k, v in row.items()} for row in top.to_dict("records")],
        "slowest": [{"name": r["name"], "mean_rate": rounded(r["mean_rate"], 2), "suspect": bool(r["suspect"])} for r in rates.tail(3).to_dict("records")],
    }
    return q2, rates, q5


def first_40c(passing: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    seasons = pd.read_csv(MART / "q3_first_40c.csv")
    usable = seasons[(seasons.days_40c > 0) & (seasons.observed_prior_7 >= 6)]
    rows = []
    for station_id, g in usable.groupby("station_id"):
        total = (seasons.station_id == station_id).sum()
        if len(g) < 15 or g.year.min() > 1995 or g.year.max() < 2015 or len(g) / total < 0.8:
            continue
        slope, intercept = np.polyfit(g.year, g.first_doy, 1)
        residual = g.first_doy - (slope * g.year + intercept)
        se = math.sqrt((residual**2).sum() / (len(g) - 2) / ((g.year - g.year.mean()) ** 2).sum())
        rows.append({"station_id": station_id, "years": len(g), "days_per_decade": slope * 10, "se": se * 10, "mean_doy": g.first_doy.mean()})
    stations = pd.DataFrame(rows).merge(passing[["station_id", "name", "state", "station_class"]], on="station_id")
    stations.to_csv(MART / "q3_station_trends.csv", index=False)

    panel = usable[usable.station_id.isin(stations.station_id)].copy()
    panel["anomaly"] = panel.first_doy - panel.groupby("station_id").first_doy.transform("mean")
    yearly = panel.groupby("year").agg(stations=("station_id", "nunique"), median_shift=("anomaly", "median"), q25=("anomaly", lambda s: s.quantile(0.25)), q75=("anomaly", lambda s: s.quantile(0.75)), median_doy=("first_doy", "median")).reset_index()
    yearly.to_csv(MART / "q3_yearly.csv", index=False)

    rates = stations.days_per_decade.to_numpy()
    earlier = int((rates < 0).sum())
    return {
        "stations": len(stations),
        "median_days_per_decade": rounded(np.median(rates), 1),
        "median_days_per_decade_ci": [rounded(v, 1) for v in bootstrap(rates, np.median)],
        "earlier": earlier,
        "later": len(rates) - earlier,
        "clearly_earlier": int(((stations.days_per_decade + 1.96 * stations.se) < 0).sum()),
        "clearly_later": int(((stations.days_per_decade - 1.96 * stations.se) > 0).sum()),
        "sign_test_p": rounded(two_sided_sign_test(earlier, len(rates)), 3),
        "typical_first_date": doy_to_date(float(stations.mean_doy.median())),
        "biggest_year_swing_days": rounded(yearly[yearly.stations >= 10].median_shift.max() - yearly[yearly.stations >= 10].median_shift.min(), 0),
        "earliest_stations": [{"name": r["name"], "days_per_decade": rounded(r["days_per_decade"], 1)} for r in stations.nsmallest(3, "days_per_decade").to_dict("records")],
    }, yearly


def monsoon() -> dict:
    seasons = pd.read_csv(MART / "q4_monsoon_seasons.csv")
    complete = seasons[(seasons.reports >= 98) & (seasons.rows_with_temperature == 0) & seasons.year.between(1901, 1970)]
    counts = complete.groupby("station_id").size()
    panel_ids = counts[counts >= 56].index
    panel = complete[complete.station_id.isin(panel_ids)].copy()
    panel["decade_start"] = (panel.year - 1) // 10 * 10 + 1
    decades = panel.groupby("decade_start").agg(stations=("station_id", "nunique"), seasons=("year", "size"), rainy_days=("rainy_days", "mean"), heavy_days=("heavy_days", "mean"), season_mm=("season_mm", "mean")).reset_index()
    decades.to_csv(MART / "q4_gauge_decades.csv", index=False)

    def slopes(column: str) -> np.ndarray:
        return panel.groupby("station_id").apply(lambda g: np.polyfit(g.year, g[column], 1)[0] * 10, include_groups=False).to_numpy()

    rainy, heavy, totals = slopes("rainy_days"), slopes("heavy_days"), slopes("season_mm")

    network = seasons.groupby("year").station_id.nunique()

    # The water-balance test: the same stations, season by season, across NOAA's sources.
    sources = pd.read_csv(MART / "q4_rain_sources.csv")
    per_season = sources.groupby(["station_id", "year"])[["reports", "season_mm", "rainy_days", "heavy_days", "zero_reports"]].sum().reset_index()
    per_season["era"] = None
    for low, high, name in RAIN_ERAS:
        per_season.loc[per_season.year.between(low, high), "era"] = name
    per_season = per_season.dropna(subset=["era"])
    by_era = per_season.groupby(["station_id", "era"])[["season_mm", "rainy_days", "heavy_days", "reports", "zero_reports"]].mean().reset_index()
    wide = by_era.pivot(index="station_id", columns="era", values="season_mm")
    same = wide.dropna(subset=["1901-72", "1982-98", "2006-15"]).index
    balance = by_era[by_era.station_id.isin(same)].groupby("era")[["season_mm", "rainy_days", "heavy_days", "reports", "zero_reports"]].mean().reindex([e[2] for e in RAIN_ERAS]).reset_index()
    balance["stations"] = len(same)
    balance.to_csv(MART / "q4_water_balance.csv", index=False)
    get = balance.set_index("era")

    # 2006-2024 is one source with steady reporting, so it can carry its own comparison, though not one with earlier years.
    recent = sources[sources.year.between(2006, 2024) & (sources.source == "S")]
    seasons_per_station = recent.groupby("station_id").size()
    recent = recent[recent.station_id.isin(seasons_per_station[seasons_per_station >= 15].index)]
    recent_slopes = recent.groupby("station_id").apply(lambda g: np.polyfit(g.year, g.heavy_days, 1)[0] * 10, include_groups=False).to_numpy()
    recent_mm = recent.groupby("station_id").apply(lambda g: np.polyfit(g.year, g.season_mm, 1)[0] * 10, include_groups=False).to_numpy()
    ratio = (wide.loc[same, "1982-98"] / wide.loc[same, "1901-72"]).median()
    ratio_recent = (wide.loc[same, "2006-15"] / wide.loc[same, "1901-72"]).median()
    return {
        "gauge_stations": len(panel_ids),
        "gauge_seasons": len(panel),
        "first_decade": {"rainy_days": rounded(decades.iloc[0].rainy_days, 1), "heavy_days": rounded(decades.iloc[0].heavy_days), "season_mm": rounded(decades.iloc[0].season_mm, 0)},
        "last_decade": {"rainy_days": rounded(decades.iloc[-1].rainy_days, 1), "heavy_days": rounded(decades.iloc[-1].heavy_days), "season_mm": rounded(decades.iloc[-1].season_mm, 0)},
        "median_rainy_days_per_decade": rounded(np.median(rainy), 2),
        "median_heavy_days_per_decade": rounded(np.median(heavy), 3),
        "mean_heavy_days_per_decade": rounded(heavy.mean(), 3),
        "mean_heavy_days_per_decade_ci": [rounded(v, 3) for v in bootstrap(heavy, np.mean)],
        "median_mm_per_decade": rounded(np.median(totals), 1),
        "stations_heavy_rising_pct": rounded(100 * (heavy > 0).mean(), 0),
        "stations_heavy_falling_pct": rounded(100 * (heavy < 0).mean(), 0),
        "recent_window": {
            "stations": int(len(recent_slopes)),
            "heavy_days_per_season": rounded(recent.heavy_days.mean()),
            "mean_heavy_days_per_decade": rounded(recent_slopes.mean(), 3),
            "mean_heavy_days_per_decade_ci": [rounded(v, 3) for v in bootstrap(recent_slopes, np.mean)],
            "stations_rising": int((recent_slopes > 0).sum()),
            "stations_falling": int((recent_slopes < 0).sum()),
            "median_mm_per_decade": rounded(np.median(recent_mm), 0),
        },
        "network_1970": int(network.get(1970)),
        "network_1973": int(network.get(1973)),
        "same_stations": len(same),
        "mm_1901_72": rounded(get.season_mm["1901-72"], 0),
        "mm_1973_81": rounded(get.season_mm["1973-81"], 0),
        "mm_1982_98": rounded(get.season_mm["1982-98"], 0),
        "mm_2006_15": rounded(get.season_mm["2006-15"], 0),
        "apparent_loss_1982_98_pct": rounded(100 * (1 - get.season_mm["1982-98"] / get.season_mm["1901-72"]), 0),
        "ratio_1982_98": rounded(ratio),
        "ratio_2006_15": rounded(ratio_recent),
        "rainy_days_1901_72": rounded(get.rainy_days["1901-72"], 1),
        "rainy_days_2006_15": rounded(get.rainy_days["2006-15"], 1),
        "heavy_days_1901_72": rounded(get.heavy_days["1901-72"]),
        "heavy_days_2006_15": rounded(get.heavy_days["2006-15"]),
    }


def countries(groups: pd.Series) -> dict:
    stations = pd.read_csv(MART / "q6_country_rates_rollup.csv", keep_default_na=False)
    names = {}
    with open(REFERENCE / "ghcnd-countries.txt", encoding="ascii") as handle:
        for line in handle:
            names[line[:2]] = line[3:].strip().split(" [")[0]
    summary = stations.groupby("country").rate_per_decade.agg(stations="count", median_rate="median", q25=lambda s: s.quantile(0.25), q75=lambda s: s.quantile(0.75)).reset_index()
    summary["name"] = summary.country.map(names)
    ranked = summary[summary.stations >= 5].sort_values("median_rate", ascending=False).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    ranked.to_csv(MART / "q6_country_summary.csv", index=False)
    india = ranked[ranked.country == "IN"].iloc[0]
    indian = stations[stations.country == "IN"].rate_per_decade.to_numpy()
    clean_only = stations[(stations.country == "IN") & stations.station_id.map(groups).eq("clean")].rate_per_decade
    others = ranked[ranked.country != "IN"].median_rate
    return {
        "stations_all_countries": len(stations),
        "countries_any": int(summary.shape[0]),
        "countries_ranked": len(ranked),
        "india_rank": int(india["rank"]),
        "india_stations": int(india.stations),
        "india_median_rate": rounded(india.median_rate, 3),
        "india_median_rate_ci": [rounded(v, 3) for v in bootstrap(indian, np.median)],
        "india_clean_stations_only": {"stations": int(len(clean_only)), "median_rate": rounded(clean_only.median(), 3), "rank": int((others > clean_only.median()).sum()) + 1},
        "median_of_countries": rounded(ranked.median_rate.median(), 3),
        "countries_faster_than_india": int((ranked.median_rate > india.median_rate).sum()),
        "fastest": [{"name": r["name"], "rate": rounded(r["median_rate"], 2)} for r in ranked.head(3).to_dict("records")],
        "slowest": [{"name": r["name"], "rate": rounded(r["median_rate"], 2)} for r in ranked.tail(3).to_dict("records")],
        "us_stations": int(ranked[ranked.country == "US"].stations.iloc[0]),
    }


def data_quality(passing: pd.DataFrame) -> dict:
    coverage = pd.read_csv(MART / "coverage_by_year.csv").set_index("year")
    log = pd.read_csv(Path(MART.parent.parent) / "docs" / "issue_log.csv", keep_default_na=False)
    detail = log[log.station == ""].set_index("check").detail.to_dict()
    count = log[log.station == ""].set_index("check")["count"].to_dict()
    stations_found = log[log.station != ""].groupby("check").size().to_dict()
    return {
        "indian_stations_in_file": int(pd.read_csv(MART / "q4_monsoon_seasons.csv", usecols=["station_id"]).station_id.nunique()),
        "stations_with_rain_1970": int(coverage.stations_rain[1970]),
        "stations_with_rain_1973": int(coverage.stations_rain[1973]),
        "stations_with_tmax_1960": int(coverage.stations_tmax[1960]),
        "stations_with_tmax_1973": int(coverage.stations_tmax[1973]),
        "stations_with_tmax_2010": int(coverage.stations_tmax[2010]),
        "stations_with_any_temperature": int(len(passing)),
        "stations_with_normals": int(passing.has_normals.sum()),
        "stations_in_heat_panel": int(passing.in_heat_panel.sum()),
        "hill_stations_in_panel": int(((passing.in_heat_panel == 1) & (passing.station_class == "hills")).sum()),
        "zero_rows_india": int(count["DQ01"]),
        "zero_detail": detail["DQ01"],
        "false_zero_rows": int(count["DQ02"]),
        "false_zero_detail": detail["DQ02"],
        "repeat_detail": detail["DQ10"],
        "whole_degree_detail": detail["DQ11"],
        "reconciliation_mismatches": int(count["DQ12"]),
        "reconciliation_detail": detail["DQ12"],
        "source_break_rows": int(count["DQ13"]),
        "stations_outside_outline": int(stations_found.get("DQ08", 0)),
        "stations_with_gap_of_a_year": int(stations_found.get("DQ07", 0)),
        "issue_rows": int(len(log)),
        "checks": int(log.check.nunique()),
    }


def main() -> None:
    passing = pd.read_csv(MART / "passing_stations.csv", keep_default_na=False)
    passing["name"] = passing.name.map(display_name)
    names = pd.read_csv(MART / "station_names.csv", keep_default_na=False)
    names["name"] = names.name.map(display_name)
    names.to_csv(MART / "station_names.csv", index=False)
    repeats, groups = analyse_repeats(passing, SEED)
    q1, _ = heatwaves(passing, groups)
    q2, rates, q5 = warming(passing, groups)
    q3, _ = first_40c(passing)
    q4 = monsoon()
    q6 = countries(groups)
    findings = {
        "scale": {
            "rows": PARQUET_ROWS,
            "measurements_before_pivot": MEASUREMENTS_BEFORE_PIVOT,
            "parquet_bytes": PARQUET_BYTES,
            "last_date": "2022-09-07",
        },
        "quality": data_quality(passing),
        "repeats": repeats,
        "q1_heatwave_days": q1,
        "q2_days_and_nights": q2,
        "q3_first_40c": q3,
        "q4_monsoon": q4,
        "q5_fastest_stations": q5,
        "q6_countries": q6,
        "imd_records": IMD_RECORDS,
    }
    (MART / "findings.json").write_text(json.dumps(findings, indent=2, default=str), encoding="utf8")
    print(json.dumps({k: findings[k] for k in ("q2_days_and_nights", "q3_first_40c", "q4_monsoon", "q5_fastest_stations", "q6_countries")}, indent=1, default=str)[:6000])
    print(json.dumps(findings["q1_heatwave_days"], indent=1, default=str)[:3800])


if __name__ == "__main__":
    main()
