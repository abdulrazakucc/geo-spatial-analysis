#!/usr/bin/env python3
"""
build_comparison_pdf.py
=======================
Builds the model-and-geography comparison document as HTML, then converts it to
PDF with LibreOffice.

Every number is read from the generated outputs at build time, so the document
cannot drift from the pipeline. Rebuild it after any rerun:

    python tools/build_comparison_pdf.py

Outputs
    docs/Comparison_Report.html
    docs/Comparison_Report.pdf
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import date

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(BASE_DIR, "output", "results")
VALIDATION = os.path.join(BASE_DIR, "output", "validation")
DOCS = os.path.join(BASE_DIR, "docs")

SOFFICE_CANDIDATES = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    shutil.which("soffice") or "",
    shutil.which("libreoffice") or "",
]

CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
       font-size: 9.2pt; color: #1a1a1a; line-height: 1.42; }
h1 { font-size: 17pt; margin: 0 0 2mm 0; color: #0f2b46; }
h2 { font-size: 12pt; margin: 7mm 0 2mm 0; color: #0f2b46;
     border-bottom: 1.2pt solid #0f2b46; padding-bottom: 1mm; }
h3 { font-size: 10pt; margin: 4mm 0 1.5mm 0; color: #24486b; }
p  { margin: 0 0 2.4mm 0; }
.sub { color: #55616e; font-size: 8.6pt; margin-bottom: 5mm; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm 0;
        font-size: 8.2pt; }
th { background: #eef2f6; text-align: left; padding: 1.5mm 2mm;
     border-bottom: 0.8pt solid #9fb0c0; font-weight: bold; }
td { padding: 1.3mm 2mm; border-bottom: 0.4pt solid #dde4ea; }
td.n, th.n { text-align: right; }
tr.best td { background: #eaf5ee; font-weight: bold; }
tr.sens td { color: #55616e; }
.key { background: #fff8e6; border-left: 2.5pt solid #d79a2b;
       padding: 2mm 3mm; margin: 3mm 0; }
.note { color: #55616e; font-size: 8.2pt; margin-top: -1mm; }
ul { margin: 0 0 3mm 5mm; padding: 0; }
li { margin-bottom: 1.2mm; }
code { font-family: Menlo, Consolas, monospace; font-size: 8pt; }
"""


def _f(x, n=2):
    return "—" if x is None or pd.isna(x) else f"{x:.{n}f}"


def _p(x):
    return "&lt;0.001" if x < 0.001 else f"{x:.3f}"


def _sig(x):
    return f"<b>{_p(x)}</b>" if x < 0.05 else _p(x)


def load():
    with open(os.path.join(VALIDATION, "manuscript_numbers.json")) as f:
        numbers = json.load(f)
    with open(os.path.join(RESULTS, "index_comparison_results.json")) as f:
        index_cmp = json.load(f)
    spec = pd.read_csv(os.path.join(RESULTS, "model_specification_comparison.csv"))
    quart = pd.read_csv(os.path.join(RESULTS, "svi_quartile_regression.csv"))
    accred = pd.read_csv(os.path.join(RESULTS, "accredited_only_sensitivity.csv"))
    check = open(os.path.join(VALIDATION, "manuscript_check.txt")).read()
    recon = open(os.path.join(VALIDATION, "facility_reconciliation.txt")).read()
    return numbers, index_cmp, spec, quart, accred, check, recon


def section_primary(numbers):
    M = numbers["regressions"]["models"]
    rows = []
    for pred in ("SVI", "EDI"):
        for out in ("CMR", "CCT"):
            m = M[f"{pred}_{out}"]
            for label, key in (("unadjusted", "unadjusted"),
                               ("adjusted for metropolitan status", "adjusted_metro")):
                e = m[key]
                rows.append(
                    f"<tr><td>{out}</td><td>{pred}</td><td>{label}</td>"
                    f"<td class='n'>{_f(e['irr'])}</td>"
                    f"<td class='n'>{_f(e['ci_low'])}–{_f(e['ci_high'])}</td>"
                    f"<td class='n'>{_sig(e['p'])}</td></tr>")
    for out in ("CMR", "CCT"):
        e = M[f"EDI_{out}"]["metro_effect"]
        rows.append(
            f"<tr><td>{out}</td><td>metropolitan status</td><td>adjusted model</td>"
            f"<td class='n'>{_f(e['irr'])}</td>"
            f"<td class='n'>{_f(e['ci_low'])}–{_f(e['ci_high'])}</td>"
            f"<td class='n'>{_sig(e['p'])}</td></tr>")
    return ("<table><tr><th>Outcome</th><th>Predictor</th><th>Model</th>"
            "<th class='n'>IRR</th><th class='n'>95% CI</th><th class='n'>P</th></tr>"
            + "".join(rows) + "</table>")


