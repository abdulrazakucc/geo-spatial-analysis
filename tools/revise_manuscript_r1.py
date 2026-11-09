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
DATE = "2026-11-08T12:00:00Z"


# ------------------------------------------------------------------ numbers
def load_numbers():
    with open(os.path.join(BASE_DIR, "output", "results", "reviewer_analyses.json")) as f:
        rv = json.load(f)
    with open(os.path.join(BASE_DIR, "output", "validation", "manuscript_numbers.json")) as f:
        mn = json.load(f)
    return rv, mn


def fe(e, p=True):
    """Estimate in the manuscript's prose format; ranges use an en dash, as the
    submitted manuscript does (the gate reads en and hyphen dashes alike)."""
    t = f"IRR {e['irr']:.2f}; 95% CI, {e['ci_low']:.2f}–{e['ci_high']:.2f}"
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
    """Revision 1, applied to the manuscript as submitted to JACR on 2026-09-25
    (manuscript/_archive/manuscript_JACR_first_submission_2026-09-25.docx). That
    file has no tables (they were uploaded separately; tables are now separate
    files from code/17, 21 and 20), section subheadings, and en dashes in ranges,
    which new text follows."""
    W, S, M, U, P = (rv["R1-02_weighting"], rv["R2-03_strata"], rv["R2-02_multiplicity"],
                     rv["R1-04_urban_core"], rv["R2-01_pca"])
    T1 = mn["table1"]
    rates, exc = W["descriptive"]["rates"], W["descriptive"]["excluded"]
    wm = W["models"]
    tests = {t["test"]: t for t in M["tests"]}
    nm, det = S["strata"]["EDI_CMR_nonmetro"], S["detail"]["EDI_CMR_nonmetro"]
    inter = S["interaction"]["EDI_CMR"]
    um, th, dsc = U["models"], U["themes"], U["descriptive"]
    n_ext = M["families"]["extended"]["n_tests"]
    n_prim = M["families"]["primary"]["n_tests"]
    sc = tests["SVI-CCT, adjusted for metropolitan status (Table 2)"]
    lo_l, hi_l = min(P["pc1_loadings"].values()), max(P["pc1_loadings"].values())
    rl = mn["sdi"]["rurality_link"]
    Mx = mn["regressions"]["models"]
    svi_m = Mx["SVI_CMR"]["metro_effect"]
    sdi_ct = mn["sdi"]["SDI_models"]["outcomes"]["cct_facility_count"]["metro_in_adjusted"]
    rucc_cmr, rucc_cct = Mx["EDI_CMR"]["adjusted_rucc"], Mx["EDI_CCT"]["adjusted_rucc"]
    n_q = sum(T1[f"edi_q{i}"]["counties"] for i in range(1, 6))
    words = {1: "one", 2: "two", 3: "three", 4: "four"}
    assert exc["cmr_facilities"] + exc["cct_facilities"] == 0
    assert lo_l > 0
    assert max(P["pc2_loadings"], key=lambda k: abs(P["pc2_loadings"][k])) == "EP_HBURD"
    assert f"{sdi_ct['CI_low']:.2f}-{sdi_ct['CI_high']:.2f}" == "1.74-2.58"
    assert fe(rucc_cmr, p=False) == "IRR 1.00; 95% CI, 0.97–1.04"
    assert rucc_cct["irr"] > 1 and rucc_cct["p"] < 0.05

    WL = "Condensed for the journal's 3,000-word limit; "
    NS = "Nonsignificance is not shown absence."
    CONV = ("Value corrected: the negative binomial fit is now taken to full convergence (Newton steps "
            "after BFGS); the submitted value was from a fit stopped short of the maximum.")
    ed = []

    # ------------------------------------------------------------ front matter
    ed += [
        E("E-04", "delete", "The closing sentence repeated the Summary Sentence and the abstract.",
          loc="Prior work has reported that neighborhood deprivation predicts",
          span=" Accredited cardiac imaging capacity is concentrated in metropolitan counties; no inverse "
               "deprivation gradient persisted after adjustment, although social vulnerability was "
               "modestly associated with higher cardiac CT capacity."),
        E("E-04", "replace", "Scope: the adjustment is for metropolitan status (exploratory models with "
          "finer urbanicity adjustment differ).", loc="Discussion: Accredited cardiac imaging",
          old="persisted after adjustment, although", new="persisted after metropolitan adjustment, although"),
        E("E-04", "replace", "Conclusion limited to what the models test.",
          loc="Discussion: Accredited cardiac imaging",
          old="Deprivation-based targeting may misidentify communities lacking this infrastructure.",
          new="Deprivation indices should not serve as unadjusted proxies for imaging capacity."),
        E("E-04", "replace", "Summary Sentence kept word for word with the abstract (JACR rule).",
          loc="Accredited cardiac imaging capacity is concentrated in metropolitan counties; no inverse deprivation gradient persisted after adjustment", old="persisted after adjustment, although",
          new="persisted after metropolitan adjustment, although"),
        E("E-04", "replace", NS, loc="Metropolitan location, not area deprivation, tracked",
          old="the economic deprivation index was not associated with either modality",
          new="the economic deprivation index was not significantly associated with either modality"),
        E("E-04", "replace", "Implication stated as untested; the adjusted IRRs are the source.",
          loc="Metropolitan counties had roughly eightfold higher cardiac MR capacity",
          old="Metropolitan counties had roughly eightfold higher cardiac MR capacity but only twofold "
              "higher cardiac CT capacity, which points to different levers by modality:",
          new="Metropolitan status was associated with roughly eightfold higher cardiac MR capacity but "
              "only twofold higher cardiac CT capacity, which suggests, though this was not tested, "
              "different levers by modality:"),
        E("E-04", "replace", "Planning conclusion stated as a hypothesis.",
          loc="Deprivation indices should not be used as proxies for cardiac imaging access",
          old="geographic measures are likely to be more informative for imaging capacity planning.",
          new="whether geographic measures better identify unmet imaging need requires direct evaluation."),
        E("E-04", "replace", NS, loc="Results: There were 722",
          old="The SVI was not associated with cardiac MR capacity",
          new="The SVI was not significantly associated with cardiac MR capacity"),
        E("E-04", "replace", "Same definition, shorter (abstract limit).", loc="Methods: Cross-sectional",
          old="Metropolitan status was defined by USDA Rural-Urban Continuum Codes 1–3.",
          new="Metropolitan counties had USDA Rural-Urban Continuum Codes 1–3."),
    ]

    # ------------------------------------------------------------ Introduction
    ed += [
        E("E-04", "replace", "Reference 1 reports cardiovascular mortality by rural-urban residence "
          "(and age, sex, race, ethnicity), not by economic status.",
          loc="Cardiovascular mortality varies markedly",
          old="and rural and economically disadvantaged populations bear the highest rates (1)",
          new="and rural populations bear the highest rates (1)"),
        E("E-04", "replace", "The effective date is not stated by the cited CMS page (reference 2).",
          loc="Cardiovascular mortality varies markedly",
          old="to bill Medicare, a requirement in effect since January 1, 2012 (2)",
          new="to bill Medicare (2)"),
        E("E-04", "replace", "The cited source does not establish that the ACR is the largest "
          "accrediting organization.", loc="Cardiovascular mortality varies markedly",
          old="is the largest such organization, so its accredited-facility registry provides",
          new="is one such organization, and its accredited-facility registry provides"),
        E("R1-03", "replace", "Binary RUCC classification is metropolitan/nonmetropolitan.",
          loc="Health equity research commonly measures",
          old="metropolitan–rural gradient", new="metropolitan–nonmetropolitan gradient"),
    ]

    # --------------------------------------------------------------- Methods
    m1 = "We conducted a cross-sectional ecologic analysis of all 3,144 US counties and county"
    m2 = "Per-capita facility rates were expressed per 100,000"
    m3 = "Area disadvantage was measured with two complementary indices"
    m4 = "Facility counts were modeled with negative binomial (NB2) regression"
    ed += [
        E("R1-01", "delete", "Sensitivity finding removed from Methods (reported in Results).", loc=m1,
          span="; a sensitivity analysis restricted to Accredited facilities yielded the same qualitative "
               "conclusions"),
        E("E-04", "replace", WL + "same definition.", loc=m1,
          old="The ACR accredits CCT as a modality that covers coronary CT angiography and coronary artery "
              "calcium scoring; CCT here denotes the accredited modality rather than a single examination "
              "type.",
          new="CCT denotes the ACR-accredited modality, which covers coronary CT angiography and coronary "
              "artery calcium scoring, rather than a single examination."),
        E("E-04", "delete", WL + "Limitations states that the counts understate total capacity.", loc=m1,
          span=" This analysis therefore quantifies ACR-accredited capacity rather than the total number "
               "of sites performing these studies."),
        E("E-04", "replace", "Source corrected: the denominators are the US Census Bureau's Vintage 2023 "
          "county population estimates for July 1, 2023 (they match that file exactly for all 3,144 "
          "counties), not American Community Survey 5-year estimates.", loc=m2,
          old="derived from American Community Survey 5-year estimates",
          new="from US Census Bureau population estimates for July 1, 2023"),
        E("R1-02", "replace", "States the number excluded and adds pooled rates, which need no "
          "exclusion.", loc=m2,
          old="counties with fewer than 1,000 eligible adults were excluded from per-capita rate "
              "calculations.",
          new=f"the {exc['n']} counties with fewer than 1,000 eligible adults were excluded from "
              f"county-level rate calculations; pooled rates (total facilities divided by total eligible "
              f"adults, equivalent to population-weighted mean county rates), which require no "
              f"exclusion, were also calculated."),
        E("R1-02", "replace", "Clarifies that all counties are in the count models.", loc=m2,
          old="They were retained in the count regressions", new="All counties were retained in the "
                                                                "count regressions"),
        E("R1-01", "delete", "Sensitivity result moved to Results with its verified size.", loc=m2,
          span=" Restricting the regressions to the same population threshold was examined as a "
               "sensitivity analysis and did not materially alter any estimate."),
        E("E-05", "insert_after", "Points to the population-characteristics table (Table 5).",
          loc=m2, anchor="lacked one or more EDI components).",
          text=" County population characteristics from the SVI 2022 and County Health Rankings 2024 are "
               "summarized in Table 5; no patient-level data were used."),
        E("R1-01", "replace", "Variance explained is a result; moved to Results with the full PCA "
          "(R2-01). Standardization stated for reproducibility.", loc=m3,
          old="The first principal component explained 58.7% of the variance; scores were converted to "
              "national percentiles (0–100).",
          new="Indicators were standardized, and scores on the first principal component were converted "
              "to national percentiles (0–100)."),
        E("E-04", "replace", WL + "the abbreviation is defined in the same paragraph.", loc=m3,
          old="It is designated the EDI throughout and is distinct from", new="It is distinct from"),
        E("E-04", "delete", WL + "the SVI themes are listed in the preceding sentence.", loc=m3,
          span=" (for example, racial composition, transportation, and household structure)"),
        E("E-04", "delete", WL + "the subheading states it.", loc=m3,
          span="Area disadvantage was measured with two complementary indices. "),
        E("R1-03", "replace", "RUCC operational definitions stated, with the terminology used "
          "throughout (USDA ERS documentation, reference 11).", loc=m4,
          old="Metropolitan versus nonmetropolitan status was defined with the US Department of "
              "Agriculture Rural-Urban Continuum Codes (RUCC; 2023 edition; codes 1–3 = metropolitan).",
          new="Metropolitan status was defined by the US Department of Agriculture Rural-Urban Continuum "
              "Codes (RUCC; 2023 edition): codes 1–3 denote metropolitan counties and codes 4–9 "
              "nonmetropolitan counties, graded by urbanization and adjacency to a metropolitan area "
              "(11). Because nonmetropolitan is not synonymous with rural, metropolitan and "
              "nonmetropolitan denote this binary classification, and rurality refers to the ordinal "
              "RUCC gradient."),
        E("R1-01", "replace", "Model-comparison result moved to Results; Methods keeps the method.",
          loc=m4,
          old="This specification was better supported by both the Akaike and Bayesian information "
              "criteria than either a model with the dispersion fixed at 1, which was evaluated as a "
              "sensitivity analysis, or a Poisson model.",
          new="Its fit was compared by the Akaike and Bayesian information criteria (AIC and BIC) with "
              "Poisson regression and with a negative binomial model with the dispersion fixed at 1."),
        E("R1-03", "replace", "Terminology.", loc=m4,
          old="correlated with rural location", new="correlated with nonmetropolitan location"),
        E("R2-03", "replace", "Adds the interaction test, the boundary rule for sparse strata "
          "(R2-03), the remaining sensitivity analyses, population weighting and its estimand "
          "(R1-02), and the exploratory urbanicity analyses (R1-04).", loc=m4,
          old="Sensitivity analyses replaced the binary metropolitan indicator with the ordinal RUCC and "
              "repeated the deprivation models within metropolitan and nonmetropolitan strata.",
          new="Sensitivity analyses replaced the binary indicator with the ordinal RUCC; repeated the "
              "deprivation models within metropolitan and nonmetropolitan strata, with an "
              "index-by-metropolitan-status interaction test; restricted the cohort to Accredited "
              "facilities or the regressions to counties with at least 1,000 eligible adults; and fixed "
              "the dispersion at 1 (Supplementary Table S2). Where a sparse stratum placed the "
              "dispersion on its boundary of zero, inference was taken from the equivalent Poisson "
              "model. The negative binomial model weights each county's rate by a factor that rises "
              "with population and levels off; Poisson regression with the same offset weights each "
              "rate by population, describing the average adult, and was fitted with robust standard "
              "errors as a population-weighted sensitivity analysis (12). Exploratory SVI models added "
              "categorical RUCC or log population density, were fitted within strata, or used the four "
              "SVI themes."),
        E("E-04", "replace", "The SDI is cited, as the Robert Graham Center requests; "
          + WL.lower() + "the SDI is defined in the paragraph above.", loc=m4,
          old="As a further sensitivity analysis, the unadjusted and adjusted models were repeated with "
              "the Robert Graham Center SDI (2015–2019 vintage), a published county-level measure, "
              "substituted for the EDI, to establish whether any association depended on the "
              "purpose-built index.",
          new="The models were also fitted with the published 2015–2019 SDI (13) in place of the EDI to "
              "test whether any association depended on the purpose-built index."),
        E("E-04", "replace", "The Mann-Whitney U test is also used for the facility versus no-facility "
          "deprivation contrast in Results.", loc=m4,
          old="Mann-Whitney U tests comparing metropolitan and nonmetropolitan counties",
          new="Mann-Whitney U tests for two-group comparisons"),
        E("E-04", "replace", WL + "same framework, stated once.",
          loc="The 3,144 counties are a complete enumeration rather than a probability sample.",
          old="The 3,144 counties are a complete enumeration rather than a probability sample. "
              "Confidence intervals and P values are therefore interpreted within a superpopulation "
              "framework, treating the observed distribution of facilities as one realization of a "
              "stochastic siting process, and quantify uncertainty about that process rather than "
              "sampling error.",
          new="Because the 3,144 counties are a complete enumeration, confidence intervals and P values "
              "are interpreted within a superpopulation framework, as uncertainty about the stochastic "
              "process that sites facilities rather than sampling error."),
        E("R2-02", "insert_after", "Declares the primary hypothesis family and the multiplicity "
          "procedures.", loc="A two-sided P < 0.05 was considered significant.",
          anchor="A two-sided P < 0.05 was considered significant.",
          text=f" The primary hypothesis family was the {words[n_prim]} metropolitan-adjusted SVI and EDI "
               f"associations, with Holm-adjusted P values (14); Benjamini-Hochberg false discovery "
               f"rate-adjusted values are given for the {n_ext} negative binomial index associations "
               f"reported (15) (Supplementary Table S3). Sensitivity analyses were intended to assess "
               f"the robustness of the primary findings."),
        E("R2-01", "replace", "Software used for the PCA named (reproducibility).",
          loc="A two-sided P < 0.05 was considered significant.",
          old="statsmodels 0.14 and SciPy 1.13.", new="statsmodels 0.14, SciPy 1.13, and scikit-learn 1.4."),
        E("E-04", "replace", WL + "same statement.", loc="A two-sided P < 0.05 was considered significant.",
          old="approval was therefore not required", new="approval was not required"),
    ]

    # ---------------------------------------------------------------- Results
    r1 = "We identified 722 accredited CMR and 1,542 accredited CCT facilities."
    r3 = "In unadjusted models, greater economic deprivation was associated with lower CMR"
    r4 = "Mean county-level CMR rates were lower in more deprived EDI quintiles"
    r5 = "To establish whether these findings depended on the purpose-built index, we repeated"
    ed += [
        E("E-04", "replace", "Consistent naming with the supplement.", loc=r1,
          old="(Figure 1A; Supplemental Figure S1)", new="(Figure 1A; Supplementary Figure S1)"),
        E("R1-02", "insert_after", "Pooled rates include every county; the excluded counties had no "
          "facilities, so the exclusion cannot create unstable rates.", loc=r1,
          anchor="(Mann-Whitney P < 0.001 for both; Table 1).",
          text=f" Pooled rates, which include every county, were "
               f"{rates['metropolitan']['CMR_pooled']:.2f} versus "
               f"{rates['nonmetropolitan']['CMR_pooled']:.2f} per 100,000 adults for CMR and "
               f"{rates['metropolitan']['CCT_pooled']:.2f} versus "
               f"{rates['nonmetropolitan']['CCT_pooled']:.2f} for CCT; none of the {exc['n']} counties "
               f"excluded from county-level rates had an accredited facility."),
        E("E-04", "replace", "These are the unadjusted estimates; " + NS.lower(),
          loc="In negative binomial regression, the SVI was not associated",
          old="In negative binomial regression, the SVI was not associated with CMR capacity",
          new="In unadjusted models, the SVI was not significantly associated with CMR capacity"),
        E("E-04", "replace", "Nonsignificant correlations do not confirm absence.",
          loc="Spearman correlations confirmed the absence",
          old="Spearman correlations confirmed the absence of a monotonic relationship",
          new="Spearman correlations were small and not significant"),
        E("E-04", "replace", WL + "the IRR gives the size of the association.", loc=r3,
          old=", a 5.2% lower facility rate for each 10-percentile increase in deprivation; the "
              "association for the more widely available CCT did not reach significance",
          new="; the association for CCT was not significant"),
        E("E-04", "replace", NS, loc=r3,
          old="deprivation was no longer associated with capacity",
          new="deprivation was no longer significantly associated with capacity"),
        E("E-04", "replace", CONV + " Completeness: with ordinal RUCC adjustment the EDI–CCT "
          "association is modestly positive (Table 3).", loc=r3,
          old="(CMR: IRR 1.00; 95% CI, 0.97–1.04; P = 0.801).",
          new=f"(CMR: {fe(rucc_cmr)}), and the EDI–CCT association was modestly positive "
              f"(P = {rucc_cct['p']:.3f})."),
        E("E-04", "replace", NS, loc=r3,
          old="Within metropolitan counties, deprivation was not associated",
          new="Within metropolitan counties, deprivation was not significantly associated"),
        E("R2-03", "replace", "The stratum is estimable: its NB2 dispersion lies on the boundary "
          "alpha = 0, where the maximum-likelihood fit is the Poisson fit.", loc=r3,
          old="Within nonmetropolitan counties the point estimate was lower (IRR 0.70), but the "
              "confidence interval and P value were not estimable because the stratum contains only 14 "
              "accredited CMR facilities; this estimate is descriptive and hypothesis-generating "
              "(Table 3).",
          new=f"Within nonmetropolitan counties, whose {nm['events']} accredited CMR facilities were "
              f"each in a different county, greater deprivation was associated with lower CMR capacity "
              f"({fe(nm['estimate'])}; interaction P = {inter['interaction_ratio']['p']:.3f}) "
              f"(Table 3). It was similar with a profile-likelihood interval "
              f"({det['poisson_profile']['ci_low']:.2f}–{det['poisson_profile']['ci_high']:.2f}), with "
              f"adjustment for ordinal RUCC (IRR {det['within_stratum_ordinal_rucc']['irr']:.2f}), and "
              f"with the SVI (IRR {S['strata']['SVI_CMR_nonmetro']['estimate']['irr']:.2f}) and SDI "
              f"(IRR {S['strata']['SDI_CMR_nonmetro']['estimate']['irr']:.2f}) (Supplementary Table "
              f"S4), but it is hypothesis-generating."),
        E("R1-02", "replace", "Consistent naming; pooled (population-weighted) quintile contrast "
          "added.", loc=r4,
          old="(Kruskal-Wallis P < 0.001; Supplemental Figure S2).",
          new=f"(Kruskal-Wallis P < 0.001; Supplementary Figure S2). For pooled rates the "
              f"corresponding difference was {mn['quintiles']['q1_over_q5_ratio_pooled']:.1f}-fold."),
        E("E-04", "replace", "The comparison sample is stated: the quintile counties (at least 1,000 "
          "adults aged 45+ and an EDI value).", loc=r4,
          old="Counties with no accredited facility had higher mean deprivation scores than counties "
              "with at least one",
          new=f"In the {n_q:,} quintile counties, those with no accredited facility had higher mean "
              f"deprivation scores than those with at least one"),
        E("E-04", "replace", WL + "the adjusted SVI and EDI results are given above and interpreted in "
          "the Discussion.", loc=r4,
          old=" (Pearson r = 0.82), but after adjustment for metropolitan status they did not behave "
              "identically: neither showed an inverse deprivation gradient, and whereas the EDI was not "
              "associated with capacity for either modality, the SVI was associated with modestly higher "
              "CCT capacity (Figure 1B).",
          new=" (Pearson r = 0.82)."),
        E("E-04", "replace_para", "The SDI analysis is a comparison with a published index fitted to "
          "the same counties, not validation in an independent population.",
          loc="External Validation With a Published Index", exact=True,
          new="Comparison With a Published Index"),
        E("E-04", "replace", CONV, loc=r5, old="CCT: IRR 2.12", new=f"CCT: IRR {sdi_ct['IRR']:.2f}"),
        E("E-04", "replace", NS, loc=r5, old="The SDI was not associated with CMR capacity",
          new="The SDI was not significantly associated with CMR capacity"),
        E("E-04", "delete", WL + "the direction is given by the estimates.", loc=r5,
          span=" These associations point toward greater accredited capacity in more deprived counties, "
               "not less."),
        E("E-04", "replace", WL + "same values (also in the Figure 2 legend and Table 4).", loc=r5,
          old="The two indices differed in how strongly they encoded rurality: the EDI correlated with the "
              "ordinal RUCC at ρ = 0.25, with a mean 16.2-percentile gap between nonmetropolitan and "
              "metropolitan counties, whereas the SDI correlated at ρ = 0.07 with a gap of 7.1 "
              "percentile points.",
          new=f"The EDI encoded rurality more strongly than the SDI (Spearman ρ with ordinal RUCC, "
              f"{rl['EDI']['spearman_vs_rucc']:.2f} vs {rl['SDI']['spearman_vs_rucc']:.2f}; mean "
              f"nonmetropolitan–metropolitan gap, {rl['EDI']['gap']:.1f} vs {rl['SDI']['gap']:.1f} "
              f"percentile points; Figure 2)."),
        E("R2-01", "insert_after", "PCA result (moved from Methods, R1-01) with the scree plot, biplot "
          "and loadings requested.", loc=r5, anchor="percentile points; Figure 2).",
          text=f" The EDI's first principal component explained "
               f"{100 * P['variance_explained'][0]:.1f}% of the variance in its six indicators "
               f"(eigenvalue {P['eigenvalues'][0]:.2f}), all six loaded positively "
               f"(loadings, {lo_l:.2f}–{hi_l:.2f}), and a second component (eigenvalue "
               f"{P['eigenvalues'][1]:.2f}; {100 * P['variance_explained'][1]:.1f}% of variance) "
               f"reflected mainly housing cost burden; parallel analysis retained "
               f"{['no', 'one', 'two'][P['parallel_analysis']['n_retained']]} component (Supplementary "
               f"Figure S3; Supplementary Table S5)."),
        E("E-04", "replace", WL + "Methods states the purpose of the SDI analysis.", loc=r5,
          old="To establish whether these findings depended on the purpose-built index, we repeated the "
              "analysis with the Robert Graham Center SDI, which matched",
          new="The SDI matched"),
    ]

    spec_wins = _spec_wins()
    w_sc = wm["SVI_CCT_adjusted"]["poisson_population_weighted_robust"]
    w_ea = wm["EDI_CMR_adjusted"]["poisson_population_weighted_robust"]
    fa_sc = mn["regressions"]["sensitivity_fixed_alpha"]["SVI_CCT"]["adjusted_metro"]["p"]
    assert w_sc["p"] < 0.05 and w_ea["p"] >= 0.05 and fa_sc >= 0.05
    assert W["max_abs_irr_change_rate_eligible_adjusted"] < 0.001
    assert sc["holm_primary"] < 0.05 and sc["bh_extended"] < 0.05
    sens = (f"In every sensitivity analysis, metropolitan status or rurality remained strongly "
            f"associated with capacity where it was modeled, and no model adjusted for metropolitan "
            f"status showed a significant inverse deprivation gradient (Supplementary Table S2); the "
            f"SVI–CCT association was not significant with the dispersion fixed at 1 (P = {fa_sc:.3f}). "
            f"The estimated-dispersion model had lower AIC and BIC than the Poisson and "
            f"fixed-dispersion models in all {spec_wins} index-outcome models. Restricting the cohort to "
            f"Accredited facilities changed no conclusion, and restricting the regressions to counties "
            f"with at least 1,000 eligible adults changed no adjusted index IRR by more than 0.001. "
            f"Population-weighted SVI and EDI estimates led to the same conclusions: SVI–CCT remained "
            f"positive ({fe(w_sc)}) and adjusted EDI–CMR not significant ({fe(w_ea)}; Table 3). The "
            f"adjusted SVI–CCT association remained significant after Holm adjustment within the primary "
            f"family (P = {sc['holm_primary']:.3f}) and after false discovery rate adjustment across the "
            f"{n_ext} negative binomial index associations (P = {sc['bh_extended']:.3f}) "
            f"(Supplementary Table S3).")
    met = um["SVI_CCT: metropolitan counties only"]["estimate"]
    non = um["SVI_CCT: nonmetropolitan counties only"]["estimate"]
    den = um["SVI_CCT: metropolitan status + log population density"]["estimate"]
    catden = um["SVI_CMR: categorical RUCC + log population density"]["estimate"]
    sv_int = S["interaction"]["SVI_CCT"]["interaction_ratio"]["p"]
    assert met["p"] < 0.05 <= non["p"] and den["p"] >= 0.05 and sv_int >= 0.05
    explore = (f"In exploratory analyses, the SVI–CCT association was detected in metropolitan but not "
               f"nonmetropolitan counties ({fe(met, p=False)} and {fe(non, p=False)}; interaction "
               f"P = {sv_int:.3f}) and was strongest for the SVI themes of housing type and "
               f"transportation ({fe(th['SVI_CCT_theme4']['adjusted_metro'], p=False)}) and racial and "
               f"ethnic minority status ({fe(th['SVI_CCT_theme3']['adjusted_metro'], p=False)}), which "
               f"rose with density within metropolitan counties "
               f"(ρ = {dsc['spearman_theme4_density_metro']['rho']:.2f} and "
               f"{dsc['spearman_theme3_density_metro']['rho']:.2f}); it was no longer significant after "
               f"adjustment for population density ({fe(den)}); with finer adjustment for urbanicity "
               f"(categorical RUCC and density), the SVI–CMR association was inverse ({fe(catden)}) "
               f"(Supplementary Table S6).")
    ed += [
        E("R1-01", "new_para_after", "Results subsection for the sensitivity and exploratory analyses.",
          loc="matched 3,133 of 3,144 counties", model="Distribution of Accredited Capacity",
          text="Sensitivity and Exploratory Analyses"),
        E("R1-01", "new_para_after", "Sensitivity findings reported in Results (moved from Methods), "
          "with population weighting (R1-02) and multiplicity (R2-02).",
          loc="Sensitivity and Exploratory Analyses", model="matched 3,133 of 3,144 counties",
          text=sens),
        E("R1-04", "new_para_after", "Exploratory analyses of the positive SVI–CCT association.",
          loc="In every sensitivity analysis, metropolitan status or rurality remained",
          model="matched 3,133 of 3,144 counties", text=explore),
    ]

    # ------------------------------------------------------------- Discussion
    d1 = "Accredited advanced cardiac imaging in the United States is concentrated"
    d2 = "Whether an unadjusted deprivation association is detected"
    d3 = "consistent with the higher cost of establishing CMR"
    d4 = "Whether incentives modeled on shortage-area designations"
    ed += [
        E("R1-03", "replace", "Terminology.", loc=d1,
          old="Most counties, and the rural populations within them, have",
          new="Most counties, including nearly all nonmetropolitan counties, have"),
        E("E-04", "replace", WL + "the unadjusted SVI results are in Results.", loc=d1,
          old="In unadjusted models the SVI showed no association with CMR capacity and a modest positive "
              "association with CCT capacity, whereas an economically focused deprivation index showed an "
              "inverse association for CMR. That association did not persist",
          new="The EDI's unadjusted inverse association with CMR capacity did not persist"),
        E("R1-03", "replace", "Terminology; 'largely' reflects the nonmetropolitan stratum result "
          "(R2-03).", loc=d1,
          old="indicating that it reflected the rural–urban gradient",
          new="indicating that it largely reflected the metropolitan–nonmetropolitan gradient"),
        E("E-04", "replace", "The SDI comparison uses the same counties, so it is a comparison with a "
          "published index rather than external validation; " + WL.lower() + "the next sentence states "
          "that every index reproduced the metropolitan concentration.",
          loc="External validation supports this interpretation.",
          old="External validation supports this interpretation. A published index that encodes rurality "
              "only weakly, the Robert Graham Center SDI, showed no inverse association with capacity "
              "even before adjustment, while reproducing the metropolitan effect almost exactly.",
          new="A published index supports this interpretation: the SDI, which encodes rurality only "
              "weakly, showed no inverse association with capacity even before adjustment."),
        E("E-04", "replace", "Inference from three indices, stated as such.", loc=d2,
          old="is detected at all therefore depends", new="is detected therefore appears to depend"),
        E("E-04", "replace", WL + "same statement.", loc=d2,
          old="whereas the concentration of capacity in metropolitan counties was reproduced",
          new="whereas metropolitan concentration was reproduced"),
        E("E-04", "delete", WL + "Methods states that the SVI blends economic with non-economic domains "
          "and was built for disaster preparedness.", loc=d2,
          span=" Because the SVI folds economic disadvantage together with non-economic domains (minority "
               "status, household composition, housing, and transportation) and was designed for "
               "disaster preparedness rather than health care access, its breadth may dilute any "
               "economic signal."),
        E("R2-03", "replace", "Scope: the primary (covariate-adjusted) models, nonsignificance not "
          "stated as absence, the estimate given in Results; the nonmetropolitan exception stated.",
          loc=d2,
          old="More important, neither index showed an inverse deprivation gradient once metropolitan "
              "status was included in the model: the adjusted EDI associations were null, and the "
              "adjusted SVI–CCT association was modestly positive (IRR 1.03; 95% CI, 1.01–1.06; "
              "P = 0.008), the opposite direction from a deprivation disadvantage.",
          new=f"More important, neither index showed a significant inverse deprivation gradient in the "
              f"primary models adjusted for metropolitan status: the adjusted "
              f"EDI associations were not significant, and the adjusted SVI–CCT association was modestly "
              f"positive, the opposite direction from a deprivation disadvantage. The exception was the "
              f"{nm['events']} CMR facilities outside metropolitan areas, which lay in less-deprived "
              f"nonmetropolitan counties, a pattern consistent across all three indices but too sparse "
              f"for firm conclusions."),
        E("E-04", "delete", WL + "the cost components are listed in the economics paragraph.", loc=d3,
          span=", including dedicated equipment, specialized technologists, and interpreting physicians"),
        E("E-04", "replace", WL + "the Introduction cites these studies (4-6) for the same point.", loc=d3,
          old="These findings extend prior work. Earlier studies mapped CMR adoption using survey and "
              "Medicare claims data (4), showed that CCT and CMR services are concentrated in large "
              "metropolitan academic centers and that distance to a cardiovascular imaging center is "
              "associated with the likelihood of receiving imaging (5), and described limited CCT "
              "availability at safety-net hospitals (6). In our data the unadjusted",
          new="The unadjusted"),
        E("E-04", "replace", "Precision: the eightfold and twofold figures are the adjusted metropolitan "
          "IRRs; mean county rates differ far more.", loc=d3,
          old="Metropolitan counties had approximately eightfold higher CMR capacity",
          new="Metropolitan status was associated with approximately eightfold higher CMR capacity"),
        E("E-04", "replace", "Implications stated as hypotheses: the data do not test what expands CMR "
          "or CCT capacity.", loc=d3,
          old="For radiology practices this points to different levers by modality: CMR expansion is a "
              "capital and workforce problem, whereas CCT expansion may respond to accreditation support "
              "and training applied to scanners already in place, which makes accreditation itself a "
              "plausible point of intervention.",
          new="For radiology practices this suggests different levers: CMR expansion may depend on "
              "capital and workforce, whereas CCT expansion may respond to accreditation support and "
              "training on existing scanners; neither was tested here."),
        E("E-04", "replace", "Statistical, not causal, wording; " + WL.lower() + "two sentences joined.",
          loc=d4,
          old="Prior work has reported that neighborhood deprivation predicts access to accredited breast "
              "imaging and advanced imaging facilities (7,8). For advanced cardiac imaging, our results "
              "indicate that such gradients are largely attributable to metropolitan location and that "
              "deprivation indices",
          new="Neighborhood deprivation has been reported to predict access to accredited breast and "
              "advanced imaging facilities (7,8); for advanced cardiac imaging, such gradients are largely "
              "accounted for by metropolitan location, and deprivation indices"),
        E("E-04", "replace", "The overlap is stated as the two documented facts it rests on; no "
          "county-level linkage was performed. Reference 11 renumbered 16.", loc=d4,
          old="The counties with the least imaging capacity overlap regions of documented excess "
              "cardiovascular mortality (1,11), although we did not link imaging supply to patient "
              "outcomes, and the design does not support causal inference.",
          new="Nonmetropolitan counties, which have the least imaging capacity, also have documented "
              "excess cardiovascular mortality (1,16), although imaging supply was not linked to "
              "outcomes here."),
        E("R1-03", "replace", "Terminology.", loc=d4,
          old="high-deprivation and rural counties", new="high-deprivation and nonmetropolitan counties"),
        E("R1-04", "new_para_after", "Plausible, non-causal explanation of the positive SVI–CCT "
          "association: tertiary centers and urban-core clustering.", loc=d4,
          text="The positive SVI–CCT association should not be read as evidence that social vulnerability "
               "attracts capacity; clustering in dense urban cores is a more plausible explanation. "
               "Within metropolitan counties the SVI themes for minority status and for housing and "
               "transportation rise with population density, so dense central counties, where tertiary "
               "centers are typically located (5), can score higher on the SVI for reasons unrelated to "
               "economic deprivation, a distinction a binary metropolitan indicator cannot make. "
               "Consistent with this, the association was detected only in metropolitan counties, was "
               "strongest for those two themes, and was attenuated by density adjustment. These "
               "analyses were exploratory, and county data cannot show whether these facilities serve "
               "the vulnerable residents of their counties."),
        E("R1-05", "new_para_after", "Economic interpretation with verified literature, including the "
          "three studies Reviewer 1 recommended (references 20-22), and alternative explanations and "
          "observational limits.", loc="The positive SVI–CCT association should not be read",
          text="Metropolitan concentration is consistent with the economics of advanced imaging. CMR "
               "and CCT require large fixed investments in scanners, site preparation, trained "
               "technologists, and subspecialty interpretation that are recovered only at sufficient "
               "volume, so services locate where population density, referral networks, and hospital "
               "infrastructure supply it. MRI adoption has responded to market and payer conditions "
               "(17), and physicians and radiologists concentrate in more populous areas (18,19). Among "
               "Medicare beneficiaries, racial gaps in access to digital mammography narrowed as the "
               "technology diffused (20), use of screening CT colonography, which Medicare did not then "
               "cover, rose steeply with income (21), and gaps in physician care by urbanicity, income, "
               "and area deprivation widened as inflation-adjusted payment declined (22). Disparities in "
               "capacity are often interpreted as evidence of bias, which these data can neither show "
               "nor exclude; the observed pattern is consistent with market size. Payer mix, "
               "certificate-of-need regulation, health-system ownership, workforce supply, and "
               "accreditation practices could also contribute; none was measured, and the "
               "cross-sectional ecologic design shows where accredited capacity is located, not why."),
    ]

    # ------------------------------------------------------------ Limitations
    lim = "The ecologic, cross-sectional design precludes inferences"
    ed += [
        E("E-04", "replace", WL + "Methods names the other accrediting organizations and the exemption.",
          loc=lim,
          old="Only ACR-accredited facilities were counted. Three other CMS-designated accrediting "
              "organizations exist, and hospitals and critical access hospitals are exempt from the "
              "accreditation requirement, so these counts understate total capacity; if unaccredited or "
              "differently accredited sites are distributed differently from ACR-accredited sites, the "
              "disparities reported here may be overstated or understated.",
          new="Because only ACR-accredited facilities were counted, these counts understate total "
              "capacity, and the disparities reported here may be overstated or understated if "
              "unaccredited or differently accredited sites are distributed differently."),
        E("E-04", "replace", "The EDI-RUCC Spearman rho is 0.25; 'strongly' overstated it.", loc=lim,
          old="are strongly correlated, and a binary", new="are correlated, and a binary"),
        E("R2-03", "replace", "Limitation of the stratified and weighted estimates stated.", loc=lim,
          old="stratified nonmetropolitan estimates are imprecise.",
          new="stratified nonmetropolitan estimates are imprecise, and differently weighted estimates "
              "answer different questions."),
        E("E-04", "replace", WL + "the SDI result is reported in Results and the Discussion.", loc=lim,
          old="Repeating the analysis with the Robert Graham Center SDI yielded the same conclusion, but "
              "the University of Wisconsin", new="The University of Wisconsin"),
        E("E-04", "delete", WL + "same statement.", loc=lim, span=", so it remains untested here"),
        E("E-04", "replace", "Table 5 presents county health indicators; the limitation is "
          "cardiovascular-specific need and that the indicators were not modeled.", loc=lim,
          old="Travel distance, use of facilities in adjacent counties, and local disease burden were "
              "not captured;",
          new="Travel distance, cross-county use, and cardiovascular-specific need were not measured, and "
              "the county health indicators in Table 5 were not modeled;"),
        E("E-04", "replace", WL + "the design is stated as cross-sectional above.", loc=lim,
          old="Finally, the analysis is a single cross-section, so change in accredited capacity over "
              "time was not assessed.",
          new="Finally, change in accredited capacity over time was not assessed."),
    ]

    # ------------------------------------------------------- Data availability
    dav = "The analytic dataset, the county-level economic deprivation index"
    ed += [
        E("E-06", "replace", "Code availability stated; " + WL.lower() + "the atlas is described here.",
          loc=dav,
          old="the county-level economic deprivation index, and a county-level cardiac imaging atlas are "
              "publicly available",
          new="the county-level economic deprivation index, the analysis code, and a county-level atlas "
              "of accredited CMR and CCT facility rates are publicly available"),
        E("E-04", "replace", "This is the revision; the bracket must not promise the URL 'at revision'. "
          "Review remains blinded, so the URL is provided on acceptance.", loc=dav,
          old="Repository URL withheld from the blinded manuscript because it identifies the authors; it "
              "is provided in the submission system and will be restored at revision.",
          new="Repository URL withheld for blinded review; it will be provided on acceptance."),
        E("E-04", "delete", WL + "same statement.", loc=dav,
          span=" The atlas maps accredited CMR and CCT facility rates across all 3,144 US counties as a "
               "standalone resource for research on geographic disparities in cardiac imaging access."),
    ]

    # ------------------------------------------------------------- References
    ed.append(E("E-04", "replace_para", "Reference rechecked; access date updated.",
                loc="2. Centers for Medicare & Medicaid Services",
                new="2. Centers for Medicare & Medicaid Services. Accreditation of advanced diagnostic "
                    "imaging suppliers. Available at: https://www.cms.gov/medicare/health-safety-"
                    "standards/quality-safety-oversight-general-information/accreditation-advanced-"
                    "diagnostic-imaging-suppliers. Accessed November 8, 2026."))
    ed.append(E("E-04", "replace_para", "New reference 11 (RUCC documentation, R1-03); Siddiqi et al. "
                "renumbered 16 in order of first citation.", loc="11. Siddiqi AK",
                new="11. US Department of Agriculture Economic Research Service. Rural-Urban Continuum "
                    "Codes, 2023: documentation. Available at: https://www.ers.usda.gov/data-products/"
                    "rural-urban-continuum-codes/documentation. Accessed November 8, 2026."))
    appended = [
        "12. Solon G, Haider SJ, Wooldridge JM. What are we weighting for? J Hum Resour. "
        "2015;50(2):301–316.",
        "13. Butler DC, Petterson S, Phillips RL, Bazemore AW. Measures of social deprivation that "
        "predict health care access and need within a rational area of primary care service delivery. "
        "Health Serv Res. 2013;48(2 Pt 1):539–559.",
        "14. Holm S. A simple sequentially rejective multiple test procedure. Scand J Stat. "
        "1979;6(2):65–70.",
        "15. Benjamini Y, Hochberg Y. Controlling the false discovery rate: a practical and powerful "
        "approach to multiple testing. J R Stat Soc Series B Stat Methodol. 1995;57(1):289–300.",
        "16. Siddiqi AK, Ali KM, Maniya MT, et al. The hidden epidemic: hypertension-related mortality "
        "surges amongst younger adults in the United States. Curr Probl Cardiol. 2024;49(12):102842.",
        "17. Baker LC. Managed care and technology adoption in health care: evidence from magnetic "
        "resonance imaging. J Health Econ. 2001;20(3):395–421.",
        "18. Rosenthal MB, Zaslavsky A, Newhouse JP. The geographic distribution of physicians "
        "revisited. Health Serv Res. 2005;40(6 Pt 1):1931–1952.",
        "19. Rosenkrantz AB, Hughes DR, Duszak R Jr. The U.S. radiologist workforce: an analysis of "
        "temporal and geographic variation by using large national datasets. Radiology. "
        "2016;279(1):175–184.",
        # Recommended by Reviewer 1 (comment 5); details verified against Europe PMC.
        "20. Christensen EW, Waid M, Scott J, et al. Relationship between race and access to newer "
        "mammographic technology in women with Medicare insurance. Radiology. 2023;306(2):e221153.",
        "21. Christensen EW, Sanelli PC, Rula EY, et al. Sociodemographic factors and screening CT "
        "colonography use among Medicare beneficiaries. AJR Am J Roentgenol. 2024;222(1):e2329703.",
        "22. Christensen EW, Drake AR, Nicola GN, et al. Association between the declining conversion "
        "factor and access to care for Medicare beneficiaries. Inquiry. 2026;63:00469580261473400.",
    ]
    prev = "11. US Department of Agriculture"
    for text in appended:
        ed.append(E("E-04", "new_para_after", "New or renumbered reference.", loc=prev, text=text))
        prev = text[:24]

    # ---------------------------------------------------------- Figure legends
    ed += [
        E("E-04", "replace", CONV, loc="Figure 1. Accredited cardiac MR capacity",
          old="SVI models: IRR 8.56 for cardiac MR", new=f"SVI models: IRR {svi_m['irr']:.2f} for cardiac MR"),
        E("E-04", "replace", "Scope: the primary models shown in the figure.",
          loc="Figure 1. Accredited cardiac MR capacity",
          old="Neither index showed an inverse deprivation gradient once metropolitan status was included "
              "in the model;",
          new="In these primary models, neither index showed a significant inverse deprivation gradient "
              "once metropolitan status was included;"),
        E("E-04", "replace", "Figure 2 is a comparison with a published index, not validation.",
          loc="Figure 2. External validation of the deprivation finding",
          old="Figure 2. External validation of the deprivation finding with a published county-level "
              "index.",
          new="Figure 2. Comparison of the deprivation finding with a published county-level index."),
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
                    model = _para(doc, e["model"]) if e.get("model") else None
                    doc.insert_paragraph_after(p, e["text"], model=model)
            elif k == "delete_para":
                hits = [q for q in doc.paragraphs()
                        if (doc.accepted_text(q).strip() == e["loc"] if e.get("exact")
                            else e["loc"] in doc.accepted_text(q))]
                if not hits:
                    status = "already applied"
                else:
                    doc.delete_paragraph(hits[0])
                    e["old"] = e["loc"]
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
            elif k == "table_after":
                if any(doc.accepted_text(q).startswith(e["title"][:40]) for q in doc.paragraphs()):
                    status = "already applied"
                else:
                    foot = _para(doc, e["loc"])
                    tp = doc.insert_paragraph_after(foot, e["title"], model=_para(doc, e["title_model"]))
                    model_tbl = tables[e["model_table"]]
                    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                    widest = max(model_tbl.findall(ns + "tr"), key=lambda r: len(r.findall(ns + "tc")))
                    total = sum(int(tc.find(ns + "tcPr/" + ns + "tcW").get(ns + "w"))
                                for tc in widest.findall(ns + "tc"))
                    ncol = len(e["rows"][0])
                    share = e["widths"]
                    assert len(share) == ncol, "one width per Table 4 column"
                    widths = [int(total * w / sum(share)) for w in share]
                    bold = [i for i, r in enumerate(e["rows"]) if i == 0 or not any(r[1:])]
                    tbl = doc.insert_table_after(tp, e["rows"], model_tbl, widths, bold_rows=bold)
                    doc.insert_paragraph_after(tbl, e["note"], model=foot)
                where = "after Table 3"
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
                    "new": e.get("new", e.get("text", "") if k not in ("rows_after", "table_after")
                                 else (e["title"] if k == "table_after"
                                       else " | ".join(" / ".join(r) for r in e["rows"]))),
                    "rationale": e["why"]})
        print(f"  {status:<18} {e['task']:<6} {k:<14} {where[:60]}")
    return applied, skipped


