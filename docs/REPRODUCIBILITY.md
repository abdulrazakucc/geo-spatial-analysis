# Reproducibility and Validation Guide

For reviewers, editors, and statisticians who want to verify the analysis.

This document explains exactly what is computed, where each published number
comes from, and how to check the manuscript against the data yourself.

---

## 1. Verify everything in one command

```bash
pip install -r requirements.txt      # Python 3.11
python code/00_run_all.py
```

No network access is needed. The analytic dataset is committed to the
repository, so the pipeline runs from source data that is already present and
completes in under ten seconds.

Then read:

```
output/validation/manuscript_check.txt
```

That file lists every value the manuscript states, the value the data produce,
and whether they agree. The expected result is:

```
Checks:   123     Mismatches: 0
Every checked value in the manuscript matches the data exactly.
```

If a mismatch appears, the check names the table, row, and column so it can be
resolved without hunting.

---

## 2. Why this validation exists

An earlier submission of this work contained two incorrect
descriptive values. They had been copied into the manuscript from a
hand-maintained narrative document (`docs/Results_and_Interpretation_Guide.md`)
rather than generated from the data. When the underlying data were refined, the
document was updated in some places and not others, and the manuscript inherited
a stale count paired with an updated percentage.

Specifically, the count of counties with neither modality was reported as 1,974
(62.3%) when the data give **2,570 (81.7%)**, and the mean deprivation contrast
was reported as 58.2 vs 41.7 when the data give **52.9 vs 39.4**.

The remedy is structural rather than a one-off correction: **no number reaches
the manuscript by hand.** `code/12_manuscript_numbers.py` recomputes every
published quantity from the data at run time, and `code/11_edi_tables_and_stats.py`
generates the supplementary tables with an internal assertion that every
"N (P%)" pair is arithmetically consistent.

`docs/Results_and_Interpretation_Guide.md` is retained for narrative context and
has been corrected, but **it is not authoritative**. Quote generated outputs.

---

## 3. Model specification

Identical across every script.

```
facility_count ~ index_per10 [+ rurality term] + offset(log(adult_pop_45plus))
```

| Element | Choice | Reason |
|---|---|---|
| Family | Negative binomial (NB2), **dispersion estimated** | Counts are overdispersed; better AIC and BIC than fixed `alpha = 1.0`, which is kept as a sensitivity |
| Offset | `log(adults aged 45+)` | Converts the count model to a rate model |
| Denominator | Adults aged 45+ | The population plausibly referred for cardiac imaging |
| Rate exclusion | Counties with < 1,000 adults aged 45+ | 106 counties; their **rates** are unstable. They are **retained in the count regressions**, which carry a population offset |
| Index scaling | Per 10 percentile points | Makes the IRR interpretable |
| Rurality, primary | Binary metropolitan indicator (RUCC 1-3) | Pre-specified primary adjustment |
| Rurality, sensitivity | Ordinal RUCC 1-9; metro-stratified fits | Shows the result is not an artifact of coding |

Software: Python 3.11.7, statsmodels 0.14.6, SciPy 1.13.0, NumPy 1.26.4, scikit-learn 1.4.2.

### Why negative binomial, stated precisely

Run `python code/12_manuscript_numbers.py` and see the `model_diagnostics`
block of `output/validation/manuscript_numbers.json` for all values below.

**The outcomes are overdispersed.** Among rate-eligible counties the
variance-to-mean ratio is **4.89** for CMR and **8.93** for CCT, against 1.0
under Poisson. Both outcomes are also mostly zero (90.5% and 82.5%).

A caution for anyone checking this: the usual Poisson dispersion statistic,
Pearson chi-squared divided by residual degrees of freedom, is **below 1** in
every model here (0.47 to 0.80). That is an artifact of sparsity rather than
evidence of underdispersion. With fitted means far below 1 for most counties,
the very many near-zero Pearson residuals dominate the statistic while the few
large counts that Poisson fits badly contribute little. The likelihood-based
comparison is the informative one.

