#!/usr/bin/env python3
"""
19_supplementary_material.py
============================
Builds the online supplement: supplementary methods, Tables S1-S6, and the
legends and images of Figures S1-S3, as one Word document, plus a CSV of every
table.

Every value is read from generated results; nothing is refitted here.

Inputs
    output/results/reviewer_analyses.json        18_reviewer_analyses.py
    output/results/comprehensive_model_table.csv 18_reviewer_analyses.py
    output/results/model_specification_comparison.csv  13_model_specification.py
    output/validation/manuscript_numbers.json    12_manuscript_numbers.py
    output/figures/FigureS{1,2,3}_*.png          16_publication_figures.py

Outputs
    output/tables/Supplementary_Material.docx
    output/tables/Supplementary_Table_S{1..6}_*.csv

Table numbering follows order of first citation in the revised manuscript:
    S1 County population characteristics (Methods)            E-05
    S2 All primary and sensitivity models; model fit (Methods) R2-05, R1-02
    S3 Multiplicity adjustment (Methods)                        R2-02
    S4 Sparse nonmetropolitan stratum diagnostics (Results)     R2-03
    S5 EDI principal component analysis (Results)               R2-01
    S6 Exploratory urbanicity analyses of the SVI (Results)     R1-04
"""

from __future__ import annotations

import csv
import json
import os

import numpy as np
import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(BASE_DIR, "output", "results")
VALID = os.path.join(BASE_DIR, "output", "validation")
FIG = os.path.join(BASE_DIR, "output", "figures")
TABLES = os.path.join(BASE_DIR, "output", "tables")
OUT_DOCX = os.path.join(TABLES, "Supplementary_Material.docx")

ABBREV = ("CCT = cardiac computed tomography; CI = confidence interval; CMR = cardiac "
          "magnetic resonance; EDI = economic deprivation index; IRR = incidence rate "
          "ratio; NB2 = negative binomial (quadratic variance); NE = not estimable; "
          "RUCC = Rural-Urban Continuum Code; SDI = Social Deprivation Index; SVI = "
          "Social Vulnerability Index.")


# --------------------------------------------------------------------- format
def f_est(irr, lo, hi, dp=2):
    if irr is None or not np.isfinite(irr):
        return "NE"
    if lo is None or hi is None or not (np.isfinite(lo) and np.isfinite(hi)):
        return f"{irr:.{dp}f} (NE)"
    return f"{irr:.{dp}f} ({lo:.{dp}f}-{hi:.{dp}f})"


def f_e(e, dp=2):
    return f_est(e["irr"], e["ci_low"], e["ci_high"], dp)


def f_p(p):
    if p is None or not np.isfinite(p):
        return "NE"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def f_pe(p):
    """P value with its relation sign: 'P = 0.003', 'P < 0.001'."""
    t = f_p(p)
    return "P NE" if t == "NE" else ("P < 0.001" if t == "<0.001" else f"P = {t}")


def f_n(x):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return ""
    return f"{int(x):,}"


# ----------------------------------------------------------------------- docx
def _set_cell_margins(table, twips=40):
    tbl_pr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side in ("top", "bottom", "left", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(twips))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tbl_pr.append(mar)


def add_table(doc, title, header, rows, notes, widths=None, font=7.5, bold_rows=()):
    p = doc.add_paragraph()
    r = p.add_run(title)
    r.bold = True
    r.font.size = Pt(10)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    _set_cell_margins(t)
    tr_pr = t.rows[0]._tr.get_or_add_trPr()
    hdr = OxmlElement("w:tblHeader")
    hdr.set(qn("w:val"), "true")
    tr_pr.append(hdr)
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        run = c.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(font)
    for k, row in enumerate(rows):
        cells = t.add_row().cells
        sub = all(v == "" for v in row[1:])
        for i, v in enumerate(row):
            cells[i].text = ""
            # A label written with leading spaces marks a sub-row: the spaces
            # become a real paragraph indent, never literal characters.
            text = str(v)
            if text != text.lstrip():
                cells[i].paragraphs[0].paragraph_format.left_indent = Pt(9)
            run = cells[i].paragraphs[0].add_run(text.strip())
            run.font.size = Pt(font)
            if sub or k in bold_rows:
                run.bold = True
    if widths:
        # Fixed layout with an explicit grid, so Word and LibreOffice both
        # honour the column widths instead of autofitting.
        t.autofit = False
        tbl_pr = t._tbl.tblPr
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        tbl_pr.append(layout)
        grid = t._tbl.tblGrid
        for i, gc in enumerate(grid.findall(qn("w:gridCol"))):
            if i < len(widths):
                gc.set(qn("w:w"), str(int(widths[i] * 1440)))
        for i, col in enumerate(t.columns):
            if i < len(widths):
                col.width = Inches(widths[i])
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    for n in notes:
        q = doc.add_paragraph()
        run = q.add_run(n)
        run.font.size = Pt(7.5)
    doc.add_paragraph()
    return t


def write_csv(name, header, rows, notes):
    path = os.path.join(TABLES, name)
    # utf-8-sig writes a byte-order mark so Excel reads "≥" and "ρ" as UTF-8.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows([[str(v).strip() for v in r] for r in rows])
        w.writerow([])
        for n in notes:
            w.writerow([n])
    return path


