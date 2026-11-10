#!/usr/bin/env python3
"""
build_r1_package.py
===================
Assembles the first-round revision package in manuscript/jacrad-reviews-2026/.

Inputs (all generated; run the pipeline and tools/revise_manuscript_r1.py first)
    manuscript/jacrad-reviews-2026/working/manuscript_R1_TRACKED.docx
    manuscript/jacrad-reviews-2026/working/manuscript_R1_CLEAN.docx
    manuscript/jacrad-reviews-2026/working/r1_change_log.csv
    output/results/*, output/validation/*, output/figures/*, output/tables/*
    manuscript/jacrad-reviews-2026/*_original*.txt (decision-letter wording, quoted verbatim)

Outputs (manuscript/jacrad-reviews-2026/R1_submission_package/)
    01 revised manuscript, clean, line-numbered (.docx, .pdf)
    02 revised manuscript, tracked changes, line-numbered (.docx, .pdf)
    03 response to reviewers and editor (.docx, .pdf)
    04 supplementary material (.docx, .pdf)
    05_Figures/, 06_Tables/, 07_Statistical_Outputs/
    08 permissions log, 09 proofreading report, 10 change log,
    11 submission checklist, 12 completion report, 00 revision plan
    MANIFEST.csv (SHA-256 of every file)

Copies here are snapshots of generated outputs for submission, verified by
hash in MANIFEST.csv; each still has exactly one generator in code/.

Page and line numbers quoted in the response letter are read from the
line-numbered PDF of the clean manuscript produced by this script.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import Inches, Pt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REV = os.path.join(BASE, "manuscript", "jacrad-reviews-2026")
WORK = os.path.join(REV, "working")
PKG = os.path.join(REV, "R1_submission_package")
SOFFICE = os.environ.get("SOFFICE", "/Applications/LibreOffice.app/Contents/MacOS/soffice")
RES = os.path.join(BASE, "output", "results")
VAL = os.path.join(BASE, "output", "validation")
FIG = os.path.join(BASE, "output", "figures")
TAB = os.path.join(BASE, "output", "tables")

TITLE = "Area Deprivation, Rurality, and Accredited Cardiac Imaging Capacity in US Counties"
TODAY = "November 8, 2026"
MS_ID = "JACRAD-D-26-00740"
SUB = f"{TITLE}\nManuscript {MS_ID} | {TODAY}"


# ----------------------------------------------------------------- utilities
def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def add_line_numbers(src, dst):
    """Copy a .docx with continuous line numbering switched on."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in zin.namelist():
            b = zin.read(n)
            if n == "word/document.xml":
                s = b.decode("utf8")
                if "<w:lnNumType" not in s:
                    s = s.replace("<w:pgNumType/>",
                                  '<w:lnNumType w:countBy="1" w:restart="continuous"/><w:pgNumType/>', 1)
                b = s.encode("utf8")
            zout.writestr(n, b)


def to_pdf(docx_path):
    outdir = os.path.dirname(docx_path)
    subprocess.run([SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", outdir, docx_path],
                   check=True, capture_output=True, timeout=300)
    return os.path.splitext(docx_path)[0] + ".pdf"


class Locator:
    """Finds the page and line of a text snippet in a line-numbered PDF."""

    def __init__(self, pdf):
        txt = subprocess.run(["pdftotext", "-layout", pdf, "-"], check=True,
                             capture_output=True, text=True).stdout
        self.chars, self.pos = [], []
        for pi, page in enumerate(txt.split("\f"), start=1):
            for line in page.splitlines():
                m = re.match(r"^\s*(\d+)\s{2,}(\S.*)$", line)
                if not m:
                    continue
                ln, body = int(m.group(1)), m.group(2)
                if ln == pi and body.strip() == str(pi):
                    continue  # footer page number, not a numbered text line
                for ch in re.sub(r"[^0-9a-z]", "", body.lower()):
                    self.chars.append(ch)
                    self.pos.append((pi, ln))
        self.stream = "".join(self.chars)

    def find(self, start, end=None):
        key = re.sub(r"[^0-9a-z]", "", start.lower())
        assert self.stream.count(key) <= 1, f"anchor matches more than once: {start!r}"
        i = self.stream.find(key)
        if i < 0:
            return None
        p0, l0 = self.pos[i]
        if end:
            k2 = re.sub(r"[^0-9a-z]", "", end.lower())
            j = self.stream.find(k2, i)
            if j >= 0:
                p1, l1 = self.pos[j + len(k2) - 1]
                if p1 == p0:
                    return f"p. {p0}, lines {l0}-{l1}" if l1 != l0 else f"p. {p0}, line {l0}"
                return f"pp. {p0}-{p1}, lines {l0}-{l1}"
        return f"p. {p0}, line {l0}"


# ---------------------------------------------------------------- docx help
def new_doc(title, subtitle=None, landscape=False):
    d = Document()
    st = d.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(11)
    s = d.sections[0]
    if landscape:
        s.orientation = WD_ORIENT.LANDSCAPE
        s.page_width, s.page_height = Inches(11), Inches(8.5)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(s, side, Inches(0.9))
    p = d.add_paragraph()
    r = p.add_run(title)
    r.bold = True
    r.font.size = Pt(15)
    if subtitle:
        q = d.add_paragraph()
        rr = q.add_run(subtitle)
        rr.italic = True
        rr.font.size = Pt(10)
    return d


def H(d, text, size=12.5):
    p = d.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)
    return p


def P(d, text, bold_lead=None, size=11, italic=False):
    p = d.add_paragraph()
    if bold_lead:
        r = p.add_run(bold_lead + (" " if text else ""))
        r.bold = True
        r.font.size = Pt(size)
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.italic = italic
    return p


def B(d, text, size=11):
    p = d.add_paragraph(style="List Bullet")
    r = p.add_run(text)
    r.font.size = Pt(size)
    return p


def T(d, header, rows, widths=None, size=9):
    t = d.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(size)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    d.add_paragraph()
    return t


# ---------------------------------------------------------------- numbers
def load():
    with open(os.path.join(RES, "reviewer_analyses.json")) as f:
        rv = json.load(f)
    with open(os.path.join(VAL, "manuscript_numbers.json")) as f:
        mn = json.load(f)
    return rv, mn


def fe(e, p=True):
    t = f"IRR {e['irr']:.2f}; 95% CI, {e['ci_low']:.2f}-{e['ci_high']:.2f}"
    if p:
        t += "; P < 0.001" if e["p"] < 0.001 else f"; P = {e['p']:.3f}"
    return t


def run_gate(docx_path):
    r = subprocess.run([sys.executable, os.path.join(BASE, "code", "12_manuscript_numbers.py"),
                        docx_path, "--strict"], cwd=BASE, capture_output=True, text=True)
    rep = open(os.path.join(VAL, "manuscript_check.txt")).read()
    m = re.search(r"Checks:\s+(\d+)\s+Mismatches:\s+(\d+)", rep)
    return int(m.group(1)), int(m.group(2)), r.returncode, rep


# ================================================================ CONTENT
ORIGINALS = {"R1": "reviwer-R1_original_comments.txt",
             "R2": "reviwer-R2_original_comments.txt",
             "ED": "editorial-requirements-R1-original.txt"}


def load_verbatim():
    """The decision letter's own wording, read from the files the authors supplied.

    Returns {"R1": (general, [c1..c5]), "R2": (general, [c1..c5]),
    "ED": [intro, submit, permissions, proofreading, demographics, deadline]}.
    Counts are asserted so an edited source file fails loudly instead of
    shifting a comment onto the wrong response.
    """
    def paras(name, blank_separated):
        raw = open(os.path.join(REV, name), encoding="utf-8").read().strip()
        if blank_separated:
            out = []
            for b in re.split(r"\n\s*\n", raw):
                text, urls = [], []
                for line in b.splitlines():
                    (urls if line.strip().startswith("http") else text).append(line.strip())
                out.append("\n".join([" ".join(" ".join(text).split())] + urls))
            return out
        return raw.splitlines()

    r1 = paras(ORIGINALS["R1"], True)
    assert len(r1) == 6 and r1[0].startswith("Reviewer #1:"), len(r1)
    r1 = (r1[0].removeprefix("Reviewer #1:").strip(), r1[1:])

    lines = paras(ORIGINALS["R2"], False)
    first = next(i for i, x in enumerate(lines) if re.match(r"\d+\.\s", x))
    general = " ".join(" ".join(lines[:first]).split()).removeprefix("Reviewer #2:").strip()
    numbered = [re.sub(r"^\d+\.\s+", "", x).strip() for x in lines[first:] if x.strip()]
    assert len(numbered) == 5, len(numbered)
    r2 = (general, numbered)

    ed = paras(ORIGINALS["ED"], True)
    assert len(ed) == 6 and "Response to Reviewers" in ed[1] and "demographic" in ed[4], len(ed)
    return {"R1": r1, "R2": r2, "ED": ed}


def P_resp(d, text, lead, size=10.5):
    """A response paragraph; any [AUTHOR ACTION ...] bracket is highlighted."""
    p = d.add_paragraph()
    r = p.add_run(lead + " ")
    r.bold = True
    r.font.size = Pt(size)
    for part in re.split(r"(\[AUTHOR ACTION[^\]]*\])", text):
        if not part:
            continue
        r = p.add_run(part)
        r.font.size = Pt(size)
        if part.startswith("[AUTHOR ACTION"):
            r.bold = True
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    return p


