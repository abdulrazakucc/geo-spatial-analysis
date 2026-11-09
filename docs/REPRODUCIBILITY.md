# Reproducibility and Validation Guide

For reviewers, editors, and statisticians who want to verify the analysis.

This document explains what is computed, where each published number comes
from, and how to check a manuscript against the data. It deliberately quotes few
numbers: the generated files named below are the authority, and every number in
this guide is one you can find in them.

---

## 1. Two ways to reproduce

**From the processed data (no network, no large files).**

```bash
pip install -r requirements.txt      # Python 3.11; requirements-lock.txt pins versions
python code/00_run_all.py            # stages B, C, D
python code/00_run_all.py --with-present   # adds stage E: figures and tables
python tests/test_pipeline.py        # pytest is not required
```

The analytic dataset is committed, so this path needs nothing else. The map
figures additionally need county geometry: the committed display geometry
redraws them, and the full TIGER/Line geometry (not committed, see section 7)
reproduces the published pixels exactly.

**From the raw data.** Stage B rebuilds the analytic dataset from the raw files in
`data/raw/` and the ACR extract. It needs `data/raw/tiger_county_2023/`, which is
not committed. Stage A (`--all`) re-downloads source data and is not a way to
reproduce the frozen submission, because the sources change over time.

**Checking a manuscript.**

```bash
python code/12_manuscript_numbers.py path/to/manuscript.docx --strict
```

The report is written to `output/validation/manuscript_check.txt`. It states the
number of checks and mismatches; a passing manuscript has zero mismatches. With
`--strict`, or with an explicit path, a missing manuscript is an error. Run
without a manuscript (as `00_run_all.py` does), the checker recomputes the values
and labels the run as analysis-only; that is not a manuscript pass.

The checker covers named values, table cells, specified wording claims, a list of
forbidden obsolete values and phrases, and every estimate quoted in the text
("IRR x; 95% CI, a-b; P = p", "x (95% CI, a-b)", or a bare "IRR x"), which must
match a computed result. It does not verify external facts such as policy, source
provenance, or what a cited paper found.

---

## 2. Why this validation exists

An earlier submission contained two incorrect descriptive values, copied by hand
from a narrative document that no script generated (since deleted). The count of
counties with neither modality was given as 1,974 (62.3%) when the data give
2,570 (81.7%), and the mean deprivation contrast between counties without and
with a facility as 58.2 vs 41.7 when the data give 52.8 vs 39.9.

The remedy is structural: no number reaches the manuscript by hand. The revision
script formats every number from generated results, and the checker recomputes
them.

---

## 3. Model specification

```
facility_count ~ index_per10 [+ metropolitan status] + offset(log(adult_pop_45plus))
```

| Element | Choice | Reason |
|---|---|---|
| Family | Negative binomial (NB2), dispersion estimated, every fit finished with Newton steps (`model_spec.fit_nb2`) | Counts are overdispersed; lowest AIC and BIC of three specifications in all 12 index-outcome models |
| Offset | `log(adults aged 45+)` | Makes the count model a rate model |
| Rate exclusion | Counties with < 1,000 adults aged 45+, from county-level **rates** only | 106 counties, none with a facility; all are retained in the count regressions |
| Index scaling | Per 10 percentile points | Interpretable IRR |
| Primary adjustment | Binary metropolitan status (RUCC 1-3) | Every index model is fitted unadjusted and adjusted |
| Sensitivity | Ordinal RUCC; metropolitan and nonmetropolitan strata with an interaction test; Accredited-only cohort; rate-eligible sample; dispersion fixed at 1; population-weighted and equally weighted Poisson; the SDI in place of the EDI | Results should not depend on one choice |

### How each model weights counties

From the score equations, writing the county rate as r = y/N and the fitted rate
as lambda:

- Poisson with the offset: `sum N x (r - lambda) = 0`. Each county's rate counts
  in proportion to its adults aged 45+ (the average adult). This is the
  population-weighted sensitivity analysis, fitted with robust (HC0) errors.
- Poisson with the offset and weights 1/N: `sum x (r - lambda) = 0`. Every
  county counts equally (the average county).
- NB2 with the offset (primary): `sum N/(1 + alpha mu) x (r - lambda) = 0`. The
  weight rises with population and levels off.

An earlier version added population weights to the offset Poisson model, which
weights rates by N squared. It is no longer used.

### Why negative binomial