def section(doc, landscape):
    s = doc.add_section()
    if landscape:
        s.orientation = WD_ORIENT.LANDSCAPE
        s.page_width, s.page_height = Inches(11), Inches(8.5)
    else:
        s.orientation = WD_ORIENT.PORTRAIT
        s.page_width, s.page_height = Inches(8.5), Inches(11)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(s, side, Inches(0.8))
    return s


def heading(doc, text, size=12):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)
    return p


def para(doc, text, size=10):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    return p


# --------------------------------------------------------------------- tables
def cohort_facts():
    """Cohort and county-assignment counts, read from the audit trail and extract."""
    a = pd.read_csv(os.path.join(BASE_DIR, "data", "processed", "facility_mapping_audit.csv"), dtype=str)
    inc = a[a.final_included == "True"]
    share = pd.to_numeric(inc.mapping_share, errors="coerce")
    calcium_only = int(a["ct_calcium_score_only"].astype(str).str.lower().eq("true").sum())
    return {"included": len(inc), "cmr": int((inc.modality_label == "CMR").sum()),
            "cct": int((inc.modality_label == "CCT").sum()),
            "accredited": int((inc.status == "Accredited").sum()),
            "under_review": int((inc.status == "Under Review").sum()),
            "hud": int((inc.mapping_method == "hud_res_ratio").sum()),
            "manual": int((inc.mapping_method == "manual_zip_override").sum()),
            "share_lt1": int((share < 1).sum()), "share_lt90": int((share < 0.9).sum()),
            "calcium_only": calcium_only}


def table_s1(R, N):
    C = R["E-05_population"]
    strata = [("all", "All counties"), ("metropolitan", "Metropolitan (RUCC 1-3)"),
              ("nonmetropolitan", "Nonmetropolitan (RUCC 4-9)"),
              ("any_facility", "≥1 accredited CMR or CCT facility"),
              ("no_facility", "No accredited facility")]
    header = ["Characteristic"] + [lab for _, lab in strata]
    rows = [["Counties, No."] + [f"{C['strata'][k]['counties']:,}" for k, _ in strata],
            ["Total population, millions"] + [f"{C['strata'][k]['population_millions']:.1f}" for k, _ in strata],
            ["Adults aged ≥45 y, millions"] + [f"{C['strata'][k]['adults_45plus_millions']:.1f}" for k, _ in strata]]
    groups = [("Age and sex", ["pct_65plus", "pct_female"]),
              ("Race and ethnicity", ["pct_nh_white", "pct_nh_black", "pct_hispanic", "pct_nh_asian",
                                      "pct_nh_aian", "pct_nh_nhpi", "pct_nh_multi_other"]),
              ("Socioeconomic and access", ["pct_pov150", "pct_uninsured", "pct_disability",
                                            "density", "pcp"]),
              ("Population health (county-level estimates)",
               ["diabetes", "obesity", "smoking", "inactivity", "premature_mortality"])]
    for g, keys in groups:
        rows.append([g] + [""] * len(strata))
        for key in keys:
            v = C["variables"][key]
            dp = 0 if key in ("density", "premature_mortality") else 1
            cells = []
            for s, _ in strata:
                b = v["by_stratum"][s]
                cells.append(f"{b['population_weighted_mean']:.{dp}f} "
                             f"[{b['median']:.{dp}f} ({b['q1']:.{dp}f}-{b['q3']:.{dp}f})]")
            nmiss = v["by_stratum"]["all"]["n_missing"]
            rows.append([v["label"] + (f" (missing, {nmiss} counties)" if nmiss else "")] + cells)
    miss = {k: v["by_stratum"]["all"]["n_missing"] for k, v in C["variables"].items()}
    chr_missing = max(miss[k] for k in ("pct_female", "diabetes", "obesity", "smoking",
                                        "inactivity", "premature_mortality", "pcp"))
    notes = [
        "Values are total-population-weighted averages of county estimates [county median "
        "(interquartile range)]. Each county's published estimate is weighted by its total "
        "population; for measures defined on adults, or age-adjusted, this approximates but is "
        "not identical to a pooled value for the stratum, and the density value is the density "
        "experienced by the average resident, not total population divided by total area. "
        "Medians describe the distribution across counties. Missing counts are for all "
        "counties.",
        "Unit of observation is the county. These are characteristics of county "
        "residents, not of patients imaged at accredited facilities; the study used no "
        "patient-level data, and cardiovascular disease prevalence, disease severity, "
        "and gender identity were not available.",
        "Sources: CDC/ATSDR Social Vulnerability Index 2022 component estimates "
        "(American Community Survey 2018-2022) for age, race and ethnicity, poverty, "
        "insurance, and disability; County Health Rankings & Roadmaps 2024 (University of "
        "Wisconsin Population Health Institute; www.countyhealthrankings.org) for sex "
        "(Census population estimates) and for diabetes, obesity, smoking, physical "
        "inactivity (model-based estimates), premature age-adjusted mortality, and "
        "primary care physicians; US Census Bureau population estimates for July 1, 2023 "
        "(the population weights, and with SVI land area for density). Race and ethnicity categories are mutually "
        "exclusive; all categories other than Hispanic or Latino are non-Hispanic.",
        f"County Health Rankings 2024 reports Connecticut by its former counties, so the "
        f"9 Connecticut planning regions lack those measures; other missing values are as "
        f"published (up to {chr_missing} counties for one measure).",
        "Rurality strata follow the 2023 USDA Rural-Urban Continuum Codes. " + ABBREV,
    ]
    return header, rows, notes


