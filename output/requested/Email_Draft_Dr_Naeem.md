# Email Draft to Dr. Naeem

**Subject:** ACR Cardiac Imaging Analysis - Complete Results Including ADI Sensitivity Analysis

---

Dear Dr. Naeem,

I hope this message finds you well. I am writing to share the complete results of our geographic disparities analysis, including the ADI sensitivity analysis you requested. Below is a summary of all findings, followed by some clarification points and additional analyses we conducted.

---

## 1. PRIMARY ANALYSIS (SVI as Predictor)

We examined whether the CDC Social Vulnerability Index (SVI) predicts the distribution of ACR-accredited cardiac imaging facilities across 3,144 US counties.

**Result: SVI does NOT predict facility distribution.**

| Modality | IRR per 10-percentile | 95% CI | p-value |
|----------|----------------------|--------|---------|
| CMR (Cardiac MRI) | 0.992 | 0.952 to 1.033 | 0.681 |
| CCT (Cardiac CT) | 1.020 | 0.989 to 1.053 | 0.213 |

Interpretation: Neither cardiac MRI nor cardiac CT facility rates show a statistically significant association with county-level social vulnerability. The Spearman correlations are also null (CMR rho = 0.008, CCT rho = 0.023).

---

## 2. ADI SENSITIVITY ANALYSIS (Your Request)

Per your suggestion to try the Area Deprivation Index as an alternative predictor, we constructed a county-level ADI using Principal Component Analysis (PCA) of 6 ACS-derived socioeconomic indicators (following Singh 2003 and Kind/Buckingham 2018 methodology).

**Result: ADI detects a SIGNIFICANT association for CMR that SVI missed.**

| Modality | IRR per 10-percentile | 95% CI | p-value | Significant? |
|----------|----------------------|--------|---------|:---:|
| CMR | 0.937 | 0.900 to 0.976 | 0.002 | YES |
| CCT | 0.979 | 0.949 to 1.010 | 0.177 | No |

**Interpretation:** For every 10-percentile increase in area deprivation, CMR facility rates decrease by 6.3%. This effect is specific to CMR (the more specialized modality with only 725 sites) and is absent for CCT (which is more widely distributed with 1,548 sites).

**Why does ADI find what SVI missed?** The SVI includes 4 themes (socioeconomic, household/disability, minority status, housing type/transportation). The non-economic themes introduce noise that dilutes the socioeconomic signal. ADI focuses purely on economic deprivation (poverty, unemployment, education, income, housing cost), which more directly relates to healthcare infrastructure investment decisions.

---

## 3. GEOGRAPHIC (METRO vs RURAL) FINDINGS

The dominant disparity is geographic, not socioeconomic:

- Metropolitan counties (37.3% of all US counties) contain 98.1% of all CMR and 92.4% of all CCT facilities.
- 90.5% of US counties have ZERO cardiac MRI sites.
- 82.4% of US counties have ZERO cardiac CT sites.
- Metro CMR rate: 0.35 per 100,000 adults 45+ vs Nonmetro: 0.02 (p < 0.0001)
- Metro CCT rate: 0.74 per 100,000 adults 45+ vs Nonmetro: 0.35 (p < 0.0001)

---

## 4. ADI QUINTILE ANALYSIS (Additional)

We stratified counties into ADI quintiles (Q1 = least deprived, Q5 = most deprived):

| ADI Quintile | Mean CMR Rate per 100,000 |
|:---:|:---:|
| Q1 (Least deprived) | 0.27 |
| Q5 (Most deprived) | 0.06 |

This represents a **4.5-fold disparity** in CMR access between the least and most economically deprived counties. The Kruskal-Wallis test across all 5 quintiles is highly significant (p < 0.0001).

---

## 5. SVI vs ADI COMPARISON MAP

We generated a 4-panel comparison figure (Figure 2, attached) showing:
- Panel A: SVI geographic distribution across counties
- Panel B: ADI geographic distribution across counties
- Panel C: CMR facility locations overlaid on the ADI map
- Panel D: Scatter plot of SVI vs ADI with CMR presence highlighted

The Pearson correlation between SVI and ADI is r = 0.826. They overlap substantially but measure different constructs. The divergent regression results confirm ADI captures unique economic information.

---