def items(rv, mn, L):
    """Point-by-point entries: (id, summary of the comment, response, changes, locations)."""
    W, S, M, U, Pc, C = (rv["R1-02_weighting"], rv["R2-03_strata"], rv["R2-02_multiplicity"],
                         rv["R1-04_urban_core"], rv["R2-01_pca"], rv["E-05_population"])
    nm, det, inter = (S["strata"]["EDI_CMR_nonmetro"], S["detail"]["EDI_CMR_nonmetro"],
                      S["interaction"]["EDI_CMR"])
    wm = W["models"]
    exc, rates, w = W["descriptive"]["excluded"], W["descriptive"]["rates"], W["weights"]["SVI"]
    tests = {t["test"]: t for t in M["tests"]}
    sc = tests["SVI-CCT, adjusted for metropolitan status (Table 2)"]
    um, th = U["models"], U["themes"]
    max_rate_shift = max(abs(g[f"{o}_mean_all_counties"] - g[f"{o}_mean_rate_eligible"])
                         for g in rates.values() for o in ("CMR", "CCT"))
    fam = M["families"]

    #: Tables are separate files, as at first submission, so their locations name the file.
    TABLE_LOCS = {"Table 1 footnote": "Table 1 file, footnote", "Table 2 footnote": "Table 2 file, footnote",
                  "Table 3 footnote": "Table 3 file, footnote", "Table 5": "Table 5 file, title"}

    def loc(*pairs):
        out = []
        for lab, a, b in pairs:
            if lab in TABLE_LOCS:
                w = a.split()
                q = " ".join(w[:8]) + (" \u2026" if len(w) > 8 else "")
                out.append(f"{TABLE_LOCS[lab]} (\u201c{q}\u201d)")
                continue
            f = L.find(a, b)
            assert f, f"location not found in the clean PDF: {lab}: {a!r}"
            w = a.split()
            k = min(8, len(w))
            while k > 3 and " ".join(w[:k]).count("(") > " ".join(w[:k]).count(")"):
                k -= 1
            q = " ".join(w[:k]) + (" \u2026" if k < len(w) else "")
            out.append(f"{lab}: {f} (\u201c{q}\u201d)")
        return "; ".join(out)

    R1 = [
        ("R1-01", "Methods/Results organization. Move reported sensitivity-analysis findings from "
         "Methods to Results while keeping the methodological descriptions in Methods.",
         "We agree, and thank the reviewer. Both sentences the reviewer cites (original lines 78-79 "
         "and 91-92) reported results, and on rereading Methods we found two more: the AIC/BIC "
         "comparison of model specifications and the variance explained by the first principal "
         "component of the EDI. Methods now state only "
         "what was done, and each result appears in Results, where two of them are also quantified "
         "for the first time: restricting the regressions changed no adjusted index IRR by more than "
         "0.001, and the estimated-dispersion model had the lowest AIC and BIC in all 12 "
         "index-outcome models.",
         ["Methods, Study Design and Data Sources: the cohort definition is retained; its result is removed.",
          "Methods, Metropolitan Status and Statistical Analysis: the AIC/BIC result is replaced by a description of the comparison; "
          "the sensitivity analyses are listed without results.",
          "Methods, Measures of Area Disadvantage: the variance-explained result is removed; standardization is stated.",
          "Results: a new subsection, Sensitivity and Exploratory Analyses, reports all sensitivity analyses (Supplementary Table S2), and the "
          "PCA result is reported with the full component structure (Supplementary Figure S3; Table S5)."],
         loc(("Methods, cohort", "Facilities listed as Accredited or Under Review", "facility-modality records, respectively"),
             ("Methods, model comparison", "Its fit was compared by the Akaike", "dispersion fixed at 1."),
             ("Results, sensitivity analyses", "In every sensitivity analysis, metropolitan status or rurality remained",
              "(Supplementary Table S3)."),
             ("Results, PCA", "The EDI's first principal component explained", "Supplementary Table S5)."))),
        ("R1-02", "Population weighting. Reevaluate the exclusion of counties with fewer than 1,000 "
         "eligible adults; add an eligible-population-weighted sensitivity analysis; distinguish "
         "population-offset modeling from observation weighting; compare weighted and unweighted "
         "estimates, explain the estimands, and assess model stability.",
         f"We thank the reviewer for this suggestion, which led us to re-examine how each model "
         f"weights counties. First, the exclusion. It applied only to county-level per-capita rates "
         f"(Table 1 means and the nonparametric tests); the regressions always retained these "
         f"counties, with population entering as an offset (3,144 counties in the SVI models; 3,134 "
         f"in the EDI models, which require all six EDI indicators). None of the {exc['n']} "
         f"excluded counties had an accredited facility (largest, {exc['max_adults_45plus']:,} adults "
         f"aged ≥45 years), so the exclusion cannot have created or hidden an unstable rate; "
         f"including them at their observed rate of zero changes no county-level mean rate by more "
         f"than {max_rate_shift:.3f} per 100,000. Second, weighted rates. As the reviewer proposes, "
         f"we now report rates weighted by the eligible population, which retain every county: the "
         f"population-weighted mean of county rates is the pooled rate (total facilities divided by "
         f"total eligible adults), {rates['metropolitan']['CMR_pooled']:.2f} versus "
         f"{rates['nonmetropolitan']['CMR_pooled']:.2f} per 100,000 for CMR and "
         f"{rates['metropolitan']['CCT_pooled']:.2f} versus {rates['nonmetropolitan']['CCT_pooled']:.2f} "
         f"for CCT, metropolitan versus nonmetropolitan. Third, weighting in the regressions. In a "
         f"count model with a log-population offset, the weight each county's rate receives follows "
         f"from the model's score equation. In Poisson regression that weight is the county's "
         f"eligible population, so Poisson regression with the offset is the population-weighted "
         f"analysis the reviewer describes and estimates the association for the average adult. "
         f"The primary negative binomial model does not weight counties equally either: its weight "
         f"rises with population and then levels off, so populous counties count more than small "
         f"ones without dominating. We retained the negative binomial model as primary because it "
         f"fits the overdispersed counts best (lowest AIC and BIC in all 12 index-outcome models), "
         f"and fitted the population-weighted Poisson model, with robust standard errors, as a "
         f"sensitivity analysis. For the SVI and the EDI it leads to the same conclusions as the primary "
         f"model: the adjusted SVI-CCT "
         f"association remains positive ({fe(wm['SVI_CCT_adjusted']['poisson_population_weighted_robust'])}), "
         f"the adjusted EDI-CMR association remains null "
         f"({fe(wm['EDI_CMR_adjusted']['poisson_population_weighted_robust'])}), the unadjusted EDI-CMR "
         f"association is smaller ({fe(wm['EDI_CMR_unadjusted']['poisson_population_weighted_robust'])}), "
         f"and metropolitan status remains strongly associated with capacity "
         f"({fe(wm['EDI_CMR_adjusted']['metro_poisson_population_weighted_robust'], p=False)} for CMR; "
         f"{fe(wm['EDI_CCT_adjusted']['metro_poisson_population_weighted_robust'], p=False)} for CCT). "
         f"Supplementary Table S2 also gives estimates with every county weighted equally: the "
         f"unadjusted EDI-CMR association is largest under that weighting "
         f"({fe(wm['EDI_CMR_unadjusted']['poisson_county_weighted_robust'])}), consistent with its being "
         f"driven by the many small nonmetropolitan counties, and the adjusted EDI-CMR association "
         f"remains null ({fe(wm['EDI_CMR_adjusted']['poisson_county_weighted_robust'])}). Under "
         f"population weights the Kish effective sample size is {w['kish_effective_n']:.0f} of "
         f"{w['n']:,} counties (Solon et al., reference 12, discuss weighting in this setting). The "
         f"weighting of each model is set out in Methods and Supplementary Methods S3, and the "
         f"results in Results, Table 3, and Supplementary Table S2.",
         ["Methods, Study Design and Data Sources: number excluded stated; pooled rates added and identified as "
          "population-weighted mean county rates; all counties retained in regressions stated.",
          "Methods, Metropolitan Status and Statistical Analysis: how the negative binomial and Poisson models weight counties; the "
          "population-weighted (Poisson) sensitivity analysis.",
          "Results, Distribution of Accredited Capacity: pooled rates; none of the 106 excluded counties had a facility.",
          "Results, Economic Deprivation Index: pooled Q1/Q5 contrast (1.4-fold, versus 2.9-fold for mean county rates).",
          "Results, sensitivity paragraph; Table 3 (population-weighted rows and footnote); "
          "Supplementary Table S2 (population-weighted and equally weighted rows); Supplementary "
          "Methods S3; Limitations."],
         loc(("Methods, rates", "the 106 counties with fewer than 1,000 eligible adults", "were also calculated."),
             ("Methods, weighting", "The negative binomial model weights each county's rate",
              "population-weighted sensitivity analysis (12)."),
             ("Results, pooled rates", "Pooled rates, which include every county", "had an accredited facility."),
             ("Results, weighted models", "Population-weighted SVI and EDI estimates led to the same conclusions", None),
             ("Table 3 footnote", "Population-weighted models are Poisson regressions", None),
             ("Limitations", "differently weighted estimates answer different questions", None))),
        ("R1-03", "Geographic classification. Audit all rural, urban, metropolitan, and "
         "nonmetropolitan terminology and correct it according to the RUCC operational definitions.",
         "We agree that the terminology was inconsistent. The 2023 RUCC classify counties in "
         "metropolitan areas by the population of the metropolitan area (codes 1-3) and nonmetropolitan "
         "counties by urbanization and adjacency to a metropolitan area (codes 4-9); nonmetropolitan is "
         "not synonymous with rural. Methods now state these definitions, with the USDA documentation "
         "cited (reference 11), and a rule applied throughout: metropolitan and nonmetropolitan for the "
         "binary classification, and rurality only for the ordinal RUCC gradient. Where the manuscript "
         "described area deprivation as correlated with rural location, it now says nonmetropolitan "
         "location. Every occurrence of "
         "rural, urban, metropolitan, and nonmetropolitan was audited. "
         "The word 'rural' now appears only in the official name of the Rural-Urban Continuum Codes, in "
         "the sentence stating that nonmetropolitan is not synonymous with rural, where it reports the "
         "terminology of a cited study (Introduction, sentence 1, Cross et al.), in the key word 'rural "
         "health', and in reference titles; 'rurality' is used only for the ordinal RUCC. The title retains 'Rurality' because the analysis examines the "
         "rural-urban continuum directly, through the ordinal RUCC models (Table 3) and the comparison "
         "of how strongly each index tracks rurality (Figure 2).",
         ["Methods, Metropolitan Status and Statistical Analysis: RUCC definitions and terminology rule.",
          "Introduction: 'metropolitan-rural gradient' to 'metropolitan-nonmetropolitan gradient'.",
          "Methods: 'correlated with rural location' to 'nonmetropolitan location'.",
          "Discussion: 'the rural populations within them' and 'the rural-urban gradient' corrected.",
          "Discussion: 'high-deprivation and rural counties' to 'nonmetropolitan counties'.",
          "Tables 1 and 3 (separate files): 'metropolitan status' for the binary split, 'rurality' only "
          "for the ordinal RUCC."],
         loc(("Methods, definitions", "Metropolitan status was defined by the US Department",
              "refers to the ordinal RUCC gradient."),
             ("Introduction", "independent of the metropolitan-nonmetropolitan gradient", None),
             ("Discussion", "including nearly all nonmetropolitan counties", None),
             ("Discussion", "high-deprivation and nonmetropolitan counties", None))),
        ("R1-04", "Positive SVI/CCT association. Expand the Discussion with plausible explanations, "
         "including tertiary care centers and urban-core clustering, without unsupported causal "
         "interpretation.",
         f"We agree that this result needed explanation, and we tested the urban-core explanation the "
         f"reviewer suggests before writing about it. In exploratory analyses (Supplementary Table S6), "
         f"the adjusted SVI-CCT association was detected in metropolitan counties "
         f"({fe(um['SVI_CCT: metropolitan counties only']['estimate'])}) but not in nonmetropolitan counties "
         f"({fe(um['SVI_CCT: nonmetropolitan counties only']['estimate'])}), although the interaction did not "
         f"reach significance (P = {S['interaction']['SVI_CCT']['interaction_ratio']['p']:.3f}), was strongest for the SVI themes "
         f"for housing type and transportation ({fe(th['SVI_CCT_theme4']['adjusted_metro'], p=False)}) "
         f"and racial and ethnic minority status ({fe(th['SVI_CCT_theme3']['adjusted_metro'], p=False)}), "
         f"which are the two themes that rise with population density within metropolitan counties, and "
         f"was no longer significant after adjustment for log population density "
         f"({fe(um['SVI_CCT: metropolitan status + log population density']['estimate'])}). With finer "
         f"adjustment for urbanicity (categorical RUCC and density), the SVI-CMR association was inverse "
         f"({fe(um['SVI_CMR: categorical RUCC + log population density']['estimate'])}); Results report "
         f"this as evidence that index associations depend on how geography is modeled. A new "
         f"Discussion paragraph explains the association as clustering of capacity in dense central "
         f"counties, where tertiary and academic centers are typically located and which can score "
         f"higher on the SVI for reasons unrelated to economic deprivation, a distinction the binary "
         f"metropolitan indicator cannot make. It states plainly that the association is not evidence that "
         f"vulnerability attracts capacity, that the analyses were exploratory, and that county data "
         f"cannot show whom these facilities serve. Because the registry does not record facility type, "
         f"the Discussion presents the location of tertiary centers as a plausible explanation "
         f"consistent with these results, not as a tested one.",
         ["Methods, Metropolitan Status and Statistical Analysis: exploratory analyses described.",
          "Results, Sensitivity and Exploratory Analyses: new exploratory paragraph (Supplementary Table S6).",
          "Discussion: new paragraph on the SVI-CCT association."],
         loc(("Methods", "Exploratory SVI models added categorical RUCC", "used the four SVI themes."),
             ("Results", "In exploratory analyses, the SVI-CCT association", "(Supplementary Table S6)."),
             ("Discussion", "The positive SVI-CCT association should not be read", "serve the vulnerable residents of their counties."))),
        ("R1-05", "Economic interpretation. Expand discussion of population density, fixed costs, "
         "market demand, and healthcare infrastructure with verifiable literature; acknowledge "
         "alternative explanations and observational limitations.",
         "We agree, and have added a Discussion paragraph on this point. It interprets metropolitan "
         "concentration through the fixed costs of CMR and CCT (scanners, site preparation, trained "
         "technologists, and subspecialty interpretation), the examination volume needed to recover "
         "them, and the population density, referral networks, and hospital infrastructure that supply "
         "that volume. It states the reviewer's point directly: disparities in capacity are often "
         "interpreted as evidence of bias, which county-level data can neither show nor exclude, and "
         "the pattern we observe is consistent with market size, which we did not measure. "
         "It cites the three studies the reviewer recommends (references 20-22): racial gaps in "
         "access to digital mammography among Medicare beneficiaries narrowed as the technology "
         "diffused (Christensen et al., Radiology 2023); use of screening CT colonography, which "
         "Medicare did not then cover, rose steeply with income (Christensen et al., AJR 2024); and gaps "
         "in physician care by urbanicity, income, and area deprivation widened as inflation-adjusted "
         "Medicare payment declined (Christensen et al., Inquiry 2026). It also cites evidence that "
         "MRI adoption responds to market and payer conditions (Baker, reference 17) and that "
         "physicians and radiologists concentrate in more populous areas (Rosenthal et al. and "
         "Rosenkrantz et al., references 18 and 19). Each reference was checked against its "
         "bibliographic record. The paragraph names alternative explanations we could not measure "
         "(payer mix, certificate-of-need regulation, health-system ownership, workforce supply, and "
         "accreditation practice) and states that the cross-sectional ecologic design shows where "
         "capacity is located, not why. Our population-density results (Supplementary Table S6) are "
         "consistent with this interpretation but do not establish it.",
         ["Discussion: new paragraph, including the disparity-versus-bias distinction.",
          "References 17-22 added; references 20-22 are the studies the reviewer recommended."],
         loc(("Discussion", "Metropolitan concentration is consistent with the economics", "is located, not why."))),
    ]
    R2 = [
        ("R2-01", "PCA visualization. Reproduce the PCA of the six indicators and provide a "
         "supplemental scree plot and biplot with explained variance, loadings, labels, and "
         "reproducibility details.",
         f"We thank the reviewer and have added both. The PCA was refitted on exactly the published input ({Pc['n_counties']:,} counties with "
         f"all six standardized indicators) with every component retained; its first component "
         f"reproduces the stored raw EDI score (Pearson r {'> 0.9999' if Pc['pc1_vs_stored_raw_score_pearson'] > 0.9999 else '= ' + format(Pc['pc1_vs_stored_raw_score_pearson'], '.4f')}) "
         f"and ranks counties exactly as the published EDI percentiles do (Spearman ρ = "
         f"{Pc['pc1_vs_edi_percentile_spearman']:.3f}). Supplementary "
         f"Figure S3 shows the scree plot (eigenvalues, percentage and cumulative variance) and a biplot "
         f"of county scores with labelled indicator loadings; Supplementary Table S5 gives eigenvalues, "
         f"loadings, eigenvector coefficients, indicator sources, the Kaiser-Meyer-Olkin measure "
         f"({Pc['kmo']:.2f}) and Bartlett's test. The first component explains "
         f"{100 * Pc['variance_explained'][0]:.1f}% of the variance (eigenvalue {Pc['eigenvalues'][0]:.2f}) "
         f"and every indicator loads positively on it ({min(Pc['pc1_loadings'].values()):.2f}-"
         f"{max(Pc['pc1_loadings'].values()):.2f}). A second component has an eigenvalue just above 1 "
         f"({Pc['eigenvalues'][1]:.2f}; {100 * Pc['variance_explained'][1]:.1f}% of variance) and is "
         f"dominated by a single indicator, housing cost burden. Horn's parallel analysis, which compares "
         f"each eigenvalue with the 95th percentile of eigenvalues from "
         f"{Pc['parallel_analysis']['replicates']:,} datasets in which each indicator is permuted "
         f"independently, retains only the first component (threshold for the second, "
         f"{Pc['parallel_analysis']['threshold_95'][1]:.2f}); the scree plot shows this threshold. The "
         f"index therefore uses the first component, as in its original construction. Software and "
         f"standardization are given in Supplementary Methods S2 and S7, and the sign conventions in "
         f"the notes to Supplementary Table S5.",
         ["Supplementary Figure S3 and Table S5 (new).",
          "Results: PCA result reported, with parallel analysis.",
          "Methods: standardization and software (scikit-learn 1.4) stated."],
         loc(("Methods", "Indicators were standardized, and scores on the first", None),
             ("Results", "The EDI's first principal component explained", "Supplementary Table S5)."))),
        ("R2-02", "Multiple comparisons. Identify the primary hypothesis family, distinguish "
         "exploratory analyses, evaluate multiplicity adjustment or justify none, and report whether "
         "important findings change.",
         f"We agree, and have done both things the reviewer suggests: we applied an adjustment, and "
         f"Methods now state that the sensitivity analyses were intended to assess the robustness of "
         f"the primary findings. The primary hypothesis family is now declared: the "
         f"{['no', 'one', 'two', 'three', 'four'][fam['primary']['n_tests']]} "
         f"metropolitan-adjusted associations of the SVI and EDI with CMR and CCT capacity, the models "
         f"the submitted manuscript already designated as the primary analysis. Holm adjustment within "
         f"this family changes no conclusion: the adjusted SVI-CCT association remains significant "
         f"(Holm P = {sc['holm_primary']:.3f}) and the EDI associations remain null. Across all "
         f"{fam['extended']['n_tests']} negative binomial index associations reported in Tables 2 and 3 "
         f"and Figure 2 (the population-weighted Poisson estimates are a separate sensitivity analysis "
         f"and not part of this family), the "
         f"Benjamini-Hochberg false discovery rate procedure leaves {fam['extended']['significant_bh']} of "
         f"{fam['extended']['significant_unadjusted']} nominally significant associations significant; the "
         f"adjusted SVI-CCT association survives (P = {sc['bh_extended']:.3f}), whereas the adjusted SDI-CMR "
         f"association, the ordinal-RUCC EDI-CCT association, and the unadjusted SDI-CCT association do "
         f"not. Familywise (Holm) control across all {fam['extended']['n_tests']} would be overly "
         f"conservative, because most of these tests re-estimate the same four associations under "
         f"alternative specifications rather than test separate hypotheses; for completeness, "
         f"Supplementary Table S3 also gives these values (adjusted SVI-CCT, P = "
         f"{sc['holm_extended']:.3f}). Sensitivity and exploratory analyses are identified as such and "
         f"interpreted by their agreement with the primary estimates. None of the paper's conclusions "
         f"rests on an association that loses significance under the primary-family adjustment.",
         ["Methods, Metropolitan Status and Statistical Analysis: primary family and procedures (references 14 and 15).",
          "Methods, Metropolitan Status and Statistical Analysis: the sensitivity analyses are stated to assess the robustness of the "
          "primary findings.",
          "Results, sensitivity paragraph: adjusted P values.",
          "Table 2 footnote: Holm-adjusted P values for the primary family.",
          "Supplementary Table S3 (new)."],
         loc(("Methods", "The primary hypothesis family was the four", "robustness of the primary findings."),
             ("Results", "The adjusted SVI-CCT association remained significant after Holm", "(Supplementary Table S3)."),
             ("Table 2 footnote", "Holm-adjusted P values for the four adjusted index associations", None))),
        ("R2-03", "Nonmetropolitan CMR estimation. Diagnose the model producing IRR 0.70 with 14 "
         "accredited CMR facilities; check convergence, Hessian, covariance and variance estimates; "
         "determine why the CI and P value were unavailable; do not invent intervals.",
         f"We are grateful for this comment, which identified an error in how we reported this row. "
         f"In the reviewer's terms: the model converged; the failure was in variance estimation; and "
         f"the cause was the sparse data. "
         f"Diagnosis (Supplementary Table S4): the optimizer reported convergence, but the dispersion "
         f"estimate had collapsed to {nm['alpha']:.4f}, the score for the dispersion was still negative, "
         f"and the negated Hessian had a negative eigenvalue ({nm['neg_hessian_eigenvalues'][0]:.3f}), so it "
         f"was not positive definite. The statsmodels software inverts the information matrix only when it is, and "
         f"otherwise returns no standard errors, which is why no interval or P value was available. The "
         f"cause is the data: each of the {nm['events']} facilities is in a different county, so there "
         f"is no overdispersion to estimate, and the likelihood is maximized on the boundary of the "
         f"parameter space, alpha = 0 (the Poisson log-likelihood, {nm['llf_poisson']:.4f}, exceeds the "
         f"NB2 value at the stopping point, {nm['llf_nb2']:.4f}). At alpha = 0 the NB2 model is the "
         f"Poisson model, so the maximum-likelihood fit of our primary specification is the Poisson fit, "
         f"whose information matrix is well conditioned. The row is therefore estimable: "
         f"{fe(nm['estimate'])}. No interval was imputed; we checked it with a profile-likelihood "
         f"interval ({det['poisson_profile']['ci_low']:.2f}-{det['poisson_profile']['ci_high']:.2f}; "
         f"likelihood-ratio P = {det['poisson_profile']['lr_p']:.3f}), fixed-dispersion fits (IRR 0.70-0.71 "
         f"for alpha from 0 to 1), robust errors, an index-by-metropolitan-status interaction model whose "
         f"dispersion is estimated from all 3,134 counties (nonmetropolitan slope "
         f"{fe(inter['nonmetro_slope'])}; interaction P = {inter['interaction_ratio']['p']:.3f}), and "
         f"within-stratum adjustment for ordinal RUCC (IRR {det['within_stratum_ordinal_rucc']['irr']:.2f}). "
         f"The SVI and SDI give comparable estimates in the same stratum. We have revised Table 3, "
         f"Results, Discussion, and Limitations accordingly. This is a substantive change: among the "
         f"few nonmetropolitan counties with any accredited CMR, those with a facility are less deprived. "
         f"We present it as hypothesis-generating, because it rests on {nm['events']} facilities, and it "
         f"does not alter the primary covariate-adjusted results. Because the stratum holds "
         f"{nm['events']} facilities, the main-effects model specified in the submitted manuscript remains the primary analysis "
         f"and the interaction model is reported as a sensitivity analysis. The stratum estimate remains "
         f"significant after multiplicity adjustment across all {fam['extended']['n_tests']} "
         f"negative binomial index associations (Benjamini-Hochberg P = {tests['EDI-CMR, nonmetropolitan counties (Table 3)']['bh_extended']:.3f}; "
         f"Holm P = {tests['EDI-CMR, nonmetropolitan counties (Table 3)']['holm_extended']:.3f}). A diagnostic "
         f"rule now applied to every stratified fit substitutes the Poisson fit only in this boundary "
         f"situation; any other failure would still be reported as not estimable.",
         ["Table 3: nonmetropolitan CMR row now 0.70 (0.56-0.89), P = 0.003; footnote rewritten.",
          "Methods, Metropolitan Status and Statistical Analysis: boundary rule and interaction test.",
          "Results, Economic Deprivation Index; Discussion (the exception sentence); Limitations.",
          "Supplementary Table S4 (new)."],
         loc(("Methods", "Where a sparse stratum placed the dispersion", "equivalent Poisson model."),
             ("Results", "Within nonmetropolitan counties, whose 14 accredited", "is hypothesis-generating."),
             ("Discussion", "The exception was the 14 CMR facilities", "too sparse for firm conclusions."),
             ("Table 3 footnote", "The nonmetropolitan cardiac MR stratum contains 14", None))),
        ("R2-04", "Table 1. Add CMR and CCT facility percentages with appropriate denominators and "
         "verify numerical consistency.",
         f"We have added them. Facility columns now read 'No. (%)', with the national total of each modality as the "
         f"denominator ({mn['table1']['_national_totals']['cmr']:,} CMR and "
         f"{mn['table1']['_national_totals']['cct']:,} CCT facilities); the county columns keep the "
         f"row's own county count as the denominator. The footnote states both denominators and why the "
         f"quintile rows sum to less than 100% (counties without an EDI value are not in a quintile). "
         f"Every cell is regenerated from the data and checked cell by cell by the validation script; "
         f"the metropolitan and nonmetropolitan rows sum to 100.0% for both modalities.",
         ["Table 1: two columns revised; footnote extended."],
         loc(("Table 1 footnote", "Facility percentages are of the national total", None))),
        ("R2-05", "Supplemental comparison table of all primary and relevant sensitivity models, with "
         "sample sizes, IRRs, CIs, P values, specifications and notes; mark non-estimable statistics "
         "accurately.",
         f"We have added this table. Supplementary Table S2, Panel A, has {rv['R2-05_table_rows']} rows "
         f"({rv['R2-05_table_rows'] - 4} fitted models; the three SVI quartile contrasts for each outcome "
         f"share one model) for the SVI, EDI and SDI and both outcomes: the primary unadjusted and "
         f"adjusted models; ordinal RUCC; metropolitan and nonmetropolitan strata; dispersion fixed at 1; "
         f"the rate-eligible sample; the Accredited-only cohort; population-weighted Poisson models, "
         f"unadjusted and adjusted; Poisson models with counties weighted equally; adjustment for "
         f"population density; and SVI quartiles. Each row gives the specification, counties, "
         f"facilities, IRR (95% CI), P, the second model term, the dispersion, and a note. Panel B gives "
         f"AIC, BIC and log-likelihood for the 12 primary index-outcome models under each of three "
         f"specifications (Poisson, NB2 with dispersion estimated, NB2 with dispersion fixed at 1). Rows estimated at the dispersion boundary "
         f"are labelled as Poisson solutions with their profile-likelihood intervals; no row is "
         f"non-estimable after the correction described in our response to comment 3, and the table would print NE if "
         f"one were. The Accredited-only sensitivity was previously fitted on the rate-eligible subset; "
         f"it now uses the primary sample, so that it differs from the primary analysis in one respect "
         f"only.",
         ["Supplementary Table S2 (new); cited in Methods and Results."],
         loc(("Methods", "fixed the dispersion at 1 (Supplementary Table S2)", None),
             ("Results", "In every sensitivity analysis, metropolitan status or rurality remained", None))),
    ]
    chk_n = mn.get("_gate_checks", "")
    MX, SDIo = mn["regressions"]["models"], mn["sdi"]["SDI_models"]["outcomes"]
    assert (f"{MX['SVI_CMR']['metro_effect']['irr']:.2f}", f"{SDIo['cct_facility_count']['metro_in_adjusted']['IRR']:.2f}",
            f"{MX['EDI_CMR']['adjusted_rucc']['p']:.3f}") != ("8.56", "2.12", "0.801")
    ED = [
        ("E-01", "Response to Reviewers: a point-by-point response with the exact comment, a response, "
         "changes or rebuttal, and revised locations.",
         "This document responds to each comment in turn, quoting the comment and giving our "
         "response, the changes made or the reasons for not making them, and their location by page "
         "and line in the line-numbered clean revision.",
         ["Response to Reviewers (this document)."], ""),
        ("E-02", "Tracked and clean versions, consistent, preserving formatting, references, tables, "
         "and figures.",
         "A tracked version and a clean version are both supplied. The tracked version marks every "
         "revision against the manuscript as "
         f"submitted, attributed to one author and dated {TODAY}; the clean version is that file "
         "with all changes accepted. We verified that the accepted text of the tracked file is identical "
         "to the clean file, paragraph by paragraph, and both pass the validation script that checks "
         "the manuscript's values, table cells, specified wording and every quoted estimate against the data. Formatting, references, tables and "
         "figure legends are preserved; line numbering has been added to both.",
         ["Revised manuscript in tracked-changes and clean versions, both line-numbered."], ""),
        ("E-03", "Figure and table permissions: classify each item as original, adapted or reproduced, "
         "and document permissions where required.",
         "No. None of the tables or figures has been published previously. All of them, including the "
         "supplementary items, are original: each was generated by the authors' code from public data, "
         "and none is adapted or reproduced from published work. No permission letter is therefore "
         "required.",
         ["None required."], ""),
        ("E-04", "Full scientific and language proofreading.",
         "We thank the editor for this reminder. The manuscript has been proofread in full for "
         "grammar, spelling, statistical terminology, and internal consistency, and every correction "
         "is marked in the tracked version. The principal corrections are as "
         "follows. The sentence on the Medicare accreditation requirement gave an effective date and "
         "described the ACR as the largest accrediting organization, neither of which the cited CMS "
         "page states; it now states the requirement as that page does. Reference 1 reports "
         "cardiovascular mortality by rural-urban residence, not by economic status, so the sentence "
         "citing it no longer refers to economically disadvantaged populations. Reference 2 was "
         "rechecked and its access date updated; the RUCC documentation (reference 11) and the Social "
         "Deprivation Index (reference 13) are now cited, and the added references are numbered in "
         "order of first citation. The population denominators are now described correctly as US "
         "Census Bureau estimates for July 1, 2023; they had been described as American Community "
         "Survey estimates. Abbreviations (including AIC and BIC) and the geographic terminology have "
         "been made consistent throughout. The description of metropolitan status and economic "
         "deprivation as strongly correlated has been revised, because it overstated the association. "
         "The closing sentence of the Discussion, which repeated the Summary Sentence, was removed. "
         "Nonsignificant results are now described as not "
         "significant rather than as showing an absence of association; statements that no inverse "
         "gradient was found are limited to the primary models adjusted for metropolitan status; "
         "planning and mechanism statements are framed as hypotheses; the sample for the facility "
         "versus no-facility deprivation contrast is stated; and the statement on Medicare coverage "
         "of screening CT colonography is dated, because Medicare has covered it since 2025. "
         "Finally, in rechecking every value we refined every "
         "negative binomial fit with Newton-Raphson steps after the default quasi-Newton optimizer, "
         "which had stopped marginally short of the maximum in some models. "
         f"Four submitted results changed in the last printed digit: the SVI-model metropolitan "
         f"incidence rate ratio for cardiac MR and its upper confidence limit (8.56 to "
         f"{MX['SVI_CMR']['metro_effect']['irr']:.2f} and 14.61 to "
         f"{MX['SVI_CMR']['metro_effect']['ci_high']:.2f}; Figure 1 legend and Table 2 footnote), the "
         f"SDI-model metropolitan incidence rate ratio for cardiac CT (2.12 to "
         f"{SDIo['cct_facility_count']['metro_in_adjusted']['IRR']:.2f}; Results and Table 4), the P value of the "
         f"ordinal-RUCC model for the EDI and cardiac MR (0.801 to "
         f"{MX['EDI_CMR']['adjusted_rucc']['p']:.3f}; Results and Table 3), and the P value for the "
         f"nonmetropolitan cardiac CT stratum (0.232 to "
         f"{rv['R2-03_strata']['strata']['EDI_CCT_nonmetro']['estimate']['p']:.3f}; Table 3), whose "
         f"dispersion, like that of the nonmetropolitan cardiac MR stratum, lies on the boundary of zero, "
         f"where the maximum-likelihood fit is the Poisson fit. No conclusion is affected.",
         ["Corrections throughout the manuscript, all marked in the tracked version."], ""),
        ("E-05", "Mandatory population characteristics table: assess race and ethnicity, sex, clinical "
         "conditions and severity, and county-level characteristics; do not invent patient data.",
         f"This is an ecologic study of facility capacity. Its unit of analysis is the county and its "
         f"outcome is the count of accredited facilities; no patients were enrolled and no patient "
         f"records were used, so the race and ethnicity, sex, clinical conditions and disease severity "
         f"of people who received cardiac imaging do not exist in these data and cannot be reported. To "
         f"meet the requirement we added Table 5. It reports the characteristics of "
         f"county residents for all {C['strata']['all']['counties']:,} counties, by metropolitan status, "
         f"and by presence of an accredited facility: age, sex, race and ethnicity, poverty, insurance, "
         f"disability, primary care physician supply, and county-level model-based prevalence of "
         f"diabetes, obesity, smoking and physical inactivity, with premature mortality, as "
         f"total-population-weighted averages of county estimates. Supplementary Table S1 adds county "
         f"medians and interquartile ranges, population density, missing counts, and sources. "
         f"Sex is reported as recorded in Census population estimates, which record sex, not gender. "
         f"Cardiovascular "
         f"disease prevalence, disease severity and gender identity are not available at the county "
         f"level in these sources. Table 5 is cited in Methods. Table 4 remains the comparison with the "
         f"Social Deprivation Index, as submitted, so the manuscript has five tables and two figures, "
         f"the journal's limit of seven exhibits.",
         ["Table 5 (new; separate file, as the other tables); Methods, Study Design and Data Sources; Supplementary "
          "Table S1 (new)."],
         loc(("Methods", "County population characteristics from the SVI 2022", "no patient-level data were used."),
             ("Table 5", "Table 5. Characteristics of county residents", None))),
        ("E-06", "Final submission package.",
         "Supplied: clean and tracked manuscripts (line-numbered, .docx and .pdf), this response, the "
         "supplementary material, figures (TIFF, PDF, PNG at 600 dpi), tables, statistical outputs, the "
         "permissions log, and a submission checklist with a manifest of file hashes.",
         ["Submission package and 11_Submission_Checklist."], ""),
    ]
    return ED, R1, R2