HEADINGS = {"INTRODUCTION", "METHODS", "RESULTS", "DISCUSSION", "STUDY LIMITATIONS", "CONCLUSION",
            "DATA AVAILABILITY", "REFERENCES"}
#: Subheadings. The submitted manuscript's stated count (2,493) excludes them,
#: and its abstract count (246) excludes the four section labels; both counts
#: here follow those definitions.
SUBHEADINGS = {"Study Design and Data Sources", "Measures of Area Disadvantage",
               "Metropolitan Status and Statistical Analysis", "Distribution of Accredited Capacity",
               "Social Vulnerability Index", "Economic Deprivation Index",
               "External Validation With a Published Index", "Comparison With a Published Index",
               "Sensitivity and Exploratory Analyses"}


def _accepted_paragraphs(path):
    spec = importlib.util.spec_from_file_location(
        "gate", os.path.join(BASE_DIR, "code", "12_manuscript_numbers.py"))
    sys.path.insert(0, os.path.join(BASE_DIR, "code"))
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    _, _, paras = gate.read_manuscript(path)
    return [t.strip() for t in paras if t.strip()]


def body_word_count(path):
    """Introduction through Data Availability, without headings, subheadings,
    bracketed editorial notes, or the AI-use declaration that follows."""
    paras = _accepted_paragraphs(path)
    lo = paras.index("INTRODUCTION")
    hi = next(i for i, t in enumerate(paras)
              if t.startswith("Declaration of generative AI") or t.upper() == "REFERENCES")
    return sum(len(t.split()) for t in paras[lo:hi]
               if t.upper() not in HEADINGS and t not in SUBHEADINGS and not t.startswith("["))


