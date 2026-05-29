# Geographic Disparities in ACR-Accredited Cardiac Imaging Capacity

A cross-sectional ecologic analysis of 3,144 US counties examining whether social vulnerability and area deprivation predict access to accredited cardiac imaging facilities.

**Authors:** Abdul Razak, MD and Naeem Ahmad, MD
**Target Journal:** JACC: Advances (Special Focus Issue on Health Equity in Cardiology)
**Last Updated:** May 28, 2026

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Background and Motivation](#background-and-motivation)
3. [Data Sources](#data-sources)
4. [Methods](#methods)
5. [Key Findings](#key-findings)
6. [Why PCA for ADI Construction](#why-pca-for-adi-construction)
7. [Project Structure](#project-structure)
8. [Quick Start](#quick-start)
9. [Outputs](#outputs)
10. [Abbreviations](#abbreviations)
11. [References](#references)

---

## Executive Summary

We analyzed the geographic distribution of 687 ACR-accredited Cardiac MRI (CMR) and 1,481 Cardiac CT (CCT) facilities across all 3,144 US counties. Our primary predictor was the CDC Social Vulnerability Index (SVI). As a sensitivity analysis, we constructed a county-level Area Deprivation Index (ADI) using Principal Component Analysis (PCA) of 6 American Community Survey (ACS) socioeconomic indicators.

**Main findings:**

| Predictor | Modality | IRR | 95% CI | p-value | Significant? |
|-----------|----------|-----|--------|---------|:---:|
| SVI per 10-percentile | CMR | 0.992 | 0.952 - 1.033 | 0.681 | No |
| SVI per 10-percentile | CCT | 1.020 | 0.989 - 1.053 | 0.213 | No |
| **ADI per 10-percentile** | **CMR** | **0.937** | **0.900 - 0.976** | **0.002** | **Yes** |
| ADI per 10-percentile | CCT | 0.979 | 0.949 - 1.010 | 0.177 | No |

**Bottom line:** The primary disparity is geographic (metro vs rural). ADI detects a significant 6.3% reduction in CMR capacity per 10-percentile increase in area deprivation, a signal that SVI missed entirely. This suggests that CMR access (more specialized, fewer sites) is sensitive to neighborhood socioeconomic factors.

---

## Background and Motivation

### Why does ACR accreditation matter?

The Deficit Reduction Act (DRA) of 2005 mandated that facilities performing advanced diagnostic imaging (including cardiac MRI and cardiac CT) must be accredited by an approved body (ACR or IAC) to receive Medicare reimbursement. Without accreditation, a facility cannot bill CMS for these services.

ACR-accredited sites represent the functional supply of cardiac imaging in the United States. If a county lacks an accredited facility, its residents must travel to access these services.

### What is the research question?

Are ACR-accredited cardiac imaging facilities equitably distributed across US counties, or do socially disadvantaged communities face systematic access barriers?

### Why two predictors (SVI and ADI)?

- **SVI (CDC Social Vulnerability Index):** A composite of 16 Census variables designed to identify communities vulnerable to disasters. It includes themes like minority status, housing type, transportation, and disability. Widely used in health services research but not designed for healthcare-access questions.

- **ADI (Area Deprivation Index):** A composite specifically designed for healthcare-access research (Singh, Am J Public Health, 2003). It focuses on socioeconomic disadvantage: income, education, employment, and housing cost burden. We constructed our own county-level ADI via PCA because no pre-built county-level ADI exists (the University of Wisconsin Neighborhood Atlas provides ADI only at the block group/ZIP level). This follows the same validated methodology used by Singh (2003), Kind/Buckingham (2018, NEJM), and Mango et al. (JACR 2023).

---

## Data Sources

| Dataset | Source | Year | Records | Role |
|---------|--------|------|---------|------|
| ACR Facility List | ACR Accredited Facility Search | May 2026 | 2,273 sites | Outcome (facility counts) |
| ZIP-County Crosswalk | US Census Bureau / HUD | 2020 | ~33,000 ZIPs | Geocoding facilities to counties |
| Social Vulnerability Index | CDC / ATSDR | 2022 | 3,144 counties | Primary predictor |
| Rural-Urban Continuum Codes | USDA ERS | 2023 | 3,144 counties | Metro/nonmetro stratifier |
| ACS 5-Year Estimates | Census Bureau | 2019-2023 | 3,144 counties | Population denominators |
| County Health Rankings | UW Population Health Institute | 2024 | 3,143 counties | ADI construction |
| TIGER/Line Shapefiles | Census Bureau | 2023 | 3,234 polygons | Mapping |

### Data Notes

- The ACR source file contains 2,273 facility records. After geocoding to counties (via ZIP-county crosswalk), 687 CMR and 1,481 CCT facilities were successfully mapped to the 3,144 county analytic framework.
- Multi-county ZIPs were assigned to the county with the largest land-area overlap.
- Both "Accredited" and "Under Review" statuses were included.

---

## Methods

### Study Design

Cross-sectional ecologic analysis. Unit of analysis: US county (n = 3,144; 50 states plus Washington DC).

### Outcome

Count of ACR-accredited facilities per county, separately for CMR and CCT.

### Rate Calculation

Rate = (facility count / adults aged 45 and older) x 100,000

Counties with fewer than 1,000 adults aged 45 and older were excluded from rate calculations and regression models (n = 106 excluded).

**Final analytic sample:** n = 3,038 counties (SVI models) or n = 3,029 counties (ADI models; 9 additional counties lacked ADI variables).

### Statistical Models

**1. Spearman Rank Correlation** - Non-parametric correlation between facility rate and predictor percentile.

**2. Negative Binomial Regression**

    log(facility count) = B0 + B1 * predictor + offset(ln[adults_45plus])

- Population offset converts the count model into a rate model.
- Negative Binomial (not Poisson) used due to severe overdispersion.
- Predictor scaled per 10-percentile increment; IRR represents multiplicative change per 10-percentile increase.

**3. Sensitivity Analyses**

- Stratified by metro vs nonmetro (RUCC codes 1-3 = metro; 4-9 = nonmetro)
- SVI quartile contrasts (Q2 vs Q1, Q3 vs Q1, Q4 vs Q1)
- ADI as alternative predictor

---

## Key Findings

### Finding 1: The Dominant Disparity is Geographic

- Metropolitan counties (1,186 counties, 37.7%) contain 98.1% of all CMR and 92.4% of all CCT facilities.
- 90.8% of counties have zero CMR sites; 83.1% have zero CCT sites.
- Metro CMR rate: 0.35 per 100,000 vs Nonmetro: 0.02 per 100,000 (p < 0.0001).
- Metro CCT rate: 0.73 per 100,000 vs Nonmetro: 0.35 per 100,000 (p < 0.0001).

### Finding 2: SVI Does Not Predict Facility Distribution

- CMR: IRR = 0.992 (95% CI: 0.952 - 1.033), p = 0.681
- CCT: IRR = 1.020 (95% CI: 0.989 - 1.053), p = 0.213
- Spearman: CMR rho = 0.008, p = 0.66; CCT rho = 0.020, p = 0.27

### Finding 3: ADI Reveals a CMR-Specific Socioeconomic Gradient

- **CMR: IRR = 0.937 (95% CI: 0.900 - 0.976), p = 0.002** (SIGNIFICANT)
- CCT: IRR = 0.979 (95% CI: 0.949 - 1.010), p = 0.177
- ADI Spearman: CMR rho = -0.172 (p < 0.0001); CCT rho = -0.163 (p < 0.0001)
- ADI Q1 (least deprived) CMR mean rate: 0.27 per 100,000
- ADI Q5 (most deprived) CMR mean rate: 0.06 per 100,000 (4.4x disparity)
- AIC comparison: ADI CMR model AIC = 1,831 vs SVI CMR model AIC = 1,851 (ADI fits better)

### Finding 4: Why CMR but Not CCT?

CMR is more specialized and rarer (687 sites vs 1,481 for CCT). Facilities offering CMR require higher-field MRI scanners with cardiac coils, specialized technologists, and expert interpretation. Because CMR has higher barriers to entry, facility siting decisions may be more sensitive to local socioeconomic conditions.

### Finding 5: Why ADI Works Where SVI Fails

The SVI includes 4 themes: (1) Socioeconomic Status, (2) Household Characteristics/Disability, (3) Racial/Ethnic Minority Status, (4) Housing Type/Transportation. Themes 2-4 introduce non-economic variation that dilutes the socioeconomic signal. ADI focuses purely on economic deprivation, which more directly relates to healthcare infrastructure investment decisions.

The correlation between SVI and ADI is Pearson r = 0.821 - strong but not identical. They measure overlapping but distinct constructs.

---

## Why PCA for ADI Construction

The Area Deprivation Index combines 6 socioeconomic indicators into one composite score using Principal Component Analysis (PCA):

1. Percent below 150% of the federal poverty line
2. Percent unemployed (ages 16+)
3. Percent without a high school diploma (ages 25+)
4. Percent with housing cost burden (more than 30% of income on housing)
5. Median household income (inverted: lower income = more deprived)
6. Percent of children in poverty

**Why PCA instead of a simple average?**

- Variables are on different scales (percentages vs dollars)
- Some are highly correlated (poverty and child poverty share information)
- PCA finds the single weighted combination that captures maximum shared variance
- The first principal component explains 58.7% of total variance across all 6 indicators
- This follows the validated methodology of Singh (2003) and Kind/Buckingham (2018)

See `docs/PCA_Explanation.md` for a detailed plain-language explanation.

---

## Project Structure

    geo-spatial-analysis/
    ├── code/
    │   ├── 01_download_datasets.py
    │   ├── 02_build_analytic_dataset.py
    │   ├── 03_descriptive_analysis.py
    │   ├── 04_choropleth_map.py
    │   ├── 05_regression_analysis.py
    │   ├── 06_adi_sensitivity_analysis.py
    │   ├── 06_run_all.py
    │   ├── 07_publication_outputs.py
    │   ├── 08_svi_adi_comparison_maps.py
    │   ├── fetch_census_population.py
    │   └── generate_requested_outputs.py
    ├── data/
    │   ├── ACR_Cardiac_Imaging_Sites.xlsx
    │   ├── raw/
    │   └── processed/
    │       ├── county_analytic_dataset.csv
    │       ├── county_analytic_geo.gpkg
    │       └── county_adi_constructed.csv
    ├── output/
    │   ├── figures/
    │   ├── tables/
    │   ├── documents/
    │   ├── supplementary_data/
    │   └── requested/
    ├── docs/
    │   ├── Data_Scientist_Task_Guide.html
    │   ├── Data_Scientist_Task_Guide.pdf
    │   ├── Results_and_Interpretation_Guide.md
    │   └── PCA_Explanation.md
    ├── Pipfile / Pipfile.lock
    ├── requirements.txt
    └── README.md

---

## Quick Start

    # Clone the repository
    git clone https://github.com/abdulrazakucc/geo-spatial-analysis.git
    cd geo-spatial-analysis

    # Install dependencies
    pipenv install
    pipenv shell

    # Or with pip
    pip install -r requirements.txt

    # Run full pipeline
    python code/06_run_all.py

---

## Outputs

### Figures

| Figure | Description |
|--------|-------------|
| Figure 1 | Two-panel choropleth: CMR and CCT facility rates by county |
| Figure 2 | Four-panel SVI vs ADI comparison (maps + scatter + CMR overlay) |
| Figure 3 | Bar chart: CMR/CCT rates by ADI quintile with 95% CI error bars |

### Tables (Word Format)

| Table | Description |
|-------|-------------|
| Table 1 | Facility capacity by SVI quartile and metro/nonmetro status |
| Table 2 | Primary regression results (SVI Negative Binomial) |
| Table 3 | Sensitivity analyses (stratified, Spearman, Mann-Whitney) |
| Table 4 | SVI vs ADI head-to-head comparison |
| Supplementary | ADI regression + quintile stratification |

---

## Abbreviations

| Abbreviation | Full Term |
|:---:|---|
| ACR | American College of Radiology |
| ACS | American Community Survey |
| ADI | Area Deprivation Index |
| AIC | Akaike Information Criterion |
| CCT | Cardiac Computed Tomography |
| CDC | Centers for Disease Control and Prevention |
| CI | Confidence Interval |
| CMR | Cardiac Magnetic Resonance Imaging |
| CMS | Centers for Medicare and Medicaid Services |
| DRA | Deficit Reduction Act |
| FIPS | Federal Information Processing Standards |
| IRR | Incidence Rate Ratio |
| PCA | Principal Component Analysis |
| RUCC | Rural-Urban Continuum Code |
| SVI | Social Vulnerability Index |

---

## References

1. Singh GK. Area deprivation and widening inequalities in US mortality, 1969-1998. Am J Public Health. 2003;93(7):1137-1143.
2. Kind AJH, Buckingham W. Making neighborhood-disadvantage metrics accessible. N Engl J Med. 2018;378:2456-2458.
3. Mango VL, et al. Impact of high neighborhood socioeconomic deprivation on access to accredited breast imaging screening and diagnostic facilities. J Am Coll Radiol. 2023;20(7):634-639.
4. Flanagan BE, et al. A social vulnerability index for disaster management. J Homel Secur Emerg Manag. 2011;8(1):Article 3.

---

## Software

- Python 3.11
- Key packages: pandas, geopandas, statsmodels, matplotlib, mapclassify, scipy, scikit-learn, python-pptx, python-docx

## License

MIT License