## 6. CLARIFICATIONS

**Q: Why is n = 3,038 and not 3,144?**
A: We excluded 106 counties with fewer than 1,000 adults aged 45 and older. These tiny counties would produce extremely unstable per-capita rates (for example, 1 facility in a county with 500 adults = a rate of 200, which would be a misleading outlier). This is a standard epidemiologic practice for ecologic rate analyses.

**Q: Why are the medians zero in Table 1?**
A: Because 90.5% of counties have zero CMR facilities and 82.4% have zero CCT facilities. In any distribution where more than half of values are zero, the median will be zero. The mean (shown in Table 1 alongside the median) provides the average rate across all counties including zeros.

**Q: Why Negative Binomial instead of Poisson or linear regression?**
A: The facility counts are heavily overdispersed (variance = 43.2, mean = 0.23 for CMR). Poisson regression assumes variance equals the mean. Linear regression assumes normal residuals. Negative Binomial handles overdispersion by adding a dispersion parameter (alpha). AIC comparison confirmed NegBin is preferred (delta-AIC > 30 vs Poisson).

---

## 7. ADDITIONAL FINDINGS NOT PREVIOUSLY REQUESTED

We conducted several additional analyses that may strengthen the manuscript:

### 7a. SVI Quartile Contrasts
- CCT shows a borderline signal in Q3 vs Q1 (IRR = 1.310, p = 0.038), but this does not survive multiple comparison correction and is inconsistent (Q4 is null).
- Nonmetro CMR shows a borderline negative trend (IRR = 0.814, p = 0.064), suggesting rural SVI may matter for CMR in non-metro areas only.

### 7b. ADI Construction Details
- PCA of 6 indicators: EP_POV150, EP_UNEMP, EP_NOHSDP, EP_HBURD, Median Household Income (inverted), Children in Poverty
- First component explains 58.7% of variance (strong single-factor structure)
- All 6 loadings are in the expected direction (poverty/unemployment load positively; income loads negatively)

### 7c. Correlation Structure
- SVI-ADI Pearson r = 0.826 (high overlap but not identical)
- ADI-CMR Spearman rho = -0.172 (p < 0.0001) -- much stronger than SVI-CMR (rho = 0.008)
- ADI-CCT Spearman rho = -0.163 (p < 0.0001) -- CCT is correlated but not significant in regression (due to overdispersion)

### 7d. Policy-Relevant Statistic
- There are 1,974 counties (62.8%) that have ZERO accredited cardiac imaging sites of any kind (neither CMR nor CCT).
- The mean ADI percentile of these "imaging desert" counties is 58.2 vs 41.7 for counties with at least one facility (p < 0.0001).
- This supports framing as "cardiac imaging deserts" analogous to "food deserts."

### 7e. Proposed Framing for Manuscript
Given the ADI finding, we could frame the paper as:
- **Title option:** "Area Deprivation and Access to Accredited Cardiac MRI: A National Ecologic Analysis"
- **Narrative:** SVI (commonly used) misses the signal; ADI (purpose-built for healthcare access research) reveals it; CMR is the more vulnerable modality due to specialization barriers.

---

## 8. FIGURES AND DOCUMENTS AVAILABLE

All outputs are in the repository and can be shared:
- Figure 1: Two-panel CMR/CCT choropleth map (300 DPI)
- Figure 2: Four-panel SVI vs ADI comparison (NEW)
- Figure 3: ADI quintile bar charts with error bars (NEW)
- Table 1-3: Word format
- Supplementary Table: ADI regression results (Word)
- Methodology PDF: Complete methods write-up
- PowerPoint: 8-slide presentation with ADI findings

---

## 9. NEXT STEPS

1. Incorporate IAC-accredited facilities (broader capture beyond ACR)
2. Travel-time analysis (drive time to nearest accredited site)
3. Temporal trends (year-over-year accreditation growth)
4. Finalize manuscript draft for JACC: Advances submission by June 1

Please let me know if you have any questions or if there are additional analyses you would like us to run. Happy to discuss at your convenience.

Best regards,
Abdul Razak, MD

---

*Attachments: Figure2_SVI_vs_ADI_Comparison.png, Figure3_ADI_Quintile_Rates.png, Supplementary_Table_ADI_Regression.docx*