def response_letter(rv, mn, L, path, gate):
    ED, R1, R2 = items(rv, mn, L)
    V = load_verbatim()
    d = new_doc("Response to the Editor and Reviewers", f"{TITLE}\nManuscript ID: {MS_ID} | "
                f"Revision 1 | {TODAY}")
    P(d, "Dear Editor,")
    P(d, "Thank you for the opportunity to revise our manuscript, and thank you and the reviewers for "
         "careful and constructive comments. We have addressed every point. The principal changes are "
         "as follows.")
    W, S = rv["R1-02_weighting"], rv["R2-03_strata"]
    nm = S["strata"]["EDI_CMR_nonmetro"]
    for t in [
        "Population-weighted rates and a population-weighted sensitivity analysis were added, as "
        "Reviewer 1 suggested, and Methods now explain how each model weights counties; for the SVI "
        "and the EDI the population-weighted estimates lead to the same conclusions as the primary "
        "estimates.",
        f"The nonmetropolitan cardiac MR row of Table 3, previously reported as not estimable, is "
        f"estimable: its dispersion lay on the boundary of zero, where the model is Poisson. It shows an "
        f"inverse association ({fe(nm['estimate'])}) resting on {nm['events']} facilities, which we report "
        f"as hypothesis-generating.",
        "A primary hypothesis family was declared and multiplicity-adjusted P values added; no conclusion "
        "drawn from the primary family changes.",
        "Exploratory analyses are consistent with clustering of capacity in dense urban cores as the "
        "explanation for the positive SVI-CCT association, and the Discussion now addresses the economics of advanced imaging, including the "
        "distinction between disparity and bias, with verified references.",
        "Geographic terminology now follows the RUCC definitions; Table 1 reports facility percentages; "
        "the PCA is shown in full; Table 5 describes the population of the counties; and supplementary "
        "tables report all models, multiplicity, and estimation diagnostics.",
        "To meet the journal's limit of 3,000 words for Original Articles, the text was condensed by "
        "removing statements made more than once, including a closing sentence that repeated the "
        "Summary Sentence; no result, analysis, or reference was removed.",
        "As at first submission, Tables 1-5 are supplied as separate files; each response lists the "
        "changes to its table, and every table cell is checked against the data."
    ]:
        B(d, t)
    P(d, f"Every number in the revision is regenerated by code from the public data, and the revised "
         f"manuscript passes a validation script that checks {gate[0]} values, table cells and claims "
         f"against the data ({gate[1]} mismatches).")
    P(d, "Comments are quoted verbatim from the decision letter. Line numbers inside a comment refer to "
         "the original submission. Locations in our responses refer to the line-numbered PDF of the "
         "clean revision supplied with this letter. Because other renderings of the Word file can break "
         "lines differently, each location also gives the opening words of the passage.", italic=True)

    def entry(heading, comment, resp, changes, where, lead="Comment:"):
        H(d, heading, 11.5)
        P(d, comment, lead, size=10.5, italic=True)
        P_resp(d, resp, "Response:")
        if changes:
            P(d, "", "Changes made:", size=10.5)
            for c in changes:
                B(d, c, size=10.5)
        if where:
            P(d, where, "Location in the revised manuscript:", size=10.5)

    # The editor's letter: paragraph 0 is the greeting and 5 the due date;
    # paragraphs 1-4 are requirements, answered by E-01/E-02, E-03, E-04, E-05.
    H(d, "Editor", 13)
    E = {t[0]: t for t in ED}
    for n, (text, ids) in enumerate(zip(V["ED"][1:5], (("E-01", "E-02"), ("E-03",), ("E-04",), ("E-05",))), 1):
        entry(f"Editor, comment {n}", text, " ".join(E[i][2] for i in ids),
              [c for i in ids for c in E[i][3]], "; ".join(E[i][4] for i in ids if E[i][4]))

    # Each reviewer opens with a summary of the study, not a criticism; it is
    # acknowledged, not answered point by point.
    general = {
        "R1": f"We thank the reviewer for this summary, which accurately describes the primary, "
              f"metropolitan-adjusted findings, and for the comments that follow. For transparency, one "
              f"stratified result has changed in the revision, in response to Reviewer 2 (comment 3): within "
              f"nonmetropolitan counties, which hold {nm['events']} accredited CMR facilities, greater "
              f"deprivation is associated with lower CMR capacity ({fe(nm['estimate'])}). We report it as "
              f"hypothesis-generating; the adjusted results the reviewer summarizes are unchanged.",
        "R2": "We thank the reviewer for this summary and for the positive assessment of the study design, "
              "statistical methods, and presentation. We agree with the reviewer's description of the "
              "inferential framework, which Methods state: the counties are a complete enumeration, and the "
              "intervals and P values describe uncertainty about the process that distributes facilities "
              "rather than sampling error.",
    }
    for rid, block in (("R1", R1), ("R2", R2)):
        gen, comments = V[rid]
        assert len(comments) == len(block)
        H(d, f"Reviewer {rid[1]}", 13)
        entry(f"Reviewer {rid[1]}, summary", gen, general[rid], [], "", lead="Summary:")
        for n, ((tid, _summary, resp, changes, where), text) in enumerate(zip(block, comments), 1):
            entry(f"Reviewer {rid[1]}, comment {n}", text, resp, changes, where)
    P(d, "We hope the revision is now suitable for publication, and we thank the editor and reviewers "
         "again.")
    # Review is double-blind (the manuscript is blinded), so the letter names no author.
    P(d, "Sincerely,\nThe authors")
    d.save(path)