def table_s2(R, N):
    t = pd.read_csv(os.path.join(RESULTS, "comprehensive_model_table.csv"))
    header = ["Index", "Outcome", "Model", "Specification", "Counties, No.", "Facilities, No.",
              "Index IRR (95% CI)", "P", "Second term", "Second term IRR (95% CI)",
              "Dispersion (alpha)", "Notes"]
    rows = []
    for _, r in t.iterrows():
        e = f_est(r.irr, r.ci_low if r.estimable else np.nan, r.ci_high if r.estimable else np.nan)
        sec = (f_est(r.second_irr, r.second_ci_low, r.second_ci_high)
               if isinstance(r.second_term, str) and r.second_term else "")
        rows.append([r["index"], r.outcome, r.model, r.specification, f_n(r.n_counties),
                     f_n(r.facilities), e, f_p(r.p if r.estimable else np.nan),
                     r.second_term if isinstance(r.second_term, str) else "", sec,
                     (f"{r.alpha:.3g}" if pd.notna(r.alpha) else
                      ("0 (Poisson)" if "Poisson" in str(r.specification) else "")),
                     r.note if isinstance(r.note, str) else ""])
    spec = pd.read_csv(os.path.join(RESULTS, "model_specification_comparison.csv"))
    rows_b = []
    for (idx, oc), g in spec.groupby(["index", "outcome"], sort=False):
        best_aic = g.loc[g.aic.idxmin(), "specification"]
        best_bic = g.loc[g.bic.idxmin(), "specification"]
        for _, r in g.iterrows():
            rows_b.append([idx, oc, r.specification,
                           "" if not np.isfinite(r.alpha) else f"{r.alpha:.3f}",
                           f"{r.aic:.1f}", f"{r.bic:.1f}", f"{r.log_likelihood:.1f}",
                           f_est(r.irr, r.ci_low, r.ci_high), f_p(r.p_value),
                           "lowest" if r.specification == best_aic else "",
                           "lowest" if r.specification == best_bic else ""])
    header_b = ["Model", "Outcome", "Specification", "Alpha", "AIC", "BIC", "Log-likelihood",
                "Index IRR (95% CI)", "P", "AIC", "BIC"]
    W = R["R1-02_weighting"]["weights"]
    notes = [
        "Panel A. IRRs are per 10-percentile increase in the index. Unless noted, models are "
        "negative binomial (NB2) with the dispersion (alpha) estimated by maximum likelihood "
        "and an offset of log(adults aged ≥45 years). The primary analysis is the SVI and EDI "
        "model adjusted for metropolitan status. Second term: metropolitan status (RUCC 1-3 vs "
        "4-9), ordinal RUCC per 1-code increase, or log population density per 1-unit increase.",
        f"Panel A has {len(rows)} rows from "
        f"{len(rows) - int((t.group == 'Index coding').sum()) + int((t.group == 'Index coding').sum()) // 3} "
        "fitted models: the three SVI quartile contrasts for each outcome come from one model. "
        "Weighting: the NB2 model weights each county's rate by N/(1 + alpha x mu), which rises "
        "with population (N) and levels off. Population-weighted rows are Poisson regressions "
        "with the same offset, which weight each county's rate by its adults aged ≥45 years and "
        "so describe the average adult; rows with counties weighted equally use weights 1/N and "
        "describe the average county; both have robust (HC0) standard errors. Under population weights "
        f"the Kish effective sample size is {W['SVI']['kish_effective_n']:.0f} of "
        f"{W['SVI']['n']:,} counties, and the largest 1% of counties carry "
        f"{100 * W['SVI']['share_of_weight_top_1pct_counties']:.1f}% of the weight.",
        "Stratified rows marked Poisson: the NB2 dispersion estimate lay on its boundary "
        "(alpha = 0): alpha was near zero and the Poisson log-likelihood was at least as high as "
        "the best NB2 value, so the maximum-likelihood NB2 fit is the Poisson fit, shown here with "
        "a profile-likelihood interval. In some of these fits the information matrix also could "
        "not be inverted at the optimizer's stopping point; the decision does not depend on it. For cardiac "
        "MR each of the 14 nonmetropolitan facilities is in a different county; for cardiac CT "
        "the 115 nonmetropolitan facilities are in 108 counties (seven with two), and the counts "
        "show no overdispersion (see Supplementary Table S4 and Supplementary Methods S4). "
        "Facility totals differ by index because counties without an index value are excluded.",
        "Panel B covers the unadjusted and metropolitan-adjusted SVI, EDI and SDI models (12 "
        "index-outcome models, each fitted as Poisson, NB2 with dispersion estimated, and NB2 "
        "with dispersion fixed at 1); it does not cover the other Panel A sensitivity rows.",
        ABBREV,
    ]
    return header, rows, header_b, rows_b, notes


