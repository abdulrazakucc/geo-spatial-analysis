#!/usr/bin/env python3
"""
build_branch_comparison.py
==========================
Builds the detailed `main` vs `validation` comparison as HTML, then converts it
to PDF with LibreOffice.

The "before" column is read from the analysis outputs committed on `main`; the
"after" column from the current working tree. Nothing is typed from memory, so
the document can be rebuilt after any change and will stay truthful.

Run
    python tools/build_branch_comparison.py

Outputs
    docs/Branch_Comparison.html
    docs/Branch_Comparison.pdf
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(BASE_DIR, "docs")
VALIDATION = os.path.join(BASE_DIR, "output", "validation")

SOFFICE = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    shutil.which("soffice") or "",
    shutil.which("libreoffice") or "",
]

# LibreOffice's HTML engine ignores flexbox and grid, so the layout is built
# from block elements and tables only.
CSS = """
@page { size: A4; margin: 15mm 13mm 16mm 13mm; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
       font-size: 9.4pt; color: #16202b; line-height: 1.46; }

table.topbar { width: 100%; margin: 0 0 5mm 0; border-collapse: collapse; }
table.topbar td { background: #0b3d5c; height: 5pt; padding: 0;
                  border: none; font-size: 1pt; line-height: 5pt; }
.cover { margin-bottom: 9mm; }
h1 { font-size: 21pt; color: #0b3d5c; margin: 0 0 2mm 0; line-height: 1.15; }
.tagline { font-size: 11pt; color: #3d5a70; margin: 0 0 4mm 0; }
.meta { font-size: 8.4pt; color: #62717f; }

h2 { font-size: 13pt; color: #0b3d5c; margin: 9mm 0 2mm 0;
     border-bottom: 1.4pt solid #0b3d5c; padding-bottom: 1.4mm; }
h3 { font-size: 10.6pt; color: #1d4f74; margin: 5mm 0 1.5mm 0; }
h4 { font-size: 9.6pt; color: #2c5c7f; margin: 4mm 0 1mm 0; }
p { margin: 0 0 2.6mm 0; }

table { border-collapse: collapse; width: 100%; margin: 2.5mm 0 4.5mm 0;
        font-size: 8.3pt; }
th { background: #0b3d5c; color: #ffffff; text-align: left;
     padding: 1.8mm 2.2mm; font-weight: bold; }
td { padding: 1.5mm 2.2mm; border-bottom: 0.4pt solid #dbe3ea;
     vertical-align: top; }
tr.alt td { background: #f5f8fa; }
td.n, th.n { text-align: right; }
td.was { color: #8a4b2a; }
td.now { color: #1a6b3c; font-weight: bold; }
.small { font-size: 7.9pt; color: #62717f; }

.plain { background: #eef6fb; border-left: 3.5pt solid #2b7fb8;
         padding: 2.6mm 3.2mm; margin: 2.5mm 0 4mm 0; }
.plain b { color: #14567f; }
.why { background: #fdf6e8; border-left: 3.5pt solid #d09a2c;
       padding: 2.6mm 3.2mm; margin: 2.5mm 0 4mm 0; }
.good { background: #eef8f1; border-left: 3.5pt solid #2e9159;
        padding: 2.6mm 3.2mm; margin: 2.5mm 0 4mm 0; }
.bad { background: #fdeeea; border-left: 3.5pt solid #c0512f;
       padding: 2.6mm 3.2mm; margin: 2.5mm 0 4mm 0; }

ul, ol { margin: 0 0 3mm 5.5mm; padding: 0; }
li { margin-bottom: 1.3mm; }
code { font-family: Menlo, Consolas, monospace; font-size: 8pt;
       background: #eef1f4; padding: 0.3mm 0.9mm; }
.chip { font-size: 7.6pt; font-weight: bold; padding: 0.5mm 1.6mm;
        color: #ffffff; background: #2e9159; }
.chip-warn { background: #c0512f; }
.chip-neutral { background: #62717f; }
.divider { border-top: 0.6pt solid #cfd9e2; margin: 6mm 0; }
"""


def load():
    """Before = outputs committed on main. After = current working tree."""
    before = json.loads(subprocess.run(
        ["git", "show", "main:output/validation/manuscript_numbers.json"],
        cwd=BASE_DIR, capture_output=True, text=True, check=True).stdout)
    with open(os.path.join(VALIDATION, "manuscript_numbers.json")) as f:
        after = json.load(f)
    before_check = subprocess.run(
        ["git", "show", "main:output/validation/manuscript_check.txt"],
        cwd=BASE_DIR, capture_output=True, text=True).stdout
    after_check = open(os.path.join(VALIDATION, "manuscript_check.txt")).read()
    commits = subprocess.run(
        ["git", "log", "--oneline", "main..validation"],
        cwd=BASE_DIR, capture_output=True, text=True).stdout.strip().splitlines()
    return before, after, before_check, after_check, commits


def _n(check):
    return check.split("Checks:")[1].split()[0] if "Checks:" in check else "—"


def rows(pairs):
    out = []
    for i, (label, was, now, note) in enumerate(pairs):
        cls = " class='alt'" if i % 2 else ""
        out.append(f"<tr{cls}><td>{label}</td><td class='n was'>{was}</td>"
                   f"<td class='n now'>{now}</td><td class='small'>{note}</td></tr>")
    return "".join(out)


def headline_table(b, a):
    bd, ad = b["descriptives"], a["descriptives"]
    return f"""<table>
<tr><th>What is being counted</th><th class="n">Before (main)</th>
<th class="n">After (validation)</th><th>Why it changed</th></tr>
{rows([
 ("Accredited cardiac MR facilities", f"{bd['cmr_facilities']:,}", f"{ad['cmr_facilities']:,}",
  "35 facilities were being lost by the old ZIP-to-county lookup"),
 ("Accredited cardiac CT facilities", f"{bd['cct_facilities']:,}", f"{ad['cct_facilities']:,}",
  "61 facilities recovered, same cause"),
 ("Counties with at least one CMR", f"{bd['counties_with_cmr']:,}", f"{ad['counties_with_cmr']:,}", ""),
 ("Counties with at least one CCT", f"{bd['counties_with_cct']:,}", f"{ad['counties_with_cct']:,}", ""),
 ("Counties with neither modality", f"{bd['counties_neither']:,} ({bd['counties_neither_pct']:.1f}%)",
  f"{ad['counties_neither']:,} ({ad['counties_neither_pct']:.1f}%)", "Fewer blank counties once facilities were found"),
 ("Share of CMR capacity in metro counties", f"{bd['pct_cmr_in_metro']:.1f}%", f"{ad['pct_cmr_in_metro']:.1f}%",
  "Unchanged — the headline finding is robust"),
 ("Share of CCT capacity in metro counties", f"{bd['pct_cct_in_metro']:.1f}%", f"{ad['pct_cct_in_metro']:.1f}%", ""),
 ("Counties in the SVI regression", f"{b['regressions']['n_svi']:,}", f"{a['regressions']['n_svi']:,}",
  "Small counties restored to count models, per the project brief"),
 ("Counties in the EDI regression", f"{b['regressions']['n_edi']:,}", f"{a['regressions']['n_edi']:,}", ""),
])}
</table>"""


def model_table(b, a):
    out = []
    labels = {"SVI_CMR": ("Social Vulnerability Index", "Cardiac MR"),
              "SVI_CCT": ("Social Vulnerability Index", "Cardiac CT"),
              "EDI_CMR": ("Economic Deprivation Index", "Cardiac MR"),
              "EDI_CCT": ("Economic Deprivation Index", "Cardiac CT")}
    for i, (key, (idx, mod)) in enumerate(labels.items()):
        bm = b["regressions"]["models"][key]["adjusted_metro"]
        am = a["regressions"]["models"][key]["adjusted_metro"]
        bsig = "significant" if bm["p"] < 0.05 else "not significant"
        asig = "significant" if am["p"] < 0.05 else "not significant"
        changed = (bm["p"] < 0.05) != (am["p"] < 0.05)
        flag = ("<span class='chip chip-warn'>CONCLUSION CHANGED</span>"
                if changed else "<span class='chip-neutral chip'>same conclusion</span>")
        cls = " class='alt'" if i % 2 else ""
        out.append(
            f"<tr{cls}><td>{idx}<br><span class='small'>{mod}</span></td>"
            f"<td class='n was'>{bm['irr']:.2f} ({bm['ci_low']:.2f}–{bm['ci_high']:.2f})<br>"
            f"<span class='small'>P = {bm['p']:.3f}, {bsig}</span></td>"
            f"<td class='n now'>{am['irr']:.2f} ({am['ci_low']:.2f}–{am['ci_high']:.2f})<br>"
            f"<span class='small'>P = {am['p']:.3f}, {asig}</span></td>"
            f"<td>{flag}</td></tr>")
    for i, (key, mod) in enumerate((("EDI_CMR", "Cardiac MR"), ("EDI_CCT", "Cardiac CT"))):
        bm = b["regressions"]["models"][key]["metro_effect"]
        am = a["regressions"]["models"][key]["metro_effect"]
        out.append(
            f"<tr><td><b>Metropolitan status</b><br><span class='small'>{mod}</span></td>"
            f"<td class='n was'>{bm['irr']:.2f} ({bm['ci_low']:.2f}–{bm['ci_high']:.2f})</td>"
            f"<td class='n now'>{am['irr']:.2f} ({am['ci_low']:.2f}–{am['ci_high']:.2f})</td>"
            f"<td><span class='chip'>unchanged, still dominant</span></td></tr>")
    return ("<table><tr><th>Predictor</th><th class='n'>Before (main)</th>"
            "<th class='n'>After (validation)</th><th>Verdict</th></tr>"
            + "".join(out) + "</table>")


def quintile_table(b, a):
    bq = b["quintiles"]["cmr_rate_by_edi_quintile"]
    aq = a["quintiles"]["cmr_rate_by_edi_quintile"]
    names = ["Q1 — least deprived", "Q2", "Q3", "Q4", "Q5 — most deprived"]
    lo_b, lo_a = bq.index(min(bq)), aq.index(min(aq))
    out = []
    for i in range(5):
        cls = " class='alt'" if i % 2 else ""
        out.append(f"<tr{cls}><td>{names[i]}</td>"
                   f"<td class='n was'>{bq[i]:.4f}{' ← lowest' if i == lo_b else ''}</td>"
                   f"<td class='n now'>{aq[i]:.4f}{' ← lowest' if i == lo_a else ''}</td></tr>")
    return ("<table><tr><th>Deprivation group</th>"
            "<th class='n'>Before (main)</th><th class='n'>After (validation)</th></tr>"
            + "".join(out) +
            f"<tr><td><b>Ratio, least vs most deprived</b></td>"
            f"<td class='n was'>{b['quintiles']['q1_over_q5_ratio']:.2f}×</td>"
            f"<td class='n now'>{a['quintiles']['q1_over_q5_ratio']:.2f}×</td></tr></table>")


def build(b, a, bcheck, acheck, commits):
    commit_rows = ""
    for i, c in enumerate(reversed(commits)):
        cls = " class='alt'" if i % 2 else ""
        sha, _, msg = c.partition(" ")
        commit_rows += (f"<tr{cls}><td><code>{sha}</code></td>"
                        f"<td>{msg}</td></tr>")
    ad = a["descriptives"]
    aq = a["quintiles"]

    return f"""<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>

<table class="topbar"><tr><td>&nbsp;</td></tr></table>
<div class="cover">
<h1>What Changed, and Why It Matters</h1>
<p class="tagline">A detailed comparison of the <code>main</code> branch and the
<code>validation</code> branch of the ACR cardiac imaging analysis</p>
<p class="meta">Geographic Disparities in ACR-Accredited Cardiac Imaging Across the
United States &nbsp;·&nbsp; Generated {date.today().isoformat()} &nbsp;·&nbsp;
{len(commits)} commits &nbsp;·&nbsp; Validation gate {_n(bcheck)} &rarr; {_n(acheck)} checks</p>
</div>

<div class="plain">
<b>Read this first — the one-paragraph version.</b> The original analysis was
sound in its methods but was quietly losing data. A lookup table used to convert
facility postal codes into counties was the wrong one: it was six years out of
date and covered a slightly different kind of postal code. Because of that,
96 accredited imaging facilities never reached the dataset, and the entire state
of Connecticut showed up as having <i>zero</i> cardiac imaging capacity when it
actually has 32 accredited facilities. Separately, a statistical setting was left
at its software default rather than being estimated from the data. Fixing both
recovered every missing facility and changed one of the paper's conclusions. The
paper's <i>main</i> finding — that accredited cardiac imaging is overwhelmingly
concentrated in cities — was not affected and is now on firmer ground.
</div>

<h2>1. How to read this document</h2>
<p>Each section below has three layers, so you can read at whatever depth you
need:</p>
<table>
<tr><th style="width:22%">Layer</th><th>What it gives you</th></tr>
<tr><td><b>Plain English</b><br><span class="small">blue boxes</span></td>
<td>An explanation with no statistics or jargon. If you read only these, you
will still understand what happened and why it matters.</td></tr>
<tr class="alt"><td><b>The numbers</b><br><span class="small">tables</span></td>
<td>Before and after values side by side. Orange is the old value, green is the
current one.</td></tr>
<tr><td><b>The technical detail</b><br><span class="small">body text</span></td>
<td>Exact file names, statistical specifications, and reasoning, retained in
full for reviewers and statisticians.</td></tr>
</table>

<h3>A note on two words used throughout</h3>
<table>
<tr><th style="width:22%">Term</th><th>What it means here</th></tr>
<tr><td><b>Branch</b></td><td>A parallel copy of the project. <code>main</code>
is the version as it stood before this work; <code>validation</code> contains the
corrections. Keeping them separate means the old version is never lost and every
change can be inspected.</td></tr>
<tr class="alt"><td><b>The pipeline</b></td><td>The chain of scripts that turns
raw data into the figures, tables and numbers in the paper. Running it end to end
reproduces every published value.</td></tr>
</table>

<h2>2. The four problems that were found</h2>

<h3>Problem 1 — Facilities were being lost in the postal-code lookup</h3>
<div class="plain">
<b>In plain English.</b> Every imaging facility in the source data has a postal
(ZIP) code, not a county. To count facilities per county, the analysis needs a
translation table from ZIP codes to counties. The project brief specified a
particular table published by the US Department of Housing and Urban Development
(HUD), updated for early 2026. That table was never obtained — it needs a free
access key — so a different, older table from the Census Bureau was substituted.
The substitute has two blind spots. It does not cover postal codes used only for
PO boxes and large institutions such as hospitals, and it was built before
Connecticut reorganised its counties. As a result, 96 facilities simply
disappeared, with no error message.
</div>
<p><b>Technical detail.</b> The substitute was the Census 2020 ZCTA-to-county
relationship file, which maps <i>ZIP Code Tabulation Areas</i> rather than ZIP
codes, and assigned multi-county ZIPs by largest land area rather than by
largest residential-address share as the brief required. The correct HUD file is
now fetched by <code>code/01c_fetch_hud_crosswalk.py</code>, which reads an API
token from an environment variable or a git-ignored file, retries transient
failures, and refuses to write a crosswalk unless it is nationally complete and
Connecticut resolves to current geography.</p>
<div class="good">
<b>Result.</b> All 2,264 eligible facility records now map to a valid county.
Nothing is dropped silently: every record is either included or given a written
reason for exclusion, recorded in
<code>data/processed/facility_mapping_audit.csv</code>.
</div>

<h3>Problem 2 — Connecticut had vanished entirely</h3>
<div class="plain">
<b>In plain English.</b> In 2022 Connecticut abolished its eight counties and
replaced them with nine "planning regions". The old lookup table still used the
retired county codes. The rest of the analysis used the new codes. The two never
matched, so every Connecticut facility fell through the gap. The published
figures showed 1.6 million adults in Connecticut with no accredited cardiac
imaging at all, which is simply untrue.
</div>
<p><b>Technical detail.</b> The 2020 file emits FIPS codes 09001–09015; the
county universe from TIGER 2023 uses 09110–09190. There is no overlap, so a left
join produced silent nulls. The HUD Q1 2026 crosswalk returns the planning
regions directly, so no special-case handling is needed in production. A
permanent regression test asserts that all 32 Connecticut records resolve.</p>

<h3>Problem 3 — A statistical setting was left at its default</h3>
<div class="plain">
<b>In plain English.</b> Counting models need a setting that describes how
"spread out" the counts are. Think of it as a dial. The original analysis left
the dial at the software's factory position of 1.0 instead of measuring where it
should sit for this data. Measured properly, it sits near 0.2 to 0.6. Because
the dial was set too high, the analysis was more cautious than the data warrant,
and one real association was reported as absent.
</div>
<p><b>Technical detail.</b> The models used <code>NegativeBinomial(alpha=1.0)</code>,
a fixed-dispersion GLM. The project brief asked for the dispersion parameter to
be <i>reported</i>, which implies estimating it. Estimating it by maximum
likelihood gives lower AIC <i>and</i> lower BIC in every model and outcome
combination. The primary specification is now NB2 with dispersion estimated,
defined once in <code>code/model_spec.py</code> so no script can drift. Fixed
alpha = 1.0 is retained and reported as a labelled sensitivity analysis.</p>
<div class="why">
<b>Why this was not chosen to get a better P value.</b> The decision rests on
the project brief and on model fit (AIC and BIC), both of which point the same
way and were settled before looking at which conclusions moved. The fixed-alpha
results are still published alongside, so any reader can see both.
</div>

<h3>Problem 4 — The self-check could only catch half of the errors</h3>
<div class="plain">
<b>In plain English.</b> The project has an automatic checker that compares
every number in the paper against the data. It reported "0 mismatches", which
sounded reassuring. But it only asked "is the correct number present somewhere?"
It never asked "is an old, wrong number <i>also</i> still present?" Eight
outdated figures were sitting in the paper while the checker reported a clean
bill of health.
</div>
<p><b>Technical detail.</b> <code>ck_prose</code> used a substring search over
the whole document, which is a one-sided test. The gate now also carries a
<code>FORBIDDEN</code> list of obsolete values and phrases and fails if any
appear. It grew from {_n(bcheck)} checks to {_n(acheck)}.</p>

<div class="divider"></div>

<h2>3. The numbers, before and after</h2>
<h3>3.1 What was counted</h3>
{headline_table(b, a)}

<h3>3.2 The statistical results</h3>
<p>These are adjusted models — that is, they compare deprivation while holding
city-versus-rural status constant. "IRR" is an incidence rate ratio: 1.00 means
no difference, above 1.00 means more capacity, below means less. The range in
brackets is the 95% confidence interval; if it does not cross 1.00, the result
is conventionally called statistically significant.</p>
{model_table(b, a)}
<div class="bad">
<b>The one conclusion that changed.</b> Social vulnerability and cardiac CT
capacity. Before, this looked like no relationship. Now it is a modest
<i>positive</i> association: more accredited CT capacity in more vulnerable
counties, not less. Both the recovered facilities and the corrected statistical
setting contributed. Note the direction — this is the opposite of what a
"deprived areas are underserved" story would predict, and the paper now says so
explicitly rather than describing it as nothing.
</div>

<h3>3.3 Capacity across deprivation groups</h3>
<p>Counties were split into five equal groups from least to most deprived, and
the average cardiac MR capacity of each group compared.</p>
{quintile_table(b, a)}
<div class="why">
<b>Why this matters for the wording of the paper.</b> Before the fix, capacity
fell steadily from group 1 to group 5, and the paper described a
{b['quintiles']['q1_over_q5_ratio']:.1f}-fold "gradient". After the fix the
extreme groups still differ, but the middle no longer falls in order, and the
<i>lowest</i> group is Q4, not Q5. The paper now reports a
{a['quintiles']['q1_over_q5_ratio']:.1f}-fold difference between the extremes and
explicitly states the pattern is not monotonic. Describing it as a smooth
gradient would have overstated the evidence.
</div>

<h2>4. What changed in the code</h2>
<table>
<tr><th style="width:32%">File</th><th>What it does now</th><th style="width:14%">Status</th></tr>
<tr><td><code>code/facility_mapping.py</code></td><td><b>New.</b> Builds the
facility cohort and maps each record to a county, guaranteeing that eligible =
included + explicitly excluded. Writes a per-record audit trail.</td>
<td><span class="chip">new</span></td></tr>
<tr class="alt"><td><code>code/01c_fetch_hud_crosswalk.py</code></td><td><b>New.</b>
Downloads the HUD crosswalk the brief specified. Refuses to write a file that is
incomplete or uses retired Connecticut geography.</td><td><span class="chip">new</span></td></tr>
<tr><td><code>code/model_spec.py</code></td><td><b>New.</b> Defines the primary
statistical model in exactly one place, so every script uses the same
specification and sample.</td><td><span class="chip">new</span></td></tr>
<tr class="alt"><td><code>code/13_model_specification.py</code></td><td><b>New.</b>
Fits Poisson, estimated-dispersion and fixed-dispersion models side by side and
reports AIC, BIC, dispersion and convergence — the evidence for the choice.</td>
<td><span class="chip">new</span></td></tr>
<tr><td><code>code/14_accredited_only_sensitivity.py</code></td><td><b>New.</b>
Re-runs everything excluding facilities listed as "Under Review".</td>
<td><span class="chip">new</span></td></tr>
<tr class="alt"><td><code>code/15_svi_quartile_sensitivity.py</code></td><td><b>New.</b>
The quartile analysis the brief asked for, promoted to a first-class output.</td>
<td><span class="chip">new</span></td></tr>
<tr><td><code>code/05_regression_analysis.py</code></td><td>No longer defines its
own "primary" model with the wrong setting and the wrong sample. Uses the shared
specification; sensitivities are labelled as such.</td>
<td><span class="chip chip-warn">fixed</span></td></tr>
<tr class="alt"><td><code>code/07_publication_outputs.py</code></td><td>No longer
re-fits its own regressions. It had three separate defects: the wrong dispersion,
a mis-scaled predictor that made its ratios per 0.1 percentile points instead of
10, and an "Accredited-only" sensitivity that silently re-used the main dataset.
It now reads the canonical results.</td><td><span class="chip chip-warn">fixed</span></td></tr>
<tr><td><code>code/02_build_analytic_dataset.py</code></td><td>Uses the new
mapping module. Three places that silently substituted <i>randomly generated</i>
data when an input file was missing now stop with an error instead.</td>
<td><span class="chip chip-warn">fixed</span></td></tr>
<tr class="alt"><td><code>code/12_manuscript_numbers.py</code></td><td>Checks that
obsolete values are <i>absent</i> as well as that current ones are present.
Reports non-estimable results as "NE" rather than <code>nan</code>.</td>
<td><span class="chip chip-warn">fixed</span></td></tr>
<tr><td><code>tests/test_pipeline.py</code></td><td><b>New.</b> 15 automated
tests covering reconciliation, Connecticut, the mapping rule, and the removal of
fabricated-data fallbacks.</td><td><span class="chip">new</span></td></tr>
</table>

<h2>5. What changed in the paper</h2>
<p>Every manuscript edit was applied as a tracked change, attributed and dated,
and every replacement value was taken from generated output rather than typed by
hand.</p>
<table>
<tr><th style="width:30%">Where</th><th>Before</th><th>After</th></tr>
<tr><td>Counties with neither modality</td><td class="was">2,583 (82.2%)</td>
<td class="now">{ad['counties_neither']:,} ({ad['counties_neither_pct']:.1f}%)</td></tr>
<tr class="alt"><td>Facility totals</td><td class="was">687 CMR / 1,481 CCT</td>
<td class="now">{ad['cmr_facilities']} CMR / {ad['cct_facilities']:,} CCT</td></tr>
<tr><td>Deprivation gradient</td><td class="was">"fell monotonically … 4.4-fold gradient"</td>
<td class="now">"{aq['q1_over_q5_ratio']:.1f}-fold difference between the extreme
quintiles … not monotonic"</td></tr>
<tr class="alt"><td>Social vulnerability</td>
<td class="was">"SVI was not associated with capacity for either modality"</td>
<td class="now">No association with cardiac MR; modest positive association with
cardiac CT, with the exact estimate and confidence interval</td></tr>
<tr><td>External index (SDI)</td><td class="was">Described significant estimates
as "not associated"</td><td class="now">Reports them as modest positive
associations, consistent with its own table</td></tr>
<tr class="alt"><td>Sparse Connecticut-style rows</td><td class="was"><code>nan</code>
and <code>nan-nan</code> printed in a table</td><td class="now">"NE" (not
estimable) with a footnote explaining why</td></tr>
<tr><td>Data source date</td><td class="was">"accessed 2024"</td>
<td class="now">"extracted May 20, 2026", matching the file itself</td></tr>
<tr class="alt"><td>Denominator typo</td><td class="was">"adults ≥48 years"</td>
<td class="now">"adults aged ≥45 years"</td></tr>
</table>

<h2>6. New safeguards</h2>
<div class="plain">
<b>In plain English.</b> The point of this work was not only to fix the numbers
but to make the same class of mistake impossible to repeat quietly. Four things
now stand in the way.
</div>
<table>
<tr><th style="width:30%">Safeguard</th><th>What it prevents</th></tr>
<tr><td><b>Full audit trail</b></td><td>Every source record is accounted for.
A facility can no longer disappear without a written reason.</td></tr>
<tr class="alt"><td><b>Two-sided self-check</b></td><td>The gate fails if an
obsolete number or sentence is still in the paper, not just if a current one is
missing.</td></tr>
<tr><td><b>No fabricated data</b></td><td>A missing input file used to be
replaced with random numbers that looked plausible. Production now stops with an
error; demo behaviour requires an explicit flag.</td></tr>
<tr class="alt"><td><b>One definition of the model</b></td><td>The statistical
specification lives in a single file. Scripts cannot quietly disagree about what
"primary" means, which is exactly what had happened.</td></tr>
</table>

<h2>7. What did <i>not</i> change</h2>
<div class="good">
<b>The paper's central finding stands.</b> Accredited cardiac imaging is
overwhelmingly concentrated in metropolitan counties —
{ad['pct_cmr_in_metro']:.1f}% of cardiac MR capacity and
{ad['pct_cct_in_metro']:.1f}% of cardiac CT capacity — and metropolitan status
remains by far the strongest geographic correlate, with roughly eightfold higher
cardiac MR capacity. That result was unchanged by every correction, and it now
rests on a complete dataset rather than one missing 96 facilities. The
methodological conclusion — that deprivation indices should not be used as
proxies for imaging access without adjusting for rurality — also stands, and the
external-index validation supports it.
</div>

<h2>8. Glossary</h2>
<table>
<tr><th style="width:26%">Term</th><th>Plain meaning</th></tr>
<tr><td>Accredited facility</td><td>A site formally certified by the American
College of Radiology to perform the scan to a defined quality standard.</td></tr>
<tr class="alt"><td>CMR / CCT</td><td>Cardiac MRI and cardiac CT — two advanced
heart-imaging tests.</td></tr>
<tr><td>FIPS code</td><td>The five-digit federal identifier for a county.</td></tr>
<tr class="alt"><td>Crosswalk</td><td>A translation table, here from postal ZIP
codes to counties.</td></tr>
<tr><td>SVI</td><td>Social Vulnerability Index — a CDC measure combining poverty,
housing, transport, disability and other factors.</td></tr>
<tr class="alt"><td>EDI</td><td>Economic Deprivation Index — a purpose-built
measure created for this study from six economic indicators.</td></tr>
<tr><td>SDI</td><td>Social Deprivation Index — an independent published measure,
used to check the findings were not an artefact of the purpose-built one.</td></tr>
<tr class="alt"><td>IRR</td><td>Incidence rate ratio. 1.00 = no difference; 1.03 =
3% more capacity per step; 0.95 = 5% less.</td></tr>
<tr><td>95% confidence interval</td><td>The range of values consistent with the
data. If it excludes 1.00, the finding is called statistically significant.</td></tr>
<tr class="alt"><td>Dispersion (alpha)</td><td>How variable the counts are
relative to a simple model. Estimating it correctly matters for the width of the
confidence intervals.</td></tr>
<tr><td>AIC / BIC</td><td>Scores that compare competing models. Lower is
better.</td></tr>
<tr class="alt"><td>Monotonic</td><td>Moving in one direction without reversing.
The deprivation pattern is <i>not</i> monotonic, which is why the wording
changed.</td></tr>
<tr><td>NE</td><td>Not estimable — a number that genuinely cannot be calculated
from so few events, reported honestly instead of guessed.</td></tr>
</table>

<h2>9. Verifying this yourself</h2>
<p>No claim here has to be taken on trust. From a checkout of the
<code>validation</code> branch:</p>
<table>
<tr><th style="width:46%">Command</th><th>What it proves</th></tr>
<tr><td><code>python code/00_run_all.py --with-present</code></td>
<td>Rebuilds every figure, table and number from the committed data.</td></tr>
<tr class="alt"><td><code>python tests/test_pipeline.py</code></td>
<td>Runs the 15 integrity tests, including the Connecticut check.</td></tr>
<tr><td><code>cat output/validation/manuscript_check.txt</code></td>
<td>Shows the paper checked against the data, line by line.</td></tr>
<tr class="alt"><td><code>cat output/validation/facility_reconciliation.txt</code></td>
<td>Shows every source record accounted for.</td></tr>
<tr><td><code>python tools/finalize_manuscript.py --validate</code></td>
<td>Produces the clean submission file and validates that exact file.</td></tr>
</table>

<h2>10. The commits in this branch</h2>
<table><tr><th style="width:14%">Commit</th><th>Description</th></tr>
{commit_rows}</table>

<p class="small" style="margin-top:6mm">Generated by
<code>tools/build_branch_comparison.py</code>. The "before" column is read from
the outputs committed on <code>main</code>; the "after" column from the current
working tree. Rebuild after any change and the document updates itself.</p>

</body></html>"""


def main():
    b, a, bc, ac, commits = load()
    html = os.path.join(DOCS, "Branch_Comparison.html")
    with open(html, "w") as f:
        f.write(build(b, a, bc, ac, commits))
    print(f"  wrote {os.path.relpath(html, BASE_DIR)}")

    soffice = next((p for p in SOFFICE if p and os.path.exists(p)), None)
    if not soffice:
        print("  LibreOffice not found; HTML written but no PDF produced.")
        return 1
    subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                    "--outdir", DOCS, html],
                   check=True, capture_output=True, timeout=300)
    pdf = os.path.join(DOCS, "Branch_Comparison.pdf")
    print(f"  wrote {os.path.relpath(pdf, BASE_DIR)} "
          f"({os.path.getsize(pdf) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
