# Sources

Each claim was checked against the source's own text in November 2026, unless the note says otherwise.

## The data

| Source | Used for |
|---|---|
| [ClickHouse: NOAA GHCN dataset](https://clickhouse.com/docs/getting-started/example-datasets/noaa) | Schema, units, the Parquet file, the count of 2,679,264,563 measurements before pivoting |
| [NOAA GHCN-Daily readme](https://noaa-ghcn-pds.s3.amazonaws.com/readme.txt) | Citation, quality and source flags, and the caution on source S |
| [NOAA per-station files](https://noaa-ghcn-pds.s3.amazonaws.com/index.html) | Raw Indian readings with flags, through October 2026 |

## How IMD defines heat

| Source | Used for |
|---|---|
| [IMD: heat wave definitions](https://internal.imd.gov.in/section/nhac/dynamic/Definition.pdf) | The full rule: plains, hills, coast, 45 C and 47 C, warm nights |
| [IMD: heat wave FAQ](https://internal.imd.gov.in/section/nhac/dynamic/FAQ_heat_wave.pdf) | Normals come from 1991-2020 |
| [IMD: glossary](https://www.imdpune.gov.in/Reports/glossary.pdf) | A rainy day is 2.5 mm or more |
| [Mongabay India, May 2026: interview with IMD's chief](https://india.mongabay.com/2026/05/both-daytime-and-nighttime-temperatures-have-risen-imd-chief-interview/) | IMD has since added percentile thresholds. The article gives no date for the change, and this project uses the published departure rule because it can be applied to every year alike |

## Context in the brief

| Claim | Source | Note |
|---|---|---|
| 2024 was India's warmest year since 1901 | [Down To Earth](https://www.downtoearth.org.in/climate-change/extreme-weather-events-in-india-2024-heatwaves-avoidable-deaths-and-an-uncertain-future) | Confirmed |
| 733 heatstroke deaths in news reports, March-June 2024, 17 states | Same article, citing Heat Watch | Confirmed |
| 536 heatwave days in summer 2024, highest in 14 years | [Scroll, 2 July 2024](https://scroll.in/latest/1070056/india-logged-536-heatwave-days-this-summer-highest-since-2010-imd), citing IMD | Confirmed. One day across five sub-divisions counts as five, so this is not 536 calendar days |
| 554 heatwave days across 2024, 230 in 2023 | [Down To Earth, 5 December 2024](https://www.downtoearth.org.in/governance/as-told-to-parliament-december-5-2024-554-heatwaves-days-were-observed-over-the-indian-region-in-2024-says-jitendra-singh), citing the minister's reply to Parliament | Confirmed, and later than the 536 figure |
| 143 deaths and 41,789 suspected heatstroke cases | [Business Today, 21 June 2024](https://www.businesstoday.in/india/story/deadly-summer-heatwaves-claim-143-lives-over-41000-cases-of-suspected-heatstrokes-toll-likely-to-rise-434205-2024-06-21), citing NCDC surveillance | Confirmed, but covers 1 March to 20 June only. The plan's source, India Weekly, could not be found |
| About 48,000 cases and 159 deaths for all of 2024 | [Deccan Herald](https://www.deccanherald.com/india/india-recorded-over-7000-suspected-heatstroke-cases-14-deaths-in-march-june-period-rti-3650589) | Read only in a search listing, because the page refused automated requests. Not used in the brief |
| A 1 C rise at night could cut wheat yields 6% and rice up to 10% | [Down To Earth](https://www.downtoearth.org.in/climate-change/india-records-earliest-heatwave-and-warm-nights-in-2025) | The article says so and links to papers without naming them. Not used in the brief |

## Independent checks on the results

| Check | Source | Result |
|---|---|---|
| Churu reached 50.8 C on 1 June 2019 | [ThePrint](https://theprint.in/india/rajasthan-reeling-from-intense-heat-wave-temperature-crosses-50-degrees-c-in-churu/2105832/), citing the Jaipur Met Centre | The data has 50.8 on that date |
| Churu reached 50.5 C on 28 May 2024 | [IMD](https://x.com/Indiametdept/status/1795458603383730491), and [IMD's press release of 30 May 2024](https://internal.imd.gov.in/press_release/20240603_pr_3037.pdf) | The data has 50.5 on that date |
| Heatwave days at 103 IMD stations: 413 in 1981-90, 575 in 2001-10, 600 in 2011-20 | [Mongabay India, April 2022](https://india.mongabay.com/2022/04/climate-change-hits-home-as-increasing-heatwave-days-scorch-india/), citing a Met Department study | IMD's rise of 45% falls between this project's two estimates |

## IMD's structure

| Claim | Source | Note |
|---|---|---|
| IMD has 6 Regional Meteorological Centres | [IMD: organisation](https://mausam.imd.gov.in/responsive/orgStructure.php) | Confirmed. The page does not list the states under each |
| The Chennai centre covers Andhra Pradesh, Telangana, Karnataka, Kerala, Tamil Nadu, the Andaman and Nicobar Islands, Lakshadweep and Puducherry | [Wikipedia: Regional Meteorological Centre, Chennai](https://en.wikipedia.org/wiki/Regional_Meteorological_Centre,_Chennai) | Secondary source. Used only to describe where the affected stations are, not to claim a cause |

## Boundaries

India's outline is simplified from [DataMeet's Census 2011 boundaries](https://github.com/datameet/maps), CC BY 4.0, and is for display only. Coastline distance uses [Natural Earth](https://www.naturalearthdata.com/).
