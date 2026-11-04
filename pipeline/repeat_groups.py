"""Sort stations by whether and when repeated maximums affected them, and test what that pattern is.

Repeats are not spread evenly. Each station's share of days repeating the previous maximum stays near a natural
level, or jumps by 20 points or more, with almost nothing in between. That gives a natural experiment: stations the
problem never touched can be compared with stations it did, on the same questions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import MART  # noqa: E402

WINDOWS = {"1982-88": (1982, 1988), "1989-2000": (1989, 2000), "2001-10": (2001, 2010), "2011-15": (2011, 2015), "2016-19": (2016, 2019)}
MINIMUM_DAYS = 200
JUMP_POINTS = 10
EARLY_SHARE = 15
CLEAN_CEILING = 12
LABELS = {"clean": "Never affected", "jumped": "Stepped at 2011", "early": "Stepped around 1990", "other": "Other", "unknown": "Too little data"}

# States and territories that Wikipedia lists under IMD's Regional Meteorological Centre at Chennai.
# Telangana was part of Andhra Pradesh in the 2011 boundaries used here.
CHENNAI_REGION = {"Andhra Pradesh", "Karnataka", "Kerala", "Tamil Nadu", "Lakshadweep", "Puducherry", "Andaman & Nicobar Island"}


def window_shares(years: pd.DataFrame, days: str, repeats: str) -> pd.DataFrame:
    shares = {}
    for name, (low, high) in WINDOWS.items():
        totals = years[years.year.between(low, high)].groupby("station_id")[[days, repeats]].sum()
        totals = totals[totals[days] >= MINIMUM_DAYS]
        shares[name] = 100 * totals[repeats] / totals[days]
    return pd.DataFrame(shares)


def classify(shares: pd.DataFrame) -> pd.Series:
    """Each station's group, from the share of days repeating the previous maximum in fixed windows."""
    groups = {}
    for station_id, row in shares.iterrows():
        if pd.isna(row["2001-10"]) or pd.isna(row["2011-15"]):
            groups[station_id] = "unknown"
        elif row["2011-15"] - row["2001-10"] >= JUMP_POINTS:
            groups[station_id] = "jumped"
        elif row["2001-10"] >= EARLY_SHARE:
            groups[station_id] = "early"
        elif row[list(WINDOWS)].max() < CLEAN_CEILING:
            groups[station_id] = "clean"
        else:
            groups[station_id] = "other"
    return pd.Series(groups, name="repeat_group")


def yearly_shares(years: pd.DataFrame, groups: pd.Series) -> pd.DataFrame:
    frame = years.merge(groups, left_on="station_id", right_index=True)
    frame = frame[frame.repeat_group.isin(["clean", "jumped", "early"])]
    totals = frame.groupby(["repeat_group", "year"]).agg(stations=("station_id", "nunique"), tmax_days=("tmax_days", "sum"), tmax_repeats=("tmax_repeats", "sum"), tmin_days=("tmin_days", "sum"), tmin_repeats=("tmin_repeats", "sum")).reset_index()
    totals["tmax_share"] = 100 * totals.tmax_repeats / totals.tmax_days
    totals["tmin_share"] = 100 * totals.tmin_repeats / totals.tmin_days.where(totals.tmin_days > 0)
    return totals


def monthly_shares(groups: pd.Series, group: str) -> pd.DataFrame:
    months = pd.read_csv(MART / "q7_repeat_months.csv")
    chosen = months[months.station_id.isin(groups[groups == group].index)]
    totals = chosen.groupby(["year", "month"])[["tmax_days", "tmax_repeats", "tmin_days", "tmin_repeats"]].sum().reset_index()
    totals["tmax_share"] = 100 * totals.tmax_repeats / totals.tmax_days
    totals["tmin_share"] = 100 * totals.tmin_repeats / totals.tmin_days
    return totals


def peak_ratios(groups: pd.Series) -> pd.DataFrame:
    """Local peaks against local troughs among repeated pairs, 2011-15, with minimums as the control."""
    pairs = pd.read_csv(MART / "q7_repeat_pairs.csv")
    pairs = pairs[pairs.year.between(2011, 2015)].merge(groups, left_on="station_id", right_index=True)
    pairs = pairs[pairs.repeat_group.isin(["clean", "jumped", "early"])]
    totals = pairs.groupby(["reading", "repeat_group"])[["pairs", "local_peaks", "local_troughs"]].sum().reset_index()
    totals["peak_pct"] = 100 * totals.local_peaks / totals.pairs
    totals["trough_pct"] = 100 * totals.local_troughs / totals.pairs
    totals["peaks_per_trough"] = totals.local_peaks / totals.local_troughs
    return totals


def gap_change(groups: pd.Series, seed: int, resamples: int = 10_000) -> dict:
    """How the day-night gap moved from 2006-10 to 2011-15 at stations that jumped, against clean ones.

    Regional weather moves maximums and minimums together, so comparing the gap removes most of it. A copied peak
    lifts only the maximum.
    """
    months = pd.read_csv(MART / "q2_monthly_anomalies.csv")
    months["gap"] = months.tmax_anomaly - months.tmin_anomaly

    def per_station(low: int, high: int) -> pd.Series:
        chosen = months[months.year.between(low, high)]
        counts = chosen.groupby("station_id").gap.count()
        return chosen.groupby("station_id").gap.mean()[counts >= 12]

    change = (per_station(2011, 2015) - per_station(2006, 2010)).dropna()
    jumped = change[change.index.isin(groups[groups == "jumped"].index)].to_numpy()
    clean = change[change.index.isin(groups[groups == "clean"].index)].to_numpy()
    rng = np.random.default_rng(seed)
    samples = [rng.choice(jumped, len(jumped)).mean() - rng.choice(clean, len(clean)).mean() for _ in range(resamples)]
    return {
        "jumped_stations": len(jumped),
        "clean_stations": len(clean),
        "jumped_change": round(float(jumped.mean()), 2),
        "clean_change": round(float(clean.mean()), 2),
        "difference": round(float(jumped.mean() - clean.mean()), 2),
        "difference_ci": [round(float(np.percentile(samples, 2.5)), 2), round(float(np.percentile(samples, 97.5)), 2)],
    }


