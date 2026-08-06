# Geographic Disparities in Accredited Cardiac Imaging Across the United States

Reproducible analysis pipeline for the manuscript

> **Area Deprivation, Rurality, and Accredited Cardiac Imaging Capacity in US Counties**
> Submitted to the *Journal of the American College of Radiology* (JACR).

This repository contains everything needed to reproduce the analysis: the source
data, the code, the generated figures and tables, and a validation script that
checks the manuscript against the data, number by number.

---

## The finding in one paragraph

Accredited cardiac MR (CMR) and cardiac CT (CCT) capacity is overwhelmingly
concentrated in metropolitan counties. **2,583 of 3,144 US counties (82.2%) have
neither modality.** Two measures of area disadvantage were tested, the CDC Social
Vulnerability Index (SVI) and a purpose-built Economic Deprivation Index (EDI).
The EDI showed an association with CMR capacity **before** adjustment for
rurality that **disappeared after** it, while metropolitan status itself carried
an eightfold effect. The conclusion is methodological: **deprivation indices
should not be used as proxies for imaging access without adjusting for
rurality.**

---

## Key results

All values below are produced by `code/12_manuscript_numbers.py` and can be
regenerated in about ten seconds. Incidence rate ratios (IRR) are per 10
percentile points, from negative binomial models with a log-population offset.

### Cardiac MR

| Exposure | Unadjusted IRR (95% CI) | P | Adjusted for metro, IRR (95% CI) | P |
|---|---|---|---|---|
| SVI | 0.99 (0.95-1.03) | 0.681 | 1.00 (0.95-1.04) | 0.870 |
| EDI | **0.94 (0.90-0.98)** | **0.002** | 0.98 (0.94-1.03) | 0.434 |
| Metropolitan status | — | — | **8.23 (4.65-14.56)** | **<0.001** |

### Cardiac CT

| Exposure | Unadjusted IRR (95% CI) | P | Adjusted for metro, IRR (95% CI) | P |
|---|---|---|---|---|
| SVI | 1.02 (0.99-1.05) | 0.213 | 1.03 (0.99-1.06) | 0.127 |
| EDI | 0.98 (0.95-1.01) | 0.177 | 1.01 (0.97-1.04) | 0.663 |
| Metropolitan status | — | — | **1.96 (1.56-2.47)** | **<0.001** |

The EDI-CMR association is the only significant deprivation result, and it does
not survive adjustment. Analytic samples: n = 3,038 (SVI), n = 3,029 (EDI).

### External validation

Because the EDI is built in-house, the whole analysis was repeated with the
**Robert Graham Center Social Deprivation Index (SDI)**, a published county-level
measure. The SDI shows **no** unadjusted CMR association (IRR 1.01, P = 0.746)
while reproducing metropolitan status almost exactly (IRR 8.66). Whether an
unadjusted deprivation signal appears at all depends on how strongly the chosen
index encodes rurality; the metropolitan finding does not. See
`output/jacr_revision/validated_index_results.txt`.

---

## Reproducing the results

Requires Python 3.11.

```bash
pip install -r requirements.txt
python code/00_run_all.py
```

That runs the analysis and validation stages and needs **no network access** —
the analytic dataset is committed. It finishes in under ten seconds and writes:

| File | What it is |
|---|---|
| `output/validation/manuscript_numbers.txt` | Every number quoted in the paper, recomputed |
| `output/validation/manuscript_numbers.json` | The same values at full precision |
| `output/validation/manuscript_check.txt` | The manuscript checked against the data, cell by cell |

Other stages are opt-in because they need external resources:

```bash
python code/00_run_all.py --with-present   # rebuild figures and Word tables
python code/00_run_all.py --with-acquire   # re-download source data (network)
python code/00_run_all.py --all            # everything
```

### For reviewers and statisticians

`code/12_manuscript_numbers.py` is the script to read first. It recomputes every
descriptive statistic, every regression coefficient, every correlation, and
every table cell in the paper directly from the committed data, then compares
them against the manuscript file and reports any disagreement. The current run
reports **123 checks, 0 mismatches**.

Full details of what is checked and how, including the model specification and
each analytic decision, are in **[docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md)**.

---

## Statistical specification

Applied identically in every script:

