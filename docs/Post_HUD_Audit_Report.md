# Post-HUD Audit Report

**Date:** 2026-08-07 · **Commit audited:** `dcd216f` · **Branch:** `validation`

Every number below was recomputed independently from `data/download.xlsx`, the
HUD Q1 2026 crosswalk, and the corrected analytic dataset. Nothing was taken
from the manuscript or from prior audit summaries. No external data was used.

Requirements are labelled **[BRIEFING]** where the Mayo briefing states them
explicitly, **[LATER]** where they are a subsequent investigator/analysis
decision, **[IMPL]** for implementation details, and **[REC]** for my own
recommendations.

---

## A. Executive summary

**The dataset is now source-complete.** All 2,264 protocol-eligible
facility-modality records map to a valid current county FIPS. Zero silent loss,
zero unresolved. Connecticut is fully restored (14 CMR, 18 CCT) and now resolves
through the ordinary HUD path with no special-case table.

**The geographic correction is verified and correct.** Multi-county ZIPs are
assigned on `RES_RATIO` exactly as the briefing requires; I re-derived the
assignment for all 436 affected records independently and found zero
disagreement.

**The analysis is not yet ready for manuscript finalization.** Three things
block it:

1. **The validation gate gives false assurance.** It reports 124 checks, 0
   mismatches, yet the manuscript still contains **eight stale pre-HUD values in
   prose**, including `2,583` counties, `92.4%`, a pre-HUD confidence interval,
   and both Spearman P values. The gate asserts that the *correct* value appears
   somewhere; it never asserts that a *contradicting* value is absent, and it
   does not check prose restatements of table values, Spearman results, or the
   Take-Home Points. This is the most important finding in the audit.
2. **The negative-binomial dispersion specification is unresolved** and it
   changes a reported conclusion (SVI–CCT). This is an investigator decision,
   presented in §F, not made here.
3. **The manuscript says "SVI was not associated with capacity for either
   modality"** in both the summary and Results. With adjusted SVI–CCT at
   P = 0.059 under the primary model, that is a categorical null claim the data
   do not support.

The EDI quintile pattern is **not monotonic**, and after the HUD correction it
has **two** order violations rather than one — Q5 is no longer the lowest
quintile. Wording must change accordingly.

---

## B. Mayo requirement vs implementation

| Mayo requirement | Current implementation | Status | Evidence | Issue | Required fix | Priority |
|---|---|---|---|---|---|---|
| HUD-USPS ZIP–County Q1 2026 **[BRIEFING §2.2]** | `01c_fetch_hud_crosswalk.py`; 54,562 rows | **PASS** | §D | — | — | — |
| Multi-county ZIP → largest **residential address share** **[BRIEFING §2.2]** | max `RES_RATIO` in `facility_mapping.load_crosswalk` | **PASS** | 436 records re-derived, 0 disagreements | 1 ZIP ties at RES_RATIO 0.0 | Define a tie-break | Low |
| 50 states + DC; Accredited **or** Under Review; MRAP/CTAP cardiac; not expired 2026-05-20 **[BRIEFING §3.1]** | `facility_mapping.classify_eligibility` | **PASS** | §C — 2,264 reproduced exactly | — | — | — |
| Every record accounted for, no silent drops **[BRIEFING §4.5 implied]** | `facility_mapping_audit.csv` + assertions | **PASS** | §C invariant holds | — | — | — |
| Counties <1,000 adults ≥45: **keep in count analyses**, exclude from rates **[BRIEFING §3.1]** | Excluded from regressions too | **INVESTIGATOR DECISION** | §H | Deviates from briefing text | Decide; effect is negligible | Medium |
| Descriptives by SVI quartile **[BRIEFING §3.3]** | Table 1 is by SVI quartile | **PASS** | `table1_publication.txt` | — | — | — |
| Spearman rate vs SVI, CMR and CCT **[BRIEFING §3.3]** | Present | **FAIL** | §I | Manuscript P values are pre-HUD | Regenerate | **High** |
| NB regression, per-10-percentile SVI, log-pop offset, IRR + 95% CI **[BRIEFING §3.3]** | Implemented | **PASS** | §F | — | — | — |
| **Dispersion parameter; AIC vs Poisson** **[BRIEFING §3.3]** | `13_model_specification.py` | **INVESTIGATOR DECISION** | §F | α fixed at 1.0 is not data-supported | Choose specification | **BLOCKER** |
| Sensitivity: Accredited-only **[BRIEFING §3.4]** | `14_accredited_only_sensitivity.py` | **PASS** | §G | — | — | — |
| Sensitivity: SVI quartile dummies **[BRIEFING §3.4]** | `05_regression_analysis.py:181` | **PASS WITH DOCUMENTATION FIX** | §I | Not surfaced in manuscript/supplement | Add to supplement | Medium |
| Sensitivity: metro-stratified **[BRIEFING §3.4]** | Present in EDI models | **PASS** | Supplementary table | — | — | — |
| Figure 1: two-panel choropleth, A=CMR, B=CCT **[BRIEFING §4.2]** | A=CMR map, B=forest plot | **INVESTIGATOR DECISION** | §B note | Deliberate later change | Confirm intent | Medium |
| ACS 2019–2023 **[BRIEFING §2.2]** | Consistent everywhere | **PASS** | grep clean | — | — | — |
| ACR extraction date 2026-05-20 **[BRIEFING §2.1]** | Manuscript says "extracted May 20, 2026" | **PASS** | §I | — | — | — |
| Under Review in primary cohort **[BRIEFING §3.1]** | Implemented correctly | **PASS WITH DOCUMENTATION FIX** | manuscript never says "Under Review" | Not disclosed to readers | Add one sentence | **High** |
| README documents versions, access dates, manual decisions **[BRIEFING §4.5]** | README updated | **PASS WITH DOCUMENTATION FIX** | — | Tie-break + override not documented | Add | Low |
| Production must not fabricate data **[REC]** | `require_input` + `PIPELINE_DEMO` | **PASS** | §15 | — | — | — |
| Environment lock, checksums, manifest **[REC]** | None | **FAIL** | 0 pinned deps | Not reproducible long-term | Add | Medium |