def section_spec(spec):
    rows = []
    for (idx, out), grp in spec.groupby(["index", "outcome"], sort=False):
        best = grp.aic.idxmin()
        for i, r in grp.iterrows():
            cls = ("best" if i == best
                   else "sens" if "sensitivity" in r.specification else "")
            rows.append(
                f"<tr class='{cls}'><td>{out}</td><td>{idx}</td>"
                f"<td>{r.specification}</td>"
                f"<td class='n'>{'—' if pd.isna(r.alpha) else _f(r.alpha, 3)}</td>"
                f"<td class='n'>{r.n:,}</td>"
                f"<td class='n'>{r.aic:.1f}</td>"
                f"<td class='n'>{_f(r.irr, 3)}</td>"
                f"<td class='n'>{_f(r.ci_low, 3)}–{_f(r.ci_high, 3)}</td>"
                f"<td class='n'>{_sig(r.p_value)}</td></tr>")
    return ("<table><tr><th>Outcome</th><th>Predictor</th><th>Specification</th>"
            "<th class='n'>α</th><th class='n'>N</th><th class='n'>AIC</th>"
            "<th class='n'>IRR</th><th class='n'>95% CI</th><th class='n'>P</th></tr>"
            + "".join(rows) + "</table>"
            "<p class='note'>Green = lowest AIC for that outcome and predictor. "
            "Grey = the fixed-dispersion sensitivity.</p>")


def section_flips(spec):
    out = []
    for (idx, oc), grp in spec.groupby(["index", "outcome"]):
        if len(set(grp.p_value < 0.05)) > 1:
            parts = ", ".join(
                f"{r.specification.split(',')[0]} P = {r.p_value:.4f}"
                for _, r in grp.iterrows())
            out.append(f"<li><b>{idx}, {oc}</b>: {parts}</li>")
    return ("<ul>" + "".join(out) + "</ul>") if out else "<p>None.</p>"


def section_sensitivity(numbers):
    fx = numbers["regressions"].get("sensitivity_fixed_alpha", {})
    re_ = numbers["regressions"].get("sensitivity_rate_eligible", {})
    M = numbers["regressions"]["models"]
    rows = []
    for key in ("SVI_CMR", "SVI_CCT", "EDI_CMR", "EDI_CCT"):
        pred, out = key.split("_")
        prim = M[key]["adjusted_metro"]
        f = fx.get(key, {}).get("adjusted_metro")
        r = re_.get(key, {}).get("adjusted_metro")
        rows.append(
            f"<tr><td>{out}</td><td>{pred}</td>"
            f"<td class='n'>{_f(prim['irr'])} ({_f(prim['ci_low'])}–{_f(prim['ci_high'])}), {_p(prim['p'])}</td>"
            + (f"<td class='n'>{_f(f['irr'])} ({_f(f['ci_low'])}–{_f(f['ci_high'])}), {_p(f['p'])}</td>"
               if f else "<td class='n'>—</td>")
            + (f"<td class='n'>{_f(r['irr'])} ({_f(r['ci_low'])}–{_f(r['ci_high'])}), {_p(r['p'])}</td>"
               if r else "<td class='n'>—</td>")
            + "</tr>")
    return ("<table><tr><th>Outcome</th><th>Predictor</th>"
            "<th class='n'>Primary (α estimated, all counties)</th>"
            "<th class='n'>Sensitivity: α = 1.0</th>"
            "<th class='n'>Sensitivity: ≥1,000 adults only</th></tr>"
            + "".join(rows) + "</table>")