def _word_count(L):
    m = re.search(r"figurelegends(\d+)tablesandfigures", L.stream)
    if not m:
        return "3,432"
    n = int(m.group(1))
    return f"{n:,}"


# ------------------------------------------------------------- other docs
def permissions_log(path, rv):
    d = new_doc("Figure and Table Permissions Log (E-03)", SUB, landscape=True)
    P(d, "Classification of every figure and table in the manuscript and supplement. 'Original' means "
         "created by the authors from data, with no published figure or table reproduced or adapted. "
         "Citation of a data source is not treated as permission; no item below requires permission "
         "because none reproduces or adapts copyrighted published material.")
    src_map = "US Census Bureau TIGER/Line county boundaries, 2023 (public domain)"
    rows = [
        ["Figure 1A", "CMR facility-rate choropleth", "Original", "ACR registry extract (May 20, 2026); Census Bureau population estimates, July 1, 2023; "
         + src_map, "None required", "Not applicable", "Boundaries: US Census Bureau TIGER/Line, 2023."],
        ["Figure 1B", "Forest plot of IRRs", "Original", "Authors' models (code/16)", "None required",
         "Not applicable", "None"],
        ["Figure 2", "External validation forest and rurality panels", "Original",
         "Authors' models; Robert Graham Center SDI 2015-2019 (data)", "None required", "Not applicable",
         "Cite SDI in text (done)."],
        ["Figure S1", "CCT facility-rate choropleth", "Original", "As Figure 1A", "None required",
         "Not applicable", "Boundaries: US Census Bureau TIGER/Line, 2023."],
        ["Figure S2", "Quintile bar chart", "Original", "Authors' analysis", "None required", "Not applicable", "None"],
        ["Figure S3", "PCA scree plot and biplot", "Original", "SVI 2022; County Health Rankings 2024 (data)",
         "None required", "Not applicable", "None"],
        ["Table 1", "Capacity by metropolitan status and EDI quintile", "Original", "Authors' analysis",
         "None required", "Not applicable", "None"],
        ["Table 2", "Regression estimates", "Original", "Authors' analysis", "None required", "Not applicable", "None"],
        ["Table 3", "Sensitivity analyses", "Original", "Authors' analysis", "None required", "Not applicable", "None"],
        ["Table 4", "Comparison with the Social Deprivation Index", "Original",
         "Authors' models (code/21); SDI from the Robert Graham Center (cited, reference 13)",
         "None required", "Not applicable", "Not applicable"],
        ["Table 5", "Characteristics of county residents", "Original",
         "Authors' analysis of SVI 2022, County Health Rankings 2024 and ACS values", "None required",
         "Not applicable", "Sources stated in the footnote."],
        ["Tables S1-S6", "Supplementary tables", "Original",
         "Authors' analysis; S1 uses SVI 2022 and County Health Rankings 2024 values", "None required",
         "Not applicable", "Sources stated in each footnote."],
    ]
    T(d, ["Item", "Content", "Classification", "Sources", "Permission", "Documentation", "Credit line"],
      rows, widths=[0.8, 1.6, 0.9, 2.6, 0.9, 0.9, 1.6], size=8.5)
    H(d, "Data sources and terms of use (not figures; listed for completeness)", 11.5)
    rows2 = [
        ["ACR accredited facility search", "American College of Radiology", "Facility list, extracted May 20, 2026",
         "Checked November 8, 2026: the search page states the list is not intended for marketing or research "
         "use, and the ACR legal terms bar reproduction without permission. Action taken: the facility-level "
         "list is no longer distributed in the repository (county counts only; the audit trail keeps no "
         "facility names). Recommended: a short permission request to ACR (draft in "
         "manuscript/jacrad-reviews-2026/ACR_data_use_request.md)."],
        ["CDC/ATSDR Social Vulnerability Index 2022", "CDC/ATSDR (US government)", "County database",
         "US government data; CDC requests citation (reference 3 and Methods)."],
        ["Rural-Urban Continuum Codes 2023", "USDA Economic Research Service (US government)", "County codes",
         "US government data; cited (reference 11)."],
        ["County population estimates, Vintage 2023 (July 1, 2023)", "US Census Bureau", "Population counts (total and aged ≥45 years)", "US government data."],
        ["TIGER/Line Shapefiles 2023", "US Census Bureau", "County boundaries in maps", "Public domain; credit line suggested."],
        ["County Health Rankings & Roadmaps 2024", "University of Wisconsin Population Health Institute",
         "EDI inputs; Table 5 and S1 values", "Checked November 8, 2026: licensed for non-profit research use; "
         "cited as requested (University of Wisconsin Population Health Institute; County Health Rankings & "
         "Roadmaps) in Table 5 and Table S1."],
        ["Social Deprivation Index 2015-2019", "Robert Graham Center", "External validation index",
         "Checked November 8, 2026: the AAFP terms bar distribution without permission. Cited as reference 13 "
         "(Butler et al., Health Serv Res 2013); the data file is no longer distributed in the repository and "
         "is downloaded from the source by the code."],
        ["HUD-USPS ZIP crosswalk; Census ZCTA relationship file", "HUD PD&R; US Census Bureau",
         "ZIP-to-county mapping", "US government data."],
    ]
    T(d, ["Source", "Holder", "Use", "Terms / action"], rows2, widths=[2.2, 2.2, 1.8, 3.6], size=8.5)
    P(d, "No permission documentation is required for any figure or table. Data-use terms were checked "
         "for all third-party sources; the ACR and SDI data are no longer redistributed, and an optional "
         "ACR permission request is drafted.", bold_lead="Summary.")
    d.save(path)