def table_s3(R):
    M = R["R2-02_multiplicity"]
    header = ["Test (location)", "IRR (95% CI)", "Unadjusted P", "Holm P, primary family",
              "BH P, primary family", "Holm P, all 18", "BH P, all 18"]
    rows = []
    for t in M["tests"]:
        rows.append([t["test"], f_est(t["irr"], t["ci_low"], t["ci_high"]), f_p(t["p"]),
                     f_p(t.get("holm_primary")) if t.get("holm_primary") is not None else "",
                     f_p(t.get("bh_primary")) if t.get("bh_primary") is not None else "",
                     f_p(t["holm_extended"]), f_p(t["bh_extended"])])
    fam = M["families"]
    notes = [
        f"Primary family: the {fam['primary']['n_tests']} metropolitan-adjusted SVI and EDI "
        "associations, designated as the primary analysis before review. Holm controls the "
        "family-wise error rate; Benjamini-Hochberg (BH) controls the false discovery rate.",
        f"Extended family: all {fam['extended']['n_tests']} negative binomial index associations "
        f"reported in Tables 2 and 3 and Figure 2; the population-weighted Poisson estimates in "
        f"Table 3 are a separate sensitivity analysis and not part of it. Significant at P < 0.05: unadjusted "
        f"{fam['extended']['significant_unadjusted']}, Holm {fam['extended']['significant_holm']}, "
        f"BH {fam['extended']['significant_bh']}.",
        f"Within the primary family no conclusion changed under either procedure. A further "
        f"two-test family restricted to the SVI, the designated primary predictor, gave the same "
        f"result ({fam['primary_svi_only']['significant_holm']} of "
        f"{fam['primary_svi_only']['n_tests']} significant after Holm adjustment).",
        "Metropolitan-status terms are not deprivation hypotheses and are not included; each had "
        "P < 0.001. " + ABBREV,
    ]
    return header, rows, notes


def table_s4(R):
    S = R["R2-03_strata"]
    s, det = S["strata"]["EDI_CMR_nonmetro"], S["detail"]["EDI_CMR_nonmetro"]
    inter = S["interaction"]["EDI_CMR"]
    header = ["Quantity", "Value"]
    eig = ", ".join(f"{x:.3f}" for x in s["neg_hessian_eigenvalues"])
    rows = [
        ["Stratum", f"{s['n']:,} nonmetropolitan counties; {s['events']} accredited CMR facilities, "
                    f"in {s['units_with_event']} counties (maximum 1 per county)"],
        ["NB2 fit, dispersion estimated (original)", ""],
        ["  Optimizer reported convergence", "Yes" if s["converged"] else "No"],
        ["  Estimated alpha", f"{s['alpha']:.4f}"],
        ["  Score at stopping point (const; EDI; alpha)",
         "; ".join(f"{v:.3g}" for v in s["gradient"].values())],
        ["  Eigenvalues of the negated Hessian", eig],
        ["  Log-likelihood, NB2 at stopping point", f"{s['llf_nb2']:.4f}"],
        ["  Log-likelihood, Poisson (alpha = 0)", f"{s['llf_poisson']:.4f}"],
        ["  Consequence", "Negated Hessian not positive definite; no covariance matrix, so no "
                          "standard error, confidence interval, or P value"],
        ["Boundary (Poisson) solution", ""],
        ["  EDI IRR (Wald 95% CI); P", f"{f_e(det['poisson_wald'])}; {f_p(det['poisson_wald']['p'])}"],
        ["  Profile-likelihood 95% CI; likelihood-ratio P",
         f"{det['poisson_profile']['ci_low']:.2f}-{det['poisson_profile']['ci_high']:.2f}; "
         f"{f_p(det['poisson_profile']['lr_p'])}"],
        ["  Robust (HC0) 95% CI; P", f"{f_e(det['poisson_robust'])}; {f_p(det['poisson_robust']['p'])}"],
        ["  Pearson dispersion statistic", f"{det['poisson_pearson_dispersion']:.3f}"],
        ["Dispersion held fixed", ""],
    ]
    for a, g in det["fixed_alpha_grid"].items():
        rows.append([f"  alpha = {float(a):g}" if float(a) >= 1e-3 else
                     f"  alpha = {float(a):.6f} (effectively Poisson)", f"{f_e(g)}; {f_pe(g['p'])}"])
    rows += [
        ["Alternative estimators", ""],
        ["  Interaction model, all counties (NB2, alpha estimated): nonmetropolitan EDI slope",
         f"{f_e(inter['nonmetro_slope'])}; {f_pe(inter['nonmetro_slope']['p'])}"],
        ["  Interaction model: metropolitan EDI slope",
         f"{f_e(inter['metro_slope'])}; {f_pe(inter['metro_slope']['p'])}"],
        ["  Interaction model: ratio of slopes", f"{f_e(inter['interaction_ratio'])}; "
                                                  f"{f_pe(inter['interaction_ratio']['p'])}"],
        ["  Within stratum, adjusted for ordinal RUCC (4-9)",
         f"{f_e(det['within_stratum_ordinal_rucc'])}; {f_pe(det['within_stratum_ordinal_rucc']['p'])}"],
        ["  Within stratum, adjusted for log population density",
         f"{f_e(det['within_stratum_log_density'])}; {f_pe(det['within_stratum_log_density']['p'])}"],
        ["Mean EDI percentile, counties with vs without a facility",
         f"{det['mean_index_with_facility']:.1f} vs {det['mean_index_without_facility']:.1f}"],
    ]
    other = []
    for idx in ("SVI", "SDI"):
        e = S["strata"][f"{idx}_CMR_nonmetro"]["estimate"]
        other.append(f"{idx} {f_e(e)}, {f_pe(e['p'])}")
    rows.append(["Same stratum, other indices (boundary solution)", "; ".join(other)])
    counties = "; ".join(f"{c['county']} (RUCC {c['rucc']}, EDI {c['index_percentile']:.0f})"
                         for c in det["facility_counties"])
    notes = [
        "The original report of this row as not estimable reflected the optimizer stopping just "
        "inside the boundary alpha = 0, where the Poisson log-likelihood is higher; the NB2 "
        "maximum-likelihood estimate is the Poisson fit. No interval was imputed: each is a "
        "standard likelihood-based interval for a fitted model. With 14 events the estimate is "
        "imprecise and hypothesis-generating.",
        f"Counties holding the {s['events']} facilities: {counties}.",
        "IRR per 10-percentile increase in the EDI. " + ABBREV,
    ]
    return header, rows, notes


