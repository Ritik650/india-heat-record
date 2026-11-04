"""Every chart in one place, built from data/mart, so the brief and the README show the same figures.

Each title states the finding. Colour carries meaning only where it is needed: blue is the corrected or
main series, grey is context, orange marks the one thing to compare, and blue to red is cool to warm.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import CHARTS, MART, ROOT  # noqa: E402

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
RED = "#d03b3b"
NEUTRAL = "#f0efec"
GREY = "#a8a6a0"
INK = "#0b0b0b"
SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
FONT = "Segoe UI"
SCALE = 2
PERIOD_ORDER = ["1982-89", "1990s", "2000s", "2010s", "2020-24"]


def theme() -> dict:
    return {
        "config": {
            "background": SURFACE,
            "font": FONT,
            "view": {"stroke": None},
            "title": {"anchor": "start", "fontSize": 15, "fontWeight": 600, "color": INK, "subtitleFontSize": 12, "subtitleColor": SECONDARY, "subtitleFontWeight": 400, "offset": 12},
            "axis": {"labelColor": SECONDARY, "titleColor": SECONDARY, "labelFontSize": 11, "titleFontSize": 11, "titleFontWeight": 400, "gridColor": GRID, "domainColor": "#c3c2b7", "tickColor": "#c3c2b7"},
            "legend": {"labelColor": SECONDARY, "titleColor": SECONDARY, "labelFontSize": 11, "titleFontSize": 11, "titleFontWeight": 400, "orient": "top"},
            "header": {"labelColor": SECONDARY, "labelFontSize": 10, "titleFontSize": 11},
        }
    }


alt.theme.register("heat", enable=True)(theme)


def save(chart, name: str) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    chart.save(str(CHARTS / f"{name}.png"), scale_factor=SCALE)
    print(f"{name}.png")


def findings() -> dict:
    return json.loads((MART / "findings.json").read_text(encoding="utf8"))


def repeats_by_group_chart(f: dict):
    r = f["repeats"]
    data = pd.read_csv(MART / "repeat_years_by_group.csv")
    data = data[data.tmax_days >= 500]
    labels = {"jumped": "Stepped at 2011", "early": "Stepped around 1990", "clean": "Never affected"}
    data["group"] = data.repeat_group.map(labels)
    maximums = data[["year", "group", "tmax_share"]].rename(columns={"tmax_share": "share"})
    minimums = data[data.repeat_group == "jumped"][["year", "tmin_share"]].rename(columns={"tmin_share": "share"}).assign(group="Minimums, same stations as 2011 group")
    long = pd.concat([maximums, minimums]).dropna()
    domain = list(labels.values()) + ["Minimums, same stations as 2011 group"]
    color = alt.Color("group:N", scale=alt.Scale(domain=domain, range=[ORANGE, AQUA, BLUE, GREY]), title=None, legend=alt.Legend(columns=2, labelLimit=0))
    dash = alt.StrokeDash("group:N", scale=alt.Scale(domain=domain, range=[[1, 0], [1, 0], [1, 0], [4, 3]]), legend=None)
    return alt.Chart(long).mark_line(strokeWidth=2).encode(
        x=alt.X("year:Q", title=None, axis=alt.Axis(format="d", tickCount=9, grid=False), scale=alt.Scale(domain=[1982, 2024])),
        y=alt.Y("share:Q", title="Days repeating the previous day's reading (%)", scale=alt.Scale(domain=[0, 40])),
        color=color, strokeDash=dash,
    ).properties(
        width=560, height=250,
        title=alt.TitleParams(
            "Repeated maximums switch on and off by group, while minimums never move",
            subtitle=[
                f"{r['groups']['jumped']} stations jump to about {r['jumped_median_share']['2011-15']:.0f}% in December 2010 and fall back in early 2016.",
                f"{r['groups']['early']} more step up around 1990. {r['groups']['clean']} stay near a natural level. All days of the year.",
            ],
        ),
    )


def repeat_groups_map(f: dict):
    r = f["repeats"]
    data = pd.read_csv(MART / "station_repeat_groups.csv", keep_default_na=False)
    data = data[data.repeat_group.isin(["clean", "jumped", "early"])]
    states = json.loads((ROOT / "data" / "geo" / "india_states_2011.geojson").read_text(encoding="utf8"))
    outline = alt.Chart(alt.Data(values=states["features"])).mark_geoshape(fill="#f0efec", stroke="#c3c2b7", strokeWidth=0.5)
    domain = ["Stepped at 2011", "Stepped around 1990", "Never affected"]
    points = alt.Chart(data).mark_point(filled=True, size=70, opacity=1, stroke=SURFACE, strokeWidth=0.7).encode(
        longitude="lon:Q", latitude="lat:Q",
        color=alt.Color("group_label:N", scale=alt.Scale(domain=domain, range=[ORANGE, AQUA, BLUE]), title=None, legend=alt.Legend(orient="top-right", direction="vertical", labelLimit=0, symbolSize=90)),
        shape=alt.Shape("group_label:N", scale=alt.Scale(domain=domain, range=["square", "triangle-up", "circle"]), title=None),
    )
    return (outline + points).project(type="mercator").properties(
        width=520, height=560,
        title=alt.TitleParams(
            "The reporting problem follows regional lines, which weather does not",
            subtitle=[
                f"{r['chennai_region']['jumped']} of {r['chennai_region']['stations']} stations in the area of IMD's Chennai centre step at 2011.",
                f"None of Maharashtra's {r['maharashtra']['stations']} do. {r['comparable_stations']} stations with data on both sides of 2011.",
            ],
        ),
    )


def q1_overall_chart(f: dict):
    q1 = f["q1_heatwave_days"]
    groups = pd.read_csv(MART / "q1_group_periods.csv")
    clean = groups[groups.repeat_group == "clean"].set_index("period").heatwave_days
    stations = pd.read_csv(MART / "q1_station_periods.csv", keep_default_na=False).groupby("period")[["heatwave_days", "heatwave_days_no_repeat"]].mean()
    rows = []
    for period in PERIOD_ORDER[:4]:
        rows.append({"period": period, "series": f"As recorded, all {q1['panel_stations']}", "index": 100 * stations.heatwave_days[period] / stations.heatwave_days["1982-89"]})
        rows.append({"period": period, "series": f"Repeats removed, all {q1['panel_stations']}", "index": 100 * stations.heatwave_days_no_repeat[period] / stations.heatwave_days_no_repeat["1982-89"]})
        rows.append({"period": period, "series": f"Never affected, {q1['by_repeat_group']['clean']['recorded']['stations']} stations", "index": 100 * clean[period] / clean["1982-89"]})
    data = pd.DataFrame(rows)
    names = data.series.drop_duplicates().tolist()
    color = alt.Color("series:N", scale=alt.Scale(domain=names, range=[GREY, BLUE, ORANGE]), legend=None)
    x = alt.X("period:N", sort=PERIOD_ORDER, title=None, axis=alt.Axis(labelAngle=0, grid=False), scale=alt.Scale(paddingOuter=0.2))
    y = alt.Y("index:Q", title="Heatwave days per station, 1982-89 = 100", scale=alt.Scale(domain=[80, 180]))
    lines = alt.Chart(data).mark_line(strokeWidth=2).encode(x=x, y=y, color=color)
    points = alt.Chart(data).mark_point(filled=True, size=60, opacity=1).encode(x=x, y=y, color=color)
    ends = data[data.period == "2010s"].assign(label=lambda d: d.series + " " + (d["index"] - 100).map("{:+.0f}%".format))
    text = alt.Chart(ends).mark_text(align="left", dx=9, fontSize=11, color=INK).encode(x=x, y=y, text="label:N")
    imd = pd.DataFrame([{"period": "2010s", "index": 100 + q1["imd_change_pct"], "label": f"IMD's 103 stations {q1['imd_change_pct']:+.0f}%"}])
    imd_mark = alt.Chart(imd).mark_point(shape="diamond", filled=True, size=70, color=INK, opacity=1).encode(x=x, y=y)
    imd_text = alt.Chart(imd).mark_text(align="left", dx=9, fontSize=11, color=SECONDARY).encode(x=x, y=y, text="label:N")
    clean_result = q1["by_repeat_group"]["clean"]["recorded"]
    return (lines + points + text + imd_mark + imd_text).properties(
        width=430, height=250,
        title=alt.TitleParams(
            "Heatwave days rose by about a third to a half, however they are counted",
            subtitle=[
                "Each station compared with itself. Removing all repeats over-corrects, so the fairest test is the stations",
                f"they never touched: {clean_result['change_pct']:+.0f}% (95% interval {clean_result['change_pct_ci'][0]:+.0f}% to {clean_result['change_pct_ci'][1]:+.0f}%).",
            ],
        ),
    )


def q1_small_multiples(f: dict):
    data = pd.read_csv(MART / "q1_station_periods.csv", keep_default_na=False)
    data["short"] = data.name
    wide = data.pivot(index="short", columns="period", values="heatwave_days_no_repeat")
    order = (wide["2010s"] - wide["1982-89"]).sort_values(ascending=False).index.tolist()
    long = data.melt(id_vars=["short", "period"], value_vars=["heatwave_days", "heatwave_days_no_repeat"], var_name="series", value_name="days")
    long["series"] = long.series.map({"heatwave_days": "As recorded", "heatwave_days_no_repeat": "Repeats removed"})
    base = alt.Chart(long).mark_line(strokeWidth=1.75, point=alt.OverlayMarkDef(size=14, filled=True)).encode(
        x=alt.X("period:N", sort=PERIOD_ORDER, title=None, axis=alt.Axis(labelAngle=-90, labelFontSize=9, grid=False)),
        y=alt.Y("days:Q", title="Days per hot season", axis=alt.Axis(tickCount=3)),
        color=alt.Color("series:N", scale=alt.Scale(domain=["As recorded", "Repeats removed"], range=[GREY, BLUE]), title=None),
    ).properties(width=112, height=78)
    q1 = f["q1_heatwave_days"]
    return base.facet(
        facet=alt.Facet("short:N", sort=order, title=None, header=alt.Header(labelFontSize=10, labelOrient="top", labelPadding=2)),
        columns=6,
        spacing=12,
    ).resolve_scale(y="shared").properties(
        title=alt.TitleParams(
            f"The rise is uneven: {q1['recorded']['stations_rising']} of {q1['recorded']['stations']} stations went up from 1982-89 to the 2010s as recorded",
            subtitle="Heatwave days per hot season at each panel station, ordered by change with repeats removed. Few stations have 2020-24 seasons.",
        )
    )


def q2_slope_chart(f: dict):
    q2 = f["q2_days_and_nights"]
    rates = pd.read_csv(MART / "station_rates.csv", keep_default_na=False)
    rates["group"] = rates.nights_faster.map({True: "Nights faster", False: "Days faster", "True": "Nights faster", "False": "Days faster"})
    long = rates.melt(id_vars=["station_id", "name", "group", "suspect"], value_vars=["tmax_rate", "tmin_rate"], var_name="when", value_name="rate")
    long["when"] = long.when.map({"tmax_rate": "Days (maximum)", "tmin_rate": "Nights (minimum)"})
    color = alt.Color("group:N", scale=alt.Scale(domain=["Days faster", "Nights faster"], range=[BLUE, ORANGE]), title=None)
    x = alt.X("when:N", title=None, sort=["Days (maximum)", "Nights (minimum)"], axis=alt.Axis(labelAngle=0, grid=False, domain=False, ticks=False), scale=alt.Scale(paddingOuter=0.08))
    y = alt.Y("rate:Q", title="Warming rate, °C per decade, 1982-2024")
    lines = alt.Chart(long).mark_line(strokeWidth=1.25, opacity=0.65).encode(x=x, y=y, color=color, detail="station_id:N")
    dots = alt.Chart(long).mark_circle(size=26, opacity=1).encode(x=x, y=y, color=color)
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#c3c2b7").encode(y="y:Q")
    median = pd.DataFrame([{"when": "Days (maximum)", "rate": q2["median_tmax_rate"]}, {"when": "Nights (minimum)", "rate": q2["median_tmin_rate"]}])
    median_line = alt.Chart(median).mark_line(color=INK, strokeWidth=3).encode(x=x, y=y)
    labelled = median.assign(label=lambda d: "median +" + d.rate.map("{:.2f}".format))
    left = alt.Chart(labelled[labelled.when == "Days (maximum)"]).mark_text(fontSize=12, color=INK, fontWeight=600, align="right", dx=-14).encode(x=x, y=y, text="label:N")
    right = alt.Chart(labelled[labelled.when == "Nights (minimum)"]).mark_text(fontSize=12, color=INK, fontWeight=600, align="left", dx=14).encode(x=x, y=y, text="label:N")
    return (zero + lines + dots + median_line + left + right).properties(
        width=430, height=340,
        title=alt.TitleParams(
            f"Nights are not outpacing days: {q2['days_faster']} of {q2['stations']} stations warmed faster by day",
            subtitle=[
                "Each line is one station. A line that climbs to the right means nights warmed faster there.",
                f"At the {q2['by_repeat_group']['clean']['stations']} stations repeats never affected, the two are level: +{q2['by_repeat_group']['clean']['median_tmax_rate']:.2f} and +{q2['by_repeat_group']['clean']['median_tmin_rate']:.2f}°C.",
            ],
        ),
    )


def q3_chart(f: dict):
    q3 = f["q3_first_40c"]
    data = pd.read_csv(MART / "q3_yearly.csv")
    data = data[data.stations >= 5].copy()
    data["segment"] = (data.year.diff().fillna(1) > 1).cumsum()
    x = alt.X("year:Q", title=None, axis=alt.Axis(format="d", tickCount=9, grid=False), scale=alt.Scale(domain=[1982, 2024]))
    y = alt.Y("median_shift:Q", title="Days earlier (-) or later (+) than the station's usual")
    band = alt.Chart(data).mark_area(color=BLUE, opacity=0.14).encode(x=x, y=alt.Y("q25:Q", title="Days earlier (-) or later (+) than the station's usual"), y2="q75:Q", detail="segment:N")
    line = alt.Chart(data).mark_line(color=BLUE, strokeWidth=2).encode(x=x, y=y, detail="segment:N")
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#c3c2b7").encode(y="y:Q")
    return (zero + band + line).properties(
        width=620, height=250,
        title=alt.TitleParams(
            f"Summer's first 40°C swings by weeks each year, with no clear drift: {q3['median_days_per_decade']:+.1f} days a decade",
            subtitle=f"Median across {q3['stations']} stations, shaded between the middle half. Usual first date is about {q3['typical_first_date']}. Years with under 5 stations are left out.",
        ),
    )


def q4_chart(f: dict):
    q4 = f["q4_monsoon"]
    data = pd.read_csv(MART / "q4_gauge_decades.csv")
    data["decade"] = data.decade_start.map(lambda d: f"{d}-{str(d + 9)[2:]}")
    x = alt.X("decade:N", title=None, axis=alt.Axis(labelAngle=0, grid=False), sort=data.decade.tolist())
    bars = alt.Chart(data).mark_bar(color=BLUE, size=46, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("decade:N", title=None, axis=alt.Axis(labels=False, ticks=False, grid=False), sort=data.decade.tolist()),
        y=alt.Y("rainy_days:Q", title="Rainy days per season", scale=alt.Scale(domain=[0, 50])),
    ).properties(width=620, height=150)
    bar_text = alt.Chart(data.assign(label=lambda d: d.rainy_days.map("{:.1f}".format))).mark_text(dy=-8, fontSize=11, color=SECONDARY).encode(x=alt.X("decade:N", sort=data.decade.tolist()), y="rainy_days:Q", text="label:N")
    heavy = alt.Chart(data).mark_line(color=ORANGE, strokeWidth=2, point=alt.OverlayMarkDef(size=60, filled=True, color=ORANGE)).encode(
        x=x, y=alt.Y("heavy_days:Q", title="Heavy days (100 mm+)", scale=alt.Scale(domain=[0, 1.2]), axis=alt.Axis(tickCount=4)),
    ).properties(width=620, height=120)
    heavy_text = alt.Chart(data.assign(label=lambda d: d.heavy_days.map("{:.2f}".format))).mark_text(dy=-12, fontSize=11, color=SECONDARY).encode(x=x, y="heavy_days:Q", text="label:N")
    return alt.vconcat((bars + bar_text), (heavy + heavy_text), spacing=8).properties(
        title=alt.TitleParams(
            "Across 1901-1970, rainy days held steady and heavy days barely moved",
            subtitle=f"June-September at the {q4['gauge_stations']:,} rain gauges with at least 56 of 70 complete seasons. Station averages per season.",
        )
    )


def water_balance_chart(f: dict):
    q4 = f["q4_monsoon"]
    data = pd.read_csv(MART / "q4_water_balance.csv")
    data["status"] = data.era.map(lambda e: "Complete rain gauges" if e == "1901-72" else ("Reporting gaps" if e in ("1973-81", "1982-98", "1999-2005") else "Later, fuller reports"))
    color = alt.Color("status:N", scale=alt.Scale(domain=["Complete rain gauges", "Reporting gaps", "Later, fuller reports"], range=[BLUE, ORANGE, GREY]), title=None)
    x = alt.X("era:N", title=None, sort=data.era.tolist(), axis=alt.Axis(labelAngle=0, grid=False))
    bars = alt.Chart(data).mark_bar(size=62, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(x=x, y=alt.Y("season_mm:Q", title="June-September rain as reported (mm)", scale=alt.Scale(domain=[0, 1100])), color=color)
    text = alt.Chart(data.assign(label=lambda d: d.season_mm.map("{:.0f}".format))).mark_text(dy=-8, fontSize=12, color=INK).encode(x=x, y="season_mm:Q", text="label:N")
    return (bars + text).properties(
        width=620, height=250,
        title=alt.TitleParams(
            f"The same stations appear to lose {q4['apparent_loss_1982_98_pct']:.0f}% of their rain when the source changes",
            subtitle=[
                f"{q4['same_stations']} stations with data in 1901-72, 1982-98 and 2006-15. A monsoon cannot fall this far and recover,",
                "so rain after 1972 is not compared with rain before it.",
            ],
        ),
    )


def q5_map(f: dict):
    q5 = f["q5_fastest_stations"]
    rates = pd.read_csv(MART / "station_rates.csv", keep_default_na=False)
    rates["short"] = rates.name
    states = json.loads((ROOT / "data" / "geo" / "india_states_2011.geojson").read_text(encoding="utf8"))
    outline = alt.Chart(alt.Data(values=states["features"])).mark_geoshape(fill="#f0efec", stroke="#c3c2b7", strokeWidth=0.5)
    limit = 0.5
    colors = alt.Scale(domain=[-limit, 0, limit], range=[BLUE, NEUTRAL, RED], clamp=True, interpolate="lab")
    trusted = rates[rates.suspect.astype(str) != "True"]
    flagged = rates[rates.suspect.astype(str) == "True"]
    circles = alt.Chart(trusted).mark_circle(size=120, opacity=1, stroke=INK, strokeWidth=0.6).encode(
        longitude="lon:Q", latitude="lat:Q",
        color=alt.Color("mean_rate:Q", scale=colors, title="°C per decade", legend=alt.Legend(orient="top-right", gradientLength=140, direction="vertical", format="+.1f", values=[-0.5, -0.25, 0, 0.25, 0.5])),
    )
    squares = alt.Chart(flagged).mark_square(size=90, opacity=1, stroke=INK, strokeWidth=1.2).encode(
        longitude="lon:Q", latitude="lat:Q", color=alt.Color("mean_rate:Q", scale=colors, legend=None),
    )
    top = rates.head(5)
    right_labels = alt.Chart(top[~top.short.isin(["Veraval", "Kurnool"])]).mark_text(align="left", dx=10, fontSize=11, color=INK, fontWeight=600).encode(longitude="lon:Q", latitude="lat:Q", text="short:N")
    left_labels = alt.Chart(top[top.short == "Veraval"]).mark_text(align="right", dx=-10, fontSize=11, color=INK, fontWeight=600).encode(longitude="lon:Q", latitude="lat:Q", text="short:N")
    above_labels = alt.Chart(top[top.short == "Kurnool"]).mark_text(align="center", dy=-14, fontSize=11, color=INK, fontWeight=600).encode(longitude="lon:Q", latitude="lat:Q", text="short:N")
    return (outline + circles + squares + right_labels + left_labels + above_labels).project(type="mercator").properties(
        width=520, height=560,
        title=alt.TitleParams(
            f"{q5['warming']} of {q5['stations']} stations warmed, led by Jaipur and three coastal stations",
            subtitle=[
                "Warming per decade, 1982-2024. The five fastest are named. Squares mark",
                f"{q5['suspect']} stations whose day and night rates differ too much to trust.",
            ],
        ),
    )


def q6_chart(f: dict):
    q6 = f["q6_countries"]
    data = pd.read_csv(MART / "q6_country_summary.csv", keep_default_na=False)
    data["is_india"] = data.country == "IN"
    y = alt.Y("name:N", sort=data.name.tolist(), title=None, axis=alt.Axis(grid=False, ticks=False, domain=False, labelFontSize=11))
    axis_title = "Median warming rate across a country's stations, °C per decade, 1982-2021"
    ticks = alt.Axis(values=[0, 0.2, 0.4, 0.6, 0.8], grid=True, format=".1f")
    x = alt.X("median_rate:Q", title=axis_title, scale=alt.Scale(domain=[0, 0.8]), axis=ticks)
    whiskers = alt.Chart(data).mark_rule(strokeWidth=1.5).encode(
        y=y, x=alt.X("q25:Q", title=axis_title, scale=alt.Scale(domain=[0, 0.8]), axis=ticks), x2="q75:Q",
        color=alt.condition(alt.datum.is_india, alt.value(ORANGE), alt.value("#d9d7d0")),
    )
    dots = alt.Chart(data).mark_circle(opacity=1).encode(
        y=y, x=x,
        size=alt.condition(alt.datum.is_india, alt.value(130), alt.value(46)),
        color=alt.condition(alt.datum.is_india, alt.value(ORANGE), alt.value(GREY)),
    )
    india = data[data.is_india].assign(label=lambda d: "India, rank " + d["rank"].astype(str) + " of " + str(len(data)) + ", +" + d.median_rate.map("{:.2f}".format))
    label = alt.Chart(india).mark_text(align="left", dx=14, fontSize=12, fontWeight=600, color=INK).encode(y=y, x=alt.X("q75:Q", title=axis_title, scale=alt.Scale(domain=[0, 0.8]), axis=ticks), text="label:N")
    return (whiskers + dots + label).properties(
        width=540, height=len(data) * 15,
        title=alt.TitleParams(
            f"India's stations warmed more slowly than {q6['countries_faster_than_india']} of the other {q6['countries_ranked'] - 1} countries",
            subtitle=[
                "Countries with at least 5 qualifying stations. Lines span the middle half of a country's stations.",
                f"The same rule applies everywhere, across {q6['stations_all_countries']:,} stations.",
            ],
        ),
    )


def coverage_chart(f: dict):
    data = pd.read_csv(MART / "coverage_by_year.csv")
    data = data[data.year.between(1901, 2022)]
    long = data.melt(id_vars="year", value_vars=["stations_rain", "stations_tmax"], var_name="what", value_name="stations")
    long["what"] = long.what.map({"stations_rain": "Reporting rain", "stations_tmax": "Reporting maximum temperature"})
    color = alt.Color("what:N", scale=alt.Scale(domain=["Reporting rain", "Reporting maximum temperature"], range=[BLUE, ORANGE]), title=None, legend=alt.Legend(labelLimit=0))
    line = alt.Chart(long).mark_line(strokeWidth=2).encode(x=alt.X("year:Q", title=None, axis=alt.Axis(format="d", tickCount=12, grid=False), scale=alt.Scale(domain=[1901, 2022])), y=alt.Y("stations:Q", title="Indian stations"), color=color)
    q = f["quality"]
    return line.properties(
        width=620, height=230,
        title=alt.TitleParams(
            f"Rain coverage falls from {q['stations_with_rain_1970']:,} stations to {q['stations_with_rain_1973']} in three years",
            subtitle="India's record in this file is two different datasets joined in the early 1970s. Temperature effectively starts in 1973, not 1900.",
        ),
    )


def benchmark_chart():
    path = MART / "benchmark.csv"
    if not path.exists():
        return None
    data = pd.read_csv(path)
    data = data[data.run == "median_warm"]
    names = {"clickhouse_raw": "ClickHouse, raw table", "clickhouse_rollup": "ClickHouse, rollup", "duckdb_parquet": "DuckDB on Parquet"}
    data["engine_label"] = data.engine.map(names)
    order = data.question.drop_duplicates().tolist()
    wide = data.pivot(index="question", columns="engine", values="seconds")
    best = (wide.clickhouse_raw / wide.clickhouse_rollup).max()
    color = alt.Color("engine_label:N", scale=alt.Scale(domain=list(names.values()), range=[GREY, BLUE, ORANGE]), title=None, legend=alt.Legend(labelLimit=0))
    y = alt.Y("question:N", sort=order, title=None, axis=alt.Axis(labelLimit=340, ticks=False, domain=False, grid=True, labelFontSize=11))
    x = alt.X("seconds:Q", title="Median warm seconds, log scale. Further left is faster.", scale=alt.Scale(type="log", domain=[0.05, 50]), axis=alt.Axis(grid=True, values=[0.1, 1, 10], format="~g"))
    # Dots, because a bar on a log scale has no honest baseline.
    return alt.Chart(data).mark_point(filled=True, size=130, opacity=1).encode(x=x, y=y, color=color, shape=alt.Shape("engine_label:N", scale=alt.Scale(domain=list(names.values()), range=["circle", "square", "diamond"]), title=None)).properties(
        width=430, height=len(order) * 34,
        title=alt.TitleParams(
            f"The rollup is up to {best:.0f} times faster, and DuckDB beats the raw table on wide scans",
            subtitle="Same 1.07B rows, 4 threads, 3 GB. The rollup returns the same answer as the full scan.",
        ),
    )


def main() -> None:
    f = findings()
    save(repeats_by_group_chart(f), "repeats_by_group")
    save(repeat_groups_map(f), "repeat_groups_map")
    save(q1_overall_chart(f), "q1_heatwave_overall")
    save(q1_small_multiples(f), "q1_small_multiples")
    save(q2_slope_chart(f), "q2_days_nights")
    save(q3_chart(f), "q3_first_40c")
    save(q4_chart(f), "q4_monsoon")
    save(water_balance_chart(f), "q4_water_balance")
    save(q5_map(f), "q5_station_map")
    save(q6_chart(f), "q6_countries")
    save(coverage_chart(f), "coverage")
    chart = benchmark_chart()
    if chart is not None:
        save(chart, "benchmark")


if __name__ == "__main__":
    main()