**Figure note:** the briefing asked for Panel A = CMR choropleth, Panel B = CCT
choropleth. The manuscript uses Panel A = CMR choropleth, Panel B = forest plot.
`figure1_choropleth.*` still contains the two-panel version the briefing
specified, so both exist. The CCT choropleth panel is generated but unused.

---

## C. Facility reconciliation

Recomputed from `download.xlsx`, independent of the pipeline.

| Stage | CMR | CCT | Total |
|---|---:|---:|---:|
| Raw cardiac source (MRAP/CTAP with Cardiac module) | 725 | 1,548 | 2,273 |
| less: status not Accredited/Under Review | 0 | 0 | 0 |
| less: expired before 2026-05-20 | 0 | 1 | 1 |
| less: outside 50 states + DC (GU, PR) | 3 | 5 | 8 |
| **Protocol-eligible** | **722** | **1,542** | **2,264** |
| Mapped via `hud_res_ratio` | 721 | 1,541 | 2,262 |
| Manually resolved (`manual_zip_override`) | 1 | 1 | 2 |
| `ct_town_manual` (no longer used) | 0 | 0 | 0 |
| **Unresolved** | **0** | **0** | **0** |
| **Final included** | **722** | **1,542** | **2,264** |
| County dataset totals | 722 | 1,542 | 2,264 |

**Invariant:** eligible (2,264) = included (2,264) + unresolved (0). **Holds.**
Silent losses: **0**. The raw 725/1,548 split matches the briefing §2.1 exactly.

**The one manual resolution:** ZIP 98415, Tacoma WA — Tacoma General / Mary
Bridge Children's Hospitals, one CMR and one CCT record. A unique hospital ZIP
present in no crosswalk of any vintage. Every other Tacoma ZIP maps to Pierce
County (53053) at RES_RATIO 1.0. Recorded as `manual_zip_override` with
`manual_review = True`.

---

## D. HUD mapping QA

| Check | Result |
|---|---|
| Crosswalk rows / distinct ZIPs | 54,562 / 39,484 |
| Multi-county ZIPs in crosswalk | 11,372 |
| Rows with missing `RES_RATIO` | **0** |
| Facility records on multi-county ZIPs | **436** |
| Assignments disagreeing with max-`RES_RATIO` | **0** |
| Ties at maximum `RES_RATIO` among used ZIPs | **1** |
| Records where the old land-area rule gives a different county | **42** |
| Eligible records with unresolved/invalid FIPS | **0** |

**The selection field is correct.** `load_crosswalk` sorts on `RES_RATIO`
descending and keeps the first row per ZIP — the residential-address share, not
land area, not total ratio, not alphabetical. I re-derived the mapping for all
436 multi-county facility records and found zero disagreement.