def table_s5(R):
    P = R["R2-01_pca"]
    header = ["Indicator", "Source", "PC1 loading", "PC2 loading", "PC1 coefficient",
              "PC2 coefficient"]
    rows = []
    for f in P["features"]:
        rows.append([P["labels"][f], P["sources"][f], f"{P['pc1_loadings'][f]:.3f}",
                     f"{P['pc2_loadings'][f]:.3f}", f"{P['pc1_coefficients'][f]:.3f}",
                     f"{P['pc2_coefficients'][f]:.3f}"])
    rows.append(["Component", "", "Eigenvalue", "Variance explained, %", "Cumulative, %", ""])
    for j, (e, v, c) in enumerate(zip(P["eigenvalues"], P["variance_explained"],
                                      P["cumulative_variance"])):
        rows.append([f"PC{j + 1}", "", f"{e:.3f}", f"{100 * v:.1f}", f"{100 * c:.1f}", ""])
    notes = [
        f"Principal component analysis of the correlation matrix of six county indicators "
        f"(n = {P['n_counties']:,} counties with all six). Indicators were standardized to "
        f"z-scores before extraction; median household income was sign-reversed so that every "
        f"indicator increases with deprivation. Loadings are indicator-component correlations "
        f"(coefficient × √eigenvalue); coefficients are eigenvector elements.",
        f"The EDI is the PC1 score, converted to national percentiles (0-100). PC1 from this full "
        f"decomposition correlates with the published index at r = "
        f"{P['pc1_vs_published_edi_pearson']:.6f}. Kaiser-Meyer-Olkin measure "
        f"{P['kmo']:.2f}; Bartlett test of sphericity χ² = {P['bartlett_chi2']:,.0f}, "
        f"df = {P['bartlett_df']}, P {'< 0.001' if P['bartlett_p'] < 0.001 else '= ' + f_p(P['bartlett_p'])}.",
        f"{['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six'][P['n_components_eigenvalue_gt_1']]} "
        f"component{'' if P['n_components_eigenvalue_gt_1'] == 1 else 's'} "
        f"{'has an eigenvalue' if P['n_components_eigenvalue_gt_1'] == 1 else 'have eigenvalues'} above 1. PC2 "
        f"(eigenvalue {P['eigenvalues'][1]:.2f}) is dominated by housing cost burden and does not "
        f"exceed the 95th percentile of eigenvalues from {P['parallel_analysis']['replicates']:,} "
        f"permuted datasets ({P['parallel_analysis']['threshold_95'][1]:.2f}); parallel analysis "
        f"retains {['no', 'one', 'two', 'three'][P['parallel_analysis']['n_retained']]} "
        f"component{'' if P['parallel_analysis']['n_retained'] == 1 else 's'}, and the index "
        f"retains PC1 only, as a single economic deprivation dimension. Software: Python 3.11, "
        f"scikit-learn 1.4 (PCA, full singular value decomposition; StandardScaler).",
        "PC2 sign is fixed so that its coefficients sum to a positive value; PC2 orientation is "
        "otherwise arbitrary. " + ABBREV,
    ]
    return header, rows, notes


def table_s6(R):
    U = R["R1-04_urban_core"]
    header = ["Outcome", "Model", "Counties, No.", "SVI IRR (95% CI)", "P"]
    rows = []
    for oname, long in (("CCT", "Cardiac CT"), ("CMR", "Cardiac MR")):
        rows.append([long, "", "", "", ""])
        for k, v in U["models"].items():
            if not k.startswith(f"SVI_{oname}:"):
                continue
            label = k.split(": ", 1)[1]
            if v["solution"].startswith("Poisson"):
                label += " (boundary Poisson solution)"
            e = v["estimate"]
            ok = v["estimable"]
            # Sentence case: a stratum label stands alone and is capitalized;
            # anything else follows "Adjusted for" and stays lowercase.
            standalone = label.startswith(("metropolitan counties", "nonmetropolitan counties"))
            text = label[0].upper() + label[1:] if standalone else "Adjusted for " + label
            rows.append(["", text, f"{v['n']:,}",
                         f_e(e) if ok else f_est(e["irr"], np.nan, np.nan),
                         f_p(e["p"]) if ok else "NE"])
        for t, name in [(1, "socioeconomic status"), (2, "household characteristics"),
                        (3, "racial and ethnic minority status"),
                        (4, "housing type and transportation")]:
            v = U["themes"][f"SVI_{oname}_theme{t}"]
            rows.append(["", f"SVI theme {t} ({name}), adjusted for metropolitan status",
                         f"{v['n']:,}", f_e(v["adjusted_metro"]), f_p(v["adjusted_metro"]["p"])])
            rows.append(["", f"SVI theme {t}, adjusted for metropolitan status and log density",
                         f"{v['n']:,}", f_e(v["adjusted_metro_density"]),
                         f_p(v["adjusted_metro_density"]["p"])])
    d = U["descriptive"]
    rucc = "; ".join(f"RUCC {k}: {v['counties']} counties, {v['cct_facilities']:,} CCT and "
                     f"{v['cmr_facilities']} CMR facilities, mean SVI {v['mean_svi']:.1f}, "
                     f"median density {v['median_density']:.0f} per sq mi"
                     for k, v in d["by_metro_rucc"].items())
    rho = "; ".join(f"theme {t} ρ = {d[f'spearman_theme{t}_density_metro']['rho']:.2f}"
                    for t in range(1, 5))
    notes = [
        "Exploratory analyses prompted by the positive SVI-CCT association; not prespecified. "
        "All models are NB2 with dispersion estimated and a log(adults aged ≥45 years) offset; "
        "IRR per 10-percentile increase in the SVI or theme. Categorical RUCC uses indicator "
        "variables for each code against code 1. Log population density is residents per "
        "square mile of land area.",
        f"For cardiac MR no county coded 8 or 9 has an accredited facility, which would leave "
        f"those coefficients without a finite estimate (quasi-complete separation), so codes "
        f"{d['rucc_groups_CMR']['7']} were combined; for cardiac CT every code has facilities and "
        f"none were combined.",
        f"Metropolitan counties by RUCC code: {rucc}.",
        f"Within metropolitan counties, Spearman correlation of log population density with the "
        f"overall SVI ρ = {d['spearman_svi_density_metro']['rho']:.2f} and with each theme: {rho}.",
        ABBREV,
    ]
    return header, rows, notes