See the `model_diagnostics` block of `output/validation/manuscript_numbers.json`
(overdispersion and NB2 versus Poisson on AIC, on the primary sample) and
`output/results/model_specification_comparison.csv` (Poisson, NB2 with the
dispersion estimated, and NB2 with the dispersion fixed at 1, on AIC and BIC).
The usual Poisson dispersion statistic is below 1 in these sparse counts; that
is an artifact of fitted means far below 1, and the likelihood comparison is the
informative one.

### Fixing the dispersion at 1

Kept as a labelled sensitivity. It is not neutral for SVI-CCT:

| Adjusted estimate | dispersion estimated (primary) | alpha = 1.0 |
|---|---|---|
| SVI-CMR | IRR 1.003, P = 0.854 | IRR 1.004, P = 0.850 |
| SVI-CCT | IRR 1.033, P = 0.008 | IRR 1.032, P = 0.058 |
| EDI-CMR | IRR 0.993, P = 0.699 | IRR 0.990, P = 0.638 |
| EDI-CCT | IRR 1.016, P = 0.186 | IRR 1.010, P = 0.562 |

The manuscript reports the primary estimate and discloses the sensitivity.

### Sparse strata

In the nonmetropolitan cardiac MR stratum each of the 14 facilities is in a
different county, and the NB2 dispersion estimate lies on its boundary
(alpha = 0), where NB2 is Poisson. `model_spec.fit_primary_checked` detects that
case and returns the Poisson fit with its interval; any other non-invertible fit
is reported as NE. The diagnostics are in
`output/results/nonmetro_cmr_diagnostics.txt` and Supplementary Table S4.

### Why adjustment matters

The EDI is correlated with rurality, and capacity is concentrated in
metropolitan counties, so an unadjusted deprivation model absorbs a geographic
signal. That is the paper's central methodological point.

---

## 4. Where each published number comes from

| Manuscript element | Produced by | Output |
|---|---|---|
| Table 1 | `17_table1.py` | `output/tables/Table1_*` |
| Tables 2 and 3, every quoted estimate | `05`, `06`, `09`, `18`, checked by `12` | `output/results/`, `output/validation/` |
| Figures 1A, 1B, 2, S1-S3 | `16_publication_figures.py` | `output/figures/` |
| Supplement (Methods S1-S8, Tables S1-S6) | `19_supplementary_material.py` | `output/tables/Supplementary_*` |
| Reviewer analyses | `18_reviewer_analyses.py` | `output/results/reviewer_analyses.json` |

Superseded scripts (`04`, `08`, `10`) are not run. There is no Table 4.

---

## 5. Construction of the Economic Deprivation Index

`code/06_edi_sensitivity_analysis.py` takes the first principal component of six
standardized county indicators: persons below 150% of the federal poverty level,
unemployment, adults without a high-school diploma, and housing cost burden (CDC/
ATSDR SVI 2022), and median household income (sign-reversed) and children in
poverty (County Health Rankings 2024). Scores are converted to national
percentiles; higher means more deprived. The full decomposition, parallel
analysis, KMO and Bartlett's test are in `output/results/edi_pca_components.csv`,
`reviewer_analyses.json` and Supplementary Table S5.

The EDI is not the Area Deprivation Index (ADI) of Singh or of the University of
Wisconsin Neighborhood Atlas.

---

## 6. Known limitations of the data

- **ACR accreditation only.** Three other CMS-designated accrediting
  organizations exist, and hospitals and critical access hospitals are exempt, so
  the counts understate total capacity.
- **Cohort rule.** MRI or CT accreditation with a cardiac module; CT records
  accredited only for calcium scoring are not included. Accredited and Under
  Review records form the primary cohort.
- **ZIP-based county assignment.** Each ZIP goes to the county with the largest
  share of its residential addresses (HUD-USPS crosswalk); this is not an address
  geocode.
- **Ecologic and cross-sectional.** No individual-level or causal inference.
- **Sparse nonmetropolitan cardiac MR stratum** (14 facilities). Its estimate is
  hypothesis-generating.
- **Complete enumeration.** Intervals are interpreted in a superpopulation
  framework.

---

## 7. What is not in the repository

| Item | Why |
|---|---|
| `data/processed/county_analytic_geo.gpkg`, `data/raw/tiger_county_2023/` | Large geometry; needed only for the raw build and exact map pixels |
| `manuscript/` | Kept out of version control while under review |
| New scripts under `tools/` | `tools/` is gitignored; version them with `git add -f` |
| `output/models/model_objects.pkl` | Regenerated by the pipeline |

The revision builders also call LibreOffice (`SOFFICE`, default
`/Applications/LibreOffice.app/Contents/MacOS/soffice`), Google Chrome
(`CHROME`), and poppler's `pdftotext` and `pdfinfo`; set the environment
variables where those tools live elsewhere.
