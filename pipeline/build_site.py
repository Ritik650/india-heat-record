"""Build the static site in site/ from the saved results, so it needs no server and no database.

The layout and colours come from the Stitch design. Every number comes from data/mart. GitHub Pages serves the result.
"""
from __future__ import annotations

import csv
import json
import math
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import CHARTS, DOCS, MART, OUTPUTS, ROOT, display_name  # noqa: E402

SITE = ROOT / "site"
REPO_URL = "https://github.com/Ritik650/india-heat-record"
SITE_URL = "https://ritik650.github.io/india-heat-record/"
SCALE = 19.5
LON_MIN, LAT_MAX = 67.6, 37.6
GROUPS = {"clean": ("Never affected", "--blue"), "jumped": ("Stepped at 2011", "--orange"), "early": ("Stepped around 1990", "--aqua"), "other": ("Other", "--grey")}


def mercator(lat: float) -> float:
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def project(lon: float, lat: float) -> tuple[float, float]:
    return round((lon - LON_MIN) * SCALE, 1), round((mercator(LAT_MAX) - mercator(lat)) * SCALE, 1)


def state_paths() -> tuple[list[str], float, float]:
    features = json.loads((ROOT / "data/geo/india_states_2011.geojson").read_text(encoding="utf8"))["features"]
    paths, max_x, max_y = [], 0.0, 0.0
    for feature in features:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        d = []
        for polygon in polygons:
            for ring in polygon:
                last = None
                part = []
                for lon, lat in ring:
                    point = project(lon, lat)
                    if point != last:
                        part.append(f"{point[0]:g} {point[1]:g}")
                        max_x, max_y = max(max_x, point[0]), max(max_y, point[1])
                        last = point
                if len(part) > 2:
                    d.append("M" + "L".join(part) + "Z")
        paths.append("".join(d))
    return paths, max_x, max_y


def stations() -> list[dict]:
    names = pd.read_csv(MART / "station_names.csv", keep_default_na=False).set_index("station_id")
    groups = pd.read_csv(MART / "station_repeat_groups.csv", keep_default_na=False).set_index("station_id")
    rates = pd.read_csv(MART / "station_rates.csv", keep_default_na=False).set_index("station_id")
    periods = pd.read_csv(MART / "q1_station_periods.csv", keep_default_na=False)
    years = pd.read_csv(MART / "q7_repeat_years.csv")
    years["tmax_share"] = (100 * years.tmax_repeats / years.tmax_days.where(years.tmax_days >= 100)).round(1)
    years["tmin_share"] = (100 * years.tmin_repeats / years.tmin_days.where(years.tmin_days >= 100)).round(1)
    order = ["1982-89", "1990s", "2000s", "2010s", "2020-24"]
    rows = []
    for station_id in names.index:
        group = groups.repeat_group.get(station_id, "unknown")
        in_rates = station_id in rates.index
        if group == "unknown" and not in_rates:
            continue
        info = names.loc[station_id]
        x, y = project(float(info.lon), float(info.lat))
        own = periods[periods.station_id == station_id].set_index("period")
        own_years = years[years.station_id == station_id].sort_values("year")
        rows.append({
            "id": station_id,
            "name": display_name(info["name"]),
            "state": info.state,
            "cls": str(info.station_class).capitalize(),
            "elev": float(info.elevation),
            "x": x,
            "y": y,
            "group": group,
            "label": GROUPS.get(group, ("Too little data to tell", ""))[0],
            "rate": round(float(rates.mean_rate[station_id]), 3) if in_rates else None,
            "rateLo": round(float(rates.ci_low[station_id]), 2) if in_rates else None,
            "rateHi": round(float(rates.ci_high[station_id]), 2) if in_rates else None,
            "tmax": round(float(rates.tmax_rate[station_id]), 3) if in_rates else None,
            "tmin": round(float(rates.tmin_rate[station_id]), 3) if in_rates else None,
            "suspect": bool(str(rates.suspect[station_id]) == "True") if in_rates else False,
            "periods": [[p, round(float(own.heatwave_days[p]), 2), round(float(own.heatwave_days_no_repeat[p]), 2)] for p in order if p in own.index] or None,
            "years": [[int(r.year), None if pd.isna(r.tmax_share) else float(r.tmax_share), None if pd.isna(r.tmin_share) else float(r.tmin_share)] for r in own_years.itertuples()],
        })
    return rows


