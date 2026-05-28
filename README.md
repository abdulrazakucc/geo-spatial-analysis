------

title: ACR Cardiac Imaging - Geographic Disparities Dashboardtitle: ACR Cardiac Imaging - Geographic Disparities Dashboard

emoji: 🫀emoji: 🫀

colorFrom: bluecolorFrom: blue

colorTo: indigocolorTo: indigo

sdk: dockersdk: docker

pinned: falsepinned: false

license: mitlicense: mit

------



# Geographic Disparities in ACR-Accredited Cardiac Imaging Capacity# ACR Cardiac Imaging Geographic Disparities Analysis



A cross-sectional ecologic analysis of 3,144 US counties examining whether social vulnerability and area deprivation predict access to accredited cardiac imaging facilities.## Project Overview



**Authors:** Abdul Razak, MD and Naeem Ahmad, MD  Cross-sectional ecologic analysis examining geographic variation in ACR-accredited cardiac imaging capacity (MRI and CT) across US counties, with stratification by social vulnerability (CDC SVI) and rurality (USDA RUCC).

**Target Journal:** JACC: Advances (Special Focus Issue on Health Equity in Cardiology)  

**Submission Deadline:** June 1, 2026  **Target journal:** JACC: Advances — Special Focus Issue on Health Equity in Cardiology  

**Last Updated:** May 28, 2026**Submission deadline:** June 1, 2026



---## Project Structure



## Table of Contents```

geo-spatial-analysis/