**The one tie is a genuine gap [REC].** ZIP 22908 (UVA Health System,
Charlottesville VA, 3 records) has `RES_RATIO = 0.0` for **both** candidate
counties — an institutional ZIP with no residential addresses. The
largest-residential-share rule is undefined here, and the current tie-break is
sort order, which picked Albemarle County (51003). By `TOT_RATIO` the split is
Charlottesville city 51540 = 0.75 versus Albemarle 51003 = 0.25, so total
addresses would put it in Charlottesville city. Affects 3 of 2,264 records
(0.13%) and does not change any conclusion. Recommend an explicit documented
tie-break: fall back to `TOT_RATIO`, then to the lower FIPS.

**Automated checks added** — see `tests/test_pipeline.py`.

---

## E. Before-HUD vs after-HUD

| Quantity | Original (Census ZCTA) | CT fix only | **After HUD** |
|---|---:|---:|---:|
| CMR facilities | 687 | 701 | **722** |
| CCT facilities | 1,481 | 1,499 | **1,542** |
| Counties ≥1 CMR | 289 | 293 | **300** |
| Counties ≥1 CCT | 532 | 538 | **552** |
| Counties with neither | 2,583 (82.2%) | 2,577 (82.0%) | **2,570 (81.7%)** |
| % CMR in metro | 98.1% | 98.1% | **98.1%** |
| % CCT in metro | 92.4% | 92.5% | **92.5%** |
| EDI Q1 mean CMR rate | 0.2715 | — | **0.2619** |
| EDI Q5 mean CMR rate | 0.0622 | — | **0.0902** |
| Q1/Q5 ratio | 4.37 | — | **2.90** |
| SVI–CMR adjusted IRR (α=1) | 1.00 (0.95–1.04) | 1.00 (0.96–1.04) | **1.00 (0.96–1.05)** P 0.852 |
| SVI–CCT adjusted IRR (α=1) | 1.03 (0.99–1.06) P 0.127 | 1.03 (0.99–1.06) P 0.108 | **1.03 (1.00–1.07) P 0.059** |
| EDI–CMR unadjusted IRR (α=1) | 0.94 (0.90–0.98) P 0.002 | — | **0.94 (0.91–0.98) P 0.004** |
| EDI–CMR adjusted IRR (α=1) | 0.98 (0.94–1.03) | — | **0.99 (0.95–1.03) P 0.637** |

**What the geographic correction changed scientifically:** the headline
metropolitan-concentration finding is unchanged and, if anything, slightly
firmer. The EDI extreme-quintile contrast weakened substantially (4.4→2.9-fold).
SVI–CCT moved from clearly non-significant to borderline (P 0.127 → 0.059).

### EDI quintiles, all five values (n = 3,029)

| Quintile | Mean CMR rate | Mean CCT rate | Pooled CMR rate | % counties zero CMR |
|---|---:|---:|---:|---:|
| Q1 (least deprived) | 0.2619 | 0.6030 | 0.5583 | 82.0% |
| Q2 | 0.1613 | 0.4129 | 0.4536 | 89.1% |
| Q3 | 0.1850 | 0.5393 | 0.5989 | 89.3% |
| Q4 | **0.0812** | 0.6174 | 0.4263 | 93.9% |
| Q5 (most deprived) | 0.0902 | 0.2996 | 0.3940 | 96.9% |

**Q1 > Q2 > Q3 > Q4 > Q5 is FALSE.** Two violations: Q3 > Q2 (+0.024) and
**Q5 > Q4 (+0.009)**. The minimum is Q4, not Q5. Kruskal-Wallis P = 1.0e-17.
Q1/Q5 = 2.904 (unweighted county means); population-weighted it is 1.42.

---

## F. Final model comparison

All models adjusted for metropolitan status, log(adults ≥45) offset,
index per 10 points. Recomputed independently.