def abstract_word_count(path):
    """The four abstract sections, without their labels."""
    paras = _accepted_paragraphs(path)
    i = next(k for k, t in enumerate(paras) if t.upper() == "ABSTRACT")
    secs = [t for t in paras[i + 1:i + 6] if t.split(":")[0] in ("Objective", "Methods", "Results",
                                                                  "Discussion")]
    assert len(secs) == 4, secs
    return sum(len(t.split(":", 1)[1].split()) for t in secs)


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

    # The front-matter counts must describe the revised text. Count them under
    # the manuscript's own definitions, then record the line as a tracked edit.
    words, abs_words = body_word_count(args.dest), abstract_word_count(args.dest)
    doc = TrackedDocument(args.dest, author=author, date=DATE, revision_id_base=300_000)
    p = doc.find_paragraph("Word count: ")
    cur = doc.accepted_text(p)
    new = (f"Word count: {words:,} (Introduction through Data Availability, excluding abstract, "
           f"references, tables, and figure legends). Abstract: {abs_words} words. Tables and figures: "
           f"5 tables, 2 figures (7 of 7 permitted); 3 supplementary figures. References: 22.")
    if cur != new:
        doc.replace(p, cur, new)
        log.append({"task": "E-04", "kind": "replace", "location": "Front matter", "status": "applied",
                    "old": cur, "new": new,
                    "rationale": "Counts recomputed for the revised text; a fifth table (population "
                                 "characteristics) and a third supplementary figure (PCA) were added."})
        print(f"  applied            E-04   replace        front-matter counts -> {words:,} / {abs_words}")
    if args.blind:
        # The submitted file's own metadata named its author; the blinded copy must not.
        doc.scrub_identity("Author")
    doc.save(args.dest)
    print(f"\n  {applied} applied, {skipped} skipped; body words {words:,}; abstract words {abs_words}")
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