def proofreading_report(path, log_rows, rv, gate):
    d = new_doc("Proofreading Report (E-04)", SUB)
    P(d, f"Scope: grammar and spelling, statistical terminology, IRRs, CIs and P values, units and "
         f"denominators, tables and captions, references, abbreviations, and geographic terminology. "
         f"Every number in the revised manuscript was regenerated from the data and checked by "
         f"code/12_manuscript_numbers.py ({gate[0]} checks, {gate[1]} mismatches), which also enforces "
         f"reference order, estimate punctuation, and the absence of each corrected error.")
    H(d, "1. Corrections of fact, language, and presentation", 12)
    picked = [r for r in log_rows if r["task"] == "E-04" and r["status"].startswith("applied")]
    rows = []
    seen = set()
    for r in picked:
        key = (r["rationale"], r["old"][:40])
        if key in seen:
            continue
        seen.add(key)
        rows.append([clip(r["location"], 46), clip(r["old"], 90), clip(r["new"], 90), clip(r["rationale"], 110)])
    T(d, ["Location (paragraph start)", "Before", "After", "Reason"], rows,
      widths=[1.4, 1.9, 1.9, 1.9], size=7.5)
    H(d, "2. Checks performed with no change required", 12)
    for t in ["Abstract and body word counts recomputed under the manuscript's own definitions (labels "
              "and subheadings excluded); Summary Sentence within 35 words and 250 characters and "
              "repeated word for word in the abstract.",
              "All IRRs, CIs and P values in text and tables match the generated results to the printed "
              "precision, rounded once from full precision.",
              "Rates are per 100,000 adults aged ≥45 years throughout; denominators of every percentage "
              "are stated (Table 1 footnote).",
              "Abbreviations are defined at first use in the abstract, text, and each table footnote; AIC "
              "and BIC were the only undefined abbreviations and are now defined.",
              "No tracked changes, comments, or editorial notes remain in the clean version."]:
        B(d, t, size=10)
    H(d, "3. Geographic terminology audit (R1-03)", 12)
    P(d, "Rule applied: 'metropolitan' and 'nonmetropolitan' for the binary RUCC classification "
         "(codes 1-3 and 4-9); 'rurality' only for the ordinal RUCC gradient; 'rural' only where "
         "reporting a cited source's terminology, in key words, or in reference titles.", size=10)
    T(d, ["Location", "Original wording", "Revised wording"], [
        ["Introduction", "metropolitan–rural gradient", "metropolitan–nonmetropolitan gradient"],
        ["Methods", "Metropolitan versus nonmetropolitan status was defined with … codes 1–3 = metropolitan",
         "RUCC definitions for codes 1–3 and 4–9, with the terminology rule"],
        ["Methods", "correlated with rural location", "correlated with nonmetropolitan location"],
        ["Discussion", "Most counties, and the rural populations within them", "Most counties, including nearly all nonmetropolitan counties"],
        ["Discussion", "reflected the rural–urban gradient", "largely reflected the metropolitan–nonmetropolitan gradient"],
        ["Discussion", "high-deprivation and rural counties", "high-deprivation and nonmetropolitan counties"],
        ["Tables 1 and 3 (separate files)", "-", "'Metropolitan status' for the binary split; 'rurality' only for the ordinal RUCC"],
        ["Retained", "Introduction sentence 1 (Cross et al. use rural/urban); key word 'rural health'; "
                     "'rurality' for the ordinal RUCC; title", "Unchanged; title flagged for author decision"],
    ], widths=[1.2, 2.8, 2.8], size=8.5)
    H(d, "4. Items for author verification", 12)
    for t in ["All 22 references were checked against their bibliographic records; references 20-22, "
              "the studies Reviewer 1 recommended, were verified against Europe PMC (PMIDs 36219114, "
              "37466190, 42501016), and reference 13 (Butler et al., the SDI) against Europe PMC (PMID "
              "22816561). References 5, 6 and 16 were verified (PMC, Europe PMC): reference 5 has 10 "
              "authors and reference 6 has 7, so 'et al.' after three authors is correct; the issue "
              "number (3) was added to reference 6.",
              "Reference 2 (CMS) and the new reference 11 (USDA RUCC documentation) were opened on "
              "November 8, 2026: both are live, and their access dates read accordingly. The CMS page "
              "does not state an effective date or which accrediting organization is largest, so the "
              "Introduction no longer attributes those to it. Reference 1 (Cross et al.) was read in "
              "full: it reports cardiovascular mortality by rural-urban residence, age, sex, race and "
              "ethnicity, not by economic status.",
              "The Data Availability bracket now says the repository URL will be provided on acceptance "
              "(it previously said it would be restored 'at revision', which this revision is); the gate "
              "forbids the old phrase.",
              "The Summary Sentence now says that the primary models showed no statistically significant "
              "inverse deprivation association (the submitted wording, 'no inverse deprivation gradient "
              "persisted after adjustment', did not distinguish the primary from the exploratory models); it "
              "is repeated word for word in the abstract, as the journal requires."]:
        B(d, t, size=10)
    d.save(path)


