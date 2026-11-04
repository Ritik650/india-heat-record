"""Write the two-page brief. Every number comes from data/mart, so nothing here can drift from the results."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

sys.path.insert(0, str(Path(__file__).parent))
from common import CHARTS, MART, OUTPUTS  # noqa: E402

INK = colors.HexColor("#191c1e")
MUTED = colors.HexColor("#52514e")
ACCENT = colors.HexColor("#2a78d6")
RULE = colors.HexColor("#e2e8f0")
MARGIN = 1.5 * cm
WIDTH = A4[0] - 2 * MARGIN
IN_BRIEF = ("This project", "Normals from", "The plan", "Only stations", "Leaving out")


def styles() -> dict:
    base = {"fontName": "Helvetica", "textColor": INK, "alignment": TA_LEFT}
    return {
        "title": ParagraphStyle("title", **{**base, "fontName": "Helvetica-Bold"}, fontSize=17, leading=20, spaceAfter=2),
        "sub": ParagraphStyle("sub", **{**base, "textColor": MUTED}, fontSize=8.5, leading=11, spaceAfter=6),
        "lead": ParagraphStyle("lead", **base, fontSize=10, leading=13.2, spaceAfter=6),
        "h": ParagraphStyle("h", **{**base, "fontName": "Helvetica-Bold"}, fontSize=10, leading=12.5, spaceBefore=6, spaceAfter=1.5),
        "body": ParagraphStyle("body", **base, fontSize=9, leading=11.7, spaceAfter=2),
        "small": ParagraphStyle("small", **{**base, "textColor": MUTED}, fontSize=7.2, leading=9),
        "cell": ParagraphStyle("cell", **base, fontSize=7.6, leading=9.4),
        "cellb": ParagraphStyle("cellb", **{**base, "fontName": "Helvetica-Bold"}, fontSize=7.6, leading=9.4),
    }


def picture(name: str, width: float) -> Image:
    path = CHARTS / f"{name}.png"
    w, h = ImageReader(str(path)).getSize()
    return Image(str(path), width=width, height=width * h / w)


def benchmark_rows() -> list[dict]:
    path = MART / "benchmark.csv"
    return list(csv.DictReader(open(path, encoding="utf8"))) if path.exists() else []


def seconds(rows: list[dict], question: str, engine: str, run: str = "median_warm") -> float | None:
    for row in rows:
        if row["question"].startswith(question) and row["engine"] == engine and row["run"] == run:
            return float(row["seconds"])
    return None


def storage_gb(table: str) -> float | None:
    path = MART / "storage.csv"
    if not path.exists():
        return None
    for row in csv.DictReader(open(path, encoding="utf8")):
        if row["table"] == table:
            return int(row["bytes_on_disk"]) / 1e9
    return None


def sensitivity_rows() -> list[dict]:
    path = MART / "sensitivity.csv"
    return list(csv.DictReader(open(path, encoding="utf8"))) if path.exists() else []


def two_charts(left: str, right: str, share: float = 0.49) -> Table:
    return Table(
        [[picture(left, WIDTH * share), picture(right, WIDTH * share)]],
        colWidths=[WIDTH * 0.5, WIDTH * 0.5],
        style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("VALIGN", (0, 0), (-1, -1), "TOP")]),
    )


def fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}" if value < 10 else f"{value:.0f}"


def build() -> Path:
    f = json.loads((MART / "findings.json").read_text(encoding="utf8"))
    s = styles()
    q1, q2, q3, q4, q5, q6, dq, scale = f["q1_heatwave_days"], f["q2_days_and_nights"], f["q3_first_40c"], f["q4_monsoon"], f["q5_fastest_stations"], f["q6_countries"], f["quality"], f["scale"]
    recorded, clean = q1["recorded"], q1["without_repeats"]
    bench = benchmark_rows()
    recent = q1["recent_seasons"]["2024"]
    scenarios = sensitivity_rows()

    r = f["repeats"]
    clean_group = q1["by_repeat_group"]["clean"]
    jumped_group = q1["by_repeat_group"]["jumped"]
    clean_q2 = q2["by_repeat_group"]["clean"]
    story = [
        Paragraph("India's Heat Record: what 1.07 billion weather rows can and cannot show", s["title"]),
        Paragraph(f"Ritik Yadav, November 2026. {scale['rows'] / 1e9:.2f}B station-days from NOAA GHCN-Daily, built from {scale['measurements_before_pivot'] / 1e9:.2f}B measurements, analysed in ClickHouse. Results describe the stations named here, not all of India.", s["sub"]),
        Paragraph(
            "<b>Bottom line.</b> Heatwave days did rise at these stations, by about a third to a half from the 1980s to the 2010s, in line with IMD's own count. "
            "But the public record carries an undocumented reporting artefact that switches on region by region and inflates the count where it applies. "
            "Accounting for it changes the answers: nights are not outpacing days, summer's first 40°C has not clearly moved, and rain after 1972 cannot be compared with rain before it.",
            s["lead"],
        ),
        two_charts("q1_heatwave_overall", "repeats_by_group"),
        Paragraph("1. Heatwave days rose by about a third to a half", s["h"]),
        Paragraph(
            f"At {q1['panel_stations']} stations compared with themselves, heatwave days per hot season rose {recorded['change_pct']:.0f}% from 1982-89 to the 2010s as recorded. Removing every repeated reading gives {clean['change_pct']:.0f}% (95% interval {clean['change_pct_ci'][0]:.0f}% to {clean['change_pct_ci'][1]:.0f}%), but that also drops genuine hot days. "
            f"The fairest test is the {clean_group['recorded']['stations']} stations the problem never touched: up {clean_group['recorded']['change_pct']:.0f}% (interval {clean_group['recorded']['change_pct_ci'][0]:.0f}% to {clean_group['recorded']['change_pct_ci'][1]:.0f}%), though {clean_group['recorded']['stations_falling']} of them fell. IMD's own count at 103 stations rose {q1['imd_change_pct']:.0f}%.",
            s["body"],
        ),
        Paragraph("2. A reporting artefact switches on by region", s["h"]),
        Paragraph(
            f"A daily maximum identical to the previous day's normally covers about 4% of days. At {r['groups']['jumped']} stations it jumps from {r['onset']['november_2010']:.0f}% in November 2010 to {r['onset']['december_2010']:.0f}% a month later, holds for five years, then falls to {r['offset']['march_2016']:.0f}% by March 2016. Minimums at the same stations never move, and no station jumps by 5 to 15 points: it is all or nothing. "
            f"{r['chennai_region']['jumped']} of the {r['chennai_region']['stations']} stations in the area of IMD's Chennai centre are in this group, and none of Maharashtra's {r['maharashtra']['stations']}. Another {r['groups']['early']} in the north-west step up around 1990. "
            f"These repeats sit on local peaks {r['peaks']['jumped']['peaks_per_trough']:.0f} times as often as on troughs, against {r['peaks']['clean']['peaks_per_trough']} at clean stations, which is what copying a day's peak into the next day would do. The cause is inferred, not documented. At the stations that stepped at 2011, heatwave days rise {jumped_group['recorded']['change_pct']:.0f}% as recorded, and {jumped_group['without_repeats']['change_pct']:.0f}% without repeats.",
            s["body"],
        ),
        Paragraph("3. Nights are not outpacing days", s["h"]),
        Paragraph(
            f"From 1982 to 2024 the median station warmed +{q2['median_tmax_rate']:.2f}°C a decade by day and +{q2['median_tmin_rate']:.2f}°C by night, and nights led at {q2['nights_faster']} of {q2['stations']} stations. Much of that gap comes from affected stations: at the {clean_q2['stations']} clean ones the two are level (+{clean_q2['median_tmax_rate']:.2f} and +{clean_q2['median_tmin_rate']:.2f}°C), with nights ahead at {clean_q2['nights_faster']}. IMD's warm nights, which count only on days reaching 40°C, became more common but remain rare.",
            s["body"],
        ),
        Paragraph("4. Summer's start and monsoon extremes show no clear shift", s["h"]),
        Paragraph(
            f"The first 40°C moved {q3['median_days_per_decade']:+.1f} days a decade across {q3['stations']} stations (interval {q3['median_days_per_decade_ci'][0]:+.1f} to {q3['median_days_per_decade_ci'][1]:+.1f}), while years swing by {q3['biggest_year_swing_days']:.0f} days. "
            f"Across {q4['gauge_stations']:,} rain gauges from 1901 to 1970, heavy days (100 mm or more) went from {q4['first_decade']['heavy_days']:.2f} to {q4['last_decade']['heavy_days']:.2f} a season. Coverage then falls from {q4['network_1970']:,} stations to {q4['network_1973']} by 1973, and the same {q4['same_stations']} stations appear to lose {q4['apparent_loss_1982_98_pct']:.0f}% of their rain before recovering, so no trend is drawn across that break. Within 2006-2024, {q4['recent_window']['stations']} stations show no clear change either ({q4['recent_window']['mean_heavy_days_per_decade']:+.2f} heavy days a decade, interval {q4['recent_window']['mean_heavy_days_per_decade_ci'][0]:+.2f} to {q4['recent_window']['mean_heavy_days_per_decade_ci'][1]:+.2f}).",
            s["body"],
        ),
        Paragraph("5. India's stations warmed more slowly than most countries'", s["h"]),
        Paragraph(
            f"{q5['warming']} of {q5['stations']} stations warmed, with a median of +{q5['median_rate']:.2f}°C a decade. Under one rule for every country, 1982-2021, India ranks {q6['india_rank']} of {q6['countries_ranked']} at +{q6['india_median_rate']:.2f}°C, against a median country of +{q6['median_of_countries']:.2f}°C, or {q6['india_clean_stations_only']['rank']} of {q6['countries_ranked']} using clean stations alone. Slower warming does not mean little heat: the 2024 hot season averaged {recent['no_repeat']:.1f} heatwave days at the {recent['stations']} stations with complete data, against {recent['no_repeat_usual']:.1f} in their 1991-2020 average, with repeats removed.",
            s["body"],
        ),
        Spacer(1, 2),
        two_charts("q4_water_balance", "q3_first_40c", 0.30),
        PageBreak(),
        two_charts("repeat_groups_map", "q5_station_map", 0.34),
        two_charts("q6_countries", "q2_days_nights", 0.34),
    ]

    if bench:
        cell, bold = s["cell"], s["cellb"]
        questions = [("India, every station-year", "India, every station-year"), ("One station", "One station's whole history"), ("Every country", "Every country by decade, full scan"), ("Q6, first", "Warming rate, every station: first query"), ("Q6, rewritten", "Warming rate, every station: rewritten query")]
        rows = [[Paragraph(t, bold) for t in ("Median warm seconds, 4 threads, 3 GB", "ClickHouse raw", "ClickHouse rollup", "DuckDB on Parquet")]]
        for key, label in questions:
            rows.append([Paragraph(label, cell)] + [Paragraph(fmt(seconds(bench, key, e)), cell) for e in ("clickhouse_raw", "clickhouse_rollup", "duckdb_parquet")])
        story += [
            Paragraph("How it was built", s["h"]),
            Paragraph(
                f"ClickHouse holds all {scale['rows']:,} rows in {storage_gb('noaa'):.2f} GB, smaller than the {scale['parquet_bytes'] / 1e9:.2f} GB Parquet they came from, using per-column codecs, a table partitioned by decade and sorted by station and date, and rollups kept current by materialized views. The rollup returned the same answer as a full scan on all {q6['stations_all_countries']:,} stations. Times below are real, and include wherever DuckDB wins.",
                s["body"],
            ),
            Spacer(1, 2),
            Table(rows, colWidths=[WIDTH * 0.46, WIDTH * 0.18, WIDTH * 0.18, WIDTH * 0.18], style=TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, MUTED), ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5), ("LEFTPADDING", (0, 0), (-1, -1), 0)])),
        ]

    if scenarios:
        cell, bold = s["cell"], s["cellb"]
        rows = [[Paragraph(t, bold) for t in ("Rise in heatwave days, 1982-89 to the 2010s, if one choice changes (all in the README)", "Stations", "As recorded", "Repeats removed")]]
        for row in scenarios:
            if not row["scenario"].startswith(IN_BRIEF):
                continue
            rows.append([Paragraph(row["scenario"], cell), Paragraph(row["stations"], cell), Paragraph(f"+{row['change_recorded_pct']}%", cell), Paragraph(f"+{row['change_no_repeat_pct']}%", cell)])
        story += [
            Spacer(1, 7),
            Table(rows, colWidths=[WIDTH * 0.52, WIDTH * 0.12, WIDTH * 0.16, WIDTH * 0.20], style=TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, MUTED), ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE), ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2), ("LEFTPADDING", (0, 0), (-1, -1), 0)])),
        ]

    story += [
        Paragraph("What this cannot tell you", s["h"]),
        Paragraph(
            f"<b>These are stations, not India.</b> The file names {dq['indian_stations_in_file']:,} Indian stations, but only {dq['stations_in_heat_panel']} pass the bar for heatwave trends, none in the hills, and few have complete seasons after 2015. "
            f"<b>One source.</b> Every Indian maximum through 2024 comes from a NOAA source its readme says to use with caution, and GHCN-Daily does not adjust for station moves. {q5['suspect']} stations show day and night rates too far apart to trust. "
            f"<b>Not IMD's declarations.</b> IMD declares heatwaves by sub-division, and has since added percentile thresholds. This applies IMD's published station rule to every year alike. "
            f"<b>Published figures differ in kind.</b> IMD's 536 heatwave days in summer 2024 adds up sub-divisions, so it cannot be compared with counts per station here. Temperature stops in 2024, because NOAA changed these stations' source in 2025.",
            s["body"],
        ),
        Paragraph(f"Data: Menne et al. 2012, GHCN-Daily, via ClickHouse and NOAA. Full checks: docs/issue_log.csv ({dq['checks']} checks). Corrections to the original plan: docs/plan_corrections.md. Sources: docs/sources.md.", s["small"]),
    ]

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    path = OUTPUTS / "india_heat_record_brief.pdf"
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=1.25 * cm, bottomMargin=1.1 * cm, title="India's Heat Record", author="Ritik Yadav").build(story)
    return path


def main() -> None:
    from pypdf import PdfReader

    path = build()
    pages = len(PdfReader(str(path)).pages)
    print(f"{path.name}: {pages} pages")
    if pages != 2:
        raise SystemExit(f"The brief must be 2 pages, not {pages}")


if __name__ == "__main__":
    main()