**AIC, negative binomial vs Poisson on identical specifications:**

| Model | NB AIC | Poisson AIC | Better |
|---|---|---|---|
| SVI, CMR, unadjusted | 1851.0 | 1932.6 | NB |
| SVI, CMR, adjusted | 1744.2 | 1795.4 | NB |
| SVI, CCT, unadjusted | 3071.3 | 3105.0 | NB |
| SVI, CCT, adjusted | 3033.7 | 3033.0 | Poisson, by 0.7 |
| EDI, CMR, unadjusted | 1831.0 | 1908.9 | NB |
| EDI, CMR, adjusted | 1733.3 | 1777.8 | NB |
| EDI, CCT, unadjusted | 3055.4 | 3083.2 | NB |
| EDI, CCT, adjusted | 3019.5 | 3002.6 | Poisson, by 16.9 |

Negative binomial fits better in six of eight models, decisively for CMR, the
primary outcome. It is retained for CCT as well so that the two outcomes are
estimated under one specification and remain comparable.

**This choice is not cosmetic for CCT, and we state the consequence plainly.**
Under Poisson the adjusted CCT deprivation terms become nominally significant
(SVI IRR 1.034, P = 0.001; EDI IRR 1.022, P = 0.024) where under negative
binomial they are not (P = 0.127 and P = 0.663). Poisson understates standard
errors when the outcome is overdispersed, which is the expected direction of
this difference. Note also that these Poisson estimates lie **above** 1, that
is, greater deprivation associated with *more* CCT capacity. They therefore
provide no support for a deprivation-disadvantage interpretation under either
family, and the paper's conclusions do not rest on them.

### The dispersion parameter

The primary models estimate the dispersion rather than fixing it. The briefing
asked for the dispersion parameter to be reported, and across every
index/outcome combination the estimated-dispersion specification was better
supported by both AIC and BIC than a specification with the dispersion fixed at
1 (see `output/results/model_specification_comparison.csv`). Estimated alpha for
the adjusted SVI models is CMR 0.44, CCT 0.18.

Fixing the dispersion at 1 is retained as a labelled sensitivity. It is not
neutral: the two specifications disagree about SVI-CCT.

| Estimate | dispersion estimated (primary) | alpha = 1.0 (sensitivity) |
|---|---|---|
| SVI-CMR, adjusted | IRR 1.003, P = 0.854 | IRR 1.004, P = 0.850 |
| SVI-CCT, adjusted | IRR 1.033, P = 0.008 | IRR 1.032, P = 0.058 |
| EDI-CMR, adjusted | IRR 0.993, P = 0.699 | IRR 0.990, P = 0.638 |
| EDI-CCT, adjusted | IRR 1.016, P = 0.186 | IRR 1.010, P = 0.562 |

The CMR conclusions are the same under both. The SVI-CCT association is
significant under the primary specification and not under the fixed-alpha
sensitivity; the manuscript reports the primary estimate and discloses the
sensitivity.

### Non-estimable inference

The nonmetropolitan cardiac MR stratum contains 14 accredited facilities. At
that event count the point estimate is obtainable but the confidence interval
and P value are not. Those cells are reported as **NE**, never as `nan`, and
never by substituting an interval from a different specification.

### Why adjustment matters here

The EDI is correlated with rurality (Spearman rho 0.25 against ordinal RUCC;
mean EDI 39.9 in metropolitan vs 56.1 in nonmetropolitan counties). Accredited
capacity is concentrated in metropolitan counties. An unadjusted deprivation
model therefore absorbs a rurality signal. This is the paper's central
methodological point, and it is why every deprivation model is fitted twice.

---

## 4. Where each published number comes from

