# Geographic Disparities in Accredited Cardiac Imaging Across the United States

Reproducible analysis pipeline for the manuscript

> **Area Deprivation, Rurality, and Accredited Cardiac Imaging Capacity in US Counties**

This repository contains everything needed to reproduce the analysis: the source
data, the code, the generated figures and tables, and a validation script that
checks the manuscript against the data, number by number.

The repository is written to be journal-agnostic. Nothing in `main` is specific
to a particular journal, so the same package can accompany a submission
anywhere. Every file in `output/` is produced by a named script in `code/`;
there are no hand-maintained artifacts.

---

## The finding in one paragraph

Accredited cardiac MR (CMR) and cardiac CT (CCT) capacity is overwhelmingly
concentrated in metropolitan counties. **2,570 of 3,144 US counties (81.7%) have
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
| SVI | 1.00 (0.96-1.04) | 0.980 | 1.00 (0.97-1.04) | 0.854 |
| EDI | **0.95 (0.91-0.98)** | **0.003** | 0.99 (0.96-1.03) | 0.699 |
| Metropolitan status | — | — | **8.33 (4.86-14.28)** | **<0.001** |

### Cardiac CT

| Exposure | Unadjusted IRR (95% CI) | P | Adjusted for metro, IRR (95% CI) | P |
|---|---|---|---|---|
| SVI | **1.03 (1.01-1.06)** | **0.014** | **1.03 (1.01-1.06)** | **0.008** |
| EDI | 0.99 (0.97-1.01) | 0.372 | 1.02 (0.99-1.04) | 0.186 |
| Metropolitan status | — | — | **2.13 (1.74-2.61)** | **<0.001** |

The EDI-CMR association does not survive adjustment for metropolitan status.
The SVI-CCT association does, in the opposite direction to a deprivation
gradient: more accredited CT capacity in more vulnerable counties. Analytic samples: n = 3,144 (SVI), n = 3,134 (EDI).

### External validation

Because the EDI is built in-house, the whole analysis was repeated with the
**Robert Graham Center Social Deprivation Index (SDI)**, a published county-level
measure. The SDI shows **no inverse** unadjusted CMR association
(IRR 1.02, 95% CI 0.98-1.05,
P = 0.322) while reproducing metropolitan status almost exactly
(IRR 8.67). After adjustment it is modestly positive
(IRR 1.04, 95% CI 1.00-1.07,
P = 0.043) — the opposite direction to a deprivation disadvantage.
Whether an inverse deprivation signal appears at all depends on how strongly the
chosen index encodes rurality; the metropolitan finding does not. See
`output/results/index_comparison_results.txt`.

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
reports **156 checks, 0 mismatches**.

Full details of what is checked and how, including the model specification and
each analytic decision, are in **[docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md)**.

---

## Statistical specification

Defined once in `code/model_spec.py` and used by every script that fits a model. `07_publication_outputs.py` fits nothing; it reads the generated results.

- **Outcome** — count of ACR-accredited facilities per county, CMR and CCT modelled separately.
- **Model** — negative binomial (NB2) with the **dispersion parameter estimated from the data**; better supported by AIC and BIC than a fixed `alpha = 1.0`, which is retained as a labelled sensitivity.
- **Offset** — `log(adults aged 45+)`, which turns the count model into a rate model.
- **Rate** — facilities per 100,000 adults aged 45+.
- **Exclusion** — counties with fewer than 1,000 adults aged 45+ are excluded
  from **rate** calculations (`rate_excluded` flag, 106 counties) because their
  rates are unstable. They are **retained in the count regressions**, which
  carry a population offset. Restricting the regressions too is a sensitivity.
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
  01c_fetch_hud_crosswalk.py    A  HUD ZIP-county crosswalk (needs a token)
  02_build_analytic_dataset.py  B  build the analytic dataset
  03_descriptive_analysis.py    C  Table 1
  05_regression_analysis.py     C  SVI models
  06_edi_sensitivity_analysis.py C  build the EDI, fit adjusted models
  09_validated_index_sdi.py     C  external validation with the Graham SDI
  13_model_specification.py     C  Poisson vs NB, estimated vs fixed dispersion
  14_accredited_only_sensitivity.py C  Accredited-only cohort sensitivity
  12_manuscript_numbers.py      D  recompute and check every manuscript number
  facility_mapping.py           helper: cohort, ZIP-to-county, audit trail
  04_choropleth_map.py          E  Figure 1A
  08_svi_edi_comparison_maps.py E  Figures 2 and 3
  10_forest_plots.py            E  Figure 1B and Figure S
  11_edi_tables_and_stats.py    E  Word tables, supplementary statistics
  07_publication_outputs.py     E  publication Figure 1 and Table 1

tests/                    pipeline integrity tests (python tests/test_pipeline.py)
tools/                    manuscript utilities, not part of the pipeline
  docx_tracked.py         library for tracked-change edits to a .docx
  revise_manuscript.py    applies a dated revision round to the manuscript
  finalize_manuscript.py  produces the clean submission file from the working one

data/raw/                 source data as downloaded
data/processed/           county_analytic_dataset.csv, the central artifact
output/validation/        the reviewer-facing validation report
output/results/           model results, machine-readable and formatted
output/models/            regression output as text
output/tables/            Word tables
output/figures/           figures for the manuscript
docs/                     methodology notes and the reproducibility guide
manuscript/               the manuscript itself (not tracked in git)
  manuscript_CLEAN.docx        working file, carries tracked changes
  manuscript_SUBMISSION.docx   all changes accepted, comments stripped