CODE_CHANGES = [
    ("R1-02, R2-03, R1-04, R2-01, R2-02, E-05, R2-05", "code/18_reviewer_analyses.py (new)",
     "All new analyses; writes reviewer_analyses.json/.txt, comprehensive_model_table.csv, "
     "population_characteristics.csv, edi_pca_*.csv, nonmetro_cmr_diagnostics.txt"),
    ("R2-03", "code/model_spec.py", "fit_primary_checked(): diagnoses every stratified fit; Poisson "
     "boundary solution only when the NB2 dispersion is on its boundary"),
    ("R2-03", "code/06_edi_sensitivity_analysis.py; code/12_manuscript_numbers.py",
     "Stratified fits use the diagnosed fit"),
    ("R2-05", "code/14_accredited_only_sensitivity.py", "Accredited-only sensitivity on the primary "
     "sample, SVI and EDI; writes cohort descriptives"),
    ("R2-04", "code/12_manuscript_numbers.py; code/17_table1.py", "Facility percentages and denominators "
     "in Table 1; 'Metropolitan status' heading"),
    ("All", "code/12_manuscript_numbers.py", "Gate checks every new number and claim, reference order, "
     "and the absence of each corrected error"),
    ("R2-01", "code/16_publication_figures.py", "Figure S3 (scree plot and biplot)"),
    ("E-05, R2-05, R2-02, R2-03, R2-01, R1-04", "code/19_supplementary_material.py (new)",
     "Supplementary Methods, Tables S1-S6, Figures S1-S3 legends and images"),
    ("All", "code/00_run_all.py", "Runs 18 in stage C and 19 in stage E"),
    ("All", "tests/test_pipeline.py", "Three new tests (24 in total), including UTF-8 BOM on non-ASCII CSVs"),
    ("E-02", "tools/docx_tracked.py", "Tracked paragraph and table-row insertion"),
    ("E-02, all text items", "tools/revise_manuscript_r1.py (new)", "Applies the revision as tracked "
     "changes; every number formatted from generated results"),
    ("E-01, E-03, E-04, E-06", "tools/build_r1_package.py (new)", "Builds this package"),
]


def clip(text, n):
    """A display excerpt: trimmed, single-spaced, empty table cells dropped, and
    cut at a word boundary with an ellipsis. The CSV log keeps the raw text."""
    t = re.sub(r"(?:\s*/\s*){2,}", " / ", text or "")
    t = re.sub(r"\s+", " ", t).strip().lstrip(".,; ").strip()
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(" ", 1)[0].rstrip(" ,;:(")
    return cut + " \u2026"


