# JACR Project — Mayo-Specification Implementation Fix Plan
## LLM-ready engineering handoff

**Purpose:** Use this document to correct the repository so that the implementation matches the Mayo Clinic project briefing and the supplied project datasets.

**Scope restriction:** Do **not** use external websites, refreshed public datasets, or outside facility registries for this task. Treat the supplied Mayo briefing, `ACR_Cardiac_Imaging_Sites.xlsx`, `download.xlsx`, the current manuscript, and the current repository/code and datasets as the governing basis.

---

# 1. Highest-priority implementation issues

| Priority | Issue | Mayo requirement | Current implementation/problem | Exact files/areas to inspect | Required fix | Validation test | Expected pass condition |
|---|---|---|---|---|---|---|---|
| **P0-1** | ZIP-to-county linkage does not follow Mayo specification | Use **HUD-USPS ZIP–County Crosswalk, Q1 2026**. For ZIPs spanning multiple counties, select the county with the **largest residential-address share**. | Current audited workflow uses a **2020 Census ZCTA-county relationship** and selects the county with the largest **land-area overlap (`AREALAND`)**. This is not equivalent. | `code/01_download_datasets.py`, `code/02_build_analytic_dataset.py` (previously audited mapping logic around lines ~84–145). | Replace the production mapping with the Mayo-specified ZIP-to-county crosswalk. Normalize ZIP to 5 digits; select the county with highest residential-address ratio/share; preserve mapping diagnostics. | Rebuild a record-level mapping table for every protocol-eligible facility and reconcile source count to mapped + explicitly excluded count. | Every eligible source row is assigned a valid current county/county-equivalent FIPS or has an explicit exclusion/manual-review reason. No silent drops. |
| **P0-2** | Eligible facility records disappear before county aggregation | Mayo cohort: 50 states + DC; `Accredited` **or** `Under Review`; cardiac MRAP/CTAP; exclude expired as of May 20, 2026. | Local reconciliation found **2,264 protocol-eligible facility-modality records** in the supplied source but only **2,168 represented in the current county totals**, a **96-record gap**. | Facility filtering/geographic merge in `code/02_build_analytic_dataset.py`, processed `county_analytic_dataset.csv`, source workbook. | Create an explicit facility disposition table before aggregation. Never silently drop unmatched records. Add `source_row_id`, `modality`, `status`, `zip`, `assigned_fips`, `mapping_method`, `included`, `exclusion_reason`, `manual_review`. | Assert `eligible_source_records == mapped_records + explicitly_excluded_records`, separately by modality/status. | Exact reconciliation with no unexplained record loss. |
| **P0-3** | Connecticut facilities are lost because geography vintages do not align | Use current county/county-equivalent geography for national analysis. | Current county master contains the **nine Connecticut planning regions**, but older ZIP/ZCTA mapping produces legacy CT county FIPS. In the current processed data, **all 32 eligible Connecticut records (14 CMR, 18 CCT) are absent**. | `code/02_build_analytic_dataset.py`, county master merge, CT rows in mapping output and `county_analytic_dataset.csv`. | Ensure CT ZIPs map directly to current planning-region FIPS. If HUD-USPS supplies current FIPS, use it; otherwise add an explicit documented conversion/manual resolution layer. | Trace every eligible CT record from source through mapping. | All 32 eligible CT records are mapped to current CT county equivalents or explicitly excluded for a documented protocol reason. |
| **P0-4** | Negative-binomial dispersion is fixed instead of evaluated | Mayo requested **negative-binomial regression**, **dispersion parameter**, and **AIC comparison against Poisson**. | Current audited model uses `statsmodels` GLM Negative Binomial with **`alpha=1.0` fixed**. | `code/05_regression_analysis.py`, `code/12_manuscript_numbers.py`, model helpers used for Tables 2–4. | Add Poisson + estimated-dispersion NB2 + optional fixed-alpha comparison. Save AIC, dispersion, coefficient, IRR, CI, P value, convergence. | Compare Poisson vs estimated NB after the corrected facility dataset is rebuilt. | Primary model is justified by documented fit and the manuscript states the exact implementation. |
| **P0-5** | Accredited-only sensitivity is not a first-class pipeline output | Mayo explicitly requested sensitivity restricted to **`Status == "Accredited"`**. | Primary inclusion of Under Review is correct, but the requested Accredited-only sensitivity is not clearly part of the normal executable/reporting pipeline. | Sensitivity sections of `code/05_regression_analysis.py` and manuscript-number/report scripts. | Add an explicit sensitivity branch that reruns descriptive counts and primary SVI models using `Status == "Accredited"` only. Save results to dedicated CSV/JSON. | Compare primary vs Accredited-only after corrected geographic rebuild. | Sensitivity runs automatically, is saved, and is summarized in manuscript/supplement/repository. |
| **P0-6** | Manuscript ACR source date is wrong | Supplied source was extracted on **May 20, 2026**. | Manuscript says **“accessed 2024.”** | Manuscript Abstract/Methods; README/data dictionary if they also state 2024. | Replace with the actual Mayo extraction date using investigator-approved wording. | Search all project text for inconsistent ACR dates. | One consistent source date everywhere. |
| **P0-7** | Final results must be regenerated after fixing the outcome build | All tables/results must follow from the Mayo-defined cohort and geographic mapping. | Current downstream results reproduce the current processed dataset, but the processed outcome dataset has the geographic reconciliation problem above. | Full pipeline: facility build → analytic dataset → EDI/SVI merges → models → tables → figures → manuscript validation. | Rebuild everything after P0-1 through P0-5. Do not manually patch manuscript numbers. | Full clean run from project inputs and compare every manuscript number to generated outputs. | All manuscript claims match generated outputs exactly or to stated rounding. |