```

### The two manuscript files

The working file accumulates every revision round as tracked changes, attributed
and dated, so collaborators can see exactly what moved and when. The submission
file is generated from it with every change accepted and all review apparatus
removed. Both are regenerated after any change to the analysis:

```bash
python tools/revise_manuscript.py --from-check   # apply regenerated values
python code/12_manuscript_numbers.py             # re-validate the working file
python tools/finalize_manuscript.py --validate   # build and validate the submission file
```

The validation gate is run against **both**. Neither file is tracked in git while
the manuscript is unpublished.

### Branches

| Branch | Contents |
|---|---|
| `main` | **This branch.** The current analysis and everything needed to reproduce and review it. |
| `old` | The state of the analysis before the facility-mapping correction and the change of primary model specification. Retained for reference only; its results are superseded. |
| `validation` | Working branch. Carries the same analysis plus the audit reports and branch-comparison documents produced while the corrections were made. |
| `webapp` | The read-only MapLibre dashboard, its Docker deployment, and ancillary material (slide deck, workflow PDF, collaborator deliverables). Kept off the analysis branches so a reviewer sees only the analysis. |

Working notes, audit reports and branch-comparison documents are deliberately
not carried here. This branch contains the analysis, the data needed to
reproduce it, and the documentation required to review it — nothing else.
Those working documents live on `validation` if you need them.

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

## Facility cohort and county mapping

Every row of the supplied registry extract is accounted for. The build writes
`data/processed/facility_mapping_audit.csv`, one row per source record, with the
assigned county, the mapping method, and — for anything excluded — the reason.
`output/validation/facility_reconciliation.txt` summarises it.

The cohort follows the project briefing: 50 states and DC, modality MRAP or
CTAP with a cardiac module, status **Accredited or Under Review**, not expired
as of the extraction date (2026-05-20). Under Review records are part of the
primary cohort by design; `14_accredited_only_sensitivity.py` reruns everything
without them and finds the same conclusions.

ZIP-to-county mapping uses whichever of two methods is available, recorded per
record:

| Method | When used |
|---|---|
| `hud_res_ratio` | Whenever `data/raw/hud_zip_county.csv` is present. Assigns each ZIP to the county with the largest residential-address share. This is the specified method. Fetch it with `python code/01c_fetch_hud_crosswalk.py`. |
| `census_zcta_arealand` | Fallback. Census 2020 ZCTA relationship file, largest land-area overlap. |
| `ct_town_manual` | Connecticut only, under the fallback. See below. |

Connecticut replaced its counties with nine planning regions in 2022. The 2020
ZCTA file still emits retired FIPS (09001-09015), which match nothing in the
current county universe (09110-09190), so all 32 eligible Connecticut records
used to vanish silently and the state showed zero capacity. They are now
resolved through a documented town-to-planning-region table and flagged for
manual review. Supplying the HUD crosswalk removes the need for that table.

**Known gap under the fallback.** Under the Census fallback, 64 eligible records
sit in ZIPs with no ZCTA (PO-box and unique ZIPs) and cannot be placed. With the
HUD crosswalk in place all 2,264 eligible records map: 2,262 through
`hud_res_ratio` and 2 through a documented per-ZIP override.

### Fetching the HUD crosswalk

Register at <https://www.huduser.gov/portal/dataset/uspszip-api.html>, then:

```bash
export HUD_API_TOKEN="your token"          # or: echo "..." > data/raw/.hud_api_token
python code/01c_fetch_hud_crosswalk.py --dry-run   # verify the token
python code/01c_fetch_hud_crosswalk.py             # 2026 Q1
python code/02_build_analytic_dataset.py           # rebuild
python code/00_run_all.py --with-present           # regenerate everything
python tests/test_pipeline.py
```

The token is read from `HUD_API_TOKEN`, then `data/raw/.hud_api_token` (both
gitignored), then a placeholder constant in the script. **Do not paste a token
into the tracked file** unless you intend it to enter git history.

The fetcher queries state by state, retries transient failures, and refuses to
write anything unless the result is nationally complete and Connecticut
resolves to planning regions rather than retired counties — so a stale vintage
cannot quietly reintroduce the bug it exists to fix.

## Count-model specification

`13_model_specification.py` fits Poisson, NB2 with dispersion estimated, and
NB2 with dispersion fixed at 1.0 for every index and outcome, and reports alpha,
AIC, IRR, CI, P, and convergence to
`output/results/model_specification_comparison.*`.

This matters. An earlier version of this analysis fixed `alpha = 1.0`, but the
data support alpha near 0.2 to 0.6, and NB2 with estimated dispersion has the
lowest AIC **and** the lowest BIC in all 12 model/outcome comparisons. Under
that better-fitting specification the SVI-CCT association is significant, which
it is not at `alpha = 1.0`. **The primary specification is the
estimated-dispersion model**, defined once in `code/model_spec.py`; the
`alpha = 1.0` results are retained as a labelled sensitivity.

---

## Data sources

| Source | Used for | Vintage |
|---|---|---|
| ACR Accredited Facility Search | CMR and CCT facility locations | extracted 2026-05-20 |
| CDC/ATSDR Social Vulnerability Index | SVI, and 4 of the 6 EDI inputs | 2022 |
| County Health Rankings | median income, child poverty (EDI inputs) | 2024 |
| American Community Survey (5-year) | population aged 45+ | 2019-2023 |
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
