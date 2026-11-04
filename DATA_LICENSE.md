# Data sources and terms

This repository's MIT licence covers its code and written documents. The data keeps its own terms.

## NOAA GHCN-Daily

Daily weather records come from NOAA's Global Historical Climatology Network, in two forms:

- `noaa_enriched.parquet`, a copy packaged by ClickHouse from GHCN-Daily, with data through 7 September 2022.
- NOAA's per-station CSV files, for Indian temperature stations, read in November 2026.

NOAA's readme states no licence and asks users to cite the publications below. As work of a US government agency, the data is generally treated as public domain in the United States.

> Menne, M.J., I. Durre, R.S. Vose, B.E. Gleason, and T.G. Houston, 2012: An overview of the Global Historical Climatology Network-Daily Database. *Journal of Atmospheric and Oceanic Technology*, 29, 897-910, doi:10.1175/JTECH-D-11-00103.1.

> Menne, M.J., I. Durre, B. Korzeniewski, S. McNeal, K. Thomas, X. Yin, S. Anthony, R. Ray, R.S. Vose, B.E. Gleason, and T.G. Houston, 2012: Global Historical Climatology Network - Daily (GHCN-Daily), Version 3. NOAA National Climatic Data Center. doi:10.7289/V5D21VHZ. Accessed November 2026.

Row-level data is not committed. `data/mart` holds only aggregates from this analysis.

## India's outline

`data/geo/india_states_2011.geojson` is simplified from DataMeet India's Census 2011 boundaries, CC BY 4.0. It is for display only and is not an official map.

## Coastline

Distance to the coast is measured from Natural Earth's 1:50m coastline, which is public domain. The coastline file is downloaded when needed and is not committed.