| Outcome | Pred | Model | α | N | IRR | 95% CI | P | logLik | AIC | BIC | Conv |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| CMR | SVI | Poisson | — | 3038 | 0.999 | 0.971–1.027 | 0.923 | −915.9 | 1837.8 | 1855.9 | Y |
| CMR | SVI | **NB2, α estimated** | 0.439 | 3038 | 1.003 | 0.968–1.040 | 0.856 | −886.3 | **1780.6** | **1804.7** | Y |
| CMR | SVI | NB GLM, α = 1.0 | 1.0 | 3038 | 1.004 | 0.963–1.047 | 0.852 | −895.8 | 1797.6 | 1815.7 | Y |
| CCT | SVI | Poisson | — | 3038 | 1.035 | 1.015–1.055 | **0.0006** | −1513.5 | 3033.0 | 3051.0 | Y |
| CCT | SVI | **NB2, α estimated** | 0.182 | 3038 | 1.033 | 1.009–1.058 | **0.0078** | −1479.0 | **2965.9** | **2990.0** | Y |
| CCT | SVI | NB GLM, α = 1.0 | 1.0 | 3038 | 1.031 | 0.999–1.065 | 0.0594 | −1538.3 | 3082.6 | 3100.7 | Y |
| CMR | EDI | Poisson | — | 3029 | 0.995 | 0.968–1.023 | 0.727 | −903.6 | 1813.2 | 1831.2 | Y |
| CMR | EDI | **NB2, α estimated** | 0.440 | 3029 | 0.993 | 0.958–1.029 | 0.698 | −874.4 | **1756.8** | **1780.8** | Y |
| CMR | EDI | NB GLM, α = 1.0 | 1.0 | 3029 | 0.990 | 0.948–1.033 | 0.637 | −883.6 | 1773.3 | 1791.3 | Y |
| CCT | EDI | Poisson | — | 3029 | 1.022 | 1.003–1.041 | **0.023** | −1505.8 | 3017.6 | 3035.6 | Y |
| CCT | EDI | **NB2, α estimated** | 0.192 | 3029 | 1.016 | 0.992–1.041 | 0.188 | −1469.6 | **2947.1** | **2971.2** | Y |
| CCT | EDI | NB GLM, α = 1.0 | 1.0 | 3029 | 1.010 | 0.977–1.043 | 0.567 | −1525.6 | 3057.1 | 3075.2 | Y |

### Dispersion diagnostics

| Model | Poisson Pearson/df | Deviance/df | var/mean of y | LR (NB2 vs Poisson) | P |
|---|---:|---:|---:|---:|---:|
| CMR SVI | 0.592 | 0.353 | 4.83 | 59.2 | 7.0e-15 |
| CCT SVI | 0.741 | 0.535 | 8.92 | 69.0 | 4.8e-17 |
| CMR EDI | 0.590 | 0.350 | 4.84 | 58.4 | 1.1e-14 |
| CCT EDI | 0.735 | 0.537 | 8.99 | 72.4 | 8.7e-18 |

**A. Which specification is better supported?** NB2 with estimated dispersion,
unambiguously. It has the lowest AIC **and** the lowest BIC in all four models,
by 17–117 AIC units. All models converged.

**B. How far is estimated α from 1.0?** Far. α̂ = 0.18–0.44, i.e. 1.0 is roughly
2.3× to 5.5× the supported value. Fixing α too high inflates standard errors and
biases toward the null.

**C. Does Poisson show overdispersion?** Yes. The likelihood-ratio test of NB2
against Poisson rejects decisively in all four models (P < 1e-14), and the
marginal variance/mean ratio of the outcome is 4.8–9.0. Note the Poisson
Pearson/df statistic is **below 1** (0.59–0.74) and is misleading here because
the counts are sparse and zero-inflated — do not cite it as evidence against
overdispersion.

**D. Does the conclusion change across specifications?** Yes, for **SVI–CCT**:
P = 0.0006 (Poisson), 0.0078 (NB2 estimated), 0.059 (α = 1.0). Also for
**EDI–CCT**: significant under Poisson only. CMR conclusions are stable under
all three.

**E. Is α = 1.0 justified by the data?** No. It is an implementation assumption
(`NegativeBinomial(alpha=1.0)` is the statsmodels default), not an estimate. The
briefing asked for the dispersion parameter to be reported, which implies
estimating it.

**F. Which most directly fulfils the briefing?** NB2 with estimated dispersion,
reported alongside the Poisson AIC comparison. The briefing asks for "dispersion
parameter; compare AIC against Poisson model to justify negative binomial" —
that is an instruction to estimate, not to fix.

**No decision is made here.** See §J.

---

## G. Accredited-only sensitivity (α = 1.0, matching current primary)

| Quantity | Primary (Accredited + Under Review) | Accredited only |
|---|---:|---:|
| CMR facilities | 722 | 716 |
| CCT facilities | 1,542 | 1,526 |
| Counties ≥1 CMR | 300 | 299 |
| Counties ≥1 CCT | 552 | 552 |
| Counties with neither | 2,570 | 2,570 |