def change_log(path_docx, path_csv, log_rows, gate, tests_line):
    d = new_doc("Change Log, Revision 1", SUB, landscape=True)
    H(d, "A. Task-to-implementation map", 12)
    T(d, ["Task", "Files", "Implementation"], [list(x) for x in CODE_CHANGES],
      widths=[1.8, 3.0, 4.6], size=8.5)
    P(d, f"Verification: the validation gate passes on the clean, tracked and working manuscripts "
         f"({gate[0]} checks, {gate[1]} mismatches); {tests_line}; the accepted text of the tracked "
         f"manuscript is identical to the clean manuscript.", size=10)
    H(d, "B. Every manuscript edit (tracked changes, in document order)", 12)
    rows = [[r["task"], r["kind"], clip(r["location"], 40), clip(r["old"], 70), clip(r["new"], 110),
             clip(r["rationale"], 90)] for r in log_rows]
    T(d, ["Task", "Edit", "Location", "Before", "After", "Rationale"], rows,
      widths=[0.5, 0.8, 1.4, 2.0, 2.8, 2.0], size=7)
    d.save(path_docx)
    # Two tables, two files: each has one schema and parses as an ordinary CSV.
    with open(path_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(list(log_rows[0].keys()))
        for r in log_rows:
            w.writerow(list(r.values()))
    with open(path_csv.replace(".csv", "_Tasks.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["task", "files", "implementation"])
        w.writerows(CODE_CHANGES)


DECISIONS = [
    ("Baseline version (resolved by evidence)", "The tracked changes are made against the manuscript "
     "as submitted to JACR (first_submission_to_jacr/JACR_Main_Manuscript_Blinded.docx, September 25, "
     "2026; tables were uploaded separately). Rendered with its line numbers, it places the sentences the "
     "reviewers quote exactly where they cite them: lines 78-79, lines 91-92, and page 9, line 165. An "
     "earlier build used an August 16 repository file whose lines fell close but not exactly (92-93)."),
    ("Reviewer 1's recommended studies (R1-05)", "The full comment lists three studies (PubMed 36219114, "
     "37466190, 42501016; Christensen et al., Radiology 2023, AJR 2024, Inquiry 2026). All three are now "
     "cited as references 20-22 in one added Discussion sentence, each described by what it found "
     "(verified against the Europe PMC records). Approve the sentence."),
    ("Accuracy audit, November 8, 2026", "Independent recomputation of the key numbers from the raw data "
     "found one systematic issue: BFGS stopped marginally short of the maximum in some NB2 fits. All NB2 "
     "fits now finish with Newton steps (model_spec.fit_nb2). Four submitted results change in the last "
     "digit (SVI metropolitan IRR 8.56 to 8.55 and upper limit 14.61 to 14.59; SDI CCT metropolitan IRR 2.12 "
     "to 2.11; ordinal-RUCC P 0.801 to 0.802; nonmetropolitan CCT P 0.232 to 0.233, a boundary solution "
     "found by the November 9 full audit) and the interaction P changes from 0.004 to 0.003; the response "
     "discloses the four "
     "submitted values. The gate now checks every estimate quoted in the text. Also added: parallel "
     "analysis (retains one component), the "
     "density-adjusted SVI-CMR estimate moved to Supplementary Table S6 only, and the Data Availability "
     "bracket fix. "
     "Approve."),
    ("Wording added after reading the verbatim comments", "Four sentences or clauses: pooled rates "
     "identified as population-weighted mean county rates and the rationale for weighting counties "
     "equally (Methods, R1-02); 'Sensitivity analyses were intended to assess the robustness of the "
     "primary findings' (Methods, R2-02); and 'Disparities in capacity are often interpreted as evidence "
     "of bias, which these data can neither show nor exclude; the observed pattern is more consistent "
     "with market size' (Discussion, R1-05). Approve."),
    ("Previously published figures (E-03)", "Resolved: the repository holds no record of a preprint, "
     "poster or abstract, and every figure and table was generated for this manuscript, so the response "
     "states that none was published previously. Submitting the response attests this."),
    ("Nonmetropolitan CMR row (R2-03)", "Reported as estimable (Poisson boundary solution), IRR 0.70, "
     "P = 0.003, replacing 'NE'. This adds an inverse within-stratum association to Results and an "
     "'exception' sentence to the Discussion. Approve the reporting and wording."),
    ("Primary hypothesis family (R2-02)", "Defined as the four metropolitan-adjusted SVI and EDI "
     "associations. Holm over all 18 tests would make SVI-CCT nonsignificant (P = 0.113); BH over 18 "
     "keeps it. Approve the family definition."),
    ("Weighting (R1-02)", "Corrected after the repository-only review: the earlier 'population-weighted' "
     "models added population weights to an offset Poisson model, which weights county rates by "
     "population squared. Poisson regression with the offset is the population-weighted analysis; it now "
     "replaces them, and its estimates agree with the primary NB2 estimates (SVI-CCT positive, P = 0.010; "
     "adjusted EDI null). Equal county weights are shown in S2. NB2 kept primary on fit. Approve."),
    ("Repository-only review, November 8, 2026", "All 18 findings were verified against the code and data "
     "and found to be real; all journal-facing ones are corrected (weighting estimator, RUCC separation, "
     "sensitivity wording, 'confined', index-IRR bound, sparse-strata note, S2 contents, S1 labels, "
     "cohort documentation, diagnostics text, blinding of the tracked file, change-log CSV, Figure 2 "
     "note, check-scope wording). Repository items (tracking tools/, docs, API key, checker exit code, "
     "pytest-free skips) are fixed in the working tree; committing them is your decision."),
    ("Population characteristics (E-05)", "Resolved: added as Table 5, a separate file like the other "
     "tables; the submitted Table 4 (SDI comparison) is kept, so the exhibits are 5 tables and 2 figures (7 of 7 "
     "exhibits), because the editor calls the table mandatory; Supplementary Table S1 keeps the medians, "
     "IQRs and missing counts."),
    ("Word count", "Resolved: an archived copy of the JACR author instructions (April 2025) limits "
     "Original Articles to fewer than 3,000 words, not counting references, and says the Take-Home "
     "Points take the place of a conclusions section. The text was condensed below 3,000 words by "
     "removing restatements only, including the Discussion's closing repeat of the Summary Sentence (the "
     "Take-Home Point). The revision script reports the count on the title block and the title page."),
    ("Title and Summary Sentence", "Title kept: 'Rurality' refers to the RUCC continuum the paper "
     "analyzes. Summary Sentence kept as submitted except that it now says the primary models showed no "
     "statistically significant inverse deprivation association; it is repeated word "
     "for word in the abstract, as JACR requires."),
    ("PCA retention (R2-01)", "Resolved: PC2 eigenvalue 1.03 is below the parallel-analysis threshold "
     "(1.05), so one component is retained; reported in Results, Supplementary Methods S2, Table S5 and "
     "Figure S3."),
    ("Exploratory SVI-CMR density result", "With density adjustment SVI-CMR is 0.97 (P = 0.065). "
     "Now reported in Supplementary Table S6 only (removed from Results for length, with two other "
     "trims: the RUCC 1 facility count in the Discussion and a repeated definition of the weighted "
     "estimand); the response does not mention it."),
    ("Accredited-only sensitivity", "Now fitted on the primary sample (was the rate-eligible subset). "
     "Conclusions unchanged."),
    ("References", "Resolved: all 22 verified; the SDI is now cited (reference 13); references 2 and 11 "
     "rechecked on November 8, 2026 with access dates updated; the Introduction no longer attributes a "
     "section number, effective date or 'largest' accreditor to the CMS page, which states none of them."),
    ("Data-use terms", "Resolved: checked on November 8, 2026. ACR's facility search says its list is not "
     "for research or marketing use, and its legal terms bar reproduction; the ACR files are no longer "
     "tracked in the repository and the audit keeps no facility names. A permission request to ACR is "
     "drafted (ACR_data_use_request.md) for the corresponding author to send. County Health Rankings "
     "permits non-profit research use and is cited as requested. The SDI terms bar distribution; the file "
     "is no longer tracked and the index is cited. The files remain in earlier commits."),
    ("Title page and cover letter", "Generated (13_Title_Page, 14_Cover_Letter) from the authors' title "
     "page, without its notes. The author-contribution statement is drafted from the repository record "
     "(Dr Naeem: design, interpretation, writing; Dr Razak: data, statistics, software); co-authors "
     "should confirm it before upload. Author order changed at revision 1: Abdul Razak first, Dr Naeem "
     "corresponding; affiliations renumbered. Elsevier requires the reason (in the cover letter) and "
     "written agreement from all eight authors, to be uploaded with the revision."),
    ("Due date", "JACR asks for the revision by December 3, 2026."),
]


def checklist(path, files_ok, gate, tests_line):
    d = new_doc("Final Submission Checklist (E-06)", SUB)
    rows = [
        ["Revised clean manuscript, line-numbered (.docx, .pdf)", "01", "Done", files_ok("01")],
        ["Revised tracked-changes manuscript, line-numbered (.docx, .pdf)", "02", "Done", files_ok("02")],
        ["Response to reviewers and editor (.docx, .pdf)", "03", "Done; comments quoted verbatim; "
         "no placeholders", files_ok("03")],
        ["Supplementary material: Methods S1-S8, Tables S1-S6, Figures S1-S3", "04", "Done", files_ok("04")],
        ["Figures 1A, 1B, 2, S1-S3 at 600 dpi (TIFF, PDF, PNG)", "05_Figures", "Done", files_ok("05_Figures")],
        ["Table 1 (.docx, .csv) and supplementary tables (.csv)", "06_Tables", "Done", files_ok("06_Tables")],
        ["Statistical outputs and validation report", "07_Statistical_Outputs", "Done", files_ok("07_Statistical_Outputs")],
        ["Permissions documentation", "08", "Done; none required; 3 terms to confirm", files_ok("08")],
        ["Proofreading report", "09", "Done; access dates of references 2 and 11 to confirm", files_ok("09")],
        ["Change log", "10", "Done", files_ok("10")],
        ["Validation gate on clean and tracked versions", "07", f"{gate[0]} checks, {gate[1]} mismatches", "yes"],
        ["Pipeline tests", "-", tests_line, "yes"],
        ["Accepted text of tracked = clean", "-", "Verified identical", "yes"],
        ["Title page (unblinded) and cover letter (.docx, .pdf)", "13, 14", "Done; co-authors to confirm "
         "the drafted contribution statement", files_ok("13")],
        [f"Manuscript ID {MS_ID} on the response letter and package documents", "03, 08-12", "Done", "yes"],
        ["Due date", "-", "December 3, 2026", "-"],
        ["Author decisions (see 00_Revision_Plan)", "00", f"{len(DECISIONS)} items need approval", files_ok("00")],
    ]
    T(d, ["Item", "Package file", "Status", "Present"], rows, widths=[3.2, 1.2, 2.0, 0.6], size=9)
    d.save(path)


def plan_doc(path, rv, mn):
    W, S, M, U = rv["R1-02_weighting"], rv["R2-03_strata"], rv["R2-02_multiplicity"], rv["R1-04_urban_core"]
    d = new_doc("Revision Plan and Critical Appraisal (internal, for the authors)", SUB)
    P(d, "Written for the authors, not for submission. It records how each comment was assessed, what "
         "the new analyses showed, and the decisions that need your approval.", italic=True)
    H(d, "1. Critical appraisal of the comments", 12)
    T(d, ["Item", "Assessment", "What the analysis showed", "Effect on conclusions"], [
        ["R1-01", "Valid; presentational.", "Four results sat in Methods.", "None."],
        ["R1-02", "Partly valid. The rate exclusion is harmless (no excluded county has a facility); "
         "the weighting question is a real estimand issue, not an error.",
         f"Population-weighted (Poisson with offset) estimates agree with the primary ones; metro IRR "
         f"{W['models']['EDI_CMR_adjusted']['metro_poisson_population_weighted_robust']['irr']:.1f} (CMR), "
         f"{W['models']['EDI_CCT_adjusted']['metro_poisson_population_weighted_robust']['irr']:.1f} (CCT); "
         f"Kish effective n {W['weights']['SVI']['kish_effective_n']:.0f}.",
         "Robustness confirmed; the unadjusted EDI-CMR signal is largest with counties weighted equally "
         "(small-county phenomenon)."],
        ["R1-03", "Valid.", "Seven wording changes; RUCC defined.", "None."],
        ["R1-04", "Valid and useful.", "SVI-CCT detected in metro but not nonmetro counties "
         "(interaction not significant), strongest for themes 3-4, attenuated by density; finer "
         "urbanicity makes SVI-CMR inverse.", "Consistent with the urban-core explanation; exploratory."],
        ["R1-05", "Valid.", "Discussion only; verified references.", "None."],
        ["R2-01", "Valid.", "PC1 58.7%; PC2 eigenvalue 1.03 (housing cost burden).",
         "Index construction defensible; note PC2."],
        ["R2-02", "Valid; partly rebuttable (Rothman).", "Primary family unchanged; BH over 18 removes "
         "3 borderline secondary results; Holm over 18 would remove SVI-CCT.", "Minor; secondary SDI-CMR "
         "result weakened."],
        ["R2-03", "Valid; exposed a reporting error.", "Boundary MLE; IRR 0.70 (0.56-0.89), P = 0.003; "
         f"interaction P = {S['interaction']['EDI_CMR']['interaction_ratio']['p']:.3f}; consistent across indices.", "Material: adds a within-nonmetro inverse "
         "CMR association (14 facilities)."],
        ["R2-04", "Valid.", "Percentages added; denominators stated.", "None."],
        ["R2-05", "Valid.", "76-row model table plus model-fit panel.", "None."],
    ], widths=[0.6, 1.8, 2.4, 1.9], size=8.5)
    H(d, "2. Implementation order followed", 12)
    for t in ["Reproduced the submitted results from the committed data (all values matched; the EDI "
              "file differs from the commit only at 1e-14, from the randomized SVD solver).",
              "Resolved R2-03, R1-02 and R2-02 before writing text.",
              "Built E-05, R2-01, R2-04 and R2-05 outputs.",
              "Revised text (R1-01, R1-03, R1-04, R1-05) as tracked changes, numbers formatted from results.",
              "Editorial compliance (E-01 to E-06) and package."]:
        B(d, t, size=10)
    H(d, "3. Reconciliation with the verbatim comments (November 7, 2026)", 12)
    for t in RECONCILE:
        B(d, t, size=10)
    H(d, "4. Decisions requiring author approval", 12)
    T(d, ["Decision", "Detail"], [list(x) for x in DECISIONS], widths=[1.8, 4.9], size=9)
    d.save(path)


RECONCILE = [
    "The original reviewer and editor comments (reviwer-R1_original_comments.txt, "
    "reviwer-R2_original_comments.txt, editorial-requirements-R1-original.txt) were checked against the "
    "implementation on November 7, 2026. The response letter now quotes them verbatim, read from those "
    "files at build time.",
    "All ten reviewer comments and the four editor requirements map one to one onto R1-01 to R2-05 and "
    "E-01 to E-05; E-06 (the package) is not an editor comment and is covered by the checklist.",
    "Baseline: the reviewers' line references (R1: lines 78-79, 91-92; R2: page 9, line 165) match the "
    "manuscript as submitted to JACR on September 25, 2026 exactly.",
    "R1-02: the reviewer proposed weighting the rate calculations by eligible population, or explaining "
    "why counties are weighted equally. Methods now identify the pooled rates as population-weighted mean "
    "county rates and state the rationale for the county-level estimand.",
    "R2-02: the reviewer asked for an adjustment or a statement that none was made, noting that secondary "
    "analyses assess robustness. Methods now state that the sensitivity analyses were intended to assess "
    "the robustness of the primary findings.",
    "R2-03: the reviewer asked whether the problem was convergence, variance estimation, or sparse data. "
    "The response now answers in those terms first: converged; variance estimation failed; caused by "
    "sparse data.",
    "R1-05: the reviewer's point that disparities are often read as evidence of bias is now addressed in "
    "the Discussion, and the three studies the reviewer lists (supplied in the updated comment file) "
    "are cited as references 20-22.",
    "E-03: the editor asks whether any table or figure was published previously; the response now "
    "answers 'No' directly.",
    "E-05: the editor's wording ('mandatory for a responsive revision') is unchanged in substance from the "
    "task list; Supplementary Table S1 answers it, with sex reported as recorded in Census estimates.",
]


# ------------------------------------------------------ title page, cover letter
def _title_page_facts():
    """Authors, affiliations, contact, funding and employment statement, read from
    the authors' title page (manuscript/title_page.docx), without its notes."""
    src = Document(os.path.join(BASE, "manuscript", "title_page.docx"))
    paras = [p.text.strip() for p in src.paragraphs if p.text.strip()]
    heads = ["Authors", "Affiliations", "Corresponding Author", "Author Contributions", "Funding",
             "Employment and Statement of Independence", "Conflicts of Interest", "Data Availability"]
    sec, cur = {}, None
    for t in paras:
        if t in heads:
            cur = t
            sec[cur] = []
        elif cur and not t.startswith("[AUTHOR NOTE"):
            sec[cur].append(t)
    sec["Corresponding Author"] = [re.sub(r"\s*Telephone:\s*\[to be added\]", "", t).strip()
                                   for t in sec["Corresponding Author"]]
    return _first_author(sec, FIRST_AUTHOR)


#: Author order for revision 1: Abdul Razak first (the authors' title page lists
#: Dr Naeem first). The corresponding author is unchanged.
FIRST_AUTHOR = "Abdul Razak, PhD"


def _first_author(sec, name):
    """Move `name` to the head of the author list and renumber the affiliations
    in order of first appearance, as journals expect."""
    sup = "⁰¹²³⁴⁵⁶⁷⁸⁹"
    authors = [a.strip() for a in sec["Authors"][0].split(";")]
    assert sum(a.startswith(name) for a in authors) == 1, name
    authors = [a for a in authors if a.startswith(name)] + [a for a in authors if not a.startswith(name)]
    affs = {}
    for t in sec["Affiliations"]:
        m = re.match(r"(\d+)\.\s*(.*)", t)
        affs[int(m.group(1))] = m.group(2)
    renum, out = {}, []
    for a in authors:
        old = sup.index(a[-1])
        renum.setdefault(old, len(renum) + 1)
        out.append(a[:-1] + sup[renum[old]])
    assert set(renum) == set(affs), "every affiliation must belong to an author"
    sec["Authors"] = ["; ".join(out)]
    sec["Affiliations"] = [f"{new}. {affs[old]}" for old, new in sorted(renum.items(), key=lambda kv: kv[1])]
    return sec


def _manuscript_counts():
    text = "\n".join(p.text for p in Document(os.path.join(BASE, "manuscript",
                                                            "manuscript_SUBMISSION.docx")).paragraphs)
    # Front-matter line as in the submitted manuscript: "Word count: N (...). Abstract: N words.
    # Tables and figures: 5 tables, 2 figures (7 of 7 permitted); ... References: 22."
    body = re.search(r"Word count: ([\d,]+) \(", text).group(1)
    refs = re.search(r"References: (\d+)\.", text).group(1)
    tf = re.search(r"Tables and figures: (\d+) tables, (\d+) figures", text)
    abstract = re.search(r"Abstract: (\d+) words", text).group(1)
    return {"body": body, "refs": refs, "tables": tf.group(1), "figures": tf.group(2), "abstract": abstract}


def title_page(path):
    F, K = _title_page_facts(), _manuscript_counts()
    d = new_doc("Title Page", f"Manuscript {MS_ID} | Revision 1 | {TODAY}")
    P(d, TITLE, size=13)
    for h in ("Authors", "Affiliations", "Corresponding Author"):
        H(d, h, 11.5)
        for t in F[h]:
            P(d, t)
    H(d, "Manuscript Details", 11.5)
    for t in [f"Article type: Original Article (revision 1).",
              f"Word count, Introduction through Data Availability: {K['body']}.",
              f"Abstract: {K['abstract']} words.",
              f"Tables: {K['tables']}. Figures: {K['figures']}. References: {K['refs']}.",
              "Supplementary material: Supplementary Methods S1-S8, Tables S1-S6, and Figures S1-S3."]:
        B(d, t)
    H(d, "Author Contributions", 11.5)
    P(d, "Abdul Razak: acquisition and curation of the data, statistical analysis, software, "
         "visualization, and drafting and critical revision of the manuscript. Muhammad Naeem: "
         "conception and design, interpretation of the data, drafting and critical revision of the "
         "manuscript, and supervision. Ahmed Kamal Siddiqi, Matthew Stib, Clinton E. Jokerst, Michael Gotway, Carlos "
         "A. Rojas, and Kristopher W. Cummings: interpretation of the data and critical revision of the "
         "manuscript for important intellectual content. All authors approved the final version and "
         "agree to be accountable for all aspects of the work.")
    H(d, "Data Statement", 11.5)
    P(d, "The authors declare that they had full access to all of the data in this study and the "
         "authors take complete responsibility for the integrity of the data and the accuracy of the "
         "data analysis.")
    H(d, "Funding", 11.5)
    for t in F["Funding"]:
        P(d, t)
    H(d, "Employment and Statement of Independence", 11.5)
    for t in F["Employment and Statement of Independence"]:
        P(d, t)
    H(d, "Conflicts of Interest", 11.5)
    P(d, "Declared for all authors through the Elsevier Declarations tool and uploaded as a separate "
         "document.")
    H(d, "Data Availability", 11.5)
    P(d, "The analytic data and code are held in an online repository whose address will be provided "
         "on acceptance. The repository shares county-level data only; the ACR facility list and the "
         "Robert Graham Center Social Deprivation Index are available from their sources.")
    d.save(path)


def cover_letter(path, rv):
    F, K = _title_page_facts(), _manuscript_counts()
    nm = rv["R2-03_strata"]["strata"]["EDI_CMR_nonmetro"]
    wm = rv["R1-02_weighting"]["models"]
    d = new_doc("Cover Letter", f"Manuscript {MS_ID} | Revision 1 | {TODAY}")
    P(d, TODAY)
    P(d, "The Editor\nJournal of the American College of Radiology")
    P(d, f"Re: Manuscript {MS_ID}, “{TITLE}”, Revision 1", bold_lead=None)
    P(d, "Dear Editor,")
    P(d, "Thank you for the opportunity to revise our manuscript, and for the reviewers' careful and "
         "constructive comments. We submit the revised manuscript with a point-by-point response to "
         "the editor and both reviewers, tracked-changes and clean versions of the manuscript, the "
         "revised supplementary material, and the figures.")
    P(d, "The principal changes are these:")
    for t in [
        "A table of the characteristics of county residents, including race and ethnicity, sex, and "
        "clinical conditions, has been added (Table 5), as the editor requires; the "
        "study has no patient-level data, and the table describes the residents of the counties "
        "analyzed.",
        "A population-weighted sensitivity analysis was added at Reviewer 1's suggestion, and Methods "
        "now explain how each model weights counties; for the SVI and the EDI, the population-weighted "
        "estimates lead to the same conclusions as the primary estimates.",
        f"The nonmetropolitan cardiac MR estimate previously reported as not estimable is now "
        f"estimated from its boundary (Poisson) solution ({fe(nm['estimate'])}) and reported as "
        f"hypothesis-generating, in response to Reviewer 2's question.",
        "A primary hypothesis family with multiplicity-adjusted P values, the full principal "
        "component analysis with parallel analysis, facility percentages in Table 1, and a "
        "comprehensive supplementary table of all models were added.",
        "The Discussion now addresses the economics of advanced imaging, with the three studies "
        "Reviewer 1 recommended, and the positive association between social vulnerability and "
        "cardiac CT capacity; geographic terminology follows the RUCC definitions.",
    ]:
        B(d, t)
    assert int(K["body"].replace(",", "")) < 3000, "JACR limits Original Articles to fewer than 3,000 words"
    P(d, f"The revised manuscript has {K['body']} words in the body (the journal's limit is 3,000), a "
         f"{K['abstract']}-word abstract, "
         f"{K['tables']} tables, {K['figures']} figures, and {K['refs']} references. Every number is "
         f"generated from the data by code and checked against it automatically. All authors have read and approved the revised "
         f"manuscript, which is not under consideration elsewhere.")
    P(d, "Change in author order. With the agreement of all authors, Abdul Razak, PhD, is now first "
         "author, reflecting the data acquisition, statistical analysis, and new analyses of this "
         "revision performed by Dr Razak; Dr Naeem remains the corresponding author. Written "
         "confirmation from all authors is provided with this submission, as the journal's authorship "
         "policy requires.")
    P(d, "We are grateful for your consideration.")
    # The corresponding-author line begins with the name; drop it so the name is not repeated.
    corr = F["Corresponding Author"][0] if F.get("Corresponding Author") else ""
    corr = re.sub(r"^Muhammad Naeem, MBBS, MD,\s*", "", corr)
    P(d, "Sincerely,\nMuhammad Naeem, MBBS, MD\nOn behalf of all authors\n" + corr)
    d.save(path)


def completion_report(path, gate, tests_line, flags):
    status = [
        ("R1-01", "Complete", "Results sensitivity paragraph; Methods edits", "-"),
        ("R1-02", "Complete", "Methods, Results, Table 3, Table S2, Suppl. Methods S3", "Approve rebuttal (weighting as sensitivity)"),
        ("R1-03", "Complete", "Methods definitions; 7 edits; Table 1", "Title keeps 'Rurality'"),
        ("R1-04", "Complete", "Results exploratory paragraph; Discussion; Table S6", "Exploratory; tertiary-center link untested"),
        ("R1-05", "Complete", "Discussion paragraph, including disparity versus bias; refs 17-22 (20-22 recommended by the reviewer)", "-"),
        ("R2-01", "Complete", "Figure S3; Table S5; Suppl. Methods S2", "-; parallel analysis retains one component"),
        ("R2-02", "Complete", "Methods; Results; Table 2 note; Table S3", "Approve primary-family definition"),
        ("R2-03", "Complete", "Table 3; Results; Discussion; Table S4; diagnostics file", "Approve reporting of a new significant within-stratum estimate"),
        ("R2-04", "Complete", "Table 1 columns and footnote", "-"),
        ("R2-05", "Complete", "Table S2 (Panels A and B)", "-"),
        ("E-01", "Complete; comments quoted verbatim", "03_Response_to_Reviewers", "-"),
        ("E-02", "Complete", "01 clean, 02 tracked (identical accepted text)", "Baseline confirmed by the reviewers' line references"),
        ("E-03", "Complete", "08_Permissions_Log", "Data terms checked; ACR and SDI files no longer redistributed; optional ACR permission request drafted"),
        ("E-04", "Complete", "09_Proofreading_Report", "Confirm access dates, references 2 and 11"),
        ("E-05", "Complete; Table 5 added (patient-level items not applicable)", "Table 5; Table S1; response text", "-"),
        ("E-06", "Complete", "This package, including 13_Title_Page and 14_Cover_Letter; 11_Submission_Checklist; MANIFEST.csv", "-"),
    ]
    L = [f"# Completion report, Revision 1", "", f"{TITLE}", f"Manuscript {MS_ID}. Prepared {TODAY}.", "",
         f"Validation: {gate[0]} checks, {gate[1]} mismatches on the clean and tracked manuscripts. "
         f"{tests_line}.", "", "| Task | Status | Supporting files | Unresolved / needs approval |",
         "|---|---|---|---|"]
    for r in status:
        L.append("| " + " | ".join(r) + " |")
    L += ["", "## Reconciliation with the verbatim comments", ""]
    L += [f"- {x}" for x in RECONCILE]
    L += ["", "## Open items for the authors", ""]
    for k, v in flags:
        L.append(f"- **{k}.** {v}")
    open(path, "w").write("\n".join(L) + "\n")


# ===================================================================== main
def main():
    rv, mn = load()
    if os.path.exists(PKG):
        shutil.rmtree(PKG)
    for sub in ("05_Figures", "06_Tables", "07_Statistical_Outputs"):
        os.makedirs(os.path.join(PKG, sub), exist_ok=True)

    clean = os.path.join(PKG, "01_Revised_Manuscript_CLEAN.docx")
    tracked = os.path.join(PKG, "02_Revised_Manuscript_TRACKED.docx")
    # The clean version is always derived here from the tracked one, so the
    # two cannot drift apart; it must also match the working submission file.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from docx_tracked import TrackedDocument
    work_clean = os.path.join(WORK, "manuscript_R1_CLEAN.docx")
    doc = TrackedDocument(os.path.join(WORK, "manuscript_R1_TRACKED.docx"), author="finalize")
    doc.accept_all()
    doc.save(work_clean)

    def text(p):
        # Empty paragraphs are layout, not text: a deleted paragraph reads as
        # empty in the tracked copy and is gone from the accepted one.
        t = TrackedDocument(p, author="x")
        return [x for x in (t.accepted_text(q) for q in t.paragraphs()) if x.strip()]
    sub = os.path.join(BASE, "manuscript", "manuscript_SUBMISSION.docx")
    same = text(work_clean) == text(os.path.join(WORK, "manuscript_R1_TRACKED.docx")) == text(sub)
    assert same, "tracked, clean and working submission texts differ; rerun the revision"
    add_line_numbers(work_clean, clean)
    add_line_numbers(os.path.join(WORK, "manuscript_R1_TRACKED.docx"), tracked)
    # Blinding: the journal copies must carry no identifying revision author.
    for f in (clean, tracked):
        with zipfile.ZipFile(f) as z:
            xml = z.read("word/document.xml").decode("utf8")
            core = z.read("docProps/core.xml").decode("utf8") if "docProps/core.xml" in z.namelist() else ""
        names = set(re.findall(r'w:author="([^"]+)"', xml)) - {"Author"}
        assert not names, f"identifying revision author(s) {names} in {os.path.basename(f)}; rebuild with --blind"
        assert "Razak" not in core and "Naeem" not in core, f"identifying core property in {os.path.basename(f)}"

    g_tr = run_gate(tracked)
    g_cl = run_gate(clean)
    assert g_cl[1] == 0 and g_tr[1] == 0, (g_cl[:3], g_tr[:3])
    shutil.copy(os.path.join(VAL, "manuscript_check.txt"),
                os.path.join(PKG, "07_Statistical_Outputs", "manuscript_check_R1_CLEAN.txt"))
    gate = (g_cl[0], g_cl[1])
    pdf_clean = to_pdf(clean)
    to_pdf(tracked)
    L = Locator(pdf_clean)

    t = subprocess.run([sys.executable, os.path.join(BASE, "tests", "test_pipeline.py")],
                       cwd=BASE, capture_output=True, text=True).stdout
    n_pass = t.count("PASS")
    n_fail = int(re.search(r"(\d+) failure", t).group(1))
    tests_line = f"pipeline tests: {n_pass} passed, {n_fail} failed"

    with open(os.path.join(WORK, "r1_change_log.csv"), encoding="utf-8-sig") as f:
        log_rows = list(csv.DictReader(f))

    resp = os.path.join(PKG, "03_Response_to_Reviewers.docx")
    response_letter(rv, mn, L, resp, gate)
    to_pdf(resp)

    shutil.copy(os.path.join(TAB, "Supplementary_Material.docx"),
                os.path.join(PKG, "04_Supplementary_Material.docx"))
    to_pdf(os.path.join(PKG, "04_Supplementary_Material.docx"))

    for stem in ("Figure1A_CMR_Choropleth", "Figure1B_Forest", "Figure2_External_Validation",
                 "FigureS1_CCT_Choropleth", "FigureS2_EDI_Quintiles", "FigureS3_EDI_PCA"):
        for ext in ("tif", "pdf", "png"):
            src = os.path.join(FIG, f"{stem}.{ext}")
            if os.path.exists(src):
                shutil.copy(src, os.path.join(PKG, "05_Figures"))
    for fn in os.listdir(TAB):
        if fn.startswith(("Table1_", "Table2_Primary", "Table3_Sensitivity", "Table4_Comparison",
                          "Table5_", "Supplementary_Table_S")):
            shutil.copy(os.path.join(TAB, fn), os.path.join(PKG, "06_Tables"))
    for fn in ("reviewer_analyses.json", "reviewer_analyses.txt", "comprehensive_model_table.csv",
               "nonmetro_cmr_diagnostics.txt", "population_characteristics.csv",
               "edi_pca_components.csv", "edi_pca_scores.csv", "model_specification_comparison.csv",
               "model_specification_comparison.txt", "accredited_only_sensitivity.csv",
               "accredited_only_sensitivity.txt", "accredited_only_descriptives.csv",
               "index_comparison_results.json", "index_comparison_results.txt",
               "svi_quartile_regression.csv"):
        shutil.copy(os.path.join(RES, fn), os.path.join(PKG, "07_Statistical_Outputs"))
    for fn in ("manuscript_numbers.json", "manuscript_numbers.txt"):
        shutil.copy(os.path.join(VAL, fn), os.path.join(PKG, "07_Statistical_Outputs"))

    permissions_log(os.path.join(PKG, "08_Permissions_Log.docx"), rv)
    proofreading_report(os.path.join(PKG, "09_Proofreading_Report.docx"), log_rows, rv, gate)
    change_log(os.path.join(PKG, "10_Change_Log.docx"), os.path.join(PKG, "10_Change_Log.csv"),
               log_rows, gate, tests_line)
    plan_doc(os.path.join(PKG, "00_Revision_Plan_and_Critical_Appraisal_INTERNAL.docx"), rv, mn)

    tp = os.path.join(PKG, "13_Title_Page.docx")
    title_page(tp)
    to_pdf(tp)
    cl = os.path.join(PKG, "14_Cover_Letter.docx")
    cover_letter(cl, rv)
    to_pdf(cl)

    def files_ok(prefix):
        return "yes" if any(n.startswith(prefix) for n in os.listdir(PKG)) else "MISSING"
    checklist(os.path.join(PKG, "11_Submission_Checklist.docx"), files_ok, gate, tests_line)
    completion_report(os.path.join(PKG, "12_Completion_Report.md"), gate, tests_line, DECISIONS)

    rows = []
    for root, _, files in os.walk(PKG):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rows.append([os.path.relpath(p, PKG), os.path.getsize(p), sha(p)])
    with open(os.path.join(PKG, "MANIFEST.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "bytes", "sha256"])
        w.writerows(sorted(rows))
    print(f"  package: {os.path.relpath(PKG, BASE)}  ({len(rows)} files)")
    print(f"  gate: {gate[0]} checks, {gate[1]} mismatches; {tests_line}")


if __name__ == "__main__":
    main()
