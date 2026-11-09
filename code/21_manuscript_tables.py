#!/usr/bin/env python3
"""
21_manuscript_tables.py
=======================
Manuscript Tables 2, 3 and 4 as separate files, the form in which the tables
were submitted to the journal (the submitted manuscript carries no tables).
Table 1 comes from 17_table1.py and Table 5 from 20_table5_population.py.

  Table 2  Association of area disadvantage and metropolitan status with
           accredited facility counts (primary models, Holm-adjusted P values)
  Table 3  Sensitivity analyses of the EDI association (ordinal RUCC,
           metropolitan strata, population-weighted models)
  Table 4  Comparison of the deprivation finding with a published county-level
           index (EDI versus SDI, with the metropolitan terms)

Reads   output/validation/manuscript_numbers.json   (12_manuscript_numbers.py)
        output/results/reviewer_analyses.json       (18_reviewer_analyses.py)
Writes  output/tables/Table2_Primary_Models.{csv,docx}
        output/tables/Table3_Sensitivity_EDI.{csv,docx}
        output/tables/Table4_Comparison_SDI.{csv,docx}

Every value is formatted here from the generated results; the gate
(12_manuscript_numbers.py) checks each cell again.
"""

import csv
import json
import os

from docx import Document
from docx.shared import Inches, Pt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(BASE_DIR, "output", "results")
VALID = os.path.join(BASE_DIR, "output", "validation")
TABLES = os.path.join(BASE_DIR, "output", "tables")
DASH = "–"


def est(e):
    irr, lo, hi = (e.get("irr", e.get("IRR")), e.get("ci_low", e.get("CI_low")),
                   e.get("ci_high", e.get("CI_high")))
    return f"{irr:.2f} ({lo:.2f}{DASH}{hi:.2f})"


def pv(e):
    p = e.get("p", e.get("P"))
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def table2(mn, rv):
    M = mn["regressions"]["models"]
    tests = {t["test"]: t for t in rv["R2-02_multiplicity"]["tests"]}
    holm = {k: tests[f"{k}, adjusted for metropolitan status (Table 2)"]["holm_primary"]
            for k in ("SVI-CMR", "SVI-CCT", "EDI-CMR", "EDI-CCT")}
    rows = [["Exposure", "Unadjusted IRR (95% CI)", "P value", "Adjusted IRR (95% CI)", "P value"]]
    for sect, mod in (("Cardiac MR", "CMR"), ("Cardiac CT", "CCT")):
        rows.append([sect, "", "", "", ""])
        for idx in ("SVI", "EDI"):
            b = M[f"{idx}_{mod}"]
            rows.append([f"{idx}, per 10 percentile", est(b["unadjusted"]), pv(b["unadjusted"]),
                         est(b["adjusted_metro"]), pv(b["adjusted_metro"])])
        m = M[f"EDI_{mod}"]["metro_effect"]
        rows.append(["Metropolitan status", "NA", "NA", est(m), pv(m)])
    s_cmr, s_cct = M["SVI_CMR"]["metro_effect"], M["SVI_CCT"]["metro_effect"]
    note = (f"EDI = economic deprivation index; IRR = incidence rate ratio; NA = not applicable; SVI = "
            f"Social Vulnerability Index. Negative binomial regression with the dispersion parameter "
            f"estimated from the data and a log-population offset (adults aged ≥45 years); adjusted models "
            f"include metropolitan status (RUCC 1{DASH}3). Metropolitan estimates shown are from the EDI "
            f"models; corresponding SVI-model estimates were {s_cmr['irr']:.2f} (95% CI, "
            f"{s_cmr['ci_low']:.2f}{DASH}{s_cmr['ci_high']:.2f}) for cardiac MR and {s_cct['irr']:.2f} "
            f"(95% CI, {s_cct['ci_low']:.2f}{DASH}{s_cct['ci_high']:.2f}) for cardiac CT. Sensitivity "
            f"analyses, including a specification with the dispersion fixed at 1, are reported in "
            f"Supplementary Table S2. P values are unadjusted; Holm-adjusted P values for the four adjusted "
            f"index associations (the primary hypothesis family) were {holm['SVI-CMR']:.3f} (SVI, cardiac "
            f"MR), {holm['SVI-CCT']:.3f} (SVI, cardiac CT), {holm['EDI-CMR']:.3f} (EDI, cardiac MR), and "
            f"{holm['EDI-CCT']:.3f} (EDI, cardiac CT). Analytic sample: {mn['regressions']['n_svi']:,} "
            f"counties (SVI), {mn['regressions']['n_edi']:,} (EDI).")
    return ("Table 2. Association of area disadvantage and metropolitan status with accredited facility "
            "counts", rows, note)