- **Outcome** — count of ACR-accredited facilities per county, CMR and CCT modelled separately.
- **Model** — negative binomial GLM (`alpha = 1.0`); the data are overdispersed, so Poisson is not used.
- **Offset** — `log(adults aged 45+)`, which turns the count model into a rate model.
- **Rate** — facilities per 100,000 adults aged 45+.
- **Exclusion** — counties with fewer than 1,000 adults aged 45+ are dropped from
  rate and regression analyses (`rate_excluded` flag, 106 counties), because
  their rates are unstable.
- **Scaling** — indices are expressed per 10 percentile points; effects reported as IRR with 95% CI.
- **Rurality** — USDA Rural-Urban Continuum Codes; 1-3 = metropolitan (`metro_indicator = 1`), 4-9 = nonmetropolitan.
- **Adjustment** — every deprivation model is fitted twice, unadjusted and
  adjusted for metropolitan status. **The adjusted estimate is the primary
  result.** Ordinal-RUCC and metro-stratified variants are fitted alongside so
  the conclusion cannot be attributed to how rurality was coded.

---

## Repository layout

```
code/                     numbered pipeline, run in order
  00_run_all.py           master runner, stages A-E
  01_download_datasets.py       A  fetch SVI, RUCC, TIGER, ZIP crosswalk
  01b_fetch_census_population.py A  ACS population via the Census API
  02_build_analytic_dataset.py  B  build the analytic dataset
  03_descriptive_analysis.py    C  Table 1
  05_regression_analysis.py     C  SVI models
  06_edi_sensitivity_analysis.py C  build the EDI, fit adjusted models
  09_validated_index_sdi.py     C  external validation with the Graham SDI
  12_manuscript_numbers.py      D  recompute and check every manuscript number
  04_choropleth_map.py          E  Figure 1A
  08_svi_edi_comparison_maps.py E  Figures 2 and 3
  10_jacr_forest_plots.py       E  Figure 1B and Figure S
  11_edi_tables_and_stats.py    E  Word tables, supplementary statistics
  07_publication_outputs.py     E  journal figures, PPTX, PDF

data/raw/                 source data as downloaded
data/processed/           county_analytic_dataset.csv, the central artifact
output/validation/        the reviewer-facing validation report
output/jacr_revision/     revision figures and external-validation results
output/tables/            Word tables
output/figures/           figures for the manuscript
docs/                     methodology notes and the reproducibility guide
webapp/                   read-only dashboard, decoupled from the pipeline
```

Script numbers reflect the order in which the analyses were developed. Stage
letters, not numbers, indicate execution order; `00_run_all.py` runs them
correctly.

### The central artifact

`data/processed/county_analytic_dataset.csv` — one row per US county (n = 3,144).
Everything downstream reads it.

```
county_fips, state_abbr, county_name, cmr_facility_count, cct_facility_count,
svi_percentile, svi_quartile, rucc_code, metro_indicator, total_population,
adult_pop_45plus, rate_excluded, cmr_rate_per_100k, cct_rate_per_100k
```

**Always read `county_fips` as a string** (`dtype={'county_fips': str}`) to
preserve leading zeros.

---

## Data sources

| Source | Used for | Vintage |
|---|---|---|
| ACR Accredited Facility Search | CMR and CCT facility locations | accessed 2024 |
| CDC/ATSDR Social Vulnerability Index | SVI, and 4 of the 6 EDI inputs | 2022 |
| County Health Rankings | median income, child poverty (EDI inputs) | 2024 |
| American Community Survey (5-year) | population aged 45+ | 2018-2022 |
| USDA Rural-Urban Continuum Codes | metropolitan classification | 2023 |
| Robert Graham Center SDI | external validation | 2015-2019 |
| Census TIGER/Line | county geometry for maps | 2023 |

---

## A note on the index name

The Economic Deprivation Index (EDI) is constructed in this repository by
principal component analysis of six county-level socioeconomic indicators; the
first component explains 58.7% of variance. It was called "ADI" in drafts before
August 2026 and was renamed because that abbreviation collides with the
validated Singh / University of Wisconsin **Area Deprivation Index**, which is a
different instrument published at the block-group level and is *not* used here.
The construction never changed, only the label. See
[docs/PCA_Explanation.md](docs/PCA_Explanation.md).

---

## Authors

Muhammad Naeem, MBBS, MD (corresponding) · Abdul Razak, PhD · and co-authors.
See the title page in the submission package for the full author list and
affiliations.