# -------------------------------------------------------------------- methods
def supplementary_methods(doc, R, N):
    W, S, M, P = (R["R1-02_weighting"], R["R2-03_strata"], R["R2-02_multiplicity"],
                  R["R2-01_pca"])
    heading(doc, "Supplementary Methods", 13)
    heading(doc, "S1. County population characteristics", 11)
    para(doc, "County characteristics were drawn from the CDC/ATSDR Social Vulnerability Index "
              "2022 component estimates (American Community Survey 2018-2022) and County Health "
              "Rankings & Roadmaps 2024 and are reported for all counties, by metropolitan status, "
              "and by the presence of any accredited facility (Supplementary Table S1). They "
              "describe county residents. The study is an ecologic analysis of facility capacity "
              "and used no patient-level data; characteristics of patients who receive cardiac "
              "imaging, cardiovascular disease prevalence, and disease severity cannot be "
              "reported from these data.")
    heading(doc, "S2. Construction of the economic deprivation index", 11)
    para(doc, f"Six indicators were combined: the percentages of residents below 150% of the "
              f"federal poverty level, of the civilian labor force unemployed, of adults aged ≥25 "
              f"years without a high-school diploma, and of housing cost-burdened households "
              f"(CDC/ATSDR SVI 2022), and median household income (sign-reversed) and the "
              f"percentage of children in poverty (County Health Rankings 2024). The "
              f"{P['n_counties']:,} counties with all six were standardized to z-scores and "
              f"decomposed by principal component analysis of the correlation matrix; the first "
              f"component score was converted to national percentiles to form the EDI. The "
              f"number of components was assessed by Horn's parallel analysis "
              f"({P['parallel_analysis']['replicates']:,} datasets with each indicator permuted "
              f"independently; a component is retained while its eigenvalue exceeds the 95th "
              f"percentile at the same rank), which retained "
              f"{['no', 'one', 'two', 'three'][P['parallel_analysis']['n_retained']]}. The scree "
              f"plot, biplot, eigenvalues, and loadings are shown in Supplementary Figure S3 and "
              f"Supplementary Table S5. Code: code/06_edi_sensitivity_analysis.py (index) and "
              f"code/18_reviewer_analyses.py (full decomposition).")
    heading(doc, "S3. How the models weight counties", 11)
    w = W["weights"]["SVI"]
    para(doc, "All count models include log(adults aged ≥45 years) as an offset, which fixes the "
              "coefficient of log population at 1 so that each model describes the facility rate. "
              "How strongly each county's rate counts follows from the score equation of each "
              "model, written in terms of the county rate r = y/N and the fitted rate lambda. "
              "For Poisson regression with the offset it is sum N x (r - lambda) = 0: each "
              "county's rate is weighted by its adults aged ≥45 years (N), so the estimate "
              "describes the association for the average adult. This is the population "
              "weighting of rates proposed by Reviewer 1, and it was fitted with robust (HC0) "
              "standard errors as the population-weighted sensitivity analysis. Adding weights "
              "1/N gives sum x (r - lambda) = 0, in which every county counts equally (the "
              "average county); this is reported as a further contrast. The primary NB2 model "
              "gives sum N/(1 + alpha mu) x (r - lambda) = 0: the weight rises with population and "
              "levels off for large counties, so populous counties count more than small ones "
              "without dominating. The NB2 model was retained as primary because it fits the "
              "overdispersed counts best (lowest AIC and BIC in all 12 index-outcome models). "
              f"Under population weights the Kish effective sample size is "
              f"{w['kish_effective_n']:.0f} counties and the largest 1% of counties carry "
              f"{100 * w['share_of_weight_top_1pct_counties']:.1f}% of the weight. "
              f"The {W['descriptive']['excluded']['n']} counties with fewer than 1,000 adults aged "
              f"≥45 years, excluded only from county-level rates, contained "
              f"{W['descriptive']['excluded']['cmr_facilities']} CMR and "
              f"{W['descriptive']['excluded']['cct_facilities']} CCT facilities.")
    heading(doc, "S4. Estimation in sparse strata", 11)
    para(doc, "In sparse strata the counts can show no overdispersion, and the "
              "maximum-likelihood estimate of the NB2 dispersion then lies on the boundary of the "
              "parameter space, alpha = 0, where the NB2 model reduces to Poisson regression. In "
              "the nonmetropolitan cardiac MR stratum each of the 14 facilities is in a different "
              "county; in the nonmetropolitan cardiac CT stratum the 115 facilities are in 108 "
              "counties, seven of them with two. Whether a fit lies on the boundary is decided by "
              "its likelihood and information matrix, not by the counts alone. Every stratified fit was checked "
              "(model_spec.fit_primary_checked): where alpha was below 0.05 and the Poisson "
              "log-likelihood (alpha = 0) was at least as high as the highest NB2 value found, "
              "whether or not the information matrix at the optimizer's stopping point was positive "
              "definite, the likelihood is maximized on the boundary and the Poisson fit was reported "
              "as the boundary solution and checked with profile-likelihood intervals, fixed-alpha "
              "fits, and an index-by-metropolitan-status interaction model whose dispersion is "
              "estimated from all counties (Supplementary Table S4). Any other failure would have "
              "been reported as not estimable; none occurred.")
    heading(doc, "S5. Multiple comparisons", 11)
    para(doc, f"The primary hypothesis family comprised the {M['families']['primary']['n_tests']} "
              f"metropolitan-adjusted associations of the SVI and EDI with CMR and CCT capacity. "
              f"Holm and Benjamini-Hochberg adjustments were applied within this family and across "
              f"all {M['families']['extended']['n_tests']} negative binomial index associations "
              f"reported in the main tables and figures (Supplementary Table S3); the population-"
              f"weighted Poisson estimates are a separate sensitivity analysis and not part of that family. Sensitivity and exploratory analyses "
              f"were interpreted by their agreement with the primary estimates.")
    heading(doc, "S6. Exploratory urbanicity analyses", 11)
    para(doc, "Because the binary metropolitan indicator does not distinguish dense central "
              "counties from outlying ones, the SVI models were refitted with categorical RUCC "
              "(each code against code 1; for cardiac MR, codes 7-9 were combined because codes 8 "
              "and 9 contain no facility, which would otherwise leave those coefficients without a "
              "finite estimate), with log population density (residents per square mile "
              "of land area; US Census Bureau population estimate for July 1, 2023 and SVI 2022 "
              "land area), within metropolitan and nonmetropolitan strata, and with each of the four "
              "SVI theme percentiles in place of the overall SVI (Supplementary Table S6). These "
              "analyses were not prespecified.")
    heading(doc, "S7. Software and reproducibility", 11)
    para(doc, "Python 3.11.7, statsmodels 0.14.6, SciPy 1.13.0, NumPy 1.26.4, scikit-learn 1.4.2. "
              "Every value in the manuscript and this supplement is regenerated from the county "
              "dataset by code/00_run_all.py. code/12_manuscript_numbers.py recomputes the "
              "manuscript's values and checks the manuscript against them: named values, table "
              "cells, specified wording, and every estimate quoted in the text.")
    heading(doc, "S8. Facility cohort and county assignment", 11)
    F = cohort_facts()
    para(doc, "The ACR accredited-facility extract (May 20, 2026) held one record per facility "
              "and accredited modality. Records were retained when the modality was MRI or CT and "
              "the accreditation listed a cardiac module, the site was in the 50 states or the "
              "District of Columbia, and the accreditation had not expired before the extraction "
              f"date. CT records accredited only for a calcium-scoring module, without a cardiac "
              f"module ({F['calcium_only']} records), were therefore not included. The cohort comprised "
              f"{F['included']:,} facility-modality records ({F['cmr']:,} CMR and {F['cct']:,} CCT), "
              f"{F['accredited']:,} listed as Accredited and {F['under_review']} as Under Review. "
              "Each record's ZIP code was assigned to the county holding the "
              "largest share of the ZIP's residential addresses in the HUD-USPS ZIP-County "
              "crosswalk (2026, first quarter), which returns Connecticut's nine planning regions "
              f"directly; {F['hud']:,} records were assigned this way, and {F['manual']} records with a unique "
              "hospital ZIP absent from every crosswalk (98415, Tacoma, Washington) were assigned "
              "to Pierce County, where every other Tacoma ZIP lies. A ZIP assignment is not an "
              f"address-level geocode: {F['share_lt1']} included records had ZIPs whose addresses span "
              f"more than one county, {F['share_lt90']} of them with less than 90% in the assigned county. Every source "
              "record is listed with its assignment or exclusion reason in "
              "data/processed/facility_mapping_audit.csv.")