def table3(mn, rv):
    M = mn["regressions"]["models"]
    S, W = rv["R2-03_strata"], rv["R1-02_weighting"]["models"]
    n = mn["regressions"]["n_edi"]
    rows = [["Model", "Counties, No.", "EDI IRR (95% CI)", "P value", "Rurality term IRR (95% CI)"],
            ["Rurality as ordinal RUCC (1-9)", "", "", "", ""]]
    for lab, mod in (("Cardiac MR", "CMR"), ("Cardiac CT", "CCT")):
        b = M[f"EDI_{mod}"]
        rows.append([lab, f"{n:,}", est(b["adjusted_rucc"]), pv(b["adjusted_rucc"]), est(b["rucc_effect"])])
    rows.append(["Stratified by metropolitan status", "", "", "", ""])
    for mod, mlab in (("CMR", "Cardiac MR"), ("CCT", "Cardiac CT")):
        b = M[f"EDI_{mod}"]
        for lay, glab in (("metro", "metropolitan"), ("nonmetro", "nonmetropolitan")):
            e = b[f"stratified_{lay}"]
            rows.append([f"{mlab}, {glab}", f"{b[f'stratified_{lay}_n']:,}", est(e), pv(e), "NA"])
    rows.append(["Population-weighted, adjusted for metropolitan status", "", "", "", ""])
    for lab, mod in (("Cardiac MR", "CMR"), ("Cardiac CT", "CCT")):
        w = W[f"EDI_{mod}_adjusted"]
        rows.append([lab, f"{w['n']:,}", est(w["poisson_population_weighted_robust"]),
                     pv(w["poisson_population_weighted_robust"]),
                     est(w["metro_poisson_population_weighted_robust"])])
    nm = S["strata"]["EDI_CMR_nonmetro"]
    prof = S["detail"]["EDI_CMR_nonmetro"]["poisson_profile"]
    assert nm["solution"].startswith("Poisson") and S["strata"]["EDI_CCT_nonmetro"]["solution"].startswith("Poisson")
    ip_cmr = S["interaction"]["EDI_CMR"]["interaction_ratio"]["p"]
    ip_cct = S["interaction"]["EDI_CCT"]["interaction_ratio"]["p"]
    note = (f"EDI = economic deprivation index; IRR = incidence rate ratio; NA = not applicable; RUCC = "
            f"Rural-Urban Continuum Code. Unless noted, models are negative binomial with a log-population "
            f"offset (adults aged ≥45 years); EDI IRRs are per 10-percentile increase. The rurality term is "
            f"the ordinal RUCC value, for which IRR < 1 indicates lower capacity with increasing rurality. "
            f"In the population-weighted rows it is metropolitan status. All rurality terms had P < 0.001. "
            f"The nonmetropolitan cardiac MR stratum contains {nm['events']} accredited facilities, each in "
            f"a different county; its dispersion estimate lay on the boundary of zero, where the negative "
            f"binomial model reduces to Poisson regression, and the estimate shown is from that fit "
            f"(profile-likelihood 95% CI, {prof['ci_low']:.2f}{DASH}{prof['ci_high']:.2f}; Supplementary "
            f"Table S4). It is imprecise and hypothesis-generating. The nonmetropolitan cardiac CT estimate "
            f"is also from the Poisson fit, because its dispersion estimate lay on the same boundary. The "
            f"EDI association differed between metropolitan and nonmetropolitan counties for cardiac MR "
            f"(interaction P = {ip_cmr:.3f}) but not for cardiac CT (interaction P = {ip_cct:.3f}). "
            f"Population-weighted models are Poisson regressions with the same offset, which weight each "
            f"county's rate by its adults aged ≥45 years, with robust standard errors.")
    return ("Table 3. Sensitivity analyses of the association between economic deprivation and "
            "accredited facility counts", rows, note)


