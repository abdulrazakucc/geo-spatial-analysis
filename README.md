---
title: ACR Cardiac Imaging - Geographic Disparities Dashboard
emoji: 🫀
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
license: mit
---

# ACR Cardiac Imaging Geographic Disparities Analysis

## Project Overview

Cross-sectional ecologic analysis examining geographic variation in ACR-accredited cardiac imaging capacity (MRI and CT) across US counties, with stratification by social vulnerability (CDC SVI) and rurality (USDA RUCC).

**Target journal:** JACC: Advances — Special Focus Issue on Health Equity in Cardiology  
**Submission deadline:** June 1, 2026

## Project Structure

```
geo-spatial-analysis/
├── code/
│   ├── 01_download_datasets.py      # Downloads external datasets
│   ├── 02_build_analytic_dataset.py  # Cleans, links, and builds county-level data
│   ├── 03_descriptive_analysis.py    # Table 1 + Spearman correlations
│   ├── 04_choropleth_map.py          # Figure 1 (two-panel US county map)
│   ├── 05_regression_analysis.py     # Negative binomial regression + sensitivity
│   └── 06_run_all.py                 # Master pipeline runner
├── data/
│   ├── ACR_Cardiac_Imaging_Sites.xlsx  # Provided by Dr. Naeem (2,273 facilities)
│   ├── acr_dataset.xlsx                # Full ACR extract (reference only)
│   ├── raw/                            # Downloaded external datasets
│   │   ├── tiger_county_2023/          # TIGER/Line county shapefiles
│   │   ├── zcta_county_crosswalk_2020.txt
│   │   ├── SVI_2022_US_county.csv      # ← Manual download required
│   │   └── ruralurbancodes2023.xls     # ← Manual download required
│   └── processed/
│       ├── county_analytic_dataset.csv # Final analytic file (3,144 counties)
│       └── county_analytic_geo.gpkg    # Geo-enabled version for mapping
├── output/
│   ├── figures/
│   │   ├── figure1_choropleth.pdf
│   │   └── figure1_choropleth.png
│   ├── tables/
│   │   ├── table1_descriptive.csv
│   │   └── table1_formatted.txt
│   └── models/
│       ├── regression_results.txt
│       └── model_objects.pkl
├── docs/
│   ├── Project_Briefing_Shiloh.docx
│   ├── Data_Scientist_Task_Guide.html
│   └── Data_Scientist_Task_Guide.pdf
├── requirements.txt
└── README.md
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run full pipeline
python code/06_run_all.py

# Or run individual steps
python code/01_download_datasets.py
python code/02_build_analytic_dataset.py
python code/03_descriptive_analysis.py
python code/04_choropleth_map.py
python code/05_regression_analysis.py
```

## Manual Data Downloads Required

The following datasets could not be auto-downloaded (government sites restructured). Download manually and place in `data/raw/`:

1. **CDC SVI 2022** → Save as `data/raw/SVI_2022_US_county.csv`
   - URL: https://www.atsdr.cdc.gov/place-health/php/svi/
   - Need: County-level CSV with `FIPS` and `RPL_THEMES` columns

2. **USDA RUCC 2023** → Save as `data/raw/ruralurbancodes2023.xls`
   - URL: https://www.ers.usda.gov/data-products/rural-urban-continuum-codes
   - Need: Excel file with `FIPS` and `RUCC_2023` columns

3. **Census ACS Population** (optional) → Save as `data/raw/acs_county_population.csv`
   - URL: https://www.census.gov/data/developers/data-sets/acs-5year.html
   - Need: CSV with columns `county_fips`, `total_population`, `adult_pop_45plus`

**Note:** The pipeline generates realistic proxy data when these files are missing, allowing the code to run end-to-end for testing. Replace with real data before publication.

## Dataset Versions & Access Dates

| Dataset | Version | Access Date |
|---------|---------|-------------|
| ACR Cardiac Imaging Sites | May 20, 2026 extraction | May 20, 2026 |
| Census TIGER/Line County | 2023 | May 22, 2026 |
| Census ZCTA-County Crosswalk | 2020 | May 22, 2026 |
| CDC SVI | 2022 (pending download) | — |
| USDA RUCC | 2023 (pending download) | — |
| ACS 5-Year | 2019-2023 (pending download) | — |

## Key Decisions

- **Unit of analysis:** US county (n=3,143; 50 states + DC)
- **Multi-county ZIPs:** Assigned to county with largest land area overlap
- **Rate denominator:** Adults aged ≥45 years
- **Rate exclusion:** Counties with <1,000 adults ≥45 excluded from per-capita rates
- **Double-counting:** Facility accredited for both MRI and CT counted once per modality
- **Inclusion:** "Accredited" and "Under Review" status (sensitivity analysis excludes "Under Review")

## Software

- Python 3.11
- Key libraries: pandas, geopandas, statsmodels, matplotlib, mapclassify, scipy
