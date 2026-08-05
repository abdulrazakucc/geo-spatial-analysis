# Geographic Disparities in Accredited Cardiac Imaging Across the United States: Social Vulnerability versus Economic Deprivation

A cross-sectional ecologic analysis of 3,144 US counties examining whether social vulnerability and area deprivation predict access to accredited cardiac imaging facilities.

**Authors:** Muhammad Naeem, MBBS, MD and Abdul Razak, PhD
**Target Journal:** JACR (Journal of the American College of Radiology). Previously submitted to JACC: Advances (rejected).
**Last Updated:** August 4, 2026

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Background and Motivation](#background-and-motivation)
3. [Data Sources](#data-sources)
4. [Methods](#methods)
5. [Key Findings](#key-findings)
6. [Why PCA for EDI Construction](#why-pca-for-edi-construction)
7. [Project Structure](#project-structure)
8. [Quick Start](#quick-start)
9. [Outputs](#outputs)
10. [Abbreviations](#abbreviations)
11. [References](#references)

---

## Executive Summary

We analyzed the geographic distribution of 687 ACR-accredited Cardiac MRI (CMR) and 1,481 Cardiac CT (CCT) facilities across all 3,144 US counties. Our primary predictor was the CDC Social Vulnerability Index (SVI). As a sensitivity analysis, we constructed a county-level **Economic Deprivation Index (EDI)** using Principal Component Analysis (PCA) of 6 American Community Survey (ACS) socioeconomic indicators.

> **Naming note.** This index was called "ADI" in earlier drafts. It was renamed **EDI** because "ADI" collides with the validated Singh / University of Wisconsin Area Deprivation Index, a different instrument that we do not use. Construction is unchanged; only the label.

**Main findings:**

| Predictor | Modality | Model | IRR | 95% CI | p-value | Significant? |
|-----------|----------|-------|-----|--------|---------|:---:|
| SVI per 10-percentile | CMR | unadjusted | 0.9915 | 0.9521 - 1.0325 | 0.6808 | No |
| SVI per 10-percentile | CCT | unadjusted | 1.0203 | 0.9885 - 1.0530 | 0.2130 | No |
| EDI per 10-percentile | CMR | unadjusted | 0.9373 | 0.9000 - 0.9762 | 0.0018 | Yes |
| EDI per 10-percentile | CMR | **adjusted for metro** | **0.9828** | **0.9409 - 1.0265** | **0.4343** | **No** |
| EDI per 10-percentile | CCT | unadjusted | 0.9789 | 0.9490 - 1.0097 | 0.1767 | No |
| EDI per 10-percentile | CCT | adjusted for metro | 1.0074 | 0.9745 - 1.0414 | 0.6633 | No |
| **Metropolitan status** | **CMR** | **adjusted** | **8.2307** | **4.65 - 14.56** | **<0.001** | **Yes** |
| Metropolitan status | CCT | adjusted | 1.9619 | 1.56 - 2.47 | <0.001 | Yes |

**Bottom line:** Accredited cardiac imaging capacity is concentrated in **metropolitan** counties. Metropolitan counties have roughly **8 times** the expected number of accredited CMR facilities. The apparent deprivation gradient (unadjusted EDI-CMR IRR 0.9373, p = 0.0018) **does not survive adjustment for rurality** (IRR 0.9828, p = 0.4343); the same holds using ordinal RUCC (IRR 0.9937, p = 0.78). The EDI itself tracks rurality (Spearman rho 0.28 against RUCC; mean EDI 39.9 in metro vs 56.9 in nonmetro counties), which is why an unadjusted model absorbs the rurality signal.

**The methodological point:** deprivation indices should not be used as proxies for imaging access without adjusting for rurality.

> **History.** An earlier version of this work (submitted to and rejected by *JACC: Advances*) reported the unadjusted EDI-CMR association as the headline finding. A reviewer correctly identified that the models were not adjusted for rurality. The revised analysis, prepared for *JACR*, is the one described above. Two descriptive values in the JACC submission also failed to reconcile with the data and were corrected; see [Data integrity](#data-integrity).

---

## Background and Motivation

### Why does ACR accreditation matter?

The Deficit Reduction Act (DRA) of 2005 mandated that facilities performing advanced diagnostic imaging (including cardiac MRI and cardiac CT) must be accredited by an approved body (ACR or IAC) to receive Medicare reimbursement. Without accreditation, a facility cannot bill CMS for these services.

ACR-accredited sites represent the functional supply of cardiac imaging in the United States. If a county lacks an accredited facility, its residents must travel to access these services.

### What is the research question?

Are ACR-accredited cardiac imaging facilities equitably distributed across US counties, or do socially disadvantaged communities face systematic access barriers?

### Why two predictors (SVI and EDI)?

- **SVI (CDC Social Vulnerability Index):** A composite of 16 Census variables designed to identify communities vulnerable to disasters. It includes themes like minority status, housing type, transportation, and disability. Widely used in health services research but not designed for healthcare-access questions.

- **EDI (Economic Deprivation Index):** A composite specifically designed for healthcare-access research (Singh, Am J Public Health, 2003). It focuses on socioeconomic disadvantage: income, education, employment, and housing cost burden. We constructed our own county-level EDI via PCA because no pre-built county-level index of this construction exists (the University of Wisconsin Neighborhood Atlas provides its ADI only at the block group/ZIP level). This follows the same validated methodology used by Singh (2003), Kind/Buckingham (2018, NEJM), and Mango et al. (JACR 2023).

---

## Data Sources

| Dataset | Source | Year | Records | Role |
|---------|--------|------|---------|------|
| ACR Facility List | ACR Accredited Facility Search | May 2026 | 2,273 sites | Outcome (facility counts) |
| ZIP-County Crosswalk | US Census Bureau / HUD | 2020 | ~33,000 ZIPs | Geocoding facilities to counties |
| Social Vulnerability Index | CDC / ATSDR | 2022 | 3,144 counties | Primary predictor |
| Rural-Urban Continuum Codes | USDA ERS | 2023 | 3,144 counties | Metro/nonmetro stratifier |
| ACS 5-Year Estimates | Census Bureau | 2019-2023 | 3,144 counties | Population denominators |
| County Health Rankings | UW Population Health Institute | 2024 | 3,143 counties | EDI construction |
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

**Final analytic sample:** n = 3,038 counties (SVI models) or n = 3,029 counties (EDI models; 9 additional counties lacked EDI variables).

### Statistical Models

**1. Spearman Rank Correlation** - Non-parametric correlation between facility rate and predictor percentile.

**2. Negative Binomial Regression**

    log(facility count) = B0 + B1 * predictor + offset(ln[adults_45plus])

- Population offset converts the count model into a rate model.
- Negative Binomial (not Poisson) used due to severe overdispersion.
- Predictor scaled per 10-percentile increment; IRR represents multiplicative change per 10-percentile increase.

**3. Rurality Adjustment (added for the JACR revision)**

Every deprivation model is fitted twice, unadjusted and adjusted, because the unadjusted estimate is confounded by rurality:

    log(facility count) = B0 + B1 * predictor + B2 * metro_indicator + offset(ln[adults_45plus])

Rurality is handled three ways so the result cannot be attributed to how rurality was coded:

- binary metropolitan indicator (RUCC 1-3 vs 4-9) — the primary adjustment
- ordinal RUCC code (1-9)
- stratified fits within metro and within nonmetro counties

**4. Other Sensitivity Analyses**

- SVI quartile contrasts (Q2 vs Q1, Q3 vs Q1, Q4 vs Q1)
- EDI as alternative predictor to SVI
- External validation against the Robert Graham Center Social Deprivation Index (SDI), 2015-2019 — a published, peer-reviewed county-level index (`code/09_validated_index_sdi.py`)

---

## Key Findings

### Finding 1: The Dominant Disparity is Geographic

- Metropolitan counties (1,186 counties, 37.72%) contain 98.11% of all CMR and 92.44% of all CCT facilities.
- 90.81% of counties have zero CMR sites; 83.08% have zero CCT sites.
- Metro CMR rate: 0.3480 per 100,000 vs Nonmetro: 0.0236 per 100,000 (p < 0.0001).
- Metro CCT rate: 0.7323 per 100,000 vs Nonmetro: 0.3540 per 100,000 (p < 0.0001).

### Finding 2: SVI Does Not Predict Facility Distribution

- CMR: IRR = 0.9915 (95% CI: 0.9521 - 1.0325), p = 0.6808
- CCT: IRR = 1.0203 (95% CI: 0.9885 - 1.0530), p = 0.2130
- Spearman: CMR rho = 0.0079, p = 0.6646; CCT rho = 0.0201, p = 0.2681

### Finding 3: The EDI Gradient is Real but Unadjusted — and It Is Rurality

The unadjusted EDI-CMR association is significant, and it disappears once rurality is in the model.

| Model | IRR | 95% CI | p-value |
|-------|-----|--------|---------|
| EDI, unadjusted | 0.9373 | 0.9000 - 0.9762 | 0.0018 |
| EDI, adjusted for metropolitan status | 0.9828 | 0.9409 - 1.0265 | 0.4343 |
| EDI, adjusted for ordinal RUCC | 0.9937 | 0.9500 - 1.0396 | 0.7834 |
| EDI, metropolitan counties only | 0.9944 | 0.9510 - 1.0395 | 0.8053 |
| EDI, nonmetropolitan counties only | 0.7265 | 0.5720 - 0.9226 | 0.0086 |
| **Metropolitan status (adjusted model)** | **8.2307** | **4.652 - 14.561** | **<0.0001** |

Supporting descriptives (all unadjusted, and therefore confounded by rurality):

- EDI Spearman: CMR rho = -0.1715; CCT rho = -0.1632
- EDI Q1 (least deprived) CMR mean rate 0.2715 vs Q5 (most deprived) 0.0622 per 100,000 — a 4.37x gradient
- Mean EDI, counties with no accredited facility vs at least one: **52.9 vs 39.4** (rate-eligible counties)

> **Caveat on the nonmetropolitan stratum.** The significant within-nonmetro estimate (IRR 0.7265) rests on just **13 CMR facilities across 13 of 1,856 nonmetropolitan counties**. It is significant under both negative binomial and Poisson families, but with 13 events it is unstable and should be treated as exploratory, not as evidence of an independent deprivation gradient.

### Finding 4: Why the Unadjusted Signal Appears

The EDI tracks rurality: Spearman rho = 0.28 against RUCC, with mean EDI 39.9 in metropolitan counties versus 56.9 in nonmetropolitan counties — a 17-point gap. Because accredited capacity is concentrated in metropolitan counties, an unadjusted deprivation model absorbs that rurality signal and reports it as deprivation.

An external check confirms this. The validated Robert Graham Center **Social Deprivation Index (SDI)**, which tracks rurality far more weakly (rho = 0.07, gap 7.1 points), shows **no** unadjusted CMR association at all (IRR 1.0064, p = 0.746) — while reproducing the metropolitan effect almost exactly (IRR 8.66). Whether an unadjusted deprivation association appears depends on which index you pick; the metropolitan finding does not. See `code/09_validated_index_sdi.py`.

### Finding 5: SVI vs EDI

The SVI includes 4 themes: (1) Socioeconomic Status, (2) Household Characteristics/Disability, (3) Racial/Ethnic Minority Status, (4) Housing Type/Transportation. Themes 2-4 introduce non-economic variation. The EDI focuses purely on economic deprivation. The correlation between SVI and EDI is Pearson r = 0.8209 — strong but not identical.

Neither index predicts accredited capacity once rurality is modelled. The practical implication is that a deprivation or vulnerability index is not a substitute for a rurality measure in imaging-access research.

---

## Data integrity

Two descriptive values in the rejected *JACC: Advances* submission did not reconcile with the committed data. Both were traced, corrected, and the rest of Table 1 was re-verified against the dataset.

| Value | Reported in JACC | Correct |
|-------|------------------|---------|
| Counties with neither modality | 1,974 (62.3%) | **2,583 (82.16%)** |
| Mean deprivation, no-facility vs facility counties | 58.2 vs 41.7 | **52.9 vs 39.4** |

**Provenance.** Both values were transcribed from `docs/Results_and_Interpretation_Guide.md`, a hand-maintained narrative document that no script generates. In that file the "combined imaging deserts" row (line 62) has read `1,974 counties (62.8%)` unchanged since the file was created, while the nonmetropolitan-county row directly beneath it was corrected three times as the data were refined: 1,971 (62.7%) → 1,958 (62.3%) → 1,958 (62.28%). The manuscript's "1,974 (62.3%)" pairs the stale count from the desert row with the refreshed percentage from the rurality row below it. The figure was never a count of facility-free counties; it was a rural-county count.

The `58.2 vs 41.7` pair is in the same document (line 309) and does not correspond to any grouping of the current data. The closest structural analogue is the metro/nonmetro contrast (39.9 vs 56.1), consistent with the same rurality-for-facility substitution, but it is not an exact match and the deprivation index has only one version in the repository's history, so the original computation cannot be reconstructed.

Neither value entered any model. All regression coefficients reproduce exactly.

There is an irony worth noting: the number that broke Table 1 was a rurality statistic wearing a deprivation label — the same confound the reviewer identified in the models.

---

## Why PCA for EDI Construction

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
    │   ├── 06_edi_sensitivity_analysis.py
    │   ├── 06_run_all.py
    │   ├── 07_publication_outputs.py
    │   ├── 08_svi_edi_comparison_maps.py
    │   ├── fetch_census_population.py
    │   └── generate_requested_outputs.py
    ├── data/
    │   ├── ACR_Cardiac_Imaging_Sites.xlsx
    │   ├── raw/
    │   └── processed/
    │       ├── county_analytic_dataset.csv
    │       ├── county_analytic_geo.gpkg
    │       └── county_edi_constructed.csv
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

    # Run the core pipeline (steps 01-05, including the rurality-adjusted models)
    python code/06_run_all.py

    # Supplementary and publication outputs (run after the core pipeline)
    python code/06_edi_sensitivity_analysis.py   # EDI construction + unadjusted/adjusted models
    python code/07_publication_outputs.py        # journal figures, Word tables, PPTX, PDF
    python code/08_svi_edi_comparison_maps.py    # Figures 2 and 3
    python code/09_validated_index_sdi.py        # external validation vs Graham Center SDI
    python code/10_jacr_forest_plots.py          # Figure 1B and Figure S
    python code/11_edi_tables_and_stats.py       # supplementary Word tables + statistics JSON

---

## Outputs

### Figures

| Figure | Description |
|--------|-------------|
| Figure 1 | Two-panel choropleth: CMR and CCT facility rates by county |
| Figure 1B | Forest plot: EDI unadjusted vs adjusted for metropolitan status (`output/jacr_revision/`) |
| Figure 2 | Four-panel SVI vs EDI comparison (maps + scatter + CMR overlay) |
| Figure 3 | Bar chart: CMR/CCT rates by EDI quintile with 95% CI error bars |
| Figure S | External validation: our EDI vs Graham Center SDI (`output/jacr_revision/`) |

### Tables (Word Format)

| Table | Description |
|-------|-------------|
| Table 1 | Facility capacity by SVI quartile and metro/nonmetro status |
| Table 2 | Primary regression results (SVI Negative Binomial) |
| Table 3 | Sensitivity analyses (stratified, Spearman, Mann-Whitney) |
| Table 4 | SVI vs EDI head-to-head comparison |
| Supplementary | EDI regression + quintile stratification |

---

## Abbreviations

| Abbreviation | Full Term |
|:---:|---|
| ACR | American College of Radiology |
| ACS | American Community Survey |
| EDI | Economic Deprivation Index (this study; formerly labelled ADI) |
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