def data(f: dict) -> dict:
    q1, q3 = f["q1_heatwave_days"], pd.read_csv(MART / "q3_yearly.csv")
    yearly = pd.read_csv(MART / "repeat_years_by_group.csv")
    yearly = yearly[yearly.tmax_days >= 500]

    def series(key: str, column: str) -> list:
        part = yearly[yearly.repeat_group == key].sort_values("year")
        return [[int(y), round(float(v), 1)] for y, v in zip(part.year, part[column]) if pd.notna(v)]

    repeats = [{"name": GROUPS[k][0], "color": GROUPS[k][1], "points": series(k, "tmax_share")} for k in ("jumped", "early", "clean")]
    repeats.append({"name": "Minimums, 2011 group", "color": "--grey", "dash": True, "points": series("jumped", "tmin_share")})

    periods = ["1982-89", "1990s", "2000s", "2010s"]
    station_periods = pd.read_csv(MART / "q1_station_periods.csv", keep_default_na=False).groupby("period")[["heatwave_days", "heatwave_days_no_repeat"]].mean()
    clean = pd.read_csv(MART / "q1_group_periods.csv")
    clean = clean[clean.repeat_group == "clean"].set_index("period").heatwave_days
    q1_series = [
        {"name": f"As recorded, all {q1['panel_stations']}", "color": "--grey", "change": f"{q1['recorded']['change_pct']:+.0f}%", "points": [round(100 * station_periods.heatwave_days[p] / station_periods.heatwave_days[periods[0]], 1) for p in periods]},
        {"name": f"Never affected, {q1['by_repeat_group']['clean']['recorded']['stations']} stations", "color": "--orange", "change": f"{q1['by_repeat_group']['clean']['recorded']['change_pct']:+.0f}%", "points": [round(100 * clean[p] / clean[periods[0]], 1) for p in periods]},
        {"name": f"Repeats removed, all {q1['panel_stations']}", "color": "--blue", "change": f"{q1['without_repeats']['change_pct']:+.0f}%", "points": [round(100 * station_periods.heatwave_days_no_repeat[p] / station_periods.heatwave_days_no_repeat[periods[0]], 1) for p in periods]},
    ]

    rates = pd.read_csv(MART / "station_rates.csv", keep_default_na=False)
    q2 = [{"name": display_name(r["name"]), "tmax": round(float(r["tmax_rate"]), 3), "tmin": round(float(r["tmin_rate"]), 3), "group": r["repeat_group"]} for r in rates.to_dict("records")]

    q3 = q3[q3.stations >= 5].sort_values("year")
    line, band, run, previous = [], [], [], None
    for r in q3.itertuples():
        if previous is not None and r.year != previous + 1:
            band.append(run)
            run = []
            line.append([previous + 1, None])
        line.append([int(r.year), round(float(r.median_shift), 1)])
        run.append([int(r.year), round(float(r.q25), 1), round(float(r.q75), 1)])
        previous = r.year
    band.append(run)

    decades = pd.read_csv(MART / "q4_gauge_decades.csv")
    label = lambda start: f"{start}-{str(start + 9)[2:]}"  # noqa: E731
    balance = pd.read_csv(MART / "q4_water_balance.csv")
    status = {"1901-72": "--blue", "1973-81": "--orange", "1982-98": "--orange", "1999-2005": "--orange", "2006-15": "--grey", "2016-24": "--grey"}

    countries = pd.read_csv(MART / "q6_country_summary.csv", keep_default_na=False)
    bench = pd.read_csv(MART / "benchmark.csv")
    bench_rows = []
    for question in bench.question.drop_duplicates():
        row = [question]
        for engine in ("clickhouse_raw", "clickhouse_rollup", "duckdb_parquet"):
            value = bench[(bench.question == question) & (bench.engine == engine) & (bench.run == "median_warm")].seconds
            row.append("" if value.empty else (f"{value.iloc[0]:.2f}" if value.iloc[0] < 10 else f"{value.iloc[0]:.1f}"))
        bench_rows.append(row)
    sens = [[r["scenario"], r["stations"], f"+{r['change_recorded_pct']}%", f"+{r['change_no_repeat_pct']}%"] for r in csv.DictReader(open(MART / "sensitivity.csv", encoding="utf8"))]

    log = pd.read_csv(DOCS / "issue_log.csv", keep_default_na=False)
    dq = []
    for check, part in log.groupby("check"):
        total = part["count"].astype(int).sum()
        dq.append({"check": check, "severity": part.severity.iloc[0], "description": part.description.iloc[0], "count": "Passed" if total == 0 else f"{total:,}", "action": part.action_taken.iloc[0]})

    coverage = pd.read_csv(MART / "coverage_by_year.csv").sort_values("year")
    coverage = coverage[coverage.year.between(1901, 2022)]

    station_rows = stations()
    paths, max_x, max_y = state_paths()
    repeats_info = f["repeats"]
    return {
        "map": {"w": round(max_x + 6), "h": round(max_y + 6), "states": paths},
        "stations": station_rows,
        "defaultStation": next(s["id"] for s in station_rows if s["name"] == "Chennai"),
        "defaultRateStation": next(s["id"] for s in station_rows if s["name"] == "Jaipur"),
        "groups": [{"name": GROUPS[k][0], "color": GROUPS[k][1], "count": repeats_info["groups"][k]} for k in ("jumped", "early", "clean", "other")],
        "repeats": repeats,
        "q1": {"periods": periods, "series": q1_series, "imd": f"{q1['imd_change_pct']:+.0f}%", "imdIndex": 100 + q1["imd_change_pct"]},
        "q2": q2,
        "q3": {"line": line, "band": band},
        "q4": {
            "rainy": [{"label": label(int(r.decade_start)), "value": round(float(r.rainy_days), 1), "text": f"{r.rainy_days:.1f}"} for r in decades.itertuples()],
            "heavy": [{"label": label(int(r.decade_start)), "value": round(float(r.heavy_days), 2), "text": f"{r.heavy_days:.2f}"} for r in decades.itertuples()],
            "balance": [{"label": r.era, "value": round(float(r.season_mm)), "text": f"{r.season_mm:.0f}", "color": status[r.era]} for r in balance.itertuples()],
            "statuses": [{"name": "Complete rain gauges", "color": "--blue"}, {"name": "Reporting gaps", "color": "--orange"}, {"name": "Later, fuller reports", "color": "--grey"}],
        },
        "q6": [{"name": r["name"], "country": r["country"], "rate": round(float(r["median_rate"]), 3), "q25": round(float(r["q25"]), 3), "q75": round(float(r["q75"]), 3), "stations": int(r["stations"]), "rank": int(r["rank"])} for r in countries.to_dict("records")],
        "coverage": [
            {"name": "Reporting rain", "color": "--blue", "points": [[int(y), int(v)] for y, v in zip(coverage.year, coverage.stations_rain)]},
            {"name": "Reporting maximum temperature", "color": "--orange", "points": [[int(y), int(v)] for y, v in zip(coverage.year, coverage.stations_tmax)]},
        ],
        "bench": bench_rows,
        "sens": sens,
        "dq": dq,
    }