def analyse(passing: pd.DataFrame, seed: int) -> tuple[dict, pd.Series]:
    years = pd.read_csv(MART / "q7_repeat_years.csv")
    shares = window_shares(years, "tmax_days", "tmax_repeats")
    minimum_shares = window_shares(years, "tmin_days", "tmin_repeats")
    groups = classify(shares)

    stations = pd.read_csv(MART / "station_names.csv", keep_default_na=False).set_index("station_id")
    table = shares.round(1).add_prefix("share_").join(groups).join(stations[["name", "state", "lat", "lon", "station_class"]])
    table["group_label"] = table.repeat_group.map(LABELS)
    table.reset_index(names="station_id").to_csv(MART / "station_repeat_groups.csv", index=False)

    comparable = table[table.repeat_group != "unknown"]
    by_state = comparable.groupby(["state", "repeat_group"]).size().unstack(fill_value=0).reindex(columns=["clean", "jumped", "early", "other"], fill_value=0).reset_index()
    by_state.to_csv(MART / "repeat_groups_by_state.csv", index=False)

    yearly = yearly_shares(years, groups)
    yearly.to_csv(MART / "repeat_years_by_group.csv", index=False)
    monthly = monthly_shares(groups, "jumped")
    monthly.to_csv(MART / "repeat_months_jumped.csv", index=False)
    ratios = peak_ratios(groups)
    ratios.to_csv(MART / "repeat_peak_ratios.csv", index=False)

    def month_share(year: int, month: int) -> float:
        return round(float(monthly[(monthly.year == year) & (monthly.month == month)].tmax_share.iloc[0]), 1)

    def group_year(group: str, year: int) -> float:
        return round(float(yearly[(yearly.repeat_group == group) & (yearly.year == year)].tmax_share.iloc[0]), 1)

    def ratio(reading: str, group: str) -> dict:
        row = ratios[(ratios.reading == reading) & (ratios.repeat_group == group)].iloc[0]
        return {"peak_pct": round(float(row.peak_pct), 1), "trough_pct": round(float(row.trough_pct), 1), "peaks_per_trough": round(float(row.peaks_per_trough), 1)}

    jump_sizes = (shares["2011-15"] - shares["2001-10"]).dropna()
    in_region = comparable[comparable.state.isin(CHENNAI_REGION)]
    jumped = comparable[comparable.repeat_group == "jumped"]
    early = comparable[comparable.repeat_group == "early"]
    jumped_ids = jumped.index
    return {
        "comparable_stations": int(len(comparable)),
        "groups": {key: int((comparable.repeat_group == key).sum()) for key in ("clean", "jumped", "early", "other")},
        "stations_jumping_5_to_15_points": int(jump_sizes.between(5, 15, inclusive="left").sum()),
        "jumped_median_share": {name: round(float(shares.loc[jumped_ids, name].median()), 1) for name in WINDOWS if shares.loc[jumped_ids, name].notna().any()},
        "jumped_median_minimum_share": {name: round(float(minimum_shares.reindex(jumped_ids)[name].median()), 1) for name in WINDOWS if minimum_shares.reindex(jumped_ids)[name].notna().any()},
        "clean_median_share_2011_15": round(float(shares.loc[comparable[comparable.repeat_group == "clean"].index, "2011-15"].median()), 1),
        "onset": {"october_2010": month_share(2010, 10), "november_2010": month_share(2010, 11), "december_2010": month_share(2010, 12), "january_2011": month_share(2011, 1)},
        "offset": {"december_2015": month_share(2015, 12), "january_2016": month_share(2016, 1), "february_2016": month_share(2016, 2), "march_2016": month_share(2016, 3)},
        "jumped_share_2015": group_year("jumped", 2015),
        "jumped_share_2016": group_year("jumped", 2016),
        "early_share_1988": group_year("early", 1988),
        "early_share_1991": group_year("early", 1991),
        "early_share_2005": group_year("early", 2005),
        "chennai_region": {
            "stations": int(len(in_region)),
            "jumped": int((in_region.repeat_group == "jumped").sum()),
            "not_jumped": sorted(in_region[in_region.repeat_group != "jumped"].name),
            "jumped_elsewhere": sorted(jumped[~jumped.state.isin(CHENNAI_REGION)].name),
        },
        "early_states": sorted(early.state.unique()),
        "maharashtra": {"stations": int((comparable.state == "Maharashtra").sum()), "jumped": int(((comparable.state == "Maharashtra") & (comparable.repeat_group == "jumped")).sum())},
        "peaks": {
            "jumped": ratio("maximum", "jumped"),
            "early": ratio("maximum", "early"),
            "clean": ratio("maximum", "clean"),
            "jumped_minimums": ratio("minimum", "jumped"),
        },
        "gap_change": gap_change(groups, seed),
    }, groups