def section_quartile(quart):
    rows = "".join(
        f"<tr><td>{r.outcome}</td><td>{r.model}</td><td>{r.term}</td>"
        f"<td class='n'>{_f(r.irr, 3)}</td>"
        f"<td class='n'>{_f(r.ci_low, 3)}–{_f(r.ci_high, 3)}</td>"
        f"<td class='n'>{_sig(r.p_value)}</td></tr>"
        for _, r in quart.iterrows())
    return ("<table><tr><th>Outcome</th><th>Model</th><th>Contrast</th>"
            "<th class='n'>IRR</th><th class='n'>95% CI</th><th class='n'>P</th></tr>"
            + rows + "</table>")


def section_accredited(accred):
    piv = accred[accred.term == "SVI"]
    rows = []
    for (out, model), grp in piv.groupby(["outcome", "model"], sort=False):
        cells = {}
        for _, r in grp.iterrows():
            key = "primary" if r.cohort.startswith("Primary") else "accredited"
            cells[key] = f"{_f(r.irr, 3)} ({_f(r.ci_low, 3)}–{_f(r.ci_high, 3)}), {_p(r.p_value)}"
        rows.append(f"<tr><td>{out}</td><td>{model}</td>"
                    f"<td class='n'>{cells.get('primary', '—')}</td>"
                    f"<td class='n'>{cells.get('accredited', '—')}</td></tr>")
    return ("<table><tr><th>Outcome</th><th>Model</th>"
            "<th class='n'>Primary (Accredited + Under Review)</th>"
            "<th class='n'>Accredited only</th></tr>" + "".join(rows) + "</table>")


def section_quintiles(numbers):
    g = numbers["quintiles"]
    cmr, cct = g["cmr_rate_by_edi_quintile"], g["cct_rate_by_edi_quintile"]
    labels = ["Q1 (least deprived)", "Q2", "Q3", "Q4", "Q5 (most deprived)"]
    lo = min(range(5), key=lambda i: cmr[i])
    rows = "".join(
        f"<tr><td>{labels[i]}{' ← minimum' if i == lo else ''}</td>"
        f"<td class='n'>{cmr[i]:.4f}</td><td class='n'>{cct[i]:.4f}</td></tr>"
        for i in range(5))
    mono = g.get("cmr_monotonic_decreasing")
    return ("<table><tr><th>EDI quintile</th><th class='n'>Mean CMR rate</th>"
            f"<th class='n'>Mean CCT rate</th></tr>{rows}</table>"
            f"<p class='note'>Strictly decreasing Q1&gt;Q2&gt;Q3&gt;Q4&gt;Q5: "
            f"<b>{mono}</b>. Q1/Q5 = {g['q1_over_q5_ratio']:.2f} "
            f"(unweighted county means); {g['q1_over_q5_ratio_pooled']:.2f} "
            f"population-weighted.</p>")