| Manuscript element | Produced by | Output file |
|---|---|---|
| Table 1, capacity by rurality and EDI quintile | `03_descriptive_analysis.py`, `12_manuscript_numbers.py` | `output/tables/`, `output/validation/` |
| Table 2, SVI and EDI models | `05_regression_analysis.py`, `06_edi_sensitivity_analysis.py` | `output/models/`, `data/processed/edi_regression_results.json` |
| Table 3, sensitivity analyses | `06_edi_sensitivity_analysis.py` | `output/models/EDI_Regression_Results.txt` |
| Table 4, external validation | `09_validated_index_sdi.py` | `output/results/index_comparison_results.json` |
| Figure 1A, choropleth | `04_choropleth_map.py` | `output/figures/` |
| Figure 1B, forest plot | `10_forest_plots.py` | `output/figures/` |
| Figure S, external validation | `10_forest_plots.py` | `output/figures/` |
| SVI-EDI correlation | `09_validated_index_sdi.py`, `11_edi_tables_and_stats.py` | `index_comparison_results.json`, `additional_statistics.json` |
| Every number, cross-checked | `12_manuscript_numbers.py` | `output/validation/` |

Figures 1B and S are drawn directly from `index_comparison_results.json`, so a
plotted estimate cannot drift away from the reported one.

---

## 5. Construction of the Economic Deprivation Index

No county-level index of this construction exists off the shelf, so one is built
in `code/06_edi_sensitivity_analysis.py` by principal component analysis of six
county-level socioeconomic indicators:

1. Percentage below 150% of the federal poverty level (SVI 2022)
2. Percentage unemployed (SVI 2022)
3. Percentage without a high-school diploma (SVI 2022)
4. Percentage with housing cost burden (SVI 2022)
5. Median household income, sign-inverted (County Health Rankings 2024)
6. Percentage of children in poverty (County Health Rankings 2024)

Inputs are standardised, the first principal component is extracted (explaining
**58.7%** of variance across 3,134 counties), and scores are converted to
national percentiles from 0 to 100. Higher means more deprived.

**The sign of a principal component is arbitrary.** It is fixed here by
inverting median income before extraction, so the component always loads in the
direction of greater deprivation. Re-running the construction reproduces the
percentiles to within 1.6e-14.

The EDI is a *secondary* predictor. The SVI, which ships pre-built from the CDC,
is the primary one. The EDI is not the validated Singh / Wisconsin Area
Deprivation Index; see the note at the end of the README.

---

## 6. Known limitations of the data

Stated here as well as in the manuscript, because they bound what the
repository can support.

- **ACR accreditation only.** Three other CMS-designated accrediting
  organisations exist, and hospitals and critical access hospitals are exempt
  from the accreditation requirement. These counts therefore understate total
  capacity, and the direction of bias depends on how unaccredited sites are
  distributed.
- **Ecologic and cross-sectional.** No individual-level or causal inference is
  supported.
- **Sparse nonmetropolitan CMR stratum.** Only 13 accredited CMR facilities lie
  outside metropolitan counties, across 1,856 counties. The stratified
  nonmetropolitan estimate is reported but is unstable and is labelled
  hypothesis-generating wherever it appears.
- **County as the unit.** Travel distance, cross-county use, and local disease
  burden are not captured.
- **Complete enumeration, not a sample.** All 3,144 counties are included.
  Confidence intervals are interpreted in a superpopulation framework, treating
  the observed siting of facilities as one realisation of a stochastic process.

---

## 7. What is not in the repository

| Item | Why |
|---|---|
| `data/processed/county_analytic_geo.gpkg` | County geometry, exceeds the GitHub file-size limit; regenerated by `02_build_analytic_dataset.py` |
| `data/raw/tiger_county_2023/` | TIGER shapefiles, same reason; re-downloaded by `01_download_datasets.py` |
| `manuscript/` | The manuscript itself, kept out of version control while under review |
| `output/models/model_objects.pkl` | Pickled model objects, regenerated by the pipeline |

The absence of these does not affect reproducing the published numbers. Only the
map figures require the geometry file.