FIGURES = [
    ("FigureS1_CCT_Choropleth.png", "Supplementary Figure S1",
     "Accredited cardiac CT capacity across US counties. County-level accredited cardiac CT "
     "facility rate per 100,000 adults aged ≥45 years. Gray denotes counties with no accredited "
     "facility; hatching denotes counties with fewer than 1,000 adults aged ≥45 years, for which "
     "a rate is not calculated. Alaska and Hawaii are shown in insets."),
    ("FigureS2_EDI_Quintiles.png", "Supplementary Figure S2",
     "Mean county-level accredited facility rates per 100,000 adults aged ≥45 years by economic "
     "deprivation index quintile, among counties with ≥1,000 adults aged ≥45 years and an EDI "
     "value. Q1 is least deprived. Neither modality declines monotonically across quintiles."),
    ("FigureS3_EDI_PCA.png", "Supplementary Figure S3",
     "Principal component analysis underlying the economic deprivation index. (A) Scree plot: "
     "eigenvalue and percentage of variance for each component, with cumulative variance; the "
     "dashed line marks an eigenvalue of 1. (B) Biplot: county scores on the first two components "
     "(points, colored by metropolitan status) and indicator loadings (arrows). The index is the "
     "first-component score. FPL = federal poverty level."),
]


def main():
    with open(os.path.join(RESULTS, "reviewer_analyses.json")) as f:
        R = json.load(f)
    with open(os.path.join(VALID, "manuscript_numbers.json")) as f:
        N = json.load(f)
    os.makedirs(TABLES, exist_ok=True)

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(10)
    s0 = doc.sections[0]
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(s0, side, Inches(1))
    t = doc.add_paragraph()
    r = t.add_run("Supplementary Material")
    r.bold = True
    r.font.size = Pt(14)
    para(doc, "Area Deprivation, Rurality, and Accredited Cardiac Imaging Capacity in US Counties")
    para(doc, "Contents: Supplementary Methods S1-S8; Supplementary Tables S1-S6; Supplementary "
              "Figures S1-S3.")
    supplementary_methods(doc, R, N)

    written = []
    section(doc, landscape=True)
    h, rows, notes = table_s1(R, N)
    add_table(doc, "Supplementary Table S1. County population characteristics by metropolitan "
                   "status and accredited capacity", h, rows, notes,
              widths=[2.2, 1.4, 1.4, 1.4, 1.4, 1.4], font=7.5, bold_rows=(0,))
    written.append(write_csv("Supplementary_Table_S1_Population_Characteristics.csv", h, rows, notes))

    h, rows, hb, rows_b, notes = table_s2(R, N)
    add_table(doc, "Supplementary Table S2. Primary and sensitivity models for the association of "
                   "each index with accredited facility counts. Panel A, all models", h, rows, [],
              widths=[0.4, 0.52, 1.4, 1.15, 0.55, 0.55, 0.95, 0.45, 0.7, 0.95, 0.5, 1.33], font=6.5)
    add_table(doc, "Supplementary Table S2, Panel B. Model fit by specification", hb, rows_b, notes,
              widths=[1.0, 0.6, 1.8, 0.6, 0.8, 0.8, 0.9, 1.1, 0.6, 0.55, 0.55], font=6.5)
    written.append(write_csv("Supplementary_Table_S2_All_Models.csv", h, rows, notes))
    written.append(write_csv("Supplementary_Table_S2B_Model_Fit.csv", hb, rows_b, []))

    h, rows, notes = table_s3(R)
    add_table(doc, "Supplementary Table S3. Adjustment for multiple comparisons", h, rows, notes,
              widths=[3.6, 1.2, 0.8, 0.9, 0.9, 0.9, 0.9], font=7.5)
    written.append(write_csv("Supplementary_Table_S3_Multiplicity.csv", h, rows, notes))

    section(doc, landscape=False)
    h, rows, notes = table_s4(R)
    add_table(doc, "Supplementary Table S4. Estimation diagnostics for the association of the EDI "
                   "with accredited CMR facilities in nonmetropolitan counties", h, rows, notes,
              widths=[3.4, 3.1], font=8)
    written.append(write_csv("Supplementary_Table_S4_Nonmetro_Diagnostics.csv", h, rows, notes))

    h, rows, notes = table_s5(R)
    add_table(doc, "Supplementary Table S5. Principal component analysis of the economic "
                   "deprivation index indicators", h, rows, notes,
              widths=[2.0, 1.5, 0.75, 0.75, 0.75, 0.75], font=7.5)
    written.append(write_csv("Supplementary_Table_S5_EDI_PCA.csv", h, rows, notes))

    h, rows, notes = table_s6(R)
    add_table(doc, "Supplementary Table S6. Exploratory analyses of the SVI association with "
                   "accredited capacity: finer urbanicity and SVI themes", h, rows, notes,
              widths=[0.8, 3.6, 0.8, 1.1, 0.6], font=7.5)
    written.append(write_csv("Supplementary_Table_S6_Urbanicity_Exploratory.csv", h, rows, notes))

    section(doc, landscape=False)
    heading(doc, "Supplementary Figures", 13)
    for fn, label, legend in FIGURES:
        path = os.path.join(FIG, fn)
        if os.path.exists(path):
            doc.add_picture(path, width=Inches(6.5))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        p = doc.add_paragraph()
        r = p.add_run(label + ". ")
        r.bold = True
        r.font.size = Pt(9)
        r2 = p.add_run(legend)
        r2.font.size = Pt(9)
        doc.add_paragraph()

    doc.save(OUT_DOCX)
    print(f"  wrote {os.path.relpath(OUT_DOCX, BASE_DIR)}")
    for w in written:
        print(f"  wrote {os.path.relpath(w, BASE_DIR)}")


if __name__ == "__main__":
    main()