---

# 2. Important point that is **not** an error

## Under Review records belong in the Mayo primary cohort

The Mayo briefing explicitly defines the primary facility inclusion as:

- 50 states + DC
- Cardiac module under MRAP or CTAP
- status **`Accredited` OR `Under Review`**
- not expired as of May 20, 2026

Therefore, **do not remove Under Review facilities from the primary analysis merely because the manuscript uses the shorthand term “accredited.”**

Instead:

1. Keep `Accredited + Under Review` for the Mayo-specified primary cohort.
2. Run the separate **Accredited-only sensitivity**.
3. Clarify manuscript terminology so readers know the primary registry cohort included both statuses at extraction.

The earlier audit interpretation that Under Review records should simply be removed was superseded after the Mayo briefing was reviewed.

---

# 3. Secondary implementation/documentation issues

| Priority | Issue | Mayo requirement | Current implementation/problem | Fix | Validation |
|---|---|---|---|---|---|
| **P1-1** | Population threshold applied more broadly than original briefing | Mayo said counties with **<1,000 adults aged ≥45** should be excluded from **rate calculations**, but retained in count-based analyses. | Current manuscript/pipeline excludes them from negative-binomial regression as well. | Decide with investigators whether this was a later approved analytic change. Preferred: run both versions and document the primary choice. | Compare regression estimates with and without the `<1000` restriction. |
| **P1-2** | SVI quartile deliverable evolved into EDI quintile emphasis | Mayo requested descriptive results by SVI quartile and quartile-regression sensitivity. | Current manuscript emphasizes EDI quintiles in Table 1. | Preserve SVI-quartile descriptive and regression outputs in results/supplement and document why EDI became prominent. | Confirm SVI quartile outputs are reproducible and saved. |
| **P1-3** | Figure structure evolved from Mayo briefing | Mayo originally requested CMR + CCT choropleths. | Current manuscript uses CMR map + regression forest plot. | This may be a valid later decision. Make code, filenames, README, manuscript legend, and final figure match exactly. | One final Figure 1 with panel labels/legend matching. |
| **P1-4** | 3,143 vs 3,144 county count | Briefing anticipated 3,143. Current geography has 3,144 current county/county-equivalent units. | Do **not** force back to 3,143 automatically. | Use current geography if intended; write “counties and county equivalents” and document the change from the initial brief. | 3,144 unique current FIPS, no duplicates, all states/DC represented. |
| **P1-5** | ACS vintage documentation inconsistency | Mayo specified ACS **2019–2023 5-year estimates**. | Audited acquisition code used the 2023 ACS 5-year vintage, while earlier README text referenced 2018–2022. | Standardize to **2019–2023** across code comments, README, data dictionary, manuscript, and manifest. | Search for `2018-2022`, `2019-2023`, and `ACS`; resolve conflicts. |
| **P1-6** | Default run is not fully end-to-end | Mayo requested reproducibility from project inputs. | Default runner reproduces downstream statistics from an existing processed dataset. | Provide one explicit full-build command such as `python code/00_run_all.py --all`. | Fresh checkout/input copy + one full command succeeds without stale outputs. |
| **P1-7** | Silent synthetic fallback data | Production build should use real required sources. | Missing SVI/RUCC/ACS inputs can trigger random proxy values. | Remove silent random fallback from production; fail hard. If demo behavior is needed, require explicit `--demo`. | Remove each required file temporarily and verify clear failure rather than fabricated data. |
| **P1-8** | Environment not sufficiently pinned | Mayo requested reproducible analysis/code archive. | Broad package constraints can lead to future numeric/plot changes. | Add exact environment lock and record Python version. | Clean environment reproduces final outputs. |
| **P1-9** | Source/build integrity checks incomplete | Reproducibility should link raw inputs to outputs. | Pipeline can reuse stale processed files. | Add checksums/data manifest and build metadata. | Final metadata records exact source hashes and code commit. |