def table4(mn):
    sd = mn["sdi"]
    E, D = sd["EDI_models"]["outcomes"], sd["SDI_models"]["outcomes"]
    rows = [["Exposure", "EDI IRR (95% CI)", "P value", "SDI IRR (95% CI)", "P value"]]
    for sect, y in (("Cardiac MR", "cmr_facility_count"), ("Cardiac CT", "cct_facility_count")):
        rows.append([sect, "", "", "", ""])
        for lab, k in (("Index, unadjusted", "unadjusted"),
                       ("Index, adjusted for metropolitan status", "adjusted"),
                       ("Metropolitan status", "metro_in_adjusted")):
            rows.append([lab, est(E[y][k]), pv(E[y][k]), est(D[y][k]), pv(D[y][k])])
    rl = sd["rurality_link"]
    note = (f"EDI = economic deprivation index; IRR = incidence rate ratio; SDI = Social Deprivation Index "
            f"(Robert Graham Center, 2015{DASH}2019). Negative binomial regression with a log-population "
            f"offset (adults aged ≥45 years); index IRRs are per 10-percentile increase. Analytic sample: "
            f"{mn['regressions']['n_edi']:,} counties (EDI) and {sd['sdi_matched_counties']:,} (SDI); the "
            f"SDI matched {sd['sdi_matched_counties']:,} of {sd['total_counties']:,} counties. The two "
            f"indices agree closely at the county level (Spearman ρ = "
            f"{sd['agreement_with_EDI']['spearman_rho']:.2f}) but differ in how strongly they encode "
            f"rurality: Spearman ρ with the ordinal Rural-Urban Continuum Code was "
            f"{rl['EDI']['spearman_vs_rucc']:.2f} for the EDI and {rl['SDI']['spearman_vs_rucc']:.2f} for the "
            f"SDI, with mean nonmetropolitan-minus-metropolitan gaps of {rl['EDI']['gap']:.1f} and "
            f"{rl['SDI']['gap']:.1f} percentile points, respectively. Metropolitan status rows are the "
            f"metropolitan-status coefficients from the corresponding adjusted models.")
    return ("Table 4. Comparison of the deprivation finding with a published county-level index", rows, note)


def write(stem, title, rows, note):
    with open(os.path.join(TABLES, f"{stem}.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([title])
        w.writerows(rows)
        w.writerow([])
        w.writerow([note])
    doc = Document()
    sec = doc.sections[0]
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(1))
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Times New Roman", Pt(10)
    r = doc.add_paragraph().add_run(title)
    r.bold = True
    t = doc.add_table(rows=0, cols=len(rows[0]))
    t.style = "Table Grid"
    for i, row in enumerate(rows):
        cells = t.add_row().cells
        section = i > 0 and all(v == "" for v in row[1:])
        for j, v in enumerate(row):
            run = cells[j].paragraphs[0].add_run(v)
            run.bold = i == 0 or section
    doc.add_paragraph().add_run(note).font.size = Pt(9)
    doc.save(os.path.join(TABLES, f"{stem}.docx"))
    print(f"  wrote output/tables/{stem}.csv and .docx")


def main():
    with open(os.path.join(VALID, "manuscript_numbers.json")) as f:
        mn = json.load(f)
    with open(os.path.join(RESULTS, "reviewer_analyses.json")) as f:
        rv = json.load(f)
    os.makedirs(TABLES, exist_ok=True)
    for stem, (title, rows, note) in (("Table2_Primary_Models", table2(mn, rv)),
                                       ("Table3_Sensitivity_EDI", table3(mn, rv)),
                                       ("Table4_Comparison_SDI", table4(mn))):
        write(stem, title, rows, note)


if __name__ == "__main__":
    main()