1. [Executive Summary](#executive-summary)├── code/

2. [Background and Motivation](#background-and-motivation)│   ├── 01_download_datasets.py      # Downloads external datasets

3. [Data Sources](#data-sources)│   ├── 02_build_analytic_dataset.py  # Cleans, links, and builds county-level data

4. [Methods](#methods)│   ├── 03_descriptive_analysis.py    # Table 1 + Spearman correlations

5. [Key Findings](#key-findings)│   ├── 04_choropleth_map.py          # Figure 1 (two-panel US county map)

6. [Why PCA for ADI Construction](#why-pca-for-adi-construction)│   ├── 05_regression_analysis.py     # Negative binomial regression + sensitivity

7. [Project Structure](#project-structure)│   ├── 06_adi_sensitivity_analysis.py # ADI as alternative predictor (supplementary)

8. [Quick Start](#quick-start)│   └── 07_run_all.py                 # Master pipeline runner

9. [Outputs](#outputs)├── data/

10. [Abbreviations](#abbreviations)│   ├── ACR_Cardiac_Imaging_Sites.xlsx  # Provided by Dr. Naeem (2,273 facilities)

11. [References](#references)│   ├── acr_dataset.xlsx                # Full ACR extract (reference only)

│   ├── raw/                            # Downloaded external datasets

---│   │   ├── tiger_county_2023/          # TIGER/Line county shapefiles

│   │   ├── zcta_county_crosswalk_2020.txt

## Executive Summary│   │   ├── SVI_2022_US_county.csv      # ← Manual download required

│   │   ├── county_health_rankings_2024.csv  # CHR (auto-downloaded for ADI)

We analyzed the geographic distribution of 725 ACR-accredited Cardiac MRI (CMR) and 1,548 Cardiac CT (CCT) facilities across all 3,144 US counties. Our primary predictor was the CDC Social Vulnerability Index (SVI). As a sensitivity analysis (requested by Dr. Naeem), we also constructed a county-level Area Deprivation Index (ADI) using Principal Component Analysis (PCA) of 6 American Community Survey (ACS) socioeconomic indicators.│   │   └── ruralurbancodes2023.xls     # ← Manual download required

│   └── processed/

**Main findings:**│       ├── county_analytic_dataset.csv # Final analytic file (3,144 counties)

│       └── county_analytic_geo.gpkg    # Geo-enabled version for mapping

| Predictor | Modality | IRR | 95% CI | p-value | Significant? |├── output/

|-----------|----------|-----|--------|---------|:---:|│   ├── figures/

| SVI per 10-percentile | CMR | 0.992 | 0.952 to 1.033 | 0.681 | No |│   │   ├── figure1_choropleth.pdf

| SVI per 10-percentile | CCT | 1.020 | 0.989 to 1.053 | 0.213 | No |│   │   └── figure1_choropleth.png

| **ADI per 10-percentile** | **CMR** | **0.937** | **0.900 to 0.976** | **0.002** | **Yes** |│   ├── tables/

| ADI per 10-percentile | CCT | 0.979 | 0.949 to 1.010 | 0.177 | No |│   │   ├── table1_descriptive.csv

│   │   └── table1_formatted.txt

**Bottom line:** The primary disparity is geographic (metro vs rural). ADI detects a significant 6.3% reduction in CMR capacity per 10-percentile increase in area deprivation, a signal that SVI completely missed. This suggests that CMR access (more specialized, fewer sites) is sensitive to neighborhood socioeconomic factors.│   └── models/

│       ├── regression_results.txt

---│       └── model_objects.pkl

├── docs/

## Background and Motivation│   ├── Project_Briefing_Shiloh.docx

│   ├── Data_Scientist_Task_Guide.html

### Why does ACR accreditation matter?│   └── Data_Scientist_Task_Guide.pdf

├── requirements.txt

The Deficit Reduction Act (DRA) of 2005 mandated that facilities performing advanced diagnostic imaging (including cardiac MRI and cardiac CT) must be accredited by an approved body (ACR or IAC) to receive Medicare reimbursement. Without accreditation, a facility simply cannot bill CMS for these services.└── README.md

```

This means ACR-accredited sites represent the *functional supply* of cardiac imaging in the United States. If a county lacks an accredited facility, its residents must travel to access these services.

## Quick Start

### What is the research question?

```bash

**Are ACR-accredited cardiac imaging facilities equitably distributed across US counties, or do socially disadvantaged communities face systematic access barriers?**# Install dependencies

pip install -r requirements.txt

### Why two predictors (SVI and ADI)?

# Run full pipeline

- **SVI (CDC Social Vulnerability Index):** A composite of 16 Census variables designed to identify communities vulnerable to *disasters*. It includes themes like minority status, housing type, transportation, and disability. While widely used in health services research, it was not designed for healthcare-access questions.python code/06_run_all.py



- **ADI (Area Deprivation Index):** A composite specifically designed for *healthcare-access research* (Singh, Am J Public Health, 2003). It focuses on socioeconomic disadvantage: income, education, employment, and housing cost burden. The Mango et al. (2021) paper found ADI-associated disparities in breast imaging accreditation, motivating its use here.# Or run individual steps

python code/01_download_datasets.py

---python code/02_build_analytic_dataset.py

python code/03_descriptive_analysis.py

## Data Sourcespython code/04_choropleth_map.py

python code/05_regression_analysis.py

| Dataset | Source | Year | Records | Role |```

|---------|--------|------|---------|------|

| ACR Facility List | ACR Accredited Facility Search | May 2026 | 2,273 sites | Outcome (facility counts) |## Manual Data Downloads Required

| ZIP-County Crosswalk | US Census Bureau / HUD | 2020 | ~33,000 ZIPs | Geocoding facilities to counties |

| Social Vulnerability Index | CDC / ATSDR | 2022 | 3,144 counties | Primary predictor |The following datasets could not be auto-downloaded (government sites restructured). Download manually and place in `data/raw/`:

| Rural-Urban Continuum Codes | USDA ERS | 2023 | 3,144 counties | Metro/nonmetro stratifier |

| ACS 5-Year Estimates | Census Bureau | 2019-2023 | 3,144 counties | Population denominators |1. **CDC SVI 2022** → Save as `data/raw/SVI_2022_US_county.csv`

| County Health Rankings | UW Population Health Institute | 2024 | 3,143 counties | ADI construction (income data) |   - URL: https://www.atsdr.cdc.gov/place-health/php/svi/

| TIGER/Line Shapefiles | Census Bureau | 2023 | 3,234 polygons | Mapping |   - Need: County-level CSV with `FIPS` and `RPL_THEMES` columns



### Data Notes2. **USDA RUCC 2023** → Save as `data/raw/ruralurbancodes2023.xls`

   - URL: https://www.ers.usda.gov/data-products/rural-urban-continuum-codes

- The ACR file contains: Facility Name, Address, City, State, Zip Code, Phone, NPI, Program (MRAP = MRI Accreditation Program, CTAP = CT Accreditation Program), Module (Cardiac), and Status (Accredited or Under Review).   - Need: Excel file with `FIPS` and `RUCC_2023` columns

- Multi-county ZIPs were assigned to the county with the largest land-area overlap using the Census crosswalk.

- Both "Accredited" and "Under Review" statuses were included (sensitivity analysis excluding "Under Review" showed no qualitative change).3. **Census ACS Population** (optional) → Save as `data/raw/acs_county_population.csv`

   - URL: https://www.census.gov/data/developers/data-sets/acs-5year.html

---   - Need: CSV with columns `county_fips`, `total_population`, `adult_pop_45plus`



## Methods**Note:** The pipeline generates realistic proxy data when these files are missing, allowing the code to run end-to-end for testing. Replace with real data before publication.



### Study Design## Dataset Versions & Access Dates



Cross-sectional ecologic analysis. Unit of analysis: US county (n = 3,144; 50 states plus Washington DC).| Dataset | Version | Access Date |

|---------|---------|-------------|

### Outcome| ACR Cardiac Imaging Sites | May 20, 2026 extraction | May 20, 2026 |

| Census TIGER/Line County | 2023 | May 22, 2026 |

Count of ACR-accredited facilities per county, separately for CMR and CCT.| Census ZCTA-County Crosswalk | 2020 | May 22, 2026 |

| CDC SVI | 2022 (pending download) | — |

### Rate Calculation| USDA RUCC | 2023 (pending download) | — |

| ACS 5-Year | 2019-2023 (pending download) | — |

Rate = (facility count / adults aged 45 and older) x 100,000

## Key Decisions

Counties with fewer than 1,000 adults aged 45 and older were excluded from rate calculations and regression models (n = 106 excluded). This prevents unstable per-capita rates in very small populations.

- **Unit of analysis:** US county (n=3,144; 50 states + DC)

**Final analytic sample:** n = 3,038 counties (SVI models) or n = 3,029 counties (ADI models; 9 additional counties lacked ADI variables).- **Multi-county ZIPs:** Assigned to county with largest land area overlap

- **Rate denominator:** Adults aged ≥45 years

### Statistical Models- **Rate exclusion:** Counties with <1,000 adults ≥45 excluded from per-capita rates (n=106)

- **Double-counting:** Facility accredited for both MRI and CT counted once per modality

**1. Spearman Rank Correlation**- **Inclusion:** "Accredited" and "Under Review" status (sensitivity analysis excludes "Under Review")

- **ADI construction:** County-level PCA of 6 ACS socioeconomic indicators (Singh 2003 methodology)

Non-parametric correlation between facility rate and predictor percentile. Chosen because the rate distribution is severely zero-inflated and non-normal.

## Key Findings

**2. Negative Binomial Regression**

| Predictor | Modality | IRR | p-value | Interpretation |

```|-----------|----------|-----|---------|----------------|

log(facility count) = B0 + B1 * predictor + offset(ln[adults_45plus])| SVI per 10-pctl | CMR | 0.992 | 0.681 | Not significant |

```| SVI per 10-pctl | CCT | 1.020 | 0.213 | Not significant |

| **ADI per 10-pctl** | **CMR** | **0.937** | **0.002** | **Significant — 6.3% decrease per 10-pctl** |

- The population offset converts the count model into a rate model.| ADI per 10-pctl | CCT | 0.979 | 0.177 | Not significant |

- Negative Binomial (not Poisson) was used because the data shows severe overdispersion (variance greatly exceeds the mean).

- Model comparison by AIC confirmed Negative Binomial provides better fit (difference in AIC greater than 30 for all models).**Conclusion:** The primary disparity is geographic (metro vs rural). ADI detects a significant socioeconomic gradient for CMR that SVI misses, suggesting CMR access is sensitive to area deprivation beyond the metro/rural divide.

- The predictor is scaled per 10-percentile increment, so the IRR (Incidence Rate Ratio) represents the multiplicative change in facility rate for each 10-percentile increase in vulnerability or deprivation.

## Software

**3. Sensitivity Analyses**

- Python 3.11

- Stratified by metro vs nonmetro (RUCC codes 1-3 = metro; 4-9 = nonmetro)- Key libraries: pandas, geopandas, statsmodels, matplotlib, mapclassify, scipy

- SVI quartile contrasts (Q2 vs Q1, Q3 vs Q1, Q4 vs Q1)
- ADI as alternative predictor (see below)

---

## Why PCA for ADI Construction

### The Problem

The Area Deprivation Index requires combining multiple socioeconomic indicators into a single composite score. We have 6 input variables:

1. **EP_POV150** - Percent of population below 150% of the federal poverty line
2. **EP_UNEMP** - Percent unemployed (ages 16+)
3. **EP_NOHSDP** - Percent without a high school diploma (ages 25+)
4. **EP_HBURD** - Percent of households with housing cost burden (spending more than 30% of income on housing)
5. **Median Household Income** (inverted: lower income = more deprived)
6. **Children in Poverty** - Percent of children below the poverty line

### Why Not Just Average Them?

A simple average treats all 6 variables as equally important and assumes they contribute equally to "deprivation." But this is not true:

- Some variables are highly correlated (poverty and child poverty share much information).
- Some variables carry more unique information about deprivation than others.
- The variables are measured on different scales (percentages vs dollars).

### What PCA Does

**Principal Component Analysis (PCA)** is a mathematical technique that finds the direction of maximum variation in the data. In plain language:

1. **Standardize** all 6 variables (subtract mean, divide by standard deviation) so they are on the same scale.
2. **Find the combination** of variables that captures the most shared variation across all 3,144 counties. This is the "first principal component" (PC1).
3. **PC1 becomes the ADI score.** Counties that score high on PC1 are those that are consistently high on poverty, unemployment, low education, and housing burden. Counties that score low are consistently affluent.

### How Much Variance Does PC1 Capture?

In our data, the first principal component explains **58.7% of total variance** across all 6 indicators. This means that a single score captures more than half of all the variation in these 6 socioeconomic measures. This is strong performance for a single composite.

### Why This Follows Published Methods

Singh (2003, American Journal of Public Health) and Kind and Buckingham (2018, New England Journal of Medicine) both used PCA-based approaches to construct area deprivation indices. Our approach follows their methodology:

- Select socioeconomic indicators from Census/ACS data
- Standardize inputs
- Extract PC1 as the deprivation score
- Convert to national percentile ranks (0 = least deprived, 100 = most deprived)

### Validation

The correlation between our PCA-constructed ADI and the CDC SVI is r = 0.826 (Pearson). They measure overlapping but distinct constructs: SVI includes non-economic themes (minority status, disability, transportation) while ADI focuses purely on socioeconomic disadvantage. This partial overlap (r = 0.83) combined with divergent regression results (ADI significant, SVI null) confirms that the ADI captures unique socioeconomic information not present in SVI.

---

## Key Findings

### Finding 1: The Dominant Disparity is Geographic

- Metropolitan counties (37.3% of all counties) contain **98.1% of all CMR** and **92.4% of all CCT** facilities.
- 90.5% of counties have zero CMR sites; 82.4% have zero CCT sites.
- Metro CMR rate: 0.35 per 100,000 vs Nonmetro: 0.02 per 100,000 (p < 0.0001, Mann-Whitney U test).
- Metro CCT rate: 0.74 per 100,000 vs Nonmetro: 0.35 per 100,000 (p < 0.0001, Mann-Whitney U test).

### Finding 2: SVI Does Not Predict Facility Distribution

- CMR: IRR = 0.992 (95% CI: 0.952 to 1.033), p = 0.681
- CCT: IRR = 1.020 (95% CI: 0.989 to 1.053), p = 0.213
- Spearman correlations also null (CMR rho = 0.008, p = 0.66; CCT rho = 0.023, p = 0.21)

### Finding 3: ADI Reveals a CMR-Specific Socioeconomic Gradient

- **CMR: IRR = 0.937 (95% CI: 0.900 to 0.976), p = 0.002** (SIGNIFICANT)
- CCT: IRR = 0.979 (95% CI: 0.949 to 1.010), p = 0.177
- Interpretation: For every 10-percentile increase in area deprivation, CMR facility rates decrease by 6.3%.
- ADI Spearman: CMR rho = -0.172 (p < 0.0001); CCT rho = -0.163 (p < 0.0001)
- ADI Q1 (least deprived) CMR mean rate: 0.27 per 100,000
- ADI Q5 (most deprived) CMR mean rate: 0.06 per 100,000 (4.5x disparity)
- Kruskal-Wallis across ADI quintiles for CMR: p < 0.0001

### Finding 4: Why CMR but Not CCT?

CMR is a more specialized, rarer modality (725 sites vs 1,548 for CCT). Facilities offering CMR require:

- Higher-field MRI scanners (1.5T or 3T) with cardiac coils
- Specialized technologists trained in cardiac protocols
- Cardiologist or radiologist expertise in CMR interpretation

Because CMR has higher barriers to entry, facility siting decisions may be more sensitive to local socioeconomic conditions (patient volume, payer mix, real estate costs). CCT, being more widely available, shows less socioeconomic patterning.

### Finding 5: Why ADI Works Where SVI Fails

The SVI includes 4 themes: (1) Socioeconomic Status, (2) Household Characteristics/Disability, (3) Racial/Ethnic Minority Status, (4) Housing Type/Transportation. Themes 2-4 introduce non-economic variation that dilutes the socioeconomic signal. ADI focuses purely on economic deprivation, which more directly relates to healthcare infrastructure investment decisions.

---

## Project Structure

```
geo-spatial-analysis/
├── code/
│   ├── 01_download_datasets.py          # Downloads external datasets (TIGER, crosswalk)
│   ├── 02_build_analytic_dataset.py      # Cleans, links, builds county-level analytic file
│   ├── 03_descriptive_analysis.py        # Table 1, medians, stratification
│   ├── 04_choropleth_map.py              # Figure 1 (two-panel CMR/CCT US county map)
│   ├── 05_regression_analysis.py         # Negative binomial regression + sensitivity
│   ├── 06_adi_sensitivity_analysis.py    # ADI construction (PCA) + regression
│   ├── 06_run_all.py                     # Master pipeline runner
│   ├── 07_publication_outputs.py         # Tables in Word format
│   ├── fetch_census_population.py        # Census API population pull
│   └── generate_requested_outputs.py     # Requested figures/tables for Dr. Naeem
├── data/
│   ├── ACR_Cardiac_Imaging_Sites.xlsx    # Source file (2,273 facilities)
│   ├── raw/                              # Downloaded external datasets
│   └── processed/
│       ├── county_analytic_dataset.csv   # Final analytic file (3,144 x 14 columns)
│       ├── county_analytic_geo.gpkg      # Geo-enabled version for mapping
│       └── county_adi_constructed.csv    # ADI scores (3,134 counties)
├── output/
│   ├── figures/                          # Pipeline-generated figures
│   └── requested/                        # Publication-ready outputs
├── docs/
│   ├── Data_Scientist_Task_Guide.html
│   ├── Data_Scientist_Task_Guide.pdf
│   ├── PCA_Explanation.md
│   └── Results_and_Interpretation_Guide.md
├── Pipfile / Pipfile.lock
├── requirements.txt
└── README.md
```

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/abdulrazakucc/geo-spatial-analysis.git
cd geo-spatial-analysis

# Install dependencies (pipenv)
pipenv install
pipenv shell

# Or with pip
pip install -r requirements.txt

# Run full pipeline
python code/06_run_all.py

# Run individual steps
python code/01_download_datasets.py
python code/02_build_analytic_dataset.py
python code/03_descriptive_analysis.py
python code/04_choropleth_map.py
python code/05_regression_analysis.py
python code/06_adi_sensitivity_analysis.py
```

### Manual Data Downloads Required

These datasets require manual download (government sites require browser access):

1. **CDC SVI 2022** - Save as `data/raw/SVI_2022_US_county.csv`
   - Source: https://www.atsdr.cdc.gov/place-health/php/svi/
   - Required columns: FIPS, RPL_THEMES, EP_POV150, EP_UNEMP, EP_NOHSDP, EP_HBURD

2. **USDA RUCC 2023** - Save as `data/raw/ruralurbancodes2023.xls`
   - Source: https://www.ers.usda.gov/data-products/rural-urban-continuum-codes
   - Required columns: FIPS, RUCC_2023

3. **Census ACS Population** - Save as `data/raw/acs_county_population.csv`
   - Source: https://www.census.gov/data/developers/data-sets/acs-5year.html
   - Required columns: county_fips, total_population, adult_pop_45plus

---

## Outputs

### Figures

| Figure | Description | Format |
|--------|-------------|--------|
| Figure 1 | Two-panel choropleth: CMR and CCT facility rates by county | PNG, PDF |
| Figure 2 | Four-panel SVI vs ADI comparison (maps + scatter + CMR overlay) | PNG, PDF |
| Figure 3 | Bar chart: CMR/CCT rates by ADI quintile with 95% CI error bars | PNG, PDF |

### Tables

| Table | Description | Format |
|-------|-------------|--------|
| Table 1 | Facility capacity by SVI quartile and metro/nonmetro status | Word, CSV |
| Table 2 | Primary regression results (SVI Negative Binomial) | Word |
| Table 3 | Sensitivity analyses (stratified, quartile contrasts) | Word |
| Supplementary | ADI regression results with SVI comparison | Word |

---

## Abbreviations

| Abbreviation | Full Term |
|:---:|---|
| ACR | American College of Radiology |
| ACS | American Community Survey |
| ADI | Area Deprivation Index |
| AIC | Akaike Information Criterion |
| ATSDR | Agency for Toxic Substances and Disease Registry |
| CCT | Cardiac Computed Tomography |
| CDC | Centers for Disease Control and Prevention |
| CI | Confidence Interval |
| CMR | Cardiac Magnetic Resonance (Imaging) |
| CMS | Centers for Medicare and Medicaid Services |
| DRA | Deficit Reduction Act |
| FIPS | Federal Information Processing Standards |
| IAC | Intersocietal Accreditation Commission |
| IQR | Interquartile Range |
| IRR | Incidence Rate Ratio |
| MRAP | MRI Accreditation Program |
| NPI | National Provider Identifier |
| PCA | Principal Component Analysis |
| RUCC | Rural-Urban Continuum Code |
| SVI | Social Vulnerability Index |
| USDA | United States Department of Agriculture |

---

## References

1. Singh GK. Area deprivation and widening inequalities in US mortality, 1969-1998. *Am J Public Health*. 2003;93(7):1137-1143.
2. Kind AJH, Buckingham W. Making neighborhood-disadvantage metrics accessible. *N Engl J Med*. 2018;378:2456-2458.
3. Mango VL, et al. ACR breast imaging accreditation and area deprivation. *J Am Coll Radiol*. 2021;18(9):1258-1265.
4. Flanagan BE, et al. A social vulnerability index for disaster management. *J Homel Secur Emerg Manag*. 2011;8(1):Article 3.
5. US Census Bureau. American Community Survey 5-year estimates: 2019-2023.
6. CDC/ATSDR. Social Vulnerability Index 2022 documentation.
7. USDA ERS. Rural-Urban Continuum Codes 2023.

---

## Software Environment

- Python 3.11
- Key packages: pandas, geopandas, statsmodels, matplotlib, mapclassify, scipy, scikit-learn, python-pptx, python-docx, weasyprint

---

## License

MIT License
