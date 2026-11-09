#!/usr/bin/env python3
"""
revise_manuscript_r1.py
=======================
Applies the first-round peer-review revision to a manuscript as tracked
changes, attributed to one author and date.

Every number this round adds to the text is formatted here from the generated
results (output/results/reviewer_analyses.json and output/validation/
manuscript_numbers.json); none is typed by hand. The gate
(code/12_manuscript_numbers.py) then checks each one against the same files.

Each edit carries the task ID it answers (R1-01 ... R2-05, E-04, E-05) and a
rationale. The script writes a change log of every edit applied.

Run
    python tools/revise_manuscript_r1.py IN.docx OUT.docx [--log CHANGES.csv]

Idempotent: an edit whose target is already gone, or whose new text is already
present, is reported and skipped.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docx_tracked import AnchorNotFound, TrackedDocument  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTHOR = "Abdul Razak"
DATE = "2026-11-07T12:00:00Z"


# ------------------------------------------------------------------ numbers
def load_numbers():
    with open(os.path.join(BASE_DIR, "output", "results", "reviewer_analyses.json")) as f:
        rv = json.load(f)
    with open(os.path.join(BASE_DIR, "output", "validation", "manuscript_numbers.json")) as f:
        mn = json.load(f)
    return rv, mn


def fe(e, p=True):
    t = f"IRR {e['irr']:.2f}; 95% CI, {e['ci_low']:.2f}-{e['ci_high']:.2f}"
    if p:
        t += "; P < 0.001" if e["p"] < 0.001 else f"; P = {e['p']:.3f}"
    return t


def cell_est(e):
    return f"{e['irr']:.2f} ({e['ci_low']:.2f}-{e['ci_high']:.2f})"


def cell_p(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# -------------------------------------------------------------------- edits
def E(task, kind, why, **kw):
    return dict(task=task, kind=kind, why=why, **kw)


def build_edits(rv, mn):
    W, S, M, U, P = (rv["R1-02_weighting"], rv["R2-03_strata"], rv["R2-02_multiplicity"],
                     rv["R1-04_urban_core"], rv["R2-01_pca"])
    T1, D = mn["table1"], mn["descriptives"]
    rates, exc = W["descriptive"]["rates"], W["descriptive"]["excluded"]
    wm = W["models"]
    tests = {t["test"]: t for t in M["tests"]}
    nm, det = S["strata"]["EDI_CMR_nonmetro"], S["detail"]["EDI_CMR_nonmetro"]
    inter = S["interaction"]["EDI_CMR"]
    um, th, dsc = U["models"], U["themes"], U["descriptive"]
    n_ext = M["families"]["extended"]["n_tests"]
    n_prim = M["families"]["primary"]["n_tests"]
    sc = tests["SVI-CCT, adjusted for metropolitan status (Table 2)"]
    sd = tests["SDI-CMR, adjusted for metropolitan status (Figure 2)"]
    lo_l, hi_l = min(P["pc1_loadings"].values()), max(P["pc1_loadings"].values())
    words = {1: "one", 2: "two", 3: "three", 4: "four"}

    ed = []
    # ---------------------------------------------------------------- Abstract
    ed.append(E("E-04", "replace_all", "Estimate punctuation standardized to 'IRR x; 95% CI, a-b' "
                "throughout; word count unchanged.",
                loc="Results: We identified", old=", 95% CI ", new="; 95% CI, "))

    # ------------------------------------------------------------ Introduction
    ed += [
        E("E-04", "replace", "The MIPPA accreditation requirement is section 135(a) "
          "(CMS; reference 2 already cites section 135(a)).",
          loc="Medicare Improvements for Patients and Providers Act of 2008, nonhospital",
          old="section 145(a)", new="section 135(a)"),
        E("E-04", "replace", "References renumbered in order of first citation.",
          loc="Medicare Improvements for Patients and Providers Act of 2008, nonhospital",
          old="January 1, 2012 (6)", new="January 1, 2012 (2)"),
        E("E-04", "replace", "References renumbered.",
          loc="Medicare Improvements for Patients and Providers Act of 2008, nonhospital",
          old="(SVI) (2), but", new="(SVI) (3), but"),
        E("E-04", "replace", "References renumbered.",
          loc="Medicare Improvements for Patients and Providers Act of 2008, nonhospital",
          old="survey and claims data (7-9)", new="survey and claims data (4-6)"),
        E("E-04", "replace", "References renumbered.",
          loc="Medicare Improvements for Patients and Providers Act of 2008, nonhospital",
          old="facilities more broadly (4,10)", new="facilities more broadly (7,8)"),
        E("R1-03", "replace", "Binary RUCC classification is metropolitan/nonmetropolitan.",
          loc="Medicare Improvements for Patients and Providers Act of 2008, nonhospital",
          old="metropolitan-rural gradient", new="metropolitan-nonmetropolitan gradient"),
    ]

    # ------------------------------------------------------------- Methods 1
    loc = "We conducted a cross-sectional ecologic analysis of all 3,144 US counties"
    ed += [
        E("R1-01", "replace", "Sensitivity finding removed from Methods (now reported in Results); "
          "cohort definition moved after the registry is introduced; spacing errors corrected.",
          loc=loc, old=".  Facilities listed by the ACR as Accredited or Under Review at the "
          "extraction date were included in the primary registry cohort (2,242 and 22 "
          "facility-modality records, respectively); a sensitivity analysis restricted to "
          "Accredited facilities yielded the same qualitative conclusions.Accredited CMR",
          new=". Accredited CMR"),
        E("R1-01", "insert_after", "Cohort definition retained in Methods without its result.",
          loc=loc, anchor="Federal Information Processing Standards codes.",
          text=" Facilities listed as Accredited or Under Review at the extraction date formed "
               "the primary registry cohort (2,242 and 22 facility-modality records, respectively)."),
        E("E-04", "replace", "References renumbered.", loc=loc,
          old="accreditation requirement (6).", new="accreditation requirement (2)."),
        E("R1-02", "replace", "States the number excluded and adds pooled rates, which need no "
          "exclusion.", loc=loc,
          old="counties with fewer than 1,000 eligible adults were excluded from per-capita rate "
              "calculations.",
          new=f"the {exc['n']} counties with fewer than 1,000 eligible adults were excluded from "
              f"county-level rate calculations; pooled rates (total facilities divided by total "
              f"eligible adults, equivalent to population-weighted mean county rates), which "
              f"require no exclusion, were also calculated."),
        E("R1-02", "replace", "Clarifies that all counties are in the count models.", loc=loc,
          old="They were retained in the count regressions", new="All counties were retained in "
              "the count regressions"),
        E("R1-01", "delete", "Sensitivity result moved to Results with its verified size.", loc=loc,
          span="; restricting the regressions to the same threshold was examined as a sensitivity "
               "analysis and did not alter any estimate materially"),
        E("E-05", "insert_after", "Points to the aggregate population-characteristics table.",
          loc=loc, anchor="n = 3,134 for EDI models).",
          text=" County population characteristics from the SVI 2022 and County Health Rankings "
               "2024 are summarized in Supplementary Table S1; no patient-level data were used."),
    ]

    # ------------------------------------------------------------- Methods 2
    loc = "Area disadvantage was measured with two complementary indices"
    ed += [
        E("E-04", "replace", "Stray space before comma; references renumbered.", loc=loc,
          old="housing/transportation) , originally developed for disaster-preparedness planning (2).",
          new="housing/transportation), originally developed for disaster-preparedness planning (3)."),
        E("E-04", "replace", "References renumbered.", loc=loc,
          old="area deprivation measures (3).", new="area deprivation measures (9)."),
        E("E-04", "replace", "References renumbered.", loc=loc,
          old="Area Deprivation Index of Singh (3) and the University of Wisconsin Neighborhood Atlas (11)",
          new="Area Deprivation Index of Singh (9) and the University of Wisconsin Neighborhood Atlas (10)"),
        E("R1-01", "replace", "Variance explained is a result; moved to Results with the full PCA "
          "(R2-01). Standardization stated for reproducibility.", loc=loc,
          old="The first principal component explained 58.7% of variance; scores were converted to "
              "national percentiles (0-100).",
          new="Indicators were standardized, and scores on the first principal component were "
              "converted to national percentiles (0-100)."),
    ]

    # ------------------------------------------------------------- Methods 3
    loc = "Facility counts were modeled with negative binomial (NB2) regression"
    ed += [
        E("R1-03", "replace", "RUCC operational definitions stated, with the terminology used "
          "throughout (USDA ERS documentation, reference 11).", loc=loc,
          old="Metropolitan versus nonmetropolitan status used the US Department of Agriculture "
              "Rural-Urban Continuum Codes (2023 edition; codes 1-3 = metropolitan).",
          new="Metropolitan status was defined by the US Department of Agriculture Rural-Urban "
              "Continuum Codes (RUCC; 2023 edition): codes 1-3 denote metropolitan counties and "
              "codes 4-9 nonmetropolitan counties, graded by urbanization and adjacency to a "
              "metropolitan area (11). Because nonmetropolitan is not synonymous with rural, "
              "metropolitan and nonmetropolitan denote this binary classification, and rurality "
              "refers to the ordinal RUCC gradient."),
        E("R1-01", "replace", "Model-comparison result moved to Results; Methods keeps the method.",
          loc=loc,
          old="This specification was better supported by both AIC and BIC than a model with the "
              "dispersion fixed at 1, which was evaluated as a sensitivity analysis, and than a "
              "Poisson model.",
          new="Its fit was compared by the Akaike and Bayesian information criteria (AIC and BIC) "
              "with Poisson regression and with a negative binomial model with the dispersion "
              "fixed at 1."),
        E("R1-03", "replace", "Terminology.", loc=loc,
          old="correlated with rural location", new="correlated with nonmetropolitan location"),
        E("R2-03", "replace", "Adds the interaction test, the boundary rule for sparse strata "
          "(R2-03), the remaining sensitivity analyses, population weighting and its estimand "
          "(R1-02), and the exploratory urbanicity analyses (R1-04).", loc=loc,
          old="Sensitivity analyses replaced the binary metropolitan indicator with the ordinal "
              "Rural-Urban Continuum Code and repeated the deprivation models within metropolitan "
              "and nonmetropolitan strata.",
          new="Sensitivity analyses replaced the binary indicator with the ordinal RUCC; repeated "
              "the deprivation models within metropolitan and nonmetropolitan strata, with an "
              "index-by-metropolitan-status interaction test; restricted the cohort to Accredited "
              "facilities or the regressions to counties with at least 1,000 eligible adults; and "
              "fixed the dispersion at 1 (Supplementary Table S2). Where a sparse stratum placed "
              "the dispersion on its boundary of zero, inference was taken from the equivalent "
              "Poisson model. The negative binomial model weights each county's rate by a factor "
              "that rises with population and levels off; Poisson regression with the same "
              "offset weights each rate by population, describing the average adult, and was fitted "
              "with robust standard errors as a population-weighted sensitivity analysis (12). "
              "Exploratory SVI models added categorical RUCC or log population density, were "
              "fitted within strata, or used the four SVI themes."),
        E("R2-02", "insert_after", "Declares the primary hypothesis family and the multiplicity "
          "procedures.", loc=loc, anchor="A two-sided P < 0.05 was considered significant.",
          text=f" The primary hypothesis family was the {words[n_prim]} metropolitan-adjusted "
               f"SVI and EDI associations, with Holm-adjusted P values (13); Benjamini-Hochberg "
               f"false discovery rate-adjusted values are given for the {n_ext} negative binomial index "
               f"associations reported (14) (Supplementary Table S3). Sensitivity analyses were "
               f"intended to assess the robustness of the primary findings."),
        E("R2-01", "replace", "Software used for the PCA named (reproducibility).", loc=loc,
          old="statsmodels 0.14 and SciPy 1.13.", new="statsmodels 0.14, SciPy 1.13, and "
                                                     "scikit-learn 1.4."),
        E("E-04", "replace", "Grammar.", loc=loc,
          old="human subjects’ research", new="human subjects research"),
    ]

    # ------------------------------------------------------------- Results 1
    loc = "We identified 722 accredited CMR and 1,542 accredited CCT facilities."
    ed += [
        E("E-04", "delete", "Misplaced insertion of the Figure S1 citation removed; reinserted "
          "below in the right place.", loc=loc,
          span=" The corresponding distribution of cardiac CT capacity is shown in Supplementary "
               "Figure S1."),
        E("E-04", "insert_after", "Figure S1 citation restored at sentence end.", loc=loc,
          anchor="P < 0.001 for both; Table 1)",
          text="; the corresponding distribution of cardiac CT capacity is shown in Supplementary "
               "Figure S1"),
        E("R1-02", "insert_after", "Pooled rates include every county; the excluded counties "
          "had no facilities, so the exclusion cannot create unstable rates.", loc=loc,
          anchor="is shown in Supplementary Figure S1.",
          text=f" Pooled rates, which include every county, were "
               f"{rates['metropolitan']['CMR_pooled']:.2f} versus "
               f"{rates['nonmetropolitan']['CMR_pooled']:.2f} per 100,000 adults for CMR and "
               f"{rates['metropolitan']['CCT_pooled']:.2f} versus "
               f"{rates['nonmetropolitan']['CCT_pooled']:.2f} for CCT; none of the "
               f"{exc['n']} counties excluded from county-level rates had an accredited facility."),
    ]
    assert exc["cmr_facilities"] + exc["cct_facilities"] == 0

    # ------------------------------------------------------------- Results 3
    loc = "In unadjusted models, greater economic deprivation was associated with lower CMR"
    ed += [
        E("E-04", "replace_all", "Estimate punctuation standardized.", loc=loc,
          old=", 95% CI,", new="; 95% CI,"),
        E("R1-03", "replace", "Abbreviation defined in Methods.", loc=loc,
          old="modeled as the ordinal Rural-Urban Continuum Code", new="modeled as the ordinal RUCC"),
        E("R2-03", "replace", "The stratum is estimable: its NB2 dispersion lies on the boundary "
          "alpha = 0, where the maximum-likelihood fit is the Poisson fit "
          "(output/results/nonmetro_cmr_diagnostics.txt).", loc=loc,
          old="Within nonmetropolitan counties the point estimate was lower (IRR 0.70), but the "
              "confidence interval and P value were not estimable because the stratum contains "
              "only 14 accredited CMR facilities; this row is descriptive and hypothesis-"
              "generating (Table 3).",
          new=f"Within nonmetropolitan counties, whose {nm['events']} accredited CMR facilities "
              f"were each in a different county, greater deprivation was associated with lower "
              f"CMR capacity ({fe(nm['estimate'])}; interaction P = "
              f"{inter['interaction_ratio']['p']:.3f}) (Table 3). It was similar with a "
              f"profile-likelihood interval "
              f"({det['poisson_profile']['ci_low']:.2f}-{det['poisson_profile']['ci_high']:.2f}), "
              f"with adjustment for ordinal RUCC "
              f"(IRR {det['within_stratum_ordinal_rucc']['irr']:.2f}), and with the SVI "
              f"(IRR {S['strata']['SVI_CMR_nonmetro']['estimate']['irr']:.2f}) and SDI "
              f"(IRR {S['strata']['SDI_CMR_nonmetro']['estimate']['irr']:.2f}) (Supplementary "
              f"Table S4), but it rests on {nm['events']} facilities and is hypothesis-generating."),
        E("E-04", "replace", "The quintile means are not monotonic (Q3 > Q2, Q5 > Q4).", loc=loc,
          old="Mean county-level CMR rates declined across EDI quintiles",
          new="Mean county-level CMR rates were lower in more-deprived EDI quintiles, although "
              "not monotonically"),
        E("E-04", "delete", "Misplaced insertion of the Figure S2 citation.", loc=loc,
          span=" (Supplementary Figure S2)"),
        E("E-04", "insert_after", "Figure S2 citation restored.", loc=loc,
          anchor="(Kruskal-Wallis P < 0.001", text="; Supplementary Figure S2"),
        E("R1-02", "insert_after", "Pooled (population-weighted) quintile contrast.", loc=loc,
          anchor="Supplementary Figure S2).",
          text=f" For pooled rates the corresponding difference was "
               f"{mn['quintiles']['q1_over_q5_ratio_pooled']:.1f}-fold."),
    ]

    # ------------------------------------------------------------- Results 4
    loc = "To establish whether these findings depended on the purpose-built index"
    ed += [
        E("R1-03", "replace", "Abbreviation.", loc=loc,
          old="the ordinal Rural-Urban Continuum Code at", new="the ordinal RUCC at"),
        E("R2-01", "insert_after", "PCA result (moved from Methods, R1-01) with the scree plot, "
          "biplot and loadings requested.", loc=loc, anchor="gap of 7.1 points (Figure 2).",
          text=f" The EDI's first principal component explained "
               f"{100 * P['variance_explained'][0]:.1f}% of the variance in its six indicators "
               f"(eigenvalue {P['eigenvalues'][0]:.2f}), all six indicators loaded positively "
               f"on it (loadings, {lo_l:.2f}-{hi_l:.2f}), and a second component (eigenvalue "
               f"{P['eigenvalues'][1]:.2f}; {100 * P['variance_explained'][1]:.1f}% of variance) "
               f"reflected mainly housing cost burden; parallel analysis retained "
               f"{['no', 'one', 'two'][P['parallel_analysis']['n_retained']]} component "
               f"(Supplementary Figure S3; Supplementary "
               f"Table S5)."),
    ]
    assert lo_l > 0
    assert max(P["pc2_loadings"], key=lambda k: abs(P["pc2_loadings"][k])) == "EP_HBURD"

    spec_wins = _spec_wins()
    w_sc = wm["SVI_CCT_adjusted"]["poisson_population_weighted_robust"]
    w_ec = wm["EDI_CMR_unadjusted"]["poisson_population_weighted_robust"]
    w_m1 = wm["EDI_CMR_adjusted"]["metro_poisson_population_weighted_robust"]
    w_m2 = wm["EDI_CCT_adjusted"]["metro_poisson_population_weighted_robust"]
    fa_sc = mn["regressions"]["sensitivity_fixed_alpha"]["SVI_CCT"]["adjusted_metro"]["p"]
    w_ea = wm["EDI_CMR_adjusted"]["poisson_population_weighted_robust"]
    assert w_sc["p"] < 0.05 and w_ea["p"] >= 0.05 and fa_sc >= 0.05
    assert W["max_abs_irr_change_rate_eligible_adjusted"] < 0.001
    assert sc["holm_primary"] < 0.05 and sc["bh_extended"] < 0.05
    sens = (f"In every sensitivity analysis, metropolitan status remained strongly associated with "
            f"capacity and no model adjusted for it showed an inverse deprivation gradient "
            f"(Supplementary Table S2); the SVI-CCT association was not significant with the "
            f"dispersion fixed at 1 (P = {fa_sc:.3f}). The "
            f"estimated-dispersion model had lower AIC and BIC than the Poisson and fixed-dispersion "
            f"models in all {spec_wins} index-outcome models. Restricting the cohort to Accredited "
            f"facilities changed no conclusion, and restricting the regressions to counties with at "
            f"least 1,000 eligible adults changed no adjusted index IRR by more than 0.001. "
            f"Population-weighted estimates agreed with the primary estimates: SVI-CCT remained "
            f"positive ({fe(w_sc)}), adjusted EDI-CMR null ({fe(w_ea)}), and metropolitan status "
            f"strongly associated (CMR "
            f"{fe(w_m1, p=False)}; CCT {fe(w_m2, p=False)}). The adjusted SVI-CCT association "
            f"remained significant after Holm adjustment within the primary family "
            f"(P = {sc['holm_primary']:.3f}) and after false discovery rate adjustment across the "
            f"{n_ext} negative binomial index associations (P = {sc['bh_extended']:.3f}) "
            f"(Supplementary Table S3).")
    cat = um["SVI_CCT: categorical RUCC"]["estimate"]
    met = um["SVI_CCT: metropolitan counties only"]["estimate"]
    non = um["SVI_CCT: nonmetropolitan counties only"]["estimate"]
    den = um["SVI_CCT: metropolitan status + log population density"]["estimate"]
    cmr_den = um["SVI_CMR: metropolitan status + log population density"]["estimate"]
    catden = um["SVI_CMR: categorical RUCC + log population density"]["estimate"]
    sv_int = S["interaction"]["SVI_CCT"]["interaction_ratio"]["p"]
    assert met["p"] < 0.05 <= non["p"] and den["p"] >= 0.05 and sv_int >= 0.05
    explore = (f"In exploratory analyses, the SVI-CCT association was detected in metropolitan but "
               f"not nonmetropolitan counties ({fe(met, p=False)} and {fe(non, p=False)}; interaction "
               f"P = {sv_int:.3f}) and was "
               f"strongest for the SVI themes of housing type and transportation "
               f"({fe(th['SVI_CCT_theme4']['adjusted_metro'], p=False)}) and racial and ethnic "
               f"minority status ({fe(th['SVI_CCT_theme3']['adjusted_metro'], p=False)}), which "
               f"rose with density within metropolitan counties "
               f"(ρ = {dsc['spearman_theme4_density_metro']['rho']:.2f} and "
               f"{dsc['spearman_theme3_density_metro']['rho']:.2f}); it was no longer "
               f"significant after adjustment for population density ({fe(den)}); with finer "
               f"adjustment for urbanicity (categorical RUCC and density), the SVI-CMR association was "
               f"inverse ({fe(catden)}) (Supplementary Table S6).")
    ed += [
        E("R1-01", "new_para_after", "Sensitivity findings reported in Results (moved from "
          "Methods), with population weighting (R1-02) and multiplicity (R2-02).",
          loc=loc, text=sens),
        E("R1-04", "new_para_after", "Exploratory analyses of the positive SVI-CCT association.",
          loc="In every sensitivity analysis, metropolitan status remained", text=explore),
    ]

    # -------------------------------------------------------------- Discussion
    loc = "Accredited advanced cardiac imaging in the United States is concentrated"
    ed += [
        E("R1-03", "replace", "Terminology.", loc=loc,
          old="Most counties, and the rural populations within them, have",
          new="Most counties, including nearly all nonmetropolitan counties, have"),
        E("R1-03", "replace", "Terminology; 'largely' reflects the nonmetropolitan stratum result "
          "(R2-03).", loc=loc,
          old="indicating that it reflected the rural-urban gradient",
          new="indicating that it largely reflected the metropolitan-nonmetropolitan gradient"),
        E("R2-03", "replace", "Distinguishes the covariate-adjusted models from the stratified "
          "result.", loc=loc,
          old="once metropolitan status was included in the model: the adjusted",
          new="once metropolitan status was included in the model as a covariate: the adjusted"),
        E("R2-03", "insert_after", "States the nonmetropolitan exception honestly.", loc=loc,
          anchor="Accredited capacity tracked metropolitan location rather than area deprivation.",
          text=f" The exception was the {nm['events']} CMR facilities outside metropolitan areas, "
               f"which lay in less-deprived nonmetropolitan counties, a pattern consistent across "
               f"all three indices but too sparse for firm conclusions."),
        E("E-04", "replace", "References renumbered.", loc=loc,
          old="Medicare claims data (7)", new="Medicare claims data (4)"),
        E("E-04", "replace", "References renumbered.", loc=loc,
          old="likelihood of receiving imaging (8)", new="likelihood of receiving imaging (5)"),
        E("E-04", "replace", "References renumbered.", loc=loc,
          old="at safety-net hospitals (9)", new="at safety-net hospitals (6)"),
        E("E-04", "replace", "References renumbered.", loc=loc,
          old="advanced imaging facilities (4,10)", new="advanced imaging facilities (7,8)"),
        E("E-04", "replace", "References renumbered.", loc=loc,
          old="cardiovascular mortality (1,5)", new="cardiovascular mortality (1,15)"),
        E("R1-04", "new_para_after", "Plausible, non-causal explanations of the positive SVI-CCT "
          "association: tertiary/academic centers and urban-core clustering.", loc=loc,
          text=f"The positive SVI-CCT association should not be read as evidence that social "
               f"vulnerability attracts capacity; clustering in dense urban cores is a more "
               f"plausible explanation. Advanced cardiac imaging is concentrated in large "
               f"metropolitan and academic centers (4,5). Within "
               f"metropolitan counties the SVI themes for minority status and for housing and "
               f"transportation rise with population density, so dense central counties, where "
               f"tertiary centers are typically located, can score higher on the SVI for reasons "
               f"unrelated to economic deprivation, a distinction a binary metropolitan indicator "
               f"cannot make. Consistent with this, the association was detected only in metropolitan "
               f"counties, was strongest for those two themes, and was attenuated by density "
               f"adjustment. These analyses were exploratory, and county data cannot show whether "
               f"these facilities serve the vulnerable residents of their counties."),
        E("R1-05", "new_para_after", "Economic interpretation with verified literature, including the "
          "three studies Reviewer 1 recommended (references 19-21), and alternative explanations and "
          "observational limits.",
          loc="The positive SVI-CCT association should not be read as evidence",
          text="Metropolitan concentration is consistent with the economics of advanced imaging, "
               "although our data cannot identify its causes. CMR and CCT require large fixed "
               "investments in scanners, site preparation, trained technologists, and subspecialty "
               "interpretation that are recovered only at sufficient volume, so services locate "
               "where population density, referral networks, and hospital infrastructure supply "
               "it. MRI adoption has responded to market and payer conditions (16), and physicians "
               "and radiologists concentrate in more populous areas (17,18). Among Medicare "
               "beneficiaries, racial gaps in access to digital mammography narrowed as the "
               "technology diffused (19), use of screening CT colonography, which Medicare does not "
               "cover, rose steeply with income (20), and gaps in physician care by urbanicity, "
               "income, and area deprivation widened as inflation-adjusted payment declined (21). "
               "Disparities in capacity are often interpreted as evidence of bias, "
               "which these data can neither show nor exclude; the observed pattern is more "
               "consistent with market size. Payer mix, certificate-of-need regulation, health-system ownership, "
               "workforce supply, and accreditation practices could also contribute; none was "
               "measured, and the cross-sectional ecologic design shows where accredited capacity "
               "is located, not why."),
    ]

    # ------------------------------------------------------------- Limitations
    loc = "The ecologic, cross-sectional design precludes inferences"
    ed += [
        E("E-04", "replace", "References renumbered.", loc=loc,
          old="facility counts (7,8)", new="facility counts (4,5)"),
        E("E-04", "replace", "EDI-RUCC Spearman rho is 0.25; 'strongly' overstated it.", loc=loc,
          old="are strongly correlated, and a binary", new="are correlated, and a binary"),
        E("R2-03", "replace", "Limitation of the stratified estimate stated precisely.", loc=loc,
          old="stratified nonmetropolitan estimates are imprecise.",
          new=f"stratified nonmetropolitan estimates are imprecise and rest on {nm['events']} "
              f"facilities, and differently weighted estimates answer different questions."),
        E("E-04", "replace", "References renumbered.", loc=loc,
          old="Area Deprivation Index (11)", new="Area Deprivation Index (10)"),
        E("R1-03", "replace", "Terminology.", loc=loc,
          old="high-deprivation and rural counties", new="high-deprivation and nonmetropolitan counties"),
        E("R2-03", "replace", "Precision: the null holds for covariate adjustment; the "
          "nonmetropolitan stratum is the exception reported in Results.", loc=loc,
          old="after adjustment for metropolitan status, area deprivation measures",
          new="after covariate adjustment for metropolitan status, area deprivation measures"),
    ]

    # -------------------------------------------------------- Data availability
    ed.append(E("E-06", "replace", "Code availability stated.",
                loc="The analytic dataset, the county-level economic deprivation index",
                old="the county-level economic deprivation index, and a county-level",
                new="the county-level economic deprivation index, the analysis code, and a "
                    "county-level"))
    ed.append(E("E-04", "replace", "This is the revision; the bracket must not promise the URL 'at "
                "revision'. Review remains blinded, so the URL is restored on acceptance.",
                loc="The analytic dataset, the county-level economic deprivation index",
                old="will be restored at revision", new="will be restored on acceptance"))

    # --------------------------------------------------------------- References
    refs_new = {
        "2. Flanagan BE": "2. Centers for Medicare & Medicaid Services. Accreditation of advanced "
            "diagnostic imaging suppliers. Section 135(a), Medicare Improvements for Patients and "
            "Providers Act of 2008 (PL 110-275). Accessed July 18, 2026. https://www.cms.gov/"
            "medicare/health-safety-standards/quality-safety-oversight-general-information/"
            "accreditation-advanced-diagnostic-imaging-suppliers",
        "3. Singh GK": "3. Flanagan BE, Gregory EW, Hallisey EJ, Heitgerd JL, Lewis B. A social "
            "vulnerability index for disaster management. J Homeland Secur Emerg Manag. "
            "2011;8(1):Article 3.",
        "4. Mango VL": "4. Li JM, Ho DR, Husain N, et al. Regional variability of cardiovascular "
            "magnetic resonance access and utilization in the United States. J Cardiovasc Magn "
            "Reson. 2024;26(2):101061.",
        "5. Siddiqi AK": "5. Spetko N, Song Y, Orui H, et al. Distance and likelihood of "
            "cardiovascular imaging receipt among Medicare beneficiaries. JACC Cardiovasc Imaging. "
            "2026;19(4):447-459.",
        "6. Centers for Medicare": "6. Delshad J, Weis T, Bayona C, et al. Access to CCTA at "
            "safety-net hospitals across the United States. J Cardiovasc Comput Tomogr. "
            "2025;19(3):340-343.",
        "7. Li JM": "7. Mango VL, Stoeckl EM, Reid NJ, et al. Impact of high neighborhood "
            "socioeconomic deprivation on access to accredited breast imaging screening and "
            "diagnostic facilities. J Am Coll Radiol. 2023;20(7):634-639.",
        "8. Spetko N": "8. Jose O, Stoeckl EM, Miles RC, et al. The impact of extreme neighborhood "
            "socioeconomic deprivation on access to American College of Radiology-accredited "
            "advanced imaging facilities. Radiology. 2023;307(3):e222182.",
        "9. Delshad J": "9. Singh GK. Area deprivation and widening inequalities in US mortality, "
            "1969-1998. Am J Public Health. 2003;93(7):1137-1143.",
        "10. Jose O": "10. Kind AJH, Buckingham WR. Making neighborhood-disadvantage metrics "
            "accessible: the Neighborhood Atlas. N Engl J Med. 2018;378(26):2456-2458.",
        "11. Kind AJH": "11. US Department of Agriculture Economic Research Service. Rural-Urban "
            "Continuum Codes, 2023: documentation. Accessed November 4, 2026. "
            "https://www.ers.usda.gov/data-products/rural-urban-continuum-codes/documentation",
    }
    for prefix, text in refs_new.items():
        ed.append(E("E-04", "replace_para", "References renumbered in order of first citation; "
                    "new references added for R1-02, R1-03, R1-05 and R2-02.",
                    loc=prefix, new=text))
    appended = [
        "12. Solon G, Haider SJ, Wooldridge JM. What are we weighting for? J Hum Resour. "
        "2015;50(2):301-316.",
        "13. Holm S. A simple sequentially rejective multiple test procedure. Scand J Stat. "
        "1979;6(2):65-70.",
        "14. Benjamini Y, Hochberg Y. Controlling the false discovery rate: a practical and "
        "powerful approach to multiple testing. J R Stat Soc Series B Stat Methodol. "
        "1995;57(1):289-300.",
        "15. Siddiqi AK, Ali KM, Maniya MT, et al. The hidden epidemic: hypertension-related "
        "mortality surges amongst younger adults in the United States. Curr Probl Cardiol. "
        "2024;49(12):102842.",
        "16. Baker LC. Managed care and technology adoption in health care: evidence from magnetic "
        "resonance imaging. J Health Econ. 2001;20(3):395-421.",
        "17. Rosenthal MB, Zaslavsky A, Newhouse JP. The geographic distribution of physicians "
        "revisited. Health Serv Res. 2005;40(6 Pt 1):1931-1952.",
        "18. Rosenkrantz AB, Hughes DR, Duszak R Jr. The U.S. radiologist workforce: an analysis of "
        "temporal and geographic variation by using large national datasets. Radiology. "
        "2016;279(1):175-184.",
        # Recommended by Reviewer 1 (comment 5); details verified against Europe PMC.
        "19. Christensen EW, Waid M, Scott J, et al. Relationship between race and access to newer "
        "mammographic technology in women with Medicare insurance. Radiology. "
        "2023;306(2):e221153.",
        "20. Christensen EW, Sanelli PC, Rula EY, et al. Sociodemographic factors and screening CT "
        "colonography use among Medicare beneficiaries. AJR Am J Roentgenol. "
        "2024;222(1):e2329703.",
        "21. Christensen EW, Drake AR, Nicola GN, et al. Association between the declining "
        "conversion factor and access to care for Medicare beneficiaries. Inquiry. "
        "2026;63:00469580261473400.",
    ]
    prev = "11. US Department of Agriculture"
    for text in appended:
        ed.append(E("E-04", "new_para_after", "New or renumbered reference.", loc=prev, text=text))
        prev = text[:24]
    ed.append(E("E-04", "replace", "Reference count.", loc="Article type: Original Article.",
                old="References: 11.", new=f"References: {len(appended) + 11}."))

    # ------------------------------------------------------------ Figure legend
    ed.append(E("E-04", "replace", "Consistent modality naming ('cardiac MR').",
                loc="FIGURE 1 Accredited Cardiac", old="Cardiac MRI Capacity",
                new="Cardiac MR Capacity"))

    # ------------------------------------------------------------------ Table 1
    ed.append(E("R1-03", "replace", "Table title terminology.",
                loc="Table 1. Accredited cardiac imaging capacity by",
                old="by rurality and economic", new="by metropolitan status and economic"))
    ed.append(E("R2-04", "cell_insert", "Facility percentage of the national total.",
                table=0, row_index=0, col=3, anchor="CMR facilities, No.", text=" (%)"))
    ed.append(E("R2-04", "cell_insert", "Facility percentage of the national total.",
                table=0, row_index=0, col=6, anchor="CCT facilities, No.", text=" (%)"))
    ed.append(E("R1-03", "cell_replace", "Stratum heading terminology.", table=0, section=None,
                row="Rurality", col=0, old="Rurality", new="Metropolitan status"))
    layout = [("All counties", "all_counties", None),
              ("Metropolitan (RUCC 1-3)", "metropolitan", None),
              ("Nonmetropolitan (RUCC 4-9)", "nonmetropolitan", None),
              ("Q1 (least deprived)", "edi_q1", "EDI quintile"), ("Q2", "edi_q2", "EDI quintile"),
              ("Q3", "edi_q3", "EDI quintile"), ("Q4", "edi_q4", "EDI quintile"),
              ("Q5 (most deprived)", "edi_q5", "EDI quintile")]
    for label, key, sect in layout:
        b = T1[key]
        ed.append(E("R2-04", "cell_insert", "Share of national facilities.", table=0, row=label,
                    section=sect, col=3, anchor=f"{b['cmr_facilities']:,}",
                    text=f" ({b['cmr_facilities_pct']:.1f})"))
        ed.append(E("R2-04", "cell_insert", "Share of national facilities.", table=0, row=label,
                    section=sect, col=6, anchor=f"{b['cct_facilities']:,}",
                    text=f" ({b['cct_facilities_pct']:.1f})"))
    tot = T1["_national_totals"]
    ed.append(E("R2-04", "replace", "Denominators stated; terminology.",
                loc="Quintiles are restricted to the 3,029 counties",
                old="rurality strata include all 3,144 counties.",
                new=f"metropolitan strata include all 3,144 counties. Facility percentages are of "
                    f"the national total for each modality ({tot['cmr']:,} CMR and {tot['cct']:,} "
                    f"CCT facilities); percentages of counties with ≥1 facility use the counties "
                    f"in the row as the denominator, and quintile rows sum to less than 100% of "
                    f"facilities because counties without an EDI value are not in a quintile. "
                    f"Mean rates exclude the {exc['n']} counties with fewer than 1,000 adults aged "
                    f"≥45 years, none of which had an accredited facility."))

    # ------------------------------------------------------------------ Table 2
    holm = {k: tests[f"{k}, adjusted for metropolitan status (Table 2)"]["holm_primary"]
            for k in ("SVI-CMR", "SVI-CCT", "EDI-CMR", "EDI-CCT")}
    ed.append(E("R2-02", "replace", "Multiplicity-adjusted P values for the primary family; "
                "duplicated sentence removed (E-04).",
                loc="Metropolitan estimates shown are from the EDI models",
                old="Primary models are negative binomial with the dispersion parameter estimated "
                    "from the data; a specification with the dispersion fixed at 1 was evaluated "
                    "as a sensitivity analysis.",
                new=f"Sensitivity analyses, including a specification with the dispersion fixed "
                    f"at 1, are reported in Supplementary Table S2. P values are unadjusted; "
                    f"Holm-adjusted P values for the {words[n_prim]} adjusted index associations "
                    f"(the primary hypothesis family) were {holm['SVI-CMR']:.3f} (SVI, cardiac MR), "
                    f"{holm['SVI-CCT']:.3f} (SVI, cardiac CT), {holm['EDI-CMR']:.3f} (EDI, cardiac "
                    f"MR), and {holm['EDI-CCT']:.3f} (EDI, cardiac CT)."))

    ed.append(E("E-04", "replace_all", "CI punctuation.",
                loc="Metropolitan estimates shown are from the EDI models",
                old="(95% CI ", new="(95% CI, "))

    ed.append(E("E-04", "replace", "Precision: the absence of an inverse gradient holds for covariate "
                "adjustment; within nonmetropolitan counties the CMR stratum shows one (Reviewer 2, "
                "comment 3).", loc="More than four of every five US counties have no ACR-accredited",
                old="after accounting for metropolitan location",
                new="after covariate adjustment for metropolitan status"))

    # ------------------------------------------- values corrected at full convergence
    # Three values in the submitted text came from NB2 fits that BFGS had stopped
    # slightly short of the maximum. model_spec.fit_nb2 now finishes every fit with
    # Newton steps; these edits replace the submitted digits with the converged
    # ones, formatted from the results, and are skipped when nothing changed.
    Mx = mn["regressions"]["models"]
    svi_m = Mx["SVI_CMR"]["metro_effect"]
    sdi_ct = mn["sdi"]["SDI_models"]["outcomes"]["cct_facility_count"]["metro_in_adjusted"]
    rucc_p = cell_p(Mx["EDI_CMR"]["adjusted_rucc"]["p"])
    why = ("Value corrected: the negative binomial fit is now taken to full convergence "
           "(Newton steps after BFGS); the submitted value was from a fit stopped short of the maximum.")
    for loc_, old, new in (
            ("Metropolitan estimates shown are from the EDI models", "8.56", f"{svi_m['irr']:.2f}"),
            ("Metropolitan estimates shown are from the EDI models", "14.61", f"{svi_m['ci_high']:.2f}"),
            ("To establish whether these findings depended on the purpose-built index",
             "CCT IRR 2.12", f"CCT IRR {sdi_ct['IRR']:.2f}"),
            ("In unadjusted models, greater economic deprivation was associated with lower CMR",
             "P = 0.801", f"P = {rucc_p}")):
        if old != new:
            ed.append(E("E-04", "replace", why, loc=loc_, old=old, new=new))
    assert f"{svi_m['ci_low']:.2f}" == "5.01" and f"{sdi_ct['CI_low']:.2f}-{sdi_ct['CI_high']:.2f}" == "1.74-2.58"
    if rucc_p != "0.801":
        ed.append(E("E-04", "cell_replace", why, table=2, section="Rurality as ordinal RUCC (1-9)",
                    row="Cardiac MR", col=3, old="0.801", new=rucc_p))

    # ------------------------------------------------------------------ Table 3
    ed.append(E("R2-03", "cell_replace", "Boundary (Poisson) solution: CI now estimable.",
                table=2, section="Stratified by metropolitan status",
                row="Cardiac MR, nonmetropolitan", col=2, old="NE",
                new=f"{nm['estimate']['ci_low']:.2f}-{nm['estimate']['ci_high']:.2f}"))
    ed.append(E("R2-03", "cell_replace", "Boundary (Poisson) solution: P now estimable.",
                table=2, section="Stratified by metropolitan status",
                row="Cardiac MR, nonmetropolitan", col=3, old="NE",
                new=cell_p(nm["estimate"]["p"])))
    wsect = "Population-weighted, adjusted for metropolitan status"
    rows = [[wsect, "", "", "", ""]]
    for lab, mod in (("Cardiac MR", "CMR"), ("Cardiac CT", "CCT")):
        w = wm[f"EDI_{mod}_adjusted"]
        rows.append([lab, f"{w['n']:,}", cell_est(w["poisson_population_weighted_robust"]),
                     cell_p(w["poisson_population_weighted_robust"]["p"]),
                     cell_est(w["metro_poisson_population_weighted_robust"])])
        assert w["metro_poisson_population_weighted_robust"]["p"] < 0.001
    ed.append(E("R1-02", "rows_after", "Population-weighted EDI models in Table 3.", table=2,
                after=("Cardiac CT, nonmetropolitan", "Stratified by metropolitan status"),
                header_model=("Stratified by metropolitan status", None),
                row_model=("Cardiac CT, nonmetropolitan", "Stratified by metropolitan status"),
                rows=rows))
    cct_int = S["interaction"]["EDI_CCT"]["interaction_ratio"]["p"]
    ed += [
        E("R1-02", "replace", "Not all Table 3 models are negative binomial now.",
          loc="The rurality term is the ordinal RUCC value",
          old="All models are negative binomial with a log-population offset",
          new="Unless noted, models are negative binomial with a log-population offset"),
        E("R1-02", "insert_after", "Defines the rurality term for the weighted rows.",
          loc="The rurality term is the ordinal RUCC value",
          anchor="lower capacity with increasing rurality.",
          text=" In the population-weighted rows it is metropolitan status."),
        E("R2-03", "replace", "Explains the boundary solution, the interaction test, and the "
          "weighted models.", loc="The rurality term is the ordinal RUCC value",
          old="NE = not estimable. The nonmetropolitan cardiac MR stratum contains only 14 "
              "accredited facilities; the point estimate is shown, but the confidence interval "
              "and P value were not estimable at that event count, so the row is descriptive and "
              "hypothesis-generating rather than inferential.",
          new=f"The nonmetropolitan cardiac MR stratum contains {nm['events']} accredited "
              f"facilities, each in a different county; its dispersion estimate lay on the "
              f"boundary of zero, where the negative binomial model reduces to Poisson regression, "
              f"and the estimate shown is from that fit (profile-likelihood 95% CI, "
              f"{det['poisson_profile']['ci_low']:.2f}-{det['poisson_profile']['ci_high']:.2f}; "
              f"Supplementary Table S4). It is imprecise and hypothesis-generating. The EDI "
              f"association differed between metropolitan and nonmetropolitan counties for "
              f"cardiac MR (interaction P = {inter['interaction_ratio']['p']:.3f}) but not for "
              f"cardiac CT (interaction P = {cct_int:.3f}). Population-weighted models are Poisson "
              f"regressions with the same offset, which weight each county's rate by its adults "
              f"aged ≥45 years, with robust standard errors."),
    ]

    # -------------------------------------------- Figure 2 is a comparison, not validation
    # The SDI is a published index fitted to the same counties: an alternative-index
    # comparison, not validation in an independent population.
    ed += [
        E("E-04", "replace", "The SDI comparison uses the same counties, so it is a comparison "
          "with a published index rather than external validation.",
          loc="Accredited advanced cardiac imaging in the United States is concentrated",
          old="External validation supports this interpretation: a published index that encodes "
              "rurality only weakly, the Graham Center SDI, showed",
          new="A published index supports this interpretation: the Graham Center SDI, which "
              "encodes rurality only weakly, showed"),
        E("E-04", "replace", "Figure 2 title: comparison with a published index.",
          loc="FIGURE 2 External Validation",
          old="External Validation of the Deprivation Finding Using a Published County-Level Index",
          new="Comparison of the Deprivation Finding With a Published County-Level Index"),
        E("E-04", "delete", "Figure 2 has no metropolitan-status rows; the sentence was obsolete.",
          loc="Analytic sample: 3,134 counties (EDI) and 3,133 (SDI)",
          span=" Metropolitan status rows are the metropolitan-status coefficients from the "
               "corresponding adjusted models."),
    ]
    return ed


def _spec_wins():
    import pandas as pd
    t = pd.read_csv(os.path.join(BASE_DIR, "output", "results", "model_specification_comparison.csv"))
    combos = t.groupby(["index", "outcome"])
    wins = [sum("estimated alpha" in g.loc[g[c].idxmin(), "specification"] for _, g in combos)
            for c in ("aic", "bic")]
    assert wins[0] == wins[1] == combos.ngroups, wins
    return combos.ngroups


# -------------------------------------------------------------------- apply
def _para(doc, loc):
    return doc.find_paragraph(loc)


def apply(doc, ed, log):
    tables = doc.tables()
    applied = skipped = 0
    for e in ed:
        k = e["kind"]
        status, where = "applied", e.get("loc", "")
        try:
            if k == "replace":
                p = _para(doc, e["loc"])
                if e["new"] in doc.accepted_text(p) and e["old"] not in doc.accepted_text(p):
                    status = "already applied"
                else:
                    doc.replace(p, e["old"], e["new"])
            elif k == "replace_all":
                p = _para(doc, e["loc"])
                n = 0
                while e["old"] in doc.accepted_text(p):
                    doc.replace(p, e["old"], e["new"])
                    n += 1
                status = f"applied x{n}" if n else "already applied"
            elif k == "delete":
                p = _para(doc, e["loc"])
                if e["span"] not in doc.accepted_text(p):
                    status = "already applied"
                else:
                    doc.delete(p, e["span"])
            elif k == "insert_after":
                p = _para(doc, e["loc"])
                if e["text"].strip() in doc.accepted_text(p):
                    status = "already applied"
                else:
                    doc.insert(p, e["anchor"], e["text"], before=False)
            elif k == "replace_para":
                p = _para(doc, e["loc"])
                old = doc.accepted_text(p)
                if old == e["new"]:
                    status = "already applied"
                else:
                    doc.replace(p, old, e["new"])
                    e["old"] = old
            elif k == "new_para_after":
                if any(doc.accepted_text(q) == e["text"] for q in doc.paragraphs()):
                    status = "already applied"
                else:
                    p = _para(doc, e["loc"])
                    doc.insert_paragraph_after(p, e["text"])
            elif k in ("cell_insert", "cell_replace"):
                tbl = tables[e["table"]]
                if "row_index" in e:
                    tr = tbl.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr")[e["row_index"]]
                else:
                    tr = doc.find_row(tbl, e["row"], e.get("section"))
                p = doc.cell_paragraph(tr, e["col"])
                cur = doc.accepted_text(p)
                where = f"Table {e['table'] + 1}, {doc.row_texts(tr)[0] or 'header'}, column {e['col'] + 1}"
                if k == "cell_insert":
                    if cur.endswith(e["text"]) or e["text"].strip() in cur:
                        status = "already applied"
                    else:
                        doc.insert(p, e["anchor"], e["text"], before=False)
                else:
                    if cur == e["new"] or (e["old"] not in cur):
                        status = "already applied"
                    else:
                        doc.replace(p, e["old"], e["new"])
            elif k == "rows_after":
                tbl = tables[e["table"]]
                labels = [doc.row_texts(tr)[0] for tr in
                          tbl.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr")]
                if e["rows"][0][0] in labels:
                    status = "already applied"
                else:
                    anchor = doc.find_row(tbl, *e["after"])
                    hmodel = doc.find_row(tbl, *e["header_model"])
                    rmodel = doc.find_row(tbl, *e["row_model"])
                    prev = anchor
                    for i, vals in enumerate(e["rows"]):
                        prev = doc.insert_table_row_after(prev, vals, hmodel if i == 0 else rmodel)
                    doc.fit_table_width(tbl)
                where = f"Table {e['table'] + 1}"
            else:
                raise ValueError(k)
        except AnchorNotFound as exc:
            status = f"SKIPPED: {exc}"
        if status.startswith("applied"):
            applied += 1
        else:
            skipped += 1
        log.append({"task": e["task"], "kind": k, "location": where[:80], "status": status,
                    "old": e.get("old", e.get("span", e.get("anchor", ""))),
                    "new": e.get("new", e.get("text", "") if k != "rows_after"
                                 else " | ".join(" / ".join(r) for r in e["rows"])),
                    "rationale": e["why"]})
        print(f"  {status:<18} {e['task']:<6} {k:<14} {where[:60]}")
    return applied, skipped


def body_word_count(path):
    spec = importlib.util.spec_from_file_location(
        "gate", os.path.join(BASE_DIR, "code", "12_manuscript_numbers.py"))
    sys.path.insert(0, os.path.join(BASE_DIR, "code"))
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    _, _, paras = gate.read_manuscript(path)
    heads = {"INTRODUCTION", "METHODS", "RESULTS", "DISCUSSION", "STUDY LIMITATIONS",
             "CONCLUSION", "DATA AVAILABILITY", "REFERENCES"}
    lo = next(i for i, t in enumerate(paras) if t.strip().upper() == "INTRODUCTION")
    hi = next(i for i, t in enumerate(paras) if t.strip().upper() == "REFERENCES")
    body = [t for t in paras[lo:hi] if t.strip() and t.strip().upper() not in heads
            and not t.strip().startswith("[")]
    return sum(len(t.split()) for t in body)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("dest")
    ap.add_argument("--log", help="write the change log here (CSV)")
    ap.add_argument("--blind", action="store_true",
                    help="attribute revisions to a neutral 'Author' (for the blinded journal copy)")
    args = ap.parse_args()

    rv, mn = load_numbers()
    ed = build_edits(rv, mn)
    author = "Author" if args.blind else AUTHOR
    doc = TrackedDocument(args.source, author=author, date=DATE, revision_id_base=200_000)
    print("=" * 78)
    print(f"  REVISION ROUND R1   {author}   {DATE[:10]}")
    print(f"  source {os.path.relpath(args.source, BASE_DIR)}")
    print("=" * 78)
    log = []
    applied, skipped = apply(doc, ed, log)
    doc.save(args.dest)

    # The body word count note must describe the revised text. Count it under
    # the manuscript's own definition, then record it as one more tracked edit.
    words = body_word_count(args.dest)
    doc = TrackedDocument(args.dest, author=author, date=DATE, revision_id_base=300_000)
    p = doc.find_paragraph("Article type: Original Article.")
    import re
    cur = re.search(r"figure legends\): ([\d,]+)\.", doc.accepted_text(p)).group(1)
    if cur != f"{words:,}":
        doc.replace(p, f"figure legends): {cur}.", f"figure legends): {words:,}.")
        log.append({"task": "E-04", "kind": "replace", "location": "Front matter",
                    "status": "applied", "old": cur, "new": f"{words:,}",
                    "rationale": "Body word count recomputed under the stated definition."})
        print(f"  applied            E-04   replace        word count {cur} -> {words:,}")
    doc.save(args.dest)
    print(f"\n  {applied} applied, {skipped} skipped; body words {words:,}")
    print(f"  wrote {os.path.relpath(args.dest, BASE_DIR)}")
    if args.log:
        with open(args.log, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["task", "kind", "location", "status", "old", "new",
                                              "rationale"])
            w.writeheader()
            w.writerows(log)
        print(f"  change log {os.path.relpath(args.log, BASE_DIR)}")
    if skipped and any(r["status"].startswith("SKIPPED") for r in log):
        sys.exit(1)


if __name__ == "__main__":
    main()