| Model | Primary IRR (95% CI), P | Accredited-only IRR (95% CI), P |
|---|---|---|
| SVI–CMR unadjusted | 0.998 (0.959–1.038), 0.914 | 0.997 (0.958–1.038), 0.892 |
| SVI–CMR adjusted | 1.004 (0.963–1.047), 0.852 | 1.003 (0.962–1.046), 0.877 |
| SVI–CCT unadjusted | 1.025 (0.994–1.058), 0.114 | 1.026 (0.994–1.058), 0.112 |
| SVI–CCT adjusted | 1.031 (0.999–1.065), 0.059 | 1.032 (0.999–1.066), 0.058 |
| EDI–CMR unadjusted | 0.943 (0.906–0.982), **0.004** | 0.943 (0.906–0.982), **0.004** |
| EDI–CMR adjusted | 0.990 (0.948–1.033), 0.637 | 0.989 (0.948–1.033), 0.631 |
| EDI–CCT unadjusted | 0.981 (0.951–1.011), 0.209 | 0.981 (0.952–1.012), 0.231 |
| EDI–CCT adjusted | 1.010 (0.977–1.043), 0.567 | 1.010 (0.978–1.044), 0.540 |

**No qualitative conclusion changes.** Saved to
`output/results/accredited_only_sensitivity.csv`.

---

## H. Population threshold sensitivity (<1,000 adults ≥45)

**What the code does [IMPL]:** `rate_excluded == 0` filters the 106 small
counties out of *both* rate calculations and regressions.

**What the briefing says [BRIEFING §3.1]:** those counties are "kept in
count-based analyses, excluded from per-capita rates."

| Model | Current (≥1,000 only) | All counties with pop > 0 |
|---|---|---|
| SVI–CMR adjusted | n 3038 · 1.004 (0.963–1.047) P 0.852 | n 3144 · 1.004 (0.963–1.047) P 0.850 |
| SVI–CCT adjusted | n 3038 · 1.031 (0.999–1.065) P 0.059 | n 3144 · 1.032 (0.999–1.065) P 0.058 |
| EDI–CMR adjusted | n 3029 · 0.990 (0.948–1.033) P 0.637 | n 3134 · 0.990 (0.948–1.033) P 0.638 |
| EDI–CCT adjusted | n 3029 · 1.010 (0.977–1.043) P 0.567 | n 3134 · 1.010 (0.977–1.044) P 0.562 |

**Immaterial.** No IRR moves by more than 0.001, no P value by more than 0.005.
The 106 counties contribute almost no population and almost no facilities. This
is a documentation issue, not a scientific one — but the Methods currently
describe a restriction that departs from the briefing without saying so.

---

## I. Manuscript claim-by-claim check

**The validation gate reports 124 checks, 0 mismatches. It is wrong to rely on
that.** `ck_prose` in `12_manuscript_numbers.py` uses `re.search` over the whole
prose: it confirms the correct value appears *somewhere* and never checks that a
contradicting value is absent. Table cells are checked properly; prose
restatements, Spearman results, and the Take-Home Points are not.

| Location | Claim | Current text | Corrected result | Assessment | Recommended replacement |
|---|---|---|---|---|---|
| Take-Home / summary | Counties with neither | "2,583 of 3,144" | 2,570 | **STALE** | "2,570 of 3,144" |
| Summary paragraph | % CCT in metro | "92.4%" | 92.5% | **STALE** | "92.5%" |
| Results | SVI–CMR unadjusted | "IRR was 0.99 (95% CI, 0.95-1.03; P = 0.914)" | 1.00 (0.96–1.04), P 0.914 | **STALE CI** | "1.00 (95% CI, 0.96–1.04; P = 0.914)" |
| Results | Spearman CMR | "ρ = 0.01, P = 0.665" | ρ = 0.015, P = 0.416 | **STALE P** | "ρ = 0.01, P = 0.42" |
| Results | Spearman CCT | "ρ = 0.02, P = 0.268" | ρ = 0.031, P = 0.087 | **STALE both** | "ρ = 0.03, P = 0.09" |
| Results | Ordinal-RUCC EDI CMR | "IRR 0.99, 95% CI, 0.95-1.04; P = 0.986" | verify against regenerated output | **VERIFY** | regenerate |
| Results | SDI unadjusted CMR | "IRR 1.01; 95% CI, 0.97-1.05; P = 0.466" | verify | **VERIFY** | regenerate |
| Summary + Results | "SVI was not associated with capacity for either modality" | categorical | SVI–CCT adjusted P = 0.059 | **OVERSTATES NULL** | see below |
| Results | EDI quintile sentence | "declined across EDI quintiles … 0.26 … 0.09 … 2.9-fold difference" | Q4 < Q5 | **IMPRECISE** | see below |
| Methods | Cohort statuses | never mentions "Under Review" | 23 records included | **OMISSION** | see below |
| Methods | Software | "SciPy 1.13" | correct | PASS | — |
| Methods | Extraction date | "extracted May 20, 2026" | correct | PASS | — |
| Table 1 | SVI quartile strata | matches generated output | 722 / 1,542 / 300 / 552 | PASS | — |

