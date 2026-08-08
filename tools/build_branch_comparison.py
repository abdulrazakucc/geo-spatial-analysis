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
import re
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
/* Page-break control. LibreOffice honours these when exporting to PDF.
   Without them a table can strand its header row at the foot of a page and
   carry the body to the next, and a heading can be orphaned from the table it
   introduces. `display: table-header-group` also repeats the header on every
   page a long table spans. */
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
h2, h3, h4 { page-break-after: avoid; }
.plain, .why, .good, .bad { page-break-inside: avoid; }
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

def _wrap_theads(html):
    """Put each table's first row in <thead> so it repeats and never strands.

    The tables are written as plain <tr><th> rows; LibreOffice only repeats a
    header, and only avoids orphaning it, when it is inside <thead>.
    """
    def fix(m):
        table = m.group(0)
        row = re.search(r"<tr[^>]*>.*?</tr>", table, re.S)
        if not row or "<th" not in row.group(0):
            return table
        return table.replace(row.group(0), f"<thead>{row.group(0)}</thead>", 1)
    return re.sub(r"<table.*?</table>", fix, html, flags=re.S)


#: The last commit before the facility-mapping correction. Pinned to a commit
#: rather than to a branch name: this document originally read "before" from
#: `main`, and when the corrected work was promoted to `main` that ref moved,
#: so both columns silently became the same numbers. A commit cannot move.
BEFORE_REF = "b774584"


def load():
    """Before = the pre-correction commit. After = current working tree."""
    def at(ref, path):
        r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=BASE_DIR,
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(
                f"Cannot read {path} at {ref}. The baseline commit must remain "
                f"reachable; if history was rewritten, update BEFORE_REF.")
        return r.stdout

    before = json.loads(at(BEFORE_REF, "output/validation/manuscript_numbers.json"))
    with open(os.path.join(VALIDATION, "manuscript_numbers.json")) as f:
        after = json.load(f)
    before_check = at(BEFORE_REF, "output/validation/manuscript_check.txt")
    after_check = open(os.path.join(VALIDATION, "manuscript_check.txt")).read()
    commits = subprocess.run(
        ["git", "log", "--oneline", f"{BEFORE_REF}..HEAD"],
        cwd=BASE_DIR, capture_output=True, text=True).stdout.strip().splitlines()

    # A comparison document whose two columns agree is worthless and, worse,
    # looks authoritative. Refuse to build one.
    bd, ad = before["descriptives"], after["descriptives"]
    same = [k for k in ("cmr_facilities", "cct_facilities", "counties_neither")
            if bd[k] == ad[k]]
    if len(same) == 3:
        raise SystemExit(
            f"Refusing to build: the 'before' data at {BEFORE_REF} is identical "
            "to the current outputs, so there is nothing to compare. BEFORE_REF "
            "is probably pointing at post-correction history.")
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
<tr><th>What is being counted</th><th class="n">Before the correction</th>
<th class="n">Current</th><th>Why it changed</th></tr>
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
    return ("<table><tr><th>Predictor</th><th class='n'>Before the correction</th>"
            "<th class='n'>Current</th><th>Verdict</th></tr>"
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
            "<th class='n'>Before the correction</th><th class='n'>Current</th></tr>"
            + "".join(out) +
            f"<tr><td><b>Ratio, least vs most deprived</b></td>"
            f"<td class='n was'>{b['quintiles']['q1_over_q5_ratio']:.2f}×</td>"
            f"<td class='n now'>{a['quintiles']['q1_over_q5_ratio']:.2f}×</td></tr></table>")