---

# 4. Manuscript corrections after the corrected rerun

Do **not** manually update final numerical results until geographic mapping and model specification are resolved.

| Manuscript item | Current wording/value | Required action |
|---|---|---|
| ACR source date | “accessed 2024” | Change to **May 20, 2026** using investigator-approved wording. |
| Facility cohort terminology | Calls all counted records “accredited” | Clarify that Mayo primary cohort included statuses Accredited and Under Review, plus Accredited-only sensitivity. |
| Total CMR/CCT facilities | Current 687 / 1,481 | Replace only with corrected rerun values. |
| Counties with CMR/CCT | Current 289 / 532 | Replace only with corrected rerun values. |
| Counties with neither | Current 2,583 | Replace only with corrected rerun value. |
| Metropolitan percentages | Current 98.1% / 92.4% | Recompute from corrected mapping. |
| Table 1 | Current rurality + EDI quintile results | Rebuild from corrected county dataset. |
| Table 2 | Fixed-alpha NB results | Rebuild after final model-specification decision. |
| Table 3 | RUCC/stratified sensitivities | Rerun after corrected geography. |
| Table 4 | SDI sensitivity | Rerun after corrected geography. |
| Figure 1 | Current panel structure/legend | Regenerate from corrected outputs; one unambiguous final panel structure. |
| Methods terminology | “all 3,144 US counties” | Prefer “3,144 counties and county equivalents” if retaining current geography. |
| Population threshold | `<1000` excluded from regression | Confirm investigator decision and align Methods to actual implementation. |

---

# 5. Required facility-level audit file

Create:

`data/processed/facility_mapping_audit.csv`

Minimum columns:

```text
source_row_id
facility_name
modality
status
expiration_date
state
zip_original
zip5
protocol_eligible
protocol_exclusion_reason
zip_crosswalk_match
assigned_county_fips
assigned_county_name
mapping_share
mapping_method
manual_review
final_included
final_exclusion_reason
```

Required assertions:

```python
assert eligible_source_count == final_included_count + explicit_exclusion_count
assert no_silent_unmatched_records
assert all(final_included_fips_are_valid_current_fips)
assert no_duplicate_source_row_ids_in_final_mapping
```

Also save reconciliation by modality, status, state, mapped/excluded, and mapping method.

---

# 6. Connecticut-specific QA

The supplied project data contain **32 eligible Connecticut facility-modality records**:

- **14 CMR**
- **18 CCT**

The pipeline must not convert Connecticut into zero capacity because old FIPS fail to merge with the nine current planning regions.

Recommended test:

```python
ct = facility_mapping_audit[
    (facility_mapping_audit["state"] == "CT")
    & (facility_mapping_audit["protocol_eligible"])
]

assert len(ct) == 32
assert ct["final_included"].sum() + ct["final_exclusion_reason"].notna().sum() == 32
assert ct.loc[ct["final_included"], "assigned_county_fips"].notna().all()
```

Then compare aggregated CT facility counts to the facility-level audit.

---

# 7. Negative-binomial model correction

The Mayo briefing specifically requested:

- negative-binomial model
- dispersion parameter
- Poisson comparison using AIC

Final code should generate a model-comparison table like:

| Outcome | Model | Dispersion/alpha | AIC | SVI IRR | 95% CI | P | Converged |
|---|---|---:|---:|---:|---|---:|---|
| CMR | Poisson | — | ... | ... | ... | ... | Yes |
| CMR | NB2 estimated | estimated | ... | ... | ... | ... | Yes |
| CMR | NB GLM fixed alpha=1 | 1.0 | ... | ... | ... | ... | Yes |
| CCT | Poisson | — | ... | ... | ... | ... | Yes |
| CCT | NB2 estimated | estimated | ... | ... | ... | ... | Yes |
| CCT | NB GLM fixed alpha=1 | 1.0 | ... | ... | ... | ... | Yes |

**Important:** do not copy diagnostic estimated-dispersion P values from an earlier audit into the manuscript. Re-estimate all models after the facility mapping is corrected.

---

# 8. Accredited-only sensitivity

Primary cohort:

```python
status in ["Accredited", "Under Review"]
```

Sensitivity cohort:

```python
status == "Accredited"
```

Rerun at minimum:

- CMR total
- CCT total
- counties with ≥1 CMR
- counties with ≥1 CCT
- counties with neither
- adjusted/unadjusted SVI models for CMR
- adjusted/unadjusted SVI models for CCT
- metropolitan coefficient where applicable

Save:

`results/accredited_only_sensitivity.csv`

---

# 9. Full end-to-end validation sequence

1. **Freeze inputs** and record hashes.
2. **Validate supplied ACR source extraction** without replacing it with outside data.
3. **Apply Mayo eligibility rules**: 50 states/DC, Accredited or Under Review, intended cardiac MRAP/CTAP cohort, valid as of May 20, 2026.
4. **Apply the Mayo-specified ZIP-to-county linkage**; no silent dropping.
5. **Resolve current FIPS**, especially Connecticut.
6. **Aggregate CMR/CCT facility counts** and reconcile back to facility-level mapping.
7. **Merge population/SVI/RUCC/EDI/SDI**, checking uniqueness/missingness after each merge.
8. **Rebuild EDI** and verify PCA orientation, explained variance, percentile conversion, missingness.
9. **Run descriptives and sensitivities**, including SVI quartiles and Accredited-only.
10. **Resolve count-model specification** with Poisson vs estimated NB comparison.
11. **Generate all tables and figures** from code.
12. **Programmatically validate manuscript claims** against generated results.
13. **Clean the document**: accept/reject tracked changes and remove author notes/comments.

---

# 10. Automated tests to add

```python
def test_source_record_reconciliation():
    assert eligible == mapped + explicitly_excluded

def test_no_silent_unmatched_facilities():
    assert silent_unmatched == 0

def test_valid_current_fips():
    assert invalid_final_fips == 0

def test_connecticut_reconciliation():
    assert eligible_ct_records == resolved_ct_records

def test_unique_county_rows():
    assert county_dataset["fips"].is_unique

def test_primary_status_definition():
    assert set(primary_source["Status"]).issubset({"Accredited", "Under Review"})

def test_accredited_only_sensitivity_exists():
    assert accredited_only_results_file.exists()

def test_no_random_production_fallback():
    # Missing required source must raise an error.
    ...

def test_model_comparison_output():
    # Poisson and estimated NB output must exist.
    ...

def test_manuscript_numbers():
    # Every numeric manuscript claim must match generated results.
    ...
```

---

# 11. Definition of done

- [ ] Mayo-specified ZIP-to-county method implemented.
- [ ] Every protocol-eligible facility accounted for.
- [ ] No silent record drops.
- [ ] Connecticut reconciled to current county-equivalent geography.
- [ ] Facility-level counts reconcile exactly to county totals.
- [ ] Primary cohort retains `Accredited + Under Review` as Mayo specified.
- [ ] Accredited-only sensitivity automatically runs and is saved.
- [ ] Poisson-vs-NB AIC comparison and dispersion estimate generated.
- [ ] Final regression choice documented in Methods.
- [ ] Population-threshold behavior explicitly decided/documented.
- [ ] ACS vintage consistently documented as 2019–2023.
- [ ] Full pipeline runs from supplied inputs without stale processed files.
- [ ] Required missing inputs cannot silently trigger random proxy data.
- [ ] Exact environment pinned.
- [ ] All tables and figures regenerated.
- [ ] Every manuscript number programmatically validated.
- [ ] ACR extraction date corrected to May 20, 2026.
- [ ] Final manuscript has no unresolved tracked changes, duplicate text, comments, or author notes.
- [ ] Final figure panels exactly match the legend and repository output.

---

# 12. Prompt to give the coding LLM

> Treat `Project_Briefing_Shiloh.docx` as the original project specification and the supplied Mayo Excel files as the source facility data. Do not fetch replacement facility data or reinterpret the project using outside sources. Review the current repository against this implementation plan. Before editing, verify every cited code path against the current repository because line numbers may have changed. Fix P0 issues first. Preserve the Mayo primary inclusion of Accredited + Under Review. Implement the Accredited-only sensitivity separately. Do not manually patch manuscript numbers. Rebuild the facility mapping, county dataset, models, tables, figures, and manuscript validation from source, and produce a final before/after reconciliation report showing every change.

---

## Final interpretation

The current project is stronger downstream than upstream:

- statistical calculations largely reproduce the current processed dataset;
- the main unresolved problem is constructing the facility outcome dataset according to the Mayo geographic specification;
- the principal statistical specification issue is fixed negative-binomial `alpha=1.0` despite Mayo's request to evaluate dispersion and compare against Poisson;
- Under Review inclusion in the primary cohort is intentional and correct according to Mayo.

Correct the source-to-county mapping and model specification first, then rerun all downstream results before finalizing the manuscript.