### Recommended wording

**SVI–CCT (§9).** Replace the categorical claim with:

> "In the primary fixed-dispersion model, SVI was not associated with cardiac MR
> capacity (IRR 1.00; 95% CI, 0.96–1.05; P = 0.85). For cardiac CT, the
> association did not reach conventional statistical significance (IRR 1.03; 95%
> CI, 1.00–1.07; P = 0.059). This result was sensitive to the negative binomial
> dispersion specification: with the dispersion parameter estimated from the data
> rather than fixed, the same association was statistically significant (IRR
> 1.03; 95% CI, 1.01–1.06; P = 0.008)."

**EDI quintiles (§5).** The pattern is not monotonic and Q5 is not the minimum:

> "Mean county-level cardiac MR capacity was higher in the least-deprived than in
> the most-deprived EDI quintile (0.26 versus 0.09 facilities per 100,000 adults
> aged ≥45 years), an approximately 2.9-fold difference between the extreme
> quintiles (Kruskal-Wallis P < 0.001). The pattern across intermediate quintiles
> was not monotonic."

**Cohort disclosure (§6).** Add to Methods:

> "Facilities listed by the ACR as Accredited or Under Review at the May 20, 2026
> extraction were included in the primary registry cohort (2,250 Accredited and
> 23 Under Review). A sensitivity analysis restricted to Accredited facilities
> only yielded materially identical results."

**Do not** change the primary cohort to Accredited-only. The briefing specifies
both statuses.

---

## J. Remaining investigator decisions

Separated from coding errors, which have all been fixed.

1. **Negative-binomial dispersion specification** — genuine scientific decision.
   Changes the SVI–CCT conclusion. See §F and the closing section.
2. **Whether <1,000-population counties stay out of the count regressions** —
   departs from the briefing, but the effect is immaterial (§H). Simplest fix is
   a Methods sentence.
3. **SVI quartile regression placement** — it exists and is reproducible
   (`05_regression_analysis.py:181`) but is not in the manuscript or supplement.
   Briefing §3.4 requested it.
4. **Figure structure** — briefing wanted A = CMR map, B = CCT map; manuscript
   uses A = CMR map, B = forest plot. The two-panel version still generates.

### Coding/documentation items I did *not* change, pending approval
- ZIP 22908 tie-break (3 records, no conclusion impact).
- The eight stale prose values — these require a manuscript revision round, and
  one of them depends on decision 1.

---

## K. Submission-readiness checklist

- [x] All 2,264 eligible records mapped; zero silent loss
- [x] HUD Q1 2026 crosswalk, residential-share rule verified independently
- [x] Connecticut reconciled (14 CMR / 18 CCT), no special-case table needed
- [x] Every included FIPS valid in current geography
- [x] Under Review retained in primary cohort
- [x] Accredited-only sensitivity run and saved
- [x] Poisson vs NB comparison generated with AIC, BIC, logLik, α, convergence
- [x] ACR extraction date corrected to 2026-05-20
- [x] ACS vintage consistent at 2019–2023
- [x] Production fails hard on missing inputs; demo behind `PIPELINE_DEMO`
- [x] Automated tests (15) covering reconciliation, CT, HUD rule, fallbacks
- [ ] **Validation gate strengthened to catch contradicting prose values**
- [ ] **Eight stale prose values corrected**
- [ ] **Dispersion specification decided and Methods updated**
- [ ] **SVI–CCT categorical null language qualified**
- [ ] **EDI quintile sentence corrected for non-monotonicity**
- [ ] Under Review disclosed in Methods
- [ ] SVI quartile regression placed in supplement
- [ ] Figure structure confirmed
- [ ] Environment pinned; input checksums and data manifest added
- [ ] Tracked changes accepted and manuscript cleaned for submission