def tokens(f: dict) -> dict:
    q1, q2, q3, q4, q6, dq, r, scale = f["q1_heatwave_days"], f["q2_days_and_nights"], f["q3_first_40c"], f["q4_monsoon"], f["q6_countries"], f["quality"], f["repeats"], f["scale"]
    clean = q1["by_repeat_group"]["clean"]["recorded"]
    storage = {row["table"]: row for row in csv.DictReader(open(MART / "storage.csv", encoding="utf8"))}
    return {
        "description": f"What {scale['rows'] / 1e9:.2f} billion weather records can and cannot show about India's heat, including an undocumented reporting artefact that follows regional lines.",
        "site_url": SITE_URL,
        "repo_url": REPO_URL,
        "rows_b": f"{scale['rows'] / 1e9:.2f}",
        "rows": f"{scale['rows']:,}",
        "rec_pct": f"{q1['recorded']['change_pct']:+.0f}%",
        "panel": str(q1["panel_stations"]),
        "clean_pct": f"{clean['change_pct']:+.0f}%",
        "clean_n": str(clean["stations"]),
        "clean_lo": f"{clean['change_pct_ci'][0]:+.0f}%",
        "clean_hi": f"{clean['change_pct_ci'][1]:+.0f}%",
        "clean_fell": str(clean["stations_falling"]),
        "imd_pct": f"{q1['imd_change_pct']:+.0f}%",
        "hit": str(r["groups"]["jumped"] + r["groups"]["early"]),
        "comparable": str(r["comparable_stations"]),
        "jumped": str(r["groups"]["jumped"]),
        "early": str(r["groups"]["early"]),
        "onset_nov": f"{r['onset']['november_2010']:.0f}",
        "onset_dec": f"{r['onset']['december_2010']:.0f}",
        "off_mar": f"{r['offset']['march_2016']:.0f}",
        "chennai_jumped": str(r["chennai_region"]["jumped"]),
        "chennai_n": str(r["chennai_region"]["stations"]),
        "maha_n": str(r["maharashtra"]["stations"]),
        "peak_ratio": f"{r['peaks']['jumped']['peaks_per_trough']:.0f}",
        "clean_ratio": str(r["peaks"]["clean"]["peaks_per_trough"]),
        "tmax": f"{q2['median_tmax_rate']:.2f}",
        "tmin": f"{q2['median_tmin_rate']:.2f}",
        "nights": str(q2["nights_faster"]),
        "trend_n": str(q2["stations"]),
        "first_date": q3["typical_first_date"],
        "q3_n": str(q3["stations"]),
        "q3_rate": f"{q3['median_days_per_decade']:+.1f}",
        "q3_lo": f"{q3['median_days_per_decade_ci'][0]:+.1f}",
        "q3_hi": f"{q3['median_days_per_decade_ci'][1]:+.1f}",
        "india_rank": str(q6["india_rank"]),
        "countries": str(q6["countries_ranked"]),
        "india_rate": f"{q6['india_median_rate']:.2f}",
        "india_clean_rank": str(q6["india_clean_stations_only"]["rank"]),
        "gauges": f"{q4['gauge_stations']:,}",
        "recent_n": str(q4["recent_window"]["stations"]),
        "recent_rate": f"{q4['recent_window']['mean_heavy_days_per_decade']:+.2f}",
        "recent_lo": f"{q4['recent_window']['mean_heavy_days_per_decade_ci'][0]:+.2f}",
        "recent_hi": f"{q4['recent_window']['mean_heavy_days_per_decade_ci'][1]:+.2f}",
        "net_1970": f"{q4['network_1970']:,}",
        "net_1973": str(q4["network_1973"]),
        "same_n": str(q4["same_stations"]),
        "rain_loss": f"{q4['apparent_loss_1982_98_pct']:.0f}",
        "noaa_gb": f"{int(storage['noaa']['bytes_on_disk']) / 1e9:.2f}",
        "parquet_gb": f"{scale['parquet_bytes'] / 1e9:.2f}",
        "in_file": f"{dq['indian_stations_in_file']:,}",
    }


def main() -> None:
    f = json.loads((MART / "findings.json").read_text(encoding="utf8"))
    values = tokens(f)
    values["data"] = json.dumps(data(f), separators=(",", ":"), ensure_ascii=False)
    template = (Path(__file__).parent / "site_template.html").read_text(encoding="utf8")

    def fill(match: re.Match) -> str:
        return values[match.group(1)]

    page = re.sub(r"\{\{(\w+)\}\}", fill, template)
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(page, encoding="utf8", newline="\n")
    (SITE / ".nojekyll").write_text("", encoding="utf8")
    shutil.copyfile(OUTPUTS / "india_heat_record_brief.pdf", SITE / "india_heat_record_brief.pdf")
    shutil.copyfile(CHARTS / "repeat_groups_map.png", SITE / "card.png")
    print(f"site/index.html: {(SITE / 'index.html').stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