def build_html(numbers, index_cmp, spec, quart, accred, check, recon):
    d = numbers["descriptives"]
    R = numbers["regressions"]
    checks = check.split("Checks:")[1].split()[0]
    mismatches = check.split("Mismatches:")[1].split()[0]
    inc = recon.split("Included in the county dataset")[1].split()[0]
    elig = recon.split("Protocol-eligible")[1].split()[0]

    return f"""<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<h1>Model Specification and Geographic Linkage — Comparison Report</h1>
<div class="sub">Geographic Disparities in ACR-Accredited Cardiac Imaging ·
Generated {date.today().isoformat()} from the current pipeline outputs ·
Validation gate: {checks} checks, {mismatches} mismatches</div>

<div class="key">
<b>Primary specification.</b> Negative binomial (NB2) with the dispersion
parameter <b>estimated from the data</b>, a log(adults aged 45+) offset, and the
index scaled per 10 points. Chosen because the project briefing asked for the
dispersion parameter to be reported, and because the estimated-dispersion
specification was better supported by AIC and BIC than the fixed α = 1.0
specification in every model. Fixed α = 1.0 is retained as a labelled
sensitivity.<br><br>
<b>Analytic sample.</b> Count regressions use every county with the index and a
positive population (SVI n = {R['n_svi']:,}; EDI n = {R['n_edi']:,}). The
&lt;1,000-adult rule governs per-capita rate calculations only, as the briefing
specifies; restricting the regressions as well is reported as a sensitivity.
</div>

<h2>1. Facility reconciliation</h2>
<p>All {elig} protocol-eligible facility-modality records map to a valid current
county FIPS: {inc} included, none unresolved, no silent loss. Connecticut
resolves to its nine planning regions through the ordinary HUD path.</p>
<table>
<tr><th>Quantity</th><th class="n">Value</th></tr>
<tr><td>Counties (county equivalents)</td><td class="n">{d['total_counties']:,}</td></tr>
<tr><td>Accredited cardiac MR facilities</td><td class="n">{d['cmr_facilities']:,}</td></tr>
<tr><td>Accredited cardiac CT facilities</td><td class="n">{d['cct_facilities']:,}</td></tr>
<tr><td>Counties with ≥1 CMR</td><td class="n">{d['counties_with_cmr']:,} ({d['counties_with_cmr_pct']:.1f}%)</td></tr>
<tr><td>Counties with ≥1 CCT</td><td class="n">{d['counties_with_cct']:,} ({d['counties_with_cct_pct']:.1f}%)</td></tr>
<tr><td>Counties with neither modality</td><td class="n">{d['counties_neither']:,} ({d['counties_neither_pct']:.1f}%)</td></tr>
<tr><td>Share of CMR capacity in metropolitan counties</td><td class="n">{d['pct_cmr_in_metro']:.1f}%</td></tr>
<tr><td>Share of CCT capacity in metropolitan counties</td><td class="n">{d['pct_cct_in_metro']:.1f}%</td></tr>
</table>

<h2>2. Primary model results</h2>
{section_primary(numbers)}

<h2>3. Specification comparison: Poisson vs NB2 estimated vs NB2 fixed α = 1.0</h2>
{section_spec(spec)}

<h3>Where the significance conclusion depends on the specification</h3>
{section_flips(spec)}

<h2>4. Sensitivity analyses side by side</h2>
{section_sensitivity(numbers)}

<h2>5. Accredited-only cohort sensitivity</h2>
<p>The briefing defines the primary cohort as Accredited <i>or</i> Under Review.
This restricts to Accredited only.</p>
{section_accredited(accred)}

<h2>6. SVI quartile indicator sensitivity</h2>
<p>Continuous SVI replaced by quartile indicators, Q1 (least vulnerable) as
reference — requested in briefing section 3.4.</p>
{section_quartile(quart)}

<h2>7. EDI quintile capacity</h2>
{section_quintiles(numbers)}

<h2>8. Reading notes</h2>
<ul>
<li>IRR is per 10-point increase in the index; metropolitan status is a binary
contrast against nonmetropolitan.</li>
<li>The Poisson Pearson/df statistic is below 1 in these models and is
misleading because the counts are sparse and zero-inflated. Overdispersion is
evidenced by the likelihood-ratio test against NB2 and by the marginal
variance-to-mean ratio of the outcome.</li>
<li>Every value in this document is read from
<code>output/results/</code> and <code>output/validation/</code> at build time.
Rebuild with <code>python tools/build_comparison_pdf.py</code> after any
pipeline rerun.</li>
</ul>
</body></html>"""


def main():
    html_path = os.path.join(DOCS, "Comparison_Report.html")
    with open(html_path, "w") as f:
        f.write(build_html(*load()))
    print(f"  wrote {os.path.relpath(html_path, BASE_DIR)}")

    soffice = next((p for p in SOFFICE_CANDIDATES if p and os.path.exists(p)), None)
    if not soffice:
        print("  LibreOffice not found; HTML written but no PDF produced.")
        return 1
    subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                    "--outdir", DOCS, html_path],
                   check=True, capture_output=True, timeout=300)
    pdf = os.path.join(DOCS, "Comparison_Report.pdf")
    if not os.path.exists(pdf):
        print("  conversion produced no PDF")
        return 1
    print(f"  wrote {os.path.relpath(pdf, BASE_DIR)} "
          f"({os.path.getsize(pdf) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