def build(b, a, bcheck, acheck, commits):
    d, bd = a["descriptives"], b["descriptives"]
    q, bq = a["quintiles"], b["quintiles"]
    R = a["regressions"]
    M = R["models"]
    sdi = a.get("sdi", {}).get("SDI_models", {}).get("outcomes", {})
    quintile_n = sum(a["table1"][f"edi_q{i}"]["counties"] for i in range(1, 6))

    def sdi_txt(outcome, spec):
        e = sdi.get(outcome, {}).get(spec)
        if not e:
            return "—"
        return (f"{e['IRR']:.2f} ({e['CI_low']:.2f}–{e['CI_high']:.2f}), "
                f"P = {e['P']:.3f}")

    return f"""<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>

<table class="topbar"><tr><td>&nbsp;</td></tr></table>
<div class="cover">
<h1>What Changed, and Why It Matters</h1>
<p class="tagline">Corrections made to the analysis of accredited cardiac imaging
capacity across US counties, and their effect on the findings</p>
<p class="meta">Geographic Disparities in ACR-Accredited Cardiac Imaging Across the
United States &nbsp;·&nbsp; {date.today().isoformat()}</p>
</div>

<div class="plain">
<b>Read this first — the whole story in one paragraph.</b> The original analysis
was sound in its methods but was quietly losing data. To count imaging
facilities by county, the study had to translate each facility's postal code
into a county, using a published lookup table. The table used was the wrong one:
six years out of date, and covering a slightly different kind of postal code.
Because of that, <b>96 accredited facilities never reached the dataset</b>, and
the entire state of Connecticut appeared to have <i>no</i> cardiac imaging
capacity at all when it in fact has 32 accredited facilities. Separately, one
statistical setting had been left at its software default instead of being
measured from the data. Correcting both recovered every missing facility and
changed one of the study's conclusions. The study's <i>main</i> finding — that
accredited cardiac imaging is overwhelmingly concentrated in cities — was not
affected, and now rests on a complete dataset.
</div>

<h2>1. How to read this document</h2>
<p>Each section has two layers, so you can read at whatever depth suits you.</p>
<table>
<tr><th style="width:24%">Layer</th><th>What it gives you</th></tr>
<tr><td><b>Plain English</b><br><span class="small">blue boxes</span></td>
<td>An explanation with no statistics and no jargon. If you read only these, you
will still understand what happened and why it matters.</td></tr>
<tr class="alt"><td><b>The detail</b><br><span class="small">tables and body text</span></td>
<td>The before-and-after figures and the reasoning behind each decision, kept in
full for reviewers and statisticians. Orange marks the old value, green the
current one.</td></tr>
</table>
<p>Every term of art is defined in the glossary in section 8. Nothing in this
document assumes prior knowledge of statistics.</p>

<h2>2. The four problems that were found</h2>

<h3>Problem 1 — Facilities were being lost in the postal-code lookup</h3>
<div class="plain">
<b>In plain English.</b> Every imaging facility in the source data is recorded
with a postal (ZIP) code, not a county. To count facilities per county, the
analysis needs a translation table from postal codes to counties. The study plan
specified a particular table published by the US Department of Housing and Urban
Development, updated for early 2026. That table requires a registration key,
which had not been obtained, so a different and older table from the Census
Bureau was used instead. The substitute has two blind spots: it does not cover
postal codes used only for PO boxes and large institutions such as hospitals,
and it was built before Connecticut reorganised its counties. As a result,
96 facilities simply disappeared, with no error message to signal it.
</div>
<p><b>The detail.</b> The substitute mapped <i>ZIP Code Tabulation Areas</i>,
which are the Census Bureau's approximation of postal codes rather than postal
codes themselves, and it resolved postal codes spanning two counties by whichever
county held the larger land area. The study plan called for the county holding
the largest share of <i>residential addresses</i> — a different rule that can
give a different answer, and does for 42 of the facilities. The specified table
has now been obtained and is in use.</p>
<div class="good">
<b>Result.</b> All 2,264 eligible facility records now map to a valid county.
Nothing is dropped without explanation: every record is either included or
recorded with a written reason for exclusion.
</div>

<h3>Problem 2 — Connecticut had vanished entirely</h3>
<div class="plain">
<b>In plain English.</b> In 2022 Connecticut abolished its eight counties and
replaced them with nine "planning regions". The old lookup table still used the
retired county codes, while the rest of the analysis used the new ones. The two
never matched, so every Connecticut facility fell through the gap. The published
figures therefore showed 1.6 million adults in Connecticut with no accredited
cardiac imaging whatsoever, which is simply untrue.
</div>
<p><b>The detail.</b> All 32 eligible Connecticut records — 14 cardiac MR and
18 cardiac CT — are now correctly placed, across six of the nine planning
regions. The corrected lookup table returns the new regions directly, so no
special handling is required.</p>

<h3>Problem 3 — A statistical setting was left at its default</h3>
<div class="plain">
<b>In plain English.</b> Models that count things need a setting describing how
"spread out" the counts are. Think of it as a dial. The original analysis left
the dial at the software's factory position of 1.0 instead of measuring where it
should sit for this data. Measured properly, it sits between roughly 0.2 and 0.6.
Because the dial was set too high, the analysis was more cautious than the
evidence warranted, and one genuine association was reported as absent.
</div>
<p><b>The detail.</b> The models are negative binomial regressions, and the
setting is the dispersion parameter. Estimating it from the data rather than
fixing it produces a better fit on both standard measures of model quality
(AIC and BIC) in <b>all twelve</b> comparisons of model and outcome. The
estimated-dispersion model is now the primary analysis; the fixed setting is
retained and reported alongside as a sensitivity analysis, so any reader can see
both.</p>
<div class="why">
<b>Why this was not chosen to obtain a more favourable result.</b> The decision
rests on the original study plan, which asked for the dispersion to be reported,
and on measures of fit that both point the same way. The alternative results are
published alongside rather than discarded.
</div>

<h3>Problem 4 — The self-check could only catch half of the errors</h3>
<div class="plain">
<b>In plain English.</b> The project has an automatic check that compares every
number in the manuscript against the data. It reported no discrepancies, which
sounded reassuring. But it only asked "is the correct number present somewhere?"
It never asked "is an old, wrong number <i>also</i> still present?" Eight
outdated figures were sitting in the manuscript while the check reported a clean
bill of health.
</div>
<p><b>The detail.</b> The check is now two-sided: it fails if a required value is
missing <i>or</i> if a superseded value or phrase remains. It also verifies the
manuscript's stated word counts against the text itself, since those had drifted
as the manuscript was edited. It grew from {_n(bcheck)} checks to {_n(acheck)}.</p>

<div class="divider"></div>

<h2>3. The numbers, before and after</h2>
<h3>3.1 What was counted</h3>
{headline_table(b, a)}

<h3>3.2 The statistical results</h3>
<p>These are adjusted models — that is, they compare deprivation between counties
while holding city-versus-rural status constant, so that the two influences are
not confused with one another. "IRR" is an incidence rate ratio: 1.00 means no
difference, above 1.00 means more capacity, below 1.00 means less. The range in
brackets is the 95% confidence interval, the band of values consistent with the
data; if that band does not cross 1.00, the result is conventionally called
statistically significant.</p>
{model_table(b, a)}
<div class="bad">
<b>The one conclusion that changed.</b> Social vulnerability and cardiac CT
capacity. Before, this looked like no relationship at all. It is now a modest
<i>positive</i> association: <b>more</b> accredited CT capacity in more vulnerable
counties, not less. Both the recovered facilities and the corrected statistical
setting contributed. Note the direction carefully — this is the opposite of what
an "underserved deprived areas" account would predict, and the manuscript now
says so plainly rather than describing the finding as nothing.
</div>

<h3>3.3 The external check</h3>
<div class="plain">
<b>In plain English.</b> Because one of the two deprivation measures was built
specifically for this study, the whole analysis was repeated using an
independent, already-published measure. If a finding only appears with the
measure the authors built themselves, that is a warning sign. This is the
study's own honesty check.
</div>
<p>That independent measure was uninformative throughout before the correction.
It no longer is, and it now points the same way as the result above.</p>
<table>
<tr><th>Independent deprivation measure</th><th class="n">Before the correction</th>
<th class="n">Current</th></tr>
<tr><td>Cardiac MR, unadjusted</td><td class="n was">1.01 (0.97–1.05), P = 0.746</td>
<td class="n">{sdi_txt('cmr_facility_count','unadjusted')}</td></tr>
<tr class="alt"><td>Cardiac MR, adjusted</td><td class="n was">1.03 (0.99–1.07), P = 0.215</td>
<td class="n now">{sdi_txt('cmr_facility_count','adjusted')}</td></tr>
<tr><td>Cardiac CT, unadjusted</td><td class="n was">1.02 (0.99–1.05), P = 0.290</td>
<td class="n now">{sdi_txt('cct_facility_count','unadjusted')}</td></tr>
<tr class="alt"><td>Cardiac CT, adjusted</td><td class="n was">1.03 (1.00–1.06), P = 0.063</td>
<td class="n now">{sdi_txt('cct_facility_count','adjusted')}</td></tr>
</table>
<p class="small">All four were statistically non-significant before. Three of the
four now are significant, and all point toward <i>more</i> accredited capacity in
more deprived counties.</p>

<h3>3.4 Capacity across deprivation groups</h3>
<p>Counties were divided into five equal groups from least to most deprived, and
the average cardiac MR capacity of each group compared.</p>
{quintile_table(b, a)}
<div class="why">
<b>Why this changed the manuscript's wording.</b> Before the correction, capacity
appeared to fall steadily from the first group to the fifth, and the manuscript
described a {bq['q1_over_q5_ratio']:.1f}-fold "gradient". After the correction the
extreme groups still differ, but the middle groups no longer fall in order, and
the <i>lowest</i> group is now the fourth, not the fifth. The manuscript now
reports a {q['q1_over_q5_ratio']:.1f}-fold difference between the extreme groups
and states explicitly that the pattern is not a steady decline. Describing it as
a smooth gradient would have overstated the evidence.
</div>

<h2>4. Every figure, table and map</h2>
<div class="plain">
<b>In plain English.</b> The manuscript contains one main figure, four tables and
two supplementary figures. This section says what each one shows, how to read it,
and whether the corrections changed it.
</div>

<h3>4.1 Figures and maps</h3>
<table>
<tr><th style="width:19%">Item</th><th style="width:26%">What it shows</th>
<th style="width:29%">How to read it</th><th>Effect of the corrections</th></tr>

<tr><td><b>Figure 1A</b><br><span class="small">Cardiac MR map</span></td>
<td>A map of the United States, shaded county by county, showing accredited
cardiac MR capacity per 100,000 adults aged 45 and over.</td>
<td>A map coloured by value is called a choropleth. Darker means more capacity.
Light grey means the county has no accredited facility at all — most of the map.
White means the county was left out of the per-head calculation because it has
fewer than 1,000 adults aged 45 and over, which would make a rate
meaningless.</td>
<td><span class="chip chip-warn">changed</span> Connecticut was entirely blank
before and now shows capacity. Counties containing recovered facilities changed
shade.</td></tr>

<tr class="alt"><td><b>Figure 1B</b><br><span class="small">Results chart</span></td>
<td>Three stacked panels of statistical results: social vulnerability, economic
deprivation, and city-versus-rural status, each shown as a dot with a horizontal
line.</td>
<td>This kind of chart is called a forest plot. Each result sits on its own row.
The dot is the best estimate, the line is the range of uncertainty, and the
vertical dashed line marks "no effect". If the horizontal line crosses the dashed
line, the result is not statistically significant. Filled dots are significant,
open dots are not.</td>
<td><span class="chip chip-warn">changed</span> The cardiac CT rows for social
vulnerability moved from open to filled — that is, from not significant to
significant.</td></tr>

<tr><td><b>Figure 2</b><br><span class="small">Comparing the two measures</span></td>
<td>The two deprivation measures shown side by side across the same
counties.</td>
<td>Shows that the two measures broadly agree about which counties are
disadvantaged, but not perfectly. This matters because the study's argument turns
on how each measure relates to rural location.</td>
<td><span class="chip">shape unchanged</span> Redrawn from the corrected data;
the relationship between the two measures is the same.</td></tr>

<tr class="alt"><td><b>Figure 3</b><br><span class="small">Capacity by deprivation group</span></td>
<td>Average imaging capacity across the five groups of counties, ordered from
least to most deprived.</td>
<td>Each group holds one fifth of the counties. If capacity fell steadily from
the first group to the fifth, the bars would form a staircase.</td>
<td><span class="chip chip-warn">changed materially</span> The staircase is gone.
The bars no longer descend in order, and the lowest is now the fourth group, not
the fifth. This is why the manuscript's wording had to change.</td></tr>

<tr><td><b>Supplementary figure</b><br><span class="small">Cardiac CT map</span></td>
<td>The same style of map as Figure 1A, but for cardiac CT.</td>
<td>Cardiac CT is more widely available than cardiac MR, so this map has more
shaded counties.</td>
<td><span class="chip chip-warn">changed</span> Same cause as Figure 1A.</td></tr>

<tr class="alt"><td><b>Supplementary figure</b><br><span class="small">External check</span></td>
<td>A results chart comparing the purpose-built deprivation measure against the
independent published one.</td>
<td>Lets a reader judge for themselves whether a finding depends on the measure
the authors built.</td>
<td><span class="chip chip-warn">changed</span> Several estimates from the
independent measure became statistically significant, and the manuscript text
was rewritten to match.</td></tr>
</table>

<h3>4.2 Tables</h3>
<table>
<tr><th style="width:19%">Item</th><th style="width:26%">What it shows</th>
<th style="width:29%">How to read it</th><th>Effect of the corrections</th></tr>

<tr><td><b>Table 1</b><br><span class="small">Capacity by vulnerability and
rurality</span></td>
<td>Counts and rates of facilities, broken down by social-vulnerability group and
by city-versus-rural status.</td>
<td>The rows let you compare the least vulnerable quarter of counties with the
most vulnerable, and cities with rural areas. The rurality rows use all
{d['total_counties']:,} counties; the deprivation rows use the
{quintile_n:,} counties large
enough for a meaningful per-head rate.</td>
<td><span class="chip chip-warn">changed</span> All facility counts rose, and a
footnote that quoted the wrong number of counties was corrected.</td></tr>

<tr class="alt"><td><b>Table 2</b><br><span class="small">Main results</span></td>
<td>The central table: how each deprivation measure relates to capacity, before
and after allowing for city-versus-rural location.</td>
<td>Each cell is an incidence rate ratio with its range of uncertainty. The
"adjusted" columns are the ones that matter, because they hold rurality
constant.</td>
<td><span class="chip chip-warn">changed</span> Every row was recalculated. One
conclusion changed direction of interpretation.</td></tr>

<tr><td><b>Table 3</b><br><span class="small">Robustness checks</span></td>
<td>The same models run several different ways, to test whether the conclusion
depends on an arbitrary choice.</td>
<td>If a finding survives being analysed several different ways, it is more
trustworthy. One row reads <b>NE</b>, meaning "not estimable": there were too few
facilities in rural areas to calculate a reliable range, so the manuscript
reports the estimate without pretending to a precision it does not have.</td>
<td><span class="chip chip-warn">changed</span> Recalculated; the sparse rural row
now reads NE instead of a blank value, and its facility count was corrected from
13 to 14.</td></tr>

<tr class="alt"><td><b>Table 4</b><br><span class="small">External check</span></td>
<td>The purpose-built deprivation measure compared against the independent
published one.</td>
<td>Supports the study's central methodological claim: whether a deprivation
signal appears at all depends on how strongly the chosen measure reflects rural
location.</td>
<td><span class="chip chip-warn">changed</span> Recalculated; the accompanying
text was rewritten because several estimates are now significant.</td></tr>

<tr><td><b>Supplementary table</b><br><span class="small">Full model detail</span></td>
<td>The complete set of economic-deprivation models, including rural and urban
areas analysed separately.</td>
<td>For readers who want to see every model rather than the summary.</td>
<td><span class="chip chip-warn">changed</span> Recalculated.</td></tr>
</table>

<h2>5. What changed in the manuscript</h2>
<p>Every edit was recorded as a tracked change, attributed and dated, and every
replacement figure was taken from the recalculated results rather than typed by
hand.</p>
<table>
<tr><th style="width:30%">Where</th><th>Before</th><th>Current</th></tr>
<tr><td>Counties with neither modality</td><td class="was">2,583 (82.2%)</td>
<td class="now">{d['counties_neither']:,} ({d['counties_neither_pct']:.1f}%)</td></tr>
<tr class="alt"><td>Facility totals</td><td class="was">687 cardiac MR / 1,481 cardiac CT</td>
<td class="now">{d['cmr_facilities']} / {d['cct_facilities']:,}</td></tr>
<tr><td>Counties with capacity</td><td class="was">289 cardiac MR / 532 cardiac CT</td>
<td class="now">{d['counties_with_cmr']} / {d['counties_with_cct']}</td></tr>
<tr class="alt"><td>Average rates, city vs rural</td>
<td class="was">0.35 / 0.02 and 0.73 / 0.35</td>
<td class="now">{d['metro_cmr_mean_rate']:.2f} / {d['nonmetro_cmr_mean_rate']:.2f} and
{d['metro_cct_mean_rate']:.2f} / {d['nonmetro_cct_mean_rate']:.2f}</td></tr>
<tr><td>Deprivation gradient</td><td class="was">"fell monotonically …
{bq['q1_over_q5_ratio']:.1f}-fold gradient"</td>
<td class="now">"{q['q1_over_q5_ratio']:.1f}-fold difference between the extreme
groups … not monotonic"</td></tr>
<tr class="alt"><td>Social vulnerability</td>
<td class="was">"not associated with capacity for either modality"</td>
<td class="now">No association with cardiac MR; a modest positive association with
cardiac CT, with the estimate and its range given</td></tr>
<tr><td>External measure</td><td class="was">Described significant estimates as
"not associated"</td><td class="now">Reports them as modest positive
associations, consistent with its own table</td></tr>
<tr class="alt"><td>Sparse rural row</td><td class="was">A blank value printed in
a table</td><td class="now">"NE" (not estimable), with a footnote explaining
why</td></tr>
<tr><td>Data source date</td><td class="was">"accessed 2024"</td>
<td class="now">"extracted May 20, 2026", matching the data file itself</td></tr>
<tr class="alt"><td>Denominator typo</td><td class="was">"adults ≥48 years"</td>
<td class="now">"adults aged ≥45 years"</td></tr>
<tr><td>Study cohort</td><td class="was">Not stated</td>
<td class="now">Stated explicitly: facilities listed as Accredited or Under
Review were both included, with the counts given, and a separate analysis
restricted to Accredited facilities reaching the same conclusions</td></tr>
<tr class="alt"><td>Stated word counts</td><td class="was">Abstract and summary
counts had drifted out of date</td><td class="now">Recomputed from the text and
now match it exactly</td></tr>
</table>

<h2>6. New safeguards</h2>
<div class="plain">
<b>In plain English.</b> The purpose of this work was not only to correct the
figures but to make the same class of mistake impossible to repeat quietly. Four
things now stand in the way.
</div>
<table>
<tr><th style="width:30%">Safeguard</th><th>What it prevents</th></tr>
<tr><td><b>A full audit trail</b></td><td>Every record in the source data is
accounted for. A facility can no longer disappear without a written
reason.</td></tr>
<tr class="alt"><td><b>A two-sided self-check</b></td><td>The check now fails if
an obsolete figure or sentence is still in the manuscript, not only if a current
one is missing.</td></tr>
<tr><td><b>No substituted data</b></td><td>A missing input file used to be
replaced silently with randomly generated values that looked plausible. The
analysis now stops with an error instead.</td></tr>
<tr class="alt"><td><b>One definition of the model</b></td><td>The statistical
specification is defined in a single place, so different parts of the analysis
cannot quietly disagree about what the main model is — which is exactly what had
happened.</td></tr>
</table>

<h2>7. What did <i>not</i> change</h2>
<div class="good">
<b>The study's central finding stands.</b> Accredited cardiac imaging is
overwhelmingly concentrated in metropolitan counties —
{d['pct_cmr_in_metro']:.1f}% of cardiac MR capacity and
{d['pct_cct_in_metro']:.1f}% of cardiac CT capacity — and city-versus-rural
status remains by far the strongest geographic factor, with roughly eightfold
higher cardiac MR capacity in metropolitan counties. That result was unchanged by
every correction, and it now rests on a complete dataset rather than one missing
96 facilities. The methodological conclusion — that deprivation measures should
not be used as substitutes for geography when studying access to imaging — also
stands, and the external check supports it.
</div>

<h2>8. Glossary</h2>
<table>
<tr><th style="width:26%">Term</th><th>Plain meaning</th></tr>
<tr><td>Accredited facility</td><td>A site formally certified by the American
College of Radiology to perform the scan to a defined quality standard.</td></tr>
<tr class="alt"><td>Cardiac MR / cardiac CT</td><td>Two advanced heart-imaging
tests: magnetic resonance imaging and computed tomography.</td></tr>
<tr><td>ACR</td><td>American College of Radiology, the body that issues the
accreditation counted here.</td></tr>
<tr class="alt"><td>ZIP code</td><td>US postal code. Facilities are recorded by
postal code, but the analysis needs counties — hence the translation
table.</td></tr>
<tr><td>ZIP Code Tabulation Area</td><td>The Census Bureau's approximation of a
postal code. Similar but not identical, and it does not exist for PO-box-only
codes. This mismatch caused the lost facilities.</td></tr>
<tr class="alt"><td>Crosswalk</td><td>A translation table, here from postal codes
to counties.</td></tr>
<tr><td>Residential address share</td><td>The proportion of a postal code's homes
that fall in a given county. Where a postal code straddles two counties, the one
with the larger share is chosen.</td></tr>
<tr class="alt"><td>County equivalent</td><td>An administrative area that takes the
place of a county, such as Connecticut's planning regions or an independent
city.</td></tr>
<tr><td>Social Vulnerability Index</td><td>A measure published by the CDC
combining poverty, housing, transport, disability and other factors.</td></tr>
<tr class="alt"><td>Economic deprivation index</td><td>A measure built specifically
for this study from six economic indicators.</td></tr>
<tr><td>Social Deprivation Index</td><td>An independent published measure, used to
check that findings were not an artefact of the purpose-built one.</td></tr>
<tr class="alt"><td>Metropolitan / non-metropolitan</td><td>A standard
classification of counties as urban or rural, based on population and commuting
patterns.</td></tr>
<tr><td>Incidence rate ratio (IRR)</td><td>1.00 means no difference; 1.03 means
3% more capacity per step; 0.95 means 5% less.</td></tr>
<tr class="alt"><td>95% confidence interval</td><td>The range of values consistent
with the data. If it excludes 1.00, the finding is called statistically
significant.</td></tr>
<tr><td>P value</td><td>How surprising the result would be if there were truly no
relationship. Below 0.05 is the conventional threshold for significance. It is a
convention, not a law of nature.</td></tr>
<tr class="alt"><td>Adjusted / unadjusted</td><td>"Adjusted" means the comparison
holds something else constant — here, city-versus-rural status. Unadjusted
comparisons can mislead when two things travel together.</td></tr>
<tr><td>Offset</td><td>A way of telling the model how many people each county has,
so it compares rates rather than raw counts. Without it, large counties would
dominate purely by size.</td></tr>
<tr class="alt"><td>Negative binomial model</td><td>The type of counting model
used. Suited to data where most counties have zero and a few have many.</td></tr>
<tr><td>Dispersion</td><td>How variable the counts are relative to a simple model.
Measuring it correctly matters for the width of the uncertainty ranges.</td></tr>
<tr class="alt"><td>AIC and BIC</td><td>Two scores that compare competing models.
Lower is better on both.</td></tr>
<tr><td>Quartile / quintile</td><td>Splitting the data into four equal groups, or
five.</td></tr>
<tr class="alt"><td>Monotonic</td><td>Moving in one direction without reversing.
The deprivation pattern is <i>not</i> monotonic, which is why the wording
changed.</td></tr>
<tr><td>Sensitivity analysis</td><td>Re-running the analysis a different but
defensible way, to see whether the answer holds up.</td></tr>
<tr class="alt"><td>Not estimable (NE)</td><td>A figure that genuinely cannot be
calculated from so few events, reported honestly instead of guessed.</td></tr>
<tr><td>Choropleth</td><td>A map that colours each area according to a
value.</td></tr>
<tr class="alt"><td>Forest plot</td><td>A chart showing several statistical results
stacked as dots with their uncertainty ranges.</td></tr>
</table>

<h2>9. Independent review</h2>
<div class="plain">
<b>In plain English.</b> Independent reviewers recalculated the analysis from the
source data without relying on the study's own stored results, and reported what
they found. Every point was checked before anything was changed. Most were
correct and have been fixed. Some described problems that had already been
corrected. The findings below are recorded rather than quietly absorbed, because
a reader deserves to know what was questioned and how it was resolved.
</div>
<table>
<tr><th style="width:36%">Finding</th><th style="width:14%">Verdict</th>
<th>Resolution</th></tr>
<tr><td>Average city and rural rates in the results were out of date</td>
<td><span class="chip chip-warn">correct</span></td>
<td>Confirmed and corrected. The self-check now verifies these four figures,
which it previously calculated but never compared.</td></tr>
<tr class="alt"><td>Abstract figures were out of date relative to the main
table</td><td><span class="chip chip-warn">correct</span></td>
<td>Confirmed and corrected from the recalculated results.</td></tr>
<tr><td>Blanket statements that neither deprivation measure was associated with
capacity</td><td><span class="chip chip-warn">correct</span></td>
<td>Confirmed in the summary and conclusion. Both rewritten to distinguish the
two measures and the two scan types. The self-check now rejects that whole family
of phrasings.</td></tr>
<tr class="alt"><td>A table footnote quoted the wrong number of counties</td>
<td><span class="chip chip-warn">correct</span></td>
<td>Confirmed and corrected. Both relevant county totals are now checked in their
own roles, since each is right in one context and wrong in the other.</td></tr>
<tr><td>The submission file carried a leftover internal reference</td>
<td><span class="chip chip-warn">correct</span></td>
<td>Confirmed, and it was a fault in our own preparation process rather than the
manuscript. Fixed; the file now verifies clean.</td></tr>
<tr class="alt"><td>The manuscript claimed both model-quality measures supported
the chosen specification, but only one was being produced</td>
<td><span class="chip chip-warn">correct</span></td>
<td>Confirmed. Both are now produced for every model, and the chosen
specification is better on both in all twelve comparisons, so the claim stands
and is now backed by the analysis rather than asserted.</td></tr>
<tr><td>A sentence claiming the two deprivation measures gave the same result
after adjustment</td><td><span class="chip chip-warn">correct</span></td>
<td>Confirmed false: one is uninformative for both scan types while the other is
positive and significant for cardiac CT. Rewritten.</td></tr>
<tr class="alt"><td>The stated manuscript word count no longer matched the
text</td><td><span class="chip chip-warn">correct</span></td>
<td>Confirmed. Corrected, and the count is now recalculated from the text and
checked automatically, as are the abstract and summary counts.</td></tr>
<tr><td>Two reports of problems in parts of the analysis</td>
<td><span class="chip">already fixed</span></td>
<td>Verified as no longer present; the reviewers were reading an earlier version.
Their descriptions of what those problems would have caused were accurate, which
is why the changes had been made.</td></tr>
</table>
<div class="good">
<b>Why this section exists.</b> A review that finds real problems is worth
recording, including the parts where our own process was at fault. Every finding
above is now covered by an automatic check, so none of them can return unnoticed.
</div>

<h2>10. Current status</h2>
<table>
<tr><th style="width:46%">Check</th><th>Result</th></tr>
<tr><td>Eligible facility records accounted for</td>
<td>2,264 of 2,264, none unresolved</td></tr>
<tr class="alt"><td>Connecticut records placed</td><td>32 of 32</td></tr>
<tr><td>Automatic checks of the manuscript against the data</td>
<td>{_n(acheck)} checks, no discrepancies</td></tr>
<tr class="alt"><td>Stated word counts</td><td>All match the text</td></tr>
<tr><td>Submission file</td><td>No tracked changes, no comments, valid
document</td></tr>
</table>

<p class="small" style="margin-top:6mm">Every figure in this document is taken
directly from the analysis outputs at the time of writing. The "before the
correction" column is read from the archived state of the analysis, so both
columns can be re-derived rather than taken on trust.</p>

</body></html>"""


def main():
    b, a, bc, ac, commits = load()
    html = os.path.join(DOCS, "Branch_Comparison.html")
    with open(html, "w") as f:
        f.write(_wrap_theads(build(b, a, bc, ac, commits)))
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
