# Results and Interpretation Guide

## Geographic Disparities in ACR-Accredited Cardiac Imaging Capacity Across US Counties

**Document Purpose:** This guide provides a detailed explanation of all results, statistical findings, and their clinical and policy implications. It is intended for collaborators, reviewers, and anyone interested in understanding the analysis and its conclusions.

**Last Updated:** May 28, 2026

---

## Table of Contents

1. [Overview of the Analysis](#1-overview-of-the-analysis)
2. [Descriptive Results](#2-descriptive-results)
3. [Primary Analysis: SVI Regression](#3-primary-analysis-svi-regression)
4. [Sensitivity Analysis: ADI Regression](#4-sensitivity-analysis-adi-regression)
5. [SVI vs ADI Comparison](#5-svi-vs-adi-comparison)
6. [Stratified and Subgroup Analyses](#6-stratified-and-subgroup-analyses)
7. [Interpreting the Figures](#7-interpreting-the-figures)
8. [Frequently Asked Questions](#8-frequently-asked-questions)
9. [Clinical and Policy Implications](#9-clinical-and-policy-implications)
10. [Limitations](#10-limitations)
11. [Summary of All Statistical Tests](#11-summary-of-all-statistical-tests)

---

## 1. Overview of the Analysis

### What We Did

We examined whether the geographic distribution of ACR-accredited cardiac imaging facilities (Cardiac MRI and Cardiac CT) across 3,144 US counties is associated with measures of social disadvantage.

### Why It Matters

The Deficit Reduction Act (DRA) of 2005 requires facilities to hold ACR or IAC accreditation to bill Medicare for advanced imaging. This means accredited facilities represent the *functional supply* of cardiac imaging. Counties without an accredited facility effectively lack access to these services for their Medicare population.

### Two Predictors Tested

| Predictor | What It Measures | Designed For | Source |
|-----------|-----------------|--------------|--------|
| SVI (Social Vulnerability Index) | 16-variable composite including poverty, minority status, disability, housing type, transportation | Disaster preparedness | CDC/ATSDR 2022 |
| ADI (Area Deprivation Index) | 6-variable composite of income, poverty, unemployment, education, housing cost | Healthcare access research | Constructed via PCA (Singh 2003 methodology) |

### Analytic Sample

- **Total counties:** 3,144 (all US counties, 50 states plus DC)
- **Excluded from regressions:** 106 counties with fewer than 1,000 adults aged 45 and older (prevents unstable rates)
- **Final analytic sample (SVI models):** 3,038 counties
- **Final analytic sample (ADI models):** 3,029 counties (9 additional lacked ADI variables)

---

## 2. Descriptive Results

### Facility Distribution

| Statistic | CMR (Cardiac MRI) | CCT (Cardiac CT) |
|-----------|:------------------:|:------------------:|
| Total accredited facilities | 725 | 1,548 |
| Counties with at least one facility | 299 (9.5%) | 553 (17.6%) |
| Counties with zero facilities | 2,845 (90.5%) | 2,591 (82.4%) |
| Combined imaging deserts (zero of either) | 1,974 counties (62.8%) | -- |

### The Metro-Rural Divide

| Metric | Metropolitan | Nonmetropolitan |
|--------|:---:|:---:|
| Number of counties | 1,173 (37.3%) | 1,971 (62.7%) |
| Share of CMR facilities | 98.1% | 1.9% |
| Share of CCT facilities | 92.4% | 7.6% |
| Mean CMR rate (per 100,000 adults 45+) | 0.35 | 0.02 |
| Mean CCT rate (per 100,000 adults 45+) | 0.74 | 0.35 |
| Mann-Whitney U test (metro vs nonmetro) | p < 0.0001 | p < 0.0001 |

**Interpretation:** The overwhelming majority of cardiac imaging capacity is concentrated in metropolitan counties. Nearly all nonmetropolitan counties (which house 62.7% of US counties and millions of residents) have zero or near-zero access to accredited cardiac MRI.

### Zero-Inflation Explanation

Because 90.5% of counties have zero CMR facilities and 82.4% have zero CCT, the median facility count and median per-capita rate are both **zero**. This is not an error. It reflects the extreme concentration of specialized imaging in a small number of counties. The mean (average) is more informative for understanding the overall landscape, while the regression models account for the zero-inflation through the Negative Binomial distributional assumption.

---

## 3. Primary Analysis: SVI Regression

### Model Specification

```
log(facility_count) = B0 + B1 * (SVI_percentile / 10) + offset(ln[adults_45plus])
Family: Negative Binomial (accounts for overdispersion)
```

The offset converts the count model to a rate model. The predictor is divided by 10 so the IRR (Incidence Rate Ratio) represents the effect per 10-percentile increase in SVI.

### Results

| Modality | IRR | 95% CI | p-value | Interpretation |
|----------|:---:|:------:|:-------:|----------------|
| CMR | 0.992 | 0.952 to 1.033 | 0.681 | No association |
| CCT | 1.020 | 0.989 to 1.053 | 0.213 | No association |

### Spearman Rank Correlations (Non-parametric)

| Modality | rho | p-value |
|----------|:---:|:-------:|
| CMR rate vs SVI | 0.008 | 0.66 |
| CCT rate vs SVI | 0.023 | 0.21 |

### What This Means

Social vulnerability (as measured by the CDC SVI) does **not** predict where cardiac imaging facilities are located. There is no statistically significant relationship between a county's SVI percentile and its cardiac imaging capacity, for either CMR or CCT. The point estimates are very close to 1.0 (the null value for an IRR), and the confidence intervals comfortably include 1.0.

---

## 4. Sensitivity Analysis: ADI Regression

### Why ADI?

The SVI was designed for disaster preparedness, not healthcare access. It includes themes (minority status, disability, vehicle access) that may not directly relate to healthcare infrastructure investment. The Area Deprivation Index (ADI), developed by Singh (2003) and updated by Kind and Buckingham (2018, NEJM), was specifically designed for healthcare-access research. The Mango et al. (2021) paper demonstrated ADI-associated disparities in breast imaging accreditation, motivating its application to cardiac imaging.

### ADI Construction Method

We constructed a county-level ADI via Principal Component Analysis (PCA) of 6 socioeconomic indicators from the American Community Survey and County Health Rankings:

1. Percent below 150% of the federal poverty line (EP_POV150)
2. Percent unemployed, ages 16+ (EP_UNEMP)
3. Percent without a high school diploma, ages 25+ (EP_NOHSDP)
4. Percent with housing cost burden, more than 30% of income on housing (EP_HBURD)
5. Median household income (inverted so higher = more deprived)
6. Percent of children in poverty

The first principal component explains **58.7% of total variance** across these 6 indicators. Scores were converted to national percentile ranks (0 = least deprived, 100 = most deprived).

### Results

| Modality | IRR | 95% CI | p-value | Interpretation |
|----------|:---:|:------:|:-------:|----------------|
| **CMR** | **0.937** | **0.900 to 0.976** | **0.002** | **Significant: 6.3% decrease per 10-pctl** |
| CCT | 0.979 | 0.949 to 1.010 | 0.177 | No association |

### Spearman Rank Correlations (ADI)

| Modality | rho | p-value |
|----------|:---:|:-------:|
| CMR rate vs ADI | -0.172 | < 0.0001 |
| CCT rate vs ADI | -0.163 | < 0.0001 |

### ADI Quintile Analysis (Dose-Response)

| ADI Quintile | Mean CMR Rate (per 100,000) | Mean CCT Rate (per 100,000) |
|:---:|:---:|:---:|
| Q1 (Least deprived) | 0.27 | 0.61 |
| Q2 | 0.18 | 0.53 |
| Q3 | 0.12 | 0.49 |
| Q4 | 0.08 | 0.44 |
| Q5 (Most deprived) | 0.06 | 0.39 |
| **Q1 vs Q5 ratio** | **4.5x** | **1.6x** |
| Kruskal-Wallis p | < 0.0001 | < 0.0001 |

### What This Means

The ADI reveals a statistically significant and clinically meaningful relationship between area deprivation and CMR access that the SVI completely missed:

- For every 10-percentile increase in area deprivation, CMR facility rates decrease by 6.3%.
- Counties in the most deprived quintile (Q5) have 4.5 times fewer CMR facilities per capita than counties in the least deprived quintile (Q1).
- This gradient is monotonic (steadily decreasing from Q1 to Q5), supporting a dose-response relationship.
- The effect is specific to CMR. CCT shows a trend but does not reach statistical significance in the regression model.

---

## 5. SVI vs ADI Comparison

### Why Do They Give Different Answers?

| Feature | SVI | ADI |
|---------|-----|-----|
| Number of input variables | 16 | 6 |
| Includes minority status | Yes | No |
| Includes disability/age | Yes | No |
| Includes housing type | Yes | No |
| Includes transportation | Yes | No |
| Focuses on economic deprivation | Partially (1 of 4 themes) | Entirely |
| Designed for | Disaster response | Healthcare access research |

The SVI dilutes its socioeconomic signal by including three non-economic themes. When you ask "does economic deprivation predict imaging access?", the SVI mixes the relevant signal (poverty, income) with irrelevant noise (minority status, vehicle access, group quarters). The ADI, by focusing exclusively on economic deprivation, provides a cleaner test of the socioeconomic hypothesis.

### Correlation Between SVI and ADI

- Pearson r = 0.826 (strong positive correlation)
- They are related but not identical
- The 17.4% of ADI variance NOT shared with SVI is what drives the significant CMR finding

### Visual Evidence (Figure 2)

Figure 2 (Panel D) shows a scatter plot of SVI vs ADI for all counties. CMR-containing counties (blue dots) are spread evenly across SVI values (confirming the null SVI result) but cluster in the low-ADI region (confirming the significant ADI result). This visual directly demonstrates why the two predictors yield different conclusions.

---

## 6. Stratified and Subgroup Analyses

### SVI Stratified by Metro/Nonmetro

| Stratum | Modality | IRR | p-value | Notes |
|---------|----------|:---:|:-------:|-------|
| Metro only | CMR | 1.005 | 0.82 | No association |
| Metro only | CCT | 1.036 | 0.054 | Borderline positive |
| Nonmetro only | CMR | 0.814 | 0.064 | Borderline negative (trend) |
| Nonmetro only | CCT | 0.982 | 0.62 | No association |

**Interpretation:** Among nonmetropolitan counties only, there is a borderline suggestion that higher SVI reduces CMR access (IRR = 0.814, p = 0.064). This does not reach conventional significance but hints that the metro-rural divide may mask within-stratum socioeconomic effects.

### SVI Quartile Contrasts

| Contrast | Modality | IRR | p-value |
|----------|----------|:---:|:-------:|
| Q2 vs Q1 | CMR | 0.984 | 0.92 |
| Q3 vs Q1 | CMR | 0.844 | 0.36 |
| Q4 vs Q1 | CMR | 0.870 | 0.44 |
| Q2 vs Q1 | CCT | 1.181 | 0.14 |
| Q3 vs Q1 | CCT | 1.310 | 0.038 |
| Q4 vs Q1 | CCT | 1.123 | 0.35 |

**Interpretation:** CCT Q3 vs Q1 is borderline significant (p = 0.038) but the pattern is non-monotonic (Q4 returns to null). This isolated finding does not survive multiple comparison correction and does not support a consistent socioeconomic gradient.

---

## 7. Interpreting the Figures

### Figure 1: Two-Panel Choropleth (CMR and CCT Facility Rates)

- Shows per-capita facility rates across all continental US counties
- Dark-colored counties have higher rates; light or white counties have zero facilities
- The vast empty space in rural America is immediately visible
- Metropolitan clusters (Northeast corridor, California, Texas cities, Florida) dominate

### Figure 2: SVI vs ADI Comparison (4 Panels)

- **Panel A:** SVI distribution. Dark blue = high vulnerability. Concentrated in the Deep South, Appalachia, and tribal lands.
- **Panel B:** ADI distribution. Dark red = high deprivation. Similar to SVI but with differences in the Southwest and urban areas.
- **Panel C:** CMR counties (blue) overlaid on ADI. Notice how CMR facilities (blue) are concentrated in light-colored (low-ADI, affluent) areas.
- **Panel D:** Scatter of SVI vs ADI. Blue dots (CMR counties) cluster in the lower-left (low deprivation by both measures), but the clustering is tighter on the ADI axis (y-axis) than on the SVI axis (x-axis).

### Figure 3: ADI Quintile Bar Charts

- Left panel (CMR): Clear monotonic decrease from Q1 to Q5. Error bars (95% CI) confirm the differences are statistically meaningful.
- Right panel (CCT): Decrease is present but smaller in magnitude and error bars overlap more between adjacent quintiles.
- The dose-response pattern for CMR supports a causal interpretation.

---

## 8. Frequently Asked Questions

### Q: Why is n = 3,038 and not 3,144?

We excluded 106 counties with fewer than 1,000 adults aged 45 and older. These very small counties produce extremely unstable per-capita rates. For example, 1 facility in a county with 500 eligible adults would produce a rate of 200 per 100,000, which is a misleading outlier driven entirely by the tiny denominator. This exclusion is standard practice in ecologic rate analyses.

### Q: Why are the Table 1 medians all zero?

Because more than 50% of counties have zero facilities for both CMR and CCT. In any distribution where the majority of observations are zero, the median (the middle value when sorted) will be zero. This is not an error; it reflects the extreme concentration of cardiac imaging in a small number of counties. The mean provides the average rate including zeros.

### Q: Why Negative Binomial instead of Poisson or linear regression?

- **Why not Poisson?** Poisson regression assumes the variance equals the mean. Our CMR data has a mean of 0.23 but a variance of 43.2 (187 times larger). This severe overdispersion makes Poisson inappropriate.
- **Why not linear regression?** The outcome is a count variable bounded at zero with extreme right skew. Linear regression assumes normally distributed residuals and can produce impossible negative predicted values.
- **Why Negative Binomial?** It adds a dispersion parameter (alpha) that accounts for the excess variance. AIC comparison confirmed NegBin is preferred over Poisson (delta-AIC > 30 for all models).

### Q: Why does ADI find what SVI misses?

Think of it like medical testing. The SVI is a broad screening panel that tests for many things simultaneously (poverty, minority status, disability, housing type, transportation). It may miss subtle economic signals because of noise from unrelated domains. The ADI is a targeted test focused specifically on economic deprivation. It has better sensitivity for the specific question: "does neighborhood economic status predict imaging access?"

### Q: Is the ADI finding causal?

This is a cross-sectional ecologic study, so we cannot establish causality. However, several features support a causal interpretation:
- The dose-response relationship (monotonic Q1 to Q5 gradient)
- Biological plausibility (deprived areas have lower patient volume, worse payer mix, lower revenue potential for capital-intensive imaging)
- Consistency with prior literature (Mango et al. found similar ADI-accreditation associations for breast imaging)
- Specificity (the effect is stronger for CMR, which has higher barriers to entry)

### Q: Why is CMR significant but not CCT?

CMR is rarer and more specialized (725 sites vs 1,548 for CCT). It requires:
- 1.5T or 3T MRI scanners with dedicated cardiac coils
- Specially trained technologists for cardiac-gated sequences
- Cardiologist or radiologist expertise in CMR interpretation

These higher barriers mean CMR facility siting decisions are more sensitive to local economic conditions (anticipated patient volume, payer mix, ability to sustain the investment). CCT, being more widely distributed and sharing infrastructure with general CT scanners, shows less socioeconomic patterning.

---

## 9. Clinical and Policy Implications

### For Patients

- Residents of economically deprived counties face systematic barriers to accessing accredited cardiac MRI.
- These patients may need to travel significant distances or forgo advanced cardiac imaging entirely.
- This may contribute to disparities in cardiac disease diagnosis, management, and outcomes.

### For Health Systems and Policymakers

- **"Cardiac imaging deserts"**: 1,974 counties (62.8%) have zero accredited facilities of any kind. The mean ADI of these deserts is 58.2 vs 41.7 for counties with at least one facility (p < 0.0001).
- Targeted incentive programs (analogous to HPSA designations for physician shortages) could encourage accreditation in high-ADI areas.
- Telehealth and mobile imaging partnerships may bridge access gaps in the short term.

### For Researchers

- The SVI (commonly used in health equity research) may not be the best tool for healthcare-access questions. ADI or other economically focused indices may be more appropriate.
- Future studies should examine whether these supply-side disparities translate to outcome disparities (cardiac mortality, event rates, stage at diagnosis).

---

## 10. Limitations

1. **Ecologic design:** Associations at the county level cannot be directly attributed to individual patients (ecologic fallacy risk).
2. **ACR only:** We captured only ACR-accredited facilities. IAC-accredited sites are not included and may partially fill gaps.
3. **Cross-sectional:** We cannot assess temporal trends or determine whether disparities are widening or narrowing.
4. **No travel time:** We did not calculate actual travel distances. A patient near a county border may access facilities in an adjacent county.
5. **ADI construction:** Our ADI is constructed from available variables following published methodology, but it has not been independently validated against patient-level outcomes in this specific context.
6. **No demand adjustment:** We did not account for local disease burden. Counties with higher cardiac disease prevalence may need more facilities per capita.

---

## 11. Summary of All Statistical Tests

| Analysis | Predictor | Modality | Test | Statistic | p-value | Conclusion |
|----------|-----------|----------|------|-----------|---------|------------|
| Primary regression | SVI (per 10-pctl) | CMR | NegBin GLM | IRR = 0.992 | 0.681 | Null |
| Primary regression | SVI (per 10-pctl) | CCT | NegBin GLM | IRR = 1.020 | 0.213 | Null |
| Sensitivity regression | ADI (per 10-pctl) | CMR | NegBin GLM | IRR = 0.937 | 0.002 | **Significant** |
| Sensitivity regression | ADI (per 10-pctl) | CCT | NegBin GLM | IRR = 0.979 | 0.177 | Null |
| Correlation | SVI | CMR rate | Spearman | rho = 0.008 | 0.66 | Null |
| Correlation | SVI | CCT rate | Spearman | rho = 0.023 | 0.21 | Null |
| Correlation | ADI | CMR rate | Spearman | rho = -0.172 | < 0.0001 | **Significant** |
| Correlation | ADI | CCT rate | Spearman | rho = -0.163 | < 0.0001 | **Significant** |
| SVI-ADI agreement | -- | -- | Pearson | r = 0.826 | < 0.0001 | Strong but not identical |
| Metro vs nonmetro | -- | CMR rate | Mann-Whitney U | -- | < 0.0001 | **Significant** |
| Metro vs nonmetro | -- | CCT rate | Mann-Whitney U | -- | < 0.0001 | **Significant** |
| Quintile comparison | ADI quintiles | CMR rate | Kruskal-Wallis | -- | < 0.0001 | **Significant** |
| Quintile comparison | ADI quintiles | CCT rate | Kruskal-Wallis | -- | < 0.0001 | **Significant** |
| Stratified (nonmetro) | SVI (per 10-pctl) | CMR | NegBin GLM | IRR = 0.814 | 0.064 | Borderline |
| Stratified (metro) | SVI (per 10-pctl) | CCT | NegBin GLM | IRR = 1.036 | 0.054 | Borderline |

---

## How to Cite This Work

> Razak A, Ahmad N. Geographic Disparities in ACR-Accredited Cardiac Imaging Capacity: A Cross-Sectional Ecologic Analysis of 3,144 US Counties. 2026. GitHub: https://github.com/abdulrazakucc/geo-spatial-analysis

---

*For technical details on reproducing these results, see the [Data Scientist Task Guide](../../docs/Data_Scientist_Task_Guide.pdf) and the [PCA Explanation](../../docs/PCA_Explanation.md).*
