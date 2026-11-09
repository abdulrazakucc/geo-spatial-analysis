#!/usr/bin/env python3
"""
20_table5_population.py
=======================
Manuscript Table 5: characteristics of county residents, overall, by
metropolitan status, and by presence of an accredited facility.

The editor required a table describing the population, including race and
ethnicity, sex, and clinical conditions. The study has no patients (its unit is
the county), so the table describes county residents. Values are
total-population-weighted averages of county estimates; the full distribution
(county medians and interquartile ranges) and missing counts are in
Supplementary Table S1.

Reads   output/results/reviewer_analyses.json   (18_reviewer_analyses.py)
Writes  output/tables/Table5_Population_Characteristics.csv
        output/tables/Table5_Population_Characteristics.docx

This is the only generator of Table 5. Table 4 is the index comparison
(21_manuscript_tables.py), as in the submitted manuscript.
"""

import csv
import json
import os

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.shared import Inches, Pt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(BASE_DIR, "output", "results")
TABLES = os.path.join(BASE_DIR, "output", "tables")
STEM = "Table5_Population_Characteristics"

TITLE = ("Table 5. Characteristics of county residents, overall, by metropolitan status, and by "
         "presence of an accredited cardiac imaging facility")
STRATA = [("all", "All counties"), ("metropolitan", "Metropolitan (RUCC 1-3)"),
          ("nonmetropolitan", "Nonmetropolitan (RUCC 4-9)"),
          ("any_facility", "≥1 accredited facility"), ("no_facility", "No accredited facility")]
GROUPS = [
    ("Age and sex", ["pct_65plus", "pct_female"]),
    ("Race and ethnicity", ["pct_nh_white", "pct_nh_black", "pct_hispanic", "pct_nh_asian",
                            "pct_nh_aian", "pct_nh_nhpi", "pct_nh_multi_other"]),
    ("Socioeconomic and access", ["pct_pov150", "pct_uninsured", "pct_disability", "pcp"]),
    ("Clinical conditions and mortality (county estimates)",
     ["diabetes", "obesity", "smoking", "inactivity", "premature_mortality"]),
]


def build(C):
    header = ["Characteristic"] + [lab for _, lab in STRATA]
    rows = [["Counties, No."] + [f"{C['strata'][k]['counties']:,}" for k, _ in STRATA],
            ["Adults aged ≥45 y, millions"] + [f"{C['strata'][k]['adults_45plus_millions']:.1f}"
                                               for k, _ in STRATA]]
    for group, keys in GROUPS:
        rows.append([group] + [""] * len(STRATA))
        for key in keys:
            v = C["variables"][key]
            dp = 0 if key == "premature_mortality" else 1
            rows.append([v["label"]] + [f"{v['by_stratum'][s]['population_weighted_mean']:.{dp}f}"
                                        for s, _ in STRATA])
    notes = [
        "RUCC = Rural-Urban Continuum Code. Values are total-population-weighted averages of "
        "county estimates, which describe county residents, not patients imaged at accredited "
        "facilities; the study used no patient-level data. County medians, interquartile ranges, "
        "missing counts, and sources are in Supplementary Table S1. Sex is as recorded in Census "
        "population estimates. Cardiovascular disease prevalence, disease severity, and gender "
        "identity were not available. Sources: CDC/ATSDR Social Vulnerability Index 2022 "
        "(American Community Survey 2018-2022) for age, race and ethnicity, poverty, insurance, "
        "and disability; County Health Rankings & Roadmaps 2024 (University of Wisconsin "
        "Population Health Institute) for sex, clinical conditions, premature mortality, and "
        "primary care physicians; US Census Bureau population estimates for July 1, 2023 for adults "
        "aged ≥45 years and for the population weights."
    ]
    return header, rows, notes


def write_csv(header, rows, notes, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
        w.writerow([])
        for n in notes:
            w.writerow([n])


def write_docx(header, rows, notes, path):
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Inches(11), Inches(8.5)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(0.8))
    r = doc.add_paragraph().add_run(TITLE)
    r.bold = True
    r.font.size = Pt(10)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for i, h in enumerate(header):
        run = t.rows[0].cells[i].paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(8.5)
    for row in rows:
        cells = t.add_row().cells
        section = all(v == "" for v in row[1:])
        for i, v in enumerate(row):
            run = cells[i].paragraphs[0].add_run(v)
            run.font.size = Pt(8.5)
            run.bold = section
    for n in notes:
        doc.add_paragraph().add_run(n).font.size = Pt(8)
    doc.save(path)


def main():
    with open(os.path.join(RESULTS, "reviewer_analyses.json")) as f:
        C = json.load(f)["E-05_population"]
    header, rows, notes = build(C)
    os.makedirs(TABLES, exist_ok=True)
    write_csv(header, rows, notes, os.path.join(TABLES, f"{STEM}.csv"))
    write_docx(header, rows, notes, os.path.join(TABLES, f"{STEM}.docx"))
    print(f"  wrote output/tables/{STEM}.csv and .docx ({len(rows)} rows)")


if __name__ == "__main__":
    main()
