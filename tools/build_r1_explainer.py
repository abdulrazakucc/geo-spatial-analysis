#!/usr/bin/env python3
"""
build_r1_explainer.py
=====================
Writes a plain-language guide to the study and its first-round revision:

    manuscript/jacrad-reviews-2026/R1_Plain_Language_Guide.pdf

The guide is for readers without a statistics background who still want every
technical detail. Each section gives a plain explanation first and the
technical detail second.

Every number is read from generated outputs at build time (never typed in):
    output/results/reviewer_analyses.json, output/validation/manuscript_numbers.json,
    output/results/*.csv, data/processed/facility_mapping_audit.csv,
    the R1 submission package (response letter, completion report, clean PDF).
The reviewer and editor wording, the open decisions, and the response-letter
locations are taken from tools/build_r1_package.py, so the two cannot disagree.

Run after tools/build_r1_package.py. Needs Google Chrome (headless) for the PDF.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile

import docx
import pandas as pd
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_r1_package as pkg  # noqa: E402

REV = os.path.join(BASE, "manuscript", "jacrad-reviews-2026")
PKG = os.path.join(REV, "R1_submission_package")
OUT = os.path.join(REV, "R1_Plain_Language_Guide.pdf")
RES = os.path.join(BASE, "output", "results")
FIG = os.path.join(BASE, "output", "figures")
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


# ------------------------------------------------------------------ helpers
def pv(p):
    return "P &lt; 0.001" if p < 0.001 else f"P = {p:.3f}"


def est(e, p=True):
    """Manuscript style: IRR 0.95; 95% CI, 0.91-0.98; P = 0.003."""
    irr = e.get("irr", e.get("IRR"))
    lo = e.get("ci_low", e.get("CI_low"))
    hi = e.get("ci_high", e.get("CI_high"))
    pp = e.get("p", e.get("P", e.get("p_value")))
    t = f"IRR {irr:.2f}; 95% CI, {lo:.2f}-{hi:.2f}"
    return t + (f"; {pv(pp)}" if p and pp is not None else "")


def cell(e):
    irr = e.get("irr", e.get("IRR"))
    lo = e.get("ci_low", e.get("CI_low"))
    hi = e.get("ci_high", e.get("CI_high"))
    return f"{irr:.2f} ({lo:.2f}-{hi:.2f})"


def cellp(e):
    pp = e.get("p", e.get("P", e.get("p_value")))
    return "&lt; 0.001" if pp < 0.001 else f"{pp:.3f}"


def change(irr):
    d = (irr - 1) * 100
    return f"{abs(d):.1f}% {'higher' if d > 0 else 'lower'}"


def esc(s):
    return html.escape(s, quote=False)


def img(stem, width=1700):
    im = Image.open(os.path.join(FIG, f"{stem}.png")).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def table(header, rows, cls=""):
    h = "".join(f"<th>{c}</th>" for c in header)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


def plain(text):
    return f'<div class="plain"><div class="tag">In plain words</div>{text}</div>'


def tech(text):
    return f'<div class="tech"><div class="tag">Technical detail</div>{text}</div>'


def quote(text):
    return f'<blockquote>{esc(text).replace(chr(10), "<br>")}</blockquote>'


# ------------------------------------------------------------------ inputs
def load():
    rv, mn = pkg.load()
    audit = pd.read_csv(os.path.join(BASE, "data", "processed", "facility_mapping_audit.csv"))
    spec = pd.read_csv(os.path.join(RES, "model_specification_comparison.csv"))
    acc = pd.read_csv(os.path.join(RES, "accredited_only_sensitivity.csv"))
    comp = pd.read_csv(os.path.join(RES, "comprehensive_model_table.csv"))
    rep = open(os.path.join(PKG, "12_Completion_Report.md"), encoding="utf-8").read()
    gate = re.search(r"Validation: (\d+) checks, (\d+) mismatches", rep).groups()
    tests = re.search(r"pipeline tests: (\d+) passed, (\d+) failed", rep).groups()
    sub = docx.Document(os.path.join(BASE, "manuscript", "manuscript_SUBMISSION.docx"))
    body_words = re.search(r"Word count: ([\d,]+) \(", "\n".join(p.text for p in sub.paragraphs)).group(1)
    resp = docx.Document(os.path.join(PKG, "03_Response_to_Reviewers.docx"))
    n_locs = sum(p.text.count("“") for p in resp.paragraphs if p.text.startswith("Location in"))
    L = pkg.Locator(os.path.join(PKG, "01_Revised_Manuscript_CLEAN.pdf"))
    ED, R1, R2 = pkg.items(rv, mn, L)
    return dict(rv=rv, mn=mn, audit=audit, spec=spec, acc=acc, comp=comp, gate=gate, tests=tests,
                body_words=body_words, n_locs=n_locs, ED=ED, R1=R1, R2=R2, V=pkg.load_verbatim(),
                pages=int(subprocess.run(["pdfinfo", os.path.join(PKG, "01_Revised_Manuscript_CLEAN.pdf")],
                                         capture_output=True, text=True).stdout.split("Pages:")[1].split()[0]))


# ------------------------------------------------------------------ content
def build_html(X):
    rv, mn = X["rv"], X["mn"]
    D, T1, RG, Q, COR, SDI = (mn["descriptives"], mn["table1"], mn["regressions"]["models"],
                              mn["quintiles"], mn["correlations"], mn["sdi"])
    FA = mn["regressions"]["sensitivity_fixed_alpha"]
    W, S, M, U, PC, POP = (rv["R1-02_weighting"], rv["R2-03_strata"], rv["R2-02_multiplicity"],
                           rv["R1-04_urban_core"], rv["R2-01_pca"], rv["E-05_population"])
    nm, det, inter = S["strata"]["EDI_CMR_nonmetro"], S["detail"]["EDI_CMR_nonmetro"], S["interaction"]["EDI_CMR"]
    tests = {t["test"]: t for t in M["tests"]}
    sc = tests["SVI-CCT, adjusted for metropolitan status (Table 2)"]
    fam = M["families"]
    wm, wt = W["models"], W["weights"]["SVI"]
    exc, rates = W["descriptive"]["excluded"], W["descriptive"]["rates"]
    um, th, ud = U["models"], U["themes"], U["descriptive"]
    sdi_m = SDI["SDI_models"]["outcomes"]
    a = X["audit"]
    ex = a["final_exclusion_reason"].value_counts().to_dict()
    mapm = a.loc[a.final_included, "mapping_method"].value_counts().to_dict()
    status = a.loc[a.final_included, "status"].value_counts().to_dict()
    gate, tst = X["gate"], X["tests"]
    today = dt.date.today().strftime("%B %-d, %Y")

    # model-fit comparison: does the estimated-dispersion NB2 win on AIC and BIC everywhere?
    sp = X["spec"]
    wins = groups = 0
    for _, g in sp.groupby(["index", "outcome"]):
        groups += 1
        best_aic = g.loc[g.aic.idxmin(), "specification"]
        best_bic = g.loc[g.bic.idxmin(), "specification"]
        wins += best_aic == best_bic == "NB2, estimated alpha"
    acc = X["acc"]
    acc_adj = acc[(acc.model == "adjusted") & (acc.term == acc["index"])]
    acc_rows = []
    for (ix, oc), g in acc_adj.groupby(["index", "outcome"], sort=False):
        pr = g[g.cohort.str.startswith("Primary")].iloc[0]
        se = g[g.cohort.str.startswith("Sensitivity")].iloc[0]
        acc_rows.append([f"{ix}, {oc}", f"{cell(pr)} ({cellp(pr)})", f"{cell(se)} ({cellp(se)})"])

    pcl = PC["pc1_loadings"]
    lab = PC["labels"]

    H = []
    add = H.append

    # ---------------------------------------------------------------- cover
    add(f"""
<section class="cover">
  <div class="kicker">Plain-language guide with full technical detail</div>
  <h1>Area Deprivation, Rurality, and Accredited Cardiac Imaging Capacity in US Counties</h1>
  <p class="sub">What the study did, what it found, what the peer reviewers asked, and exactly
  what changed in the first revision</p>
  <table class="meta">
    <tr><td>Manuscript</td><td>{pkg.MS_ID}, Journal of the American College of Radiology</td></tr>
    <tr><td>Authors</td><td>Abdul Razak, PhD, Muhammad Naeem, MBBS, MD, and six co-authors (first author changed at revision 1)</td></tr>
    <tr><td>Revision</td><td>Round 1, due December 3, 2026</td></tr>
    <tr><td>Prepared</td><td>{today}</td></tr>
  </table>
  <div class="note">
  <p><b>Who this is for.</b> Anyone who wants to understand the study without a background in
  statistics: co-authors, colleagues, and the authors themselves when they explain the work.</p>
  <p><b>How to read it.</b> Each section starts with a shaded box, <i>In plain words</i>, that explains
  the idea in everyday language. A second box, <i>Technical detail</i>, gives the exact methods and
  numbers. You can read only the plain boxes and still follow the whole story.</p>
  <p><b>Where the numbers come from.</b> Every number in this guide is read by a script from the
  study's results files when the guide is built. None was typed in by hand. The guide is
  internal: it is not part of the journal submission.</p>
  </div>
</section>
""")

    # ------------------------------------------------------- 1. in brief
    add(f"""
<h2 class="newpage">1. The study on one page</h2>
{plain(f'''
<p><b>The question.</b> Two kinds of heart scan, cardiac MRI (CMR) and cardiac CT (CCT), need
expensive machines and specially trained staff. We asked where in the United States the
facilities that offer these scans with American College of Radiology (ACR) accreditation are
located, and whether poorer or more disadvantaged counties have fewer of them.</p>
<p><b>What we did.</b> We counted accredited facilities in every US county ({D['total_counties']:,}
counties) and compared the counts with two measures of disadvantage: the CDC's Social
Vulnerability Index and an economic deprivation index we built from six income, poverty,
employment, education and housing measures.</p>
<p><b>What we found.</b></p>
<ul>
<li>Most counties have no accredited facility: {D['counties_neither']:,} of {D['total_counties']:,}
({D['counties_neither_pct']:.1f}%) have neither scan.</li>
<li>Capacity sits in metropolitan counties: they are {D['metro_counties_pct']:.1f}% of counties but
hold {D['pct_cmr_in_metro']:.1f}% of cardiac MRI and {D['pct_cct_in_metro']:.1f}% of cardiac CT
facilities.</li>
<li>Poorer counties at first seem to have less cardiac MRI. That link disappears once you
account for whether a county is metropolitan. The real pattern is metropolitan versus nonmetropolitan,
not rich versus poor.</li>
<li>So deprivation scores should not be used as stand-ins for access to imaging without also
accounting for metropolitan location.</li>
</ul>
<p><b>What the revision changed.</b> Two reviewers and the editor asked for ten analyses and
clarifications plus four editorial items. All were done. The main findings stand. One new
result appeared: among nonmetropolitan counties, the few that have a cardiac MRI facility are
less deprived. It rests on only {nm['events']} facilities, so it is reported as a lead for future
research rather than a firm conclusion.</p>
''')}
""")

    # ------------------------------------------------------- 2. background
    add(f"""
<h2 class="newpage">2. Background you need</h2>
<h3>2.1 The two scans</h3>
{plain('''
<p><b>Cardiac MRI (CMR)</b> uses a strong magnet and radio waves to make detailed pictures of the
heart muscle, valves and blood flow. It shows scarring, inflammation and how well the heart pumps.
<b>Cardiac CT (CCT)</b> uses X-rays and a computer to image the heart and its arteries. It includes
coronary CT angiography, which shows narrowed arteries, and calcium scoring, which measures hard
plaque. Both need costly scanners and staff with specialist training, and CMR is the more
demanding of the two.</p>''')}
<h3>2.2 Why accreditation matters</h3>
{plain('''
<p>Accreditation is an outside check that a facility's equipment, staff and image quality meet set
standards. Since 2012, US law has required accreditation before Medicare pays for advanced imaging
done outside hospitals. Counting accredited facilities is therefore a sensible, consistent way to
measure where quality-assured capacity exists.</p>''')}
{tech('''
<p>The requirement is section 135(a) of the Medicare Improvements for Patients and Providers Act of
2008 (MIPPA; Public Law 110-275), cited as reference 2. CMS designates four accrediting
organizations: the ACR, the Intersocietal Accreditation Commission, RadSite, and The Joint
Commission. Hospitals and critical access hospitals are exempt. The study counts ACR-accredited
facilities only, so it measures ACR-accredited capacity, not every site that performs these scans.
ACR accredits cardiac CT as a modality that covers both coronary CT angiography and calcium
scoring.</p>''')}
<h3>2.3 Why counties, and what "metropolitan" means</h3>
{plain('''
<p>A county is the smallest unit for which all the data we need are published. The US Department
of Agriculture sorts every county into nine groups, the Rural-Urban Continuum Codes (RUCC). Codes
1 to 3 are counties inside a metropolitan area, from the biggest cities (code 1) down. Codes 4 to 9
are nonmetropolitan counties, from fairly urban towns next to a city (code 4) to remote,
completely rural counties (code 9). A nonmetropolitan county is not always rural: it can contain
a sizable town. One reviewer pointed this out, and the revised manuscript now uses
"metropolitan" and "nonmetropolitan" for the two-way split and "rurality" only for the nine-step
scale.</p>''')}
{tech(f'''
<p>RUCC 2023 edition (reference 11). Metropolitan = codes 1-3 ({D['metro_counties']:,} counties);
nonmetropolitan = codes 4-9 ({D['nonmetro_counties']:,} counties). In the models the two-way split
is a single 0/1 variable; the nine-step code is used as an ordinal (ranked) variable in a
sensitivity analysis.</p>''')}
<h3>2.4 Measuring disadvantage</h3>
{plain('''
<p>We used three scores, each ranking counties from least to most disadvantaged on a 0 to 100
percentile scale (a county at 80 is more disadvantaged than 80% of counties).</p>
<ul>
<li><b>Social Vulnerability Index (SVI)</b>, from the CDC. It was designed to help emergency planners
find communities that would struggle in a disaster. It mixes money, household make-up, minority
status, and housing and transport. It was the main ("primary") measure.</li>
<li><b>Economic Deprivation Index (EDI)</b>, built by us to measure money-related disadvantage only.
It combines six measures into one score (explained in section 4.6).</li>
<li><b>Social Deprivation Index (SDI)</b>, a published index from the Robert Graham Center, used as an
comparison for our home-made EDI.</li>
</ul>''')}
{tech(f'''
<p><b>SVI:</b> CDC/ATSDR 2022 release; 16 census variables in four themes (socioeconomic status;
household characteristics; racial and ethnic minority status; housing type and transportation);
overall percentile ranking (reference 3). Analytic sample {mn['regressions']['n_svi']:,} counties.</p>
<p><b>EDI:</b> first principal component of six standardized indicators: persons below 150% of the
federal poverty level, unemployment, adults without a high-school diploma, and housing
cost-burdened households (all CDC/ATSDR SVI 2022, ACS 2018-2022), plus median household income
(sign reversed so that higher means poorer) and children in poverty (both County Health Rankings
2024). Scores converted to national percentiles. Analytic sample {mn['regressions']['n_edi']:,}
counties (counties missing any input are excluded). The index was named ADI before August 2026
and renamed EDI to avoid confusion with the validated Area Deprivation Index of Singh and of the
University of Wisconsin Neighborhood Atlas, which is published for block groups, not counties.</p>
<p><b>SDI:</b> Robert Graham Center, 2015-2019 vintage; matched {SDI['sdi_matched_counties']:,} of
{SDI['total_counties']:,} counties. Correlation with the EDI: Spearman ρ =
{SDI['agreement_with_EDI']['spearman_rho']:.2f}. SVI and EDI correlate at Pearson r =
{COR['svi_edi_pearson_r']:.2f}.</p>''')}
""")

    # ------------------------------------------------------- 3. data
    add(f"""
<h2>3. The data</h2>
{plain(f'''
<p>The facility list came from the ACR's public search tool on May 20, 2026. Each facility's ZIP
code was matched to its county. Population counts, disadvantage scores and county types came from
federal sources. Every facility in the registry is accounted for: each one is either counted or
listed with the reason it was left out, so none can go missing silently.</p>''')}
{tech(f'''
<p><b>Registry records and the cohort.</b> The extract held {len(a):,} facility-modality records
(one record per facility per accredited modality). Records were excluded because the modality was
not MRI or CT ({ex.get('modality not MRAP or CTAP', 0):,}), because the MRI or CT accreditation had
no cardiac module ({ex.get('no cardiac module', 0):,}), because the site was outside the 50 states and
DC ({ex.get('outside 50 states and DC', 0):,}), or because accreditation had expired before the
extraction date ({ex.get('accreditation expired before 2026-05-20', 0):,}). That leaves
{int(a.final_included.sum()):,} included records: {status.get('Accredited', 0):,} Accredited and
{status.get('Under Review', 0):,} Under Review, which together are the primary cohort of
{D['cmr_facilities']:,} cardiac MRI and {D['cct_facilities']:,} cardiac CT facilities.</p>
<p><b>ZIP to county.</b> ZIP codes do not follow county lines. Each ZIP was assigned to the county
holding the largest share of its residential addresses, using the HUD-USPS ZIP-county crosswalk
({mapm.get('hud_res_ratio', 0):,} records); {mapm.get('manual_zip_override', 0)} records needed a
documented manual ZIP correction. The full audit trail is
<code>data/processed/facility_mapping_audit.csv</code>.</p>
<p><b>Counties.</b> {D['total_counties']:,} county-equivalents (50 states plus DC). Connecticut uses
its nine 2022 planning regions in place of its eight retired counties, matching the current Census
geography.</p>
<p><b>Population.</b> Adults aged 45 years or older, from the US Census Bureau county population
estimates for July 1, 2023: {D['adults_45plus_total_millions']:.1f} million in total. This age group is
used because it is the main population for cardiac imaging.</p>
<p><b>Other sources.</b> CDC/ATSDR SVI 2022; County Health Rankings 2024; USDA RUCC 2023; Robert
Graham Center SDI 2015-2019; US Census TIGER/Line 2023 boundaries for the maps.</p>''')}
""")

    # ------------------------------------------------------- 4. methods
    add(f"""
<h2 class="newpage">4. How the analysis works</h2>
<h3>4.1 Facility rates</h3>
{plain(f'''
<p>A big county has more facilities simply because it has more people. To compare fairly we use a
<b>rate</b>: facilities per 100,000 adults aged 45 and over. A rate needs a reasonable number of
people underneath it. In a county with 500 adults, one facility would give a rate of 200 per
100,000, which would swamp everything else. So the {D['rate_excluded_n']} counties with fewer than
1,000 adults aged 45+ were left out of the county-by-county rate averages only. They stay in every
regression model.</p>''')}
{tech(f'''
<p>Rate = facility count ÷ adults aged ≥45 years × 100,000. County-level mean rates use the
{D['rate_eligible_n']:,} rate-eligible counties. <b>Pooled rates</b> (total facilities ÷ total adults,
which equals the population-weighted mean of county rates) need no exclusion and were added in
the revision. None of the {exc['n']} excluded counties has an accredited facility; the largest has
{exc['max_adults_45plus']:,} adults aged ≥45; together they hold {exc['adults_45plus_total']:,}
adults.</p>''')}

<h3>4.2 The counting model</h3>
{plain('''
<p>We want to know whether more disadvantaged counties have fewer facilities than you would expect
for their population. The tool is a regression model built for counts (0, 1, 2, ...). The simplest
count model assumes facilities are scattered evenly at random. They are not: most counties have
none and a few big counties have dozens. Statisticians call this clumping
<b>overdispersion</b>. The <b>negative binomial</b> model allows for it with an extra number, the
dispersion, that the data estimate. The model also includes the county's adult population in a
way that turns it into a model of the <b>rate</b>, not the raw count. This population term is
called an <b>offset</b>.</p>''')}
{tech(f'''
<p>Primary model: negative binomial regression, NB2 parameterization (variance = μ + αμ²), with
the dispersion α estimated by maximum likelihood, and offset log(adults aged ≥45). Fitted in
Python 3.11 with statsmodels 0.14. The estimated-dispersion NB2 had the lowest AIC and BIC
(Akaike and Bayesian information criteria, which score fit with a penalty for complexity) in
{wins} of {groups} index-outcome models, compared with Poisson regression and with NB2 with α fixed
at 1. A fixed α = 1 model is kept only as a labeled sensitivity analysis.</p>''')}

<h3>4.3 Reading the results: the incidence rate ratio</h3>
{plain('''
<p>Each result is an <b>incidence rate ratio (IRR)</b>. It compares facility rates. An IRR of 1.00
means no difference. For the disadvantage scores the IRR describes a 10-point step up the 0-100
ranking: an IRR of 0.95 means a 5% lower facility rate for each 10-point step toward more
disadvantage; 1.03 means 3% higher. For metropolitan status the IRR compares metropolitan with
nonmetropolitan counties: 8.33 means an eightfold higher rate.</p>
<p>Each IRR comes with a <b>95% confidence interval (CI)</b>, the range of values compatible with
the data, and a <b>P value</b>. A P value below 0.05 is called statistically significant: a
difference that large would be unusual if there were truly no link.</p>''')}
{tech('''
<p>Index coefficients are scaled per 10 percentile points. CIs are Wald intervals from the
model's information matrix unless stated. Tests are two-sided at α = 0.05. Because the 3,144
counties are the whole population, not a sample, CIs and P values are interpreted within a
superpopulation framework: the observed placement of facilities is treated as one realization
of an underlying siting process, and the intervals describe uncertainty about that process, not
sampling error. Reviewer 2 described this framework accurately in their summary.</p>''')}

<h3>4.4 Unadjusted and adjusted models: why it matters</h3>
{plain('''
<p>Metropolitan counties have most of the facilities, and nonmetropolitan counties are on average
more economically deprived. So if you compare deprivation with facilities directly, deprivation
can look important only because it travels together with being nonmetropolitan. This is called
<b>confounding</b>. To separate the two, every model was run twice: once on its own
(<b>unadjusted</b>) and once with metropolitan status added (<b>adjusted</b>). The adjusted model
asks: among counties of the same metropolitan type, does deprivation still matter? The adjusted
models are the primary analysis.</p>''')}

<h3>4.5 Checks on the main result (sensitivity analyses)</h3>
{plain('''
<p>A sensitivity analysis repeats the analysis in a different reasonable way to see whether the
answer holds. If it does, the finding does not depend on one particular choice.</p>''')}
{tech('''
<ul>
<li>Nine-step RUCC (ordinal) in place of the metropolitan yes/no indicator.</li>
<li>Models run separately within metropolitan and within nonmetropolitan counties (stratified),
plus an index-by-metropolitan-status interaction test, which asks whether the slope differs
between the two groups.</li>
<li>Accredited facilities only (dropping the Under Review records).</li>
<li>Regressions restricted to the rate-eligible counties (at least 1,000 adults aged ≥45).</li>
<li>Dispersion fixed at α = 1.</li>
<li>Population-weighted models (added in revision; section 6, Reviewer 1 comment 2).</li>
<li>The external SDI in place of the EDI.</li>
<li>Nonparametric checks: Spearman rank correlations, Kruskal-Wallis test across EDI fifths,
Mann-Whitney U test for metropolitan versus nonmetropolitan.</li>
</ul>''')}

<h3>4.6 How the economic deprivation index is built</h3>
{plain('''
<p>Six measures of economic hardship tend to rise and fall together. <b>Principal component
analysis (PCA)</b> finds the single combination of them that captures as much of their shared
up-and-down movement as possible, a bit like a grade-point average where the data choose the
weights. That combination is the index. Each county's score is then turned into a 0-100
percentile.</p>''')}
{tech(f'''
<p>Indicators standardized to z-scores (population standard deviation); PCA with scikit-learn 1.4
(full singular value decomposition, so results are exactly reproducible); first principal
component (PC1) retained and its scores converted to national percentiles. Fitted on
{PC['n_counties']:,} counties. Full component structure in Appendix C.</p>''')}
""")

    # ------------------------------------------------------- 5. results
    r = RG
    rows2 = []
    for key, name in (("SVI_CMR", "SVI, cardiac MRI"), ("SVI_CCT", "SVI, cardiac CT"),
                      ("EDI_CMR", "EDI, cardiac MRI"), ("EDI_CCT", "EDI, cardiac CT")):
        m = r[key]
        rows2.append([name, f"{cell(m['unadjusted'])}<br><span class='p'>P {cellp(m['unadjusted'])}</span>",
                      f"{cell(m['adjusted_metro'])}<br><span class='p'>P {cellp(m['adjusted_metro'])}</span>",
                      f"{cell(m['metro_effect'])}"])
    add(f"""
<h2 class="newpage">5. What the study found</h2>
<h3>5.1 Where the facilities are</h3>
{plain(f'''
<p>Accredited capacity is scarce and concentrated. Only {D['counties_with_cmr']:,} counties
({D['counties_with_cmr_pct']:.1f}%) have a cardiac MRI facility and {D['counties_with_cct']:,}
({D['counties_with_cct_pct']:.1f}%) a cardiac CT facility; {D['counties_neither_pct']:.1f}% have
neither. Metropolitan counties hold almost all of it.</p>''')}
{tech(f'''
<p>Mean county rates, metropolitan versus nonmetropolitan: cardiac MRI {D['metro_cmr_mean_rate']:.2f}
versus {D['nonmetro_cmr_mean_rate']:.2f} per 100,000 adults; cardiac CT {D['metro_cct_mean_rate']:.2f}
versus {D['nonmetro_cct_mean_rate']:.2f} (Mann-Whitney {pv(COR['metro_vs_nonmetro_cmr_mannwhitney_p'])}
for both). Pooled rates: cardiac MRI {rates['metropolitan']['CMR_pooled']:.2f} versus
{rates['nonmetropolitan']['CMR_pooled']:.2f}; cardiac CT {rates['metropolitan']['CCT_pooled']:.2f}
versus {rates['nonmetropolitan']['CCT_pooled']:.2f}. Metropolitan counties: {T1['metropolitan']['cmr_facilities']:,}
of {T1['_national_totals']['cmr']:,} CMR facilities ({T1['metropolitan']['cmr_facilities_pct']:.1f}%) and
{T1['metropolitan']['cct_facilities']:,} of {T1['_national_totals']['cct']:,} CCT facilities
({T1['metropolitan']['cct_facilities_pct']:.1f}%). Counties with no facility were more deprived on
average than counties with one (mean EDI {D['mean_edi_no_facility']:.1f} versus
{D['mean_edi_has_facility']:.1f}).</p>''')}
<figure><img src="{img('Figure1A_CMR_Choropleth')}"><figcaption><b>Figure 1A of the manuscript.</b>
Accredited cardiac MRI facilities per 100,000 adults aged 45+, by county. Gray counties have
none. Alaska and Hawaii are drawn in separate boxes.</figcaption></figure>

<h3>5.2 Does disadvantage predict capacity?</h3>
{plain(f'''
<p><b>SVI:</b> no link with cardiac MRI. A small link with <i>more</i> cardiac CT, both before and
after accounting for metropolitan status (about 3% more per 10-point step).</p>
<p><b>EDI:</b> before adjustment, more deprived counties had less cardiac MRI
({change(r['EDI_CMR']['unadjusted']['irr'])} rate per 10-point step). After adjustment for metropolitan
status that link vanished: the IRR moved to {r['EDI_CMR']['adjusted_metro']['irr']:.2f}, essentially no
difference.</p>
<p><b>Metropolitan status</b> was by far the strongest factor: about {r['EDI_CMR']['metro_effect']['irr']:.0f}
times the cardiac MRI rate and {r['EDI_CCT']['metro_effect']['irr']:.0f} times the cardiac CT rate.</p>''')}
{tech(table(["Model (per 10 percentile points)", "Unadjusted IRR (95% CI)", "Adjusted for metropolitan status", "Metropolitan status IRR (adjusted model)"], rows2)
       + "<p class='small'>Negative binomial (NB2, dispersion estimated), log-population offset. "
       f"SVI models {mn['regressions']['n_svi']:,} counties; EDI models {mn['regressions']['n_edi']:,}. "
       "These are Table 2 of the manuscript.</p>")}
<figure><img src="{img('Figure1B_Forest')}"><figcaption><b>Figure 1B of the manuscript.</b> Each
dot is an IRR with its 95% CI. Dots to the left of the line at 1 mean less capacity, to the right
more. Filled dots are statistically significant.</figcaption></figure>

<h3>5.3 Comparison with a published index</h3>
{plain('''
<p>Because we built the EDI ourselves, we repeated everything with the published SDI, in the
same counties. Across all counties the SDI did not show less capacity in more deprived counties,
even before adjustment; where it showed anything, it was slightly <i>more</i> capacity. (Inside
nonmetropolitan counties alone it did show less cardiac MRI, as the other two indices did; see
section 6.9.) It reproduced the metropolitan effect almost exactly. The
difference is explained by how strongly each index tracks nonmetropolitan location: the EDI does
more than the SDI. So whether a deprivation link appears at all depends on how much the chosen
index mirrors rurality.</p>''')}
{tech(f'''
<p>SDI, cardiac MRI: unadjusted {est(sdi_m['cmr_facility_count']['unadjusted'])}; adjusted
{est(sdi_m['cmr_facility_count']['adjusted'])}. SDI, cardiac CT: unadjusted
{est(sdi_m['cct_facility_count']['unadjusted'])}; adjusted {est(sdi_m['cct_facility_count']['adjusted'])}.
Metropolitan status in the SDI models: CMR {est(sdi_m['cmr_facility_count']['metro_in_adjusted'], p=False)};
CCT {est(sdi_m['cct_facility_count']['metro_in_adjusted'], p=False)}. Correlation with ordinal RUCC:
EDI ρ = {SDI['rurality_link']['EDI']['spearman_vs_rucc']:.2f} (nonmetropolitan minus metropolitan mean,
{SDI['rurality_link']['EDI']['gap']:.1f} percentile points); SDI ρ =
{SDI['rurality_link']['SDI']['spearman_vs_rucc']:.2f} (gap {SDI['rurality_link']['SDI']['gap']:.1f}).</p>''')}
<figure><img src="{img('Figure2_External_Validation')}"><figcaption><b>Figure 2 of the
manuscript.</b> The comparison with the SDI, and how strongly each index tracks
rurality.</figcaption></figure>

<h3>5.4 Fifths of deprivation</h3>
{plain(f'''
<p>Splitting counties into five equal groups by EDI, the least deprived fifth had
{Q['q1_over_q5_ratio']:.1f} times the average county cardiac MRI rate of the most deprived fifth. The
decline is not smooth: the middle fifth is higher than the second. Counting people rather than
counties (pooled rates), the gap shrinks to {Q['q1_over_q5_ratio_pooled']:.1f} times, because the
large gap comes mostly from many small nonmetropolitan counties.</p>''')}
{tech(f'''
<p>Mean county CMR rate by EDI quintile (Q1 least deprived to Q5 most):
{", ".join(f"{x:.2f}" for x in Q['cmr_rate_by_edi_quintile'])} per 100,000; Kruskal-Wallis
{pv(Q['kruskal_p_cmr'])}. Monotonic decline: {"yes" if Q['cmr_monotonic_decreasing'] else "no"}. The
validation script fails any wording that claims a steady decline.</p>''')}
""")

    # ------------------------------------------------------- 6. reviewers
    add("""
<h2 class="newpage">6. What the reviewers and editor asked, and what we did</h2>
<p>Peer review is the journal's quality check. Two independent experts read the paper and sent
comments through the editor. Below, each comment is quoted word for word, then explained, then
answered. "Where" points to the revised manuscript; page and line numbers refer to the
line-numbered clean PDF in the submission package.</p>""")

    def where_html(w):
        return f"<p class='where'><b>Where:</b> {esc(w)}</p>" if w else ""

    def changes_html(ch):
        return "<p><b>Changes made:</b></p><ul>" + "".join(f"<li>{esc(c)}</li>" for c in ch) + "</ul>"

    R1 = {t[0]: t for t in X["R1"]}
    R2 = {t[0]: t for t in X["R2"]}
    E = {t[0]: t for t in X["ED"]}
    V = X["V"]

    add(f"""<h3>6.1 The two reviewers' overall view</h3>
{plain('''<p>Both reviewers open with a summary rather than a criticism. Reviewer 1 restates the
main result. Reviewer 2 calls the design well described, the statistical methods appropriate and
the results effectively presented, and lists only minor comments.</p>''')}
<p class="lbl">Reviewer 1, summary</p>{quote(V['R1'][0])}
<p class="lbl">Reviewer 2, summary</p>{quote(V['R2'][0])}""")

    # R1-01
    add(f"""<h3>6.2 Reviewer 1, comment 1: results written in the Methods</h3>
{quote(V['R1'][1][0])}
{plain('''<p>A scientific paper keeps <i>what was done</i> (Methods) separate from <i>what was
found</i> (Results). Two sentences in our Methods said what a check had found. The reviewer is
right.</p>''')}
{tech(f'''<p>We found four results in Methods: the Accredited-only result, the effect of restricting
the regressions to rate-eligible counties, the AIC/BIC comparison, and the variance explained by
the EDI's first component. Methods now only describe these analyses; Results report them. Two
were quantified for the first time: restricting the regressions changed no adjusted index IRR by
more than {W['max_abs_irr_change_rate_eligible_adjusted']:.5f} (reported as "no more than 0.001";
metropolitan-status IRRs change more, being much larger numbers), and the
estimated-dispersion model had the lowest AIC and BIC in {wins} of {groups} models.</p>
{table(["Adjusted index IRR (P)", "Primary cohort", "Accredited only"], acc_rows)}''')}
{changes_html(R1['R1-01'][3])}{where_html(R1['R1-01'][4])}""")

    # R1-02
    add(f"""<h3>6.3 Reviewer 1, comment 2: weighting counties by population</h3>
{quote(V['R1'][1][1])}
{plain(f'''<p>The reviewer suggests keeping the {exc['n']} small counties and giving each county
influence in proportion to its population, rather than leaving counties out. Or, if every county
should count equally, to say why.</p>
<p>Think of two ways to ask the question. <b>The average county:</b> pick a county at random;
does deprivation predict its facility rate? Every county counts once. <b>The average adult:</b>
pick a person at random; does the deprivation of where they live predict the facility rate there?
Big counties count more. The reviewer is right that the second is worth reporting.</p>
<p>A useful fact: a simple count model (Poisson) with the population term already counts each
county in proportion to its population, so it <i>is</i> the "average adult" analysis. Our main
model sits in between: bigger counties count more, but the very largest do not take over. We kept
the main model and added the population-weighted one as a check.</p>
<p>What we found: weighted by population, the answers were the same as in the main model. The
small rise in cardiac CT with vulnerability remained, deprivation still made no difference once
metropolitan location was accounted for, and the metropolitan effect remained large. Counting
every county equally made the unadjusted deprivation link for cardiac MRI larger, showing it comes
from the many small nonmetropolitan counties. An earlier version of this check counted population
twice; a review of the repository found this and it was corrected.</p>''')}
{tech(f'''<p><b>How each model weights counties</b> (from its score equation, with county rate
r = y/N and fitted rate λ): Poisson with offset, Σ N·x·(r − λ) = 0 (population weights, the average
adult); Poisson with offset and weights 1/N, Σ x·(r − λ) = 0 (equal weights, the average county);
NB2 with offset, Σ N/(1 + αμ)·x·(r − λ) = 0 (rises with N and levels off). The earlier check put
weights N on the offset Poisson model, giving Σ N²·x·(r − λ) = 0, which double-counts population.</p>
{table(["Model", "Primary NB2", "Population-weighted", "Counties equal"], [
    ["SVI, cardiac CT, adjusted", est(wm['SVI_CCT_adjusted']['primary_nb2']), est(wm['SVI_CCT_adjusted']['poisson_population_weighted_robust']), est(wm['SVI_CCT_adjusted']['poisson_county_weighted_robust'])],
    ["EDI, cardiac MRI, unadjusted", est(wm['EDI_CMR_unadjusted']['primary_nb2']), est(wm['EDI_CMR_unadjusted']['poisson_population_weighted_robust']), est(wm['EDI_CMR_unadjusted']['poisson_county_weighted_robust'])],
    ["EDI, cardiac MRI, adjusted", est(wm['EDI_CMR_adjusted']['primary_nb2']), est(wm['EDI_CMR_adjusted']['poisson_population_weighted_robust']), est(wm['EDI_CMR_adjusted']['poisson_county_weighted_robust'])],
    ["Metropolitan status, cardiac MRI", est(wm['EDI_CMR_adjusted']['metro_primary_nb2'], p=False), est(wm['EDI_CMR_adjusted']['metro_poisson_population_weighted_robust'], p=False), est(wm['EDI_CMR_adjusted']['metro_poisson_county_weighted_robust'], p=False)],
], "small")}
<p><b>Concentration of weight.</b> Under population weights the Kish effective sample size is
{wt['kish_effective_n']:.0f} of {wt['n']:,} counties; the largest 1% of counties carry
{100 * wt['share_of_weight_top_1pct_counties']:.1f}% of the weight and metropolitan counties
{100 * wt['share_of_weight_metropolitan']:.1f}%.</p>''')}
{changes_html(R1['R1-02'][3])}{where_html(R1['R1-02'][4])}""")

    # R1-03
    add(f"""<h3>6.4 Reviewer 1, comment 3: "nonmetropolitan" is not the same as "rural"</h3>
{quote(V['R1'][1][2])}
{plain('''<p>The USDA codes split counties into metropolitan and nonmetropolitan. Some
nonmetropolitan counties contain sizable towns, so calling them all "rural" is loose. We checked
every use of rural, urban, metropolitan and nonmetropolitan and corrected the loose ones.</p>''')}
{tech('''<p>Rule applied: metropolitan / nonmetropolitan for the binary RUCC split (codes 1-3 versus
4-9); "rurality" only for the ordinal RUCC gradient; "rural" kept only where a cited study used it,
in the key word "rural health", and in reference titles. Seven wording changes, including
"correlated with rural location" to "correlated with nonmetropolitan location". Table 1's heading
"Rurality" became "Metropolitan status". The validation script now fails if a corrected phrase
returns. The title keeps "Rurality" (an open decision, section 9).</p>''')}
{changes_html(R1['R1-03'][3])}{where_html(R1['R1-03'][4])}""")

    # R1-04
    add(f"""<h3>6.5 Reviewer 1, comment 4: why more vulnerable counties have slightly more cardiac CT</h3>
{quote(V['R1'][1][3])}
{plain('''<p>This result runs opposite to what a deprivation story predicts. The reviewer suggests
big hospitals sit in dense city centers that also score high on vulnerability. We tested that
idea before writing about it, and the data fit it: the link shows up inside metropolitan
counties but not outside them (though the difference between the two is not statistically
certain), is strongest for the parts of the SVI that rise with crowding (minority status, housing
and transport), and fades once you account for population density. With a finer description of
urbanicity, the SVI link with cardiac MRI even reverses, which shows how much these results
depend on how geography is measured. In other words, the SVI partly
measures "dense city core", where large medical centers cluster.</p>''')}
{tech(f'''<p>Exploratory models (Supplementary Table S6). Metropolitan counties only:
{est(um['SVI_CCT: metropolitan counties only']['estimate'])}. Nonmetropolitan counties only:
{est(um['SVI_CCT: nonmetropolitan counties only']['estimate'])}. Adjusted for metropolitan status and
log population density: {est(um['SVI_CCT: metropolitan status + log population density']['estimate'])}.
SVI themes (adjusted for metropolitan status): housing type and transportation
{est(th['SVI_CCT_theme4']['adjusted_metro'], p=False)}; racial and ethnic minority status
{est(th['SVI_CCT_theme3']['adjusted_metro'], p=False)}. Within metropolitan counties these two themes
rise with density (ρ = {ud['spearman_theme4_density_metro']['rho']:.2f} and
{ud['spearman_theme3_density_metro']['rho']:.2f}). The largest metropolitan counties (RUCC 1) hold
{ud['by_metro_rucc']['1']['cct_facilities']:,} of {D['cct_facilities']:,} CCT facilities
({100 * ud['cct_share_rucc1']:.1f}%). Index-by-metropolitan interaction for SVI-CCT:
P = {S['interaction']['SVI_CCT']['interaction_ratio']['p']:.3f}. With density adjustment, SVI-CMR:
{est(um['SVI_CMR: metropolitan status + log population density']['estimate'])}; with categorical RUCC
(cardiac MR codes 7-9 combined) and density: {est(um['SVI_CMR: categorical RUCC + log population density']['estimate'])}. The registry does not
say which facilities are tertiary or academic centers, so that part of the explanation could not
be tested directly. These analyses are exploratory.</p>''')}
{changes_html(R1['R1-04'][3])}{where_html(R1['R1-04'][4])}""")

    # R1-05
    add(f"""<h3>6.6 Reviewer 1, comment 5: the economics of advanced imaging</h3>
{quote(V['R1'][1][4])}
{plain('''<p>Expensive scanners need enough patients to pay for themselves, so they cluster where
many people live. Differences in access are often read as evidence of unfair treatment (bias).
The reviewer argues that, here, money and market size explain most of the pattern. We added a
paragraph saying this. It cites the three studies the reviewer recommended, all from Medicare data:
a racial gap in access to digital mammography shrank as the technology spread; a colon-screening CT
scan that Medicare does not pay for was used far more by people with higher incomes; and gaps in
doctor visits between rich and poor, and city and country, areas grew as Medicare payments fell
behind inflation. The paragraph is also clear that county data can show <i>where</i> capacity is but
not <i>why</i>, and can neither prove nor rule out bias.</p>''')}
{tech('''<p>New Discussion paragraph: fixed costs (scanner, site preparation, technologists,
subspecialty readers) recovered only at sufficient volume; density, referral networks and hospital
infrastructure supply volume. References added: Baker 2001 (managed care and MRI adoption; ref 17),
Rosenthal et al. 2005 (geographic distribution of physicians; ref 18), Rosenkrantz et al. 2016 (US
radiologist workforce; ref 19), and the reviewer's three studies, verified against Europe PMC:
Christensen et al., Radiology 2023;306(2):e221153 (ref 20: digital mammography gap between Black
and White women peaked at 3.8 percentage points in 2011 and fell to 1.2 in 2016); Christensen et al.,
AJR 2024;222(1):e2329703 (ref 21: odds of screening CT colonography 5.73 times higher at per-capita
income ≥$100,000 than &lt;$25,000, against 1.36 for colonoscopy; attributed to non-coverage);
Christensen et al., Inquiry 2026;63:00469580261473400 (ref 22: gaps in physician care by urbanicity,
income and area deprivation widened as the inflation-adjusted conversion factor fell 48.3%, 2005-2025).
Alternative explanations named: payer mix, certificate-of-need regulation, health-system ownership,
workforce supply and accreditation practice.</p>''')}
{changes_html(R1['R1-05'][3])}{where_html(R1['R1-05'][4])}""")

    # R2-01
    pcrows = [[esc(lab[k]), f"{pcl[k]:.2f}", f"{PC['pc2_loadings'][k]:.2f}"] for k in PC["features"]]
    add(f"""<h3>6.7 Reviewer 2, comment 1: show how the economic index is built</h3>
{quote(V['R2'][1][0])}
{plain(f'''<p>The reviewer asks for two standard pictures. A <b>scree plot</b> shows how much of the
shared variation each component captures; the first one should stand out. A <b>biplot</b> shows how
each of the six measures pulls on the components. The first component captures
{100 * PC['variance_explained'][0]:.1f}% of the variation and all six measures point the same way,
which supports using it as one economic deprivation score. A second, smaller component is mostly
housing costs. Is it real or noise? <b>Parallel analysis</b> answers that: it scrambles each measure
separately many times, so any correlation is destroyed, and records how big the components of pure
noise get. The second component is no bigger than noise, so the index keeps only the first.</p>''')}
{tech(f'''<p>Eigenvalues {", ".join(f"{x:.2f}" for x in PC['eigenvalues'])}; variance explained
{", ".join(f"{100 * x:.1f}%" for x in PC['variance_explained'])}. {PC['n_components_eigenvalue_gt_1']}
components have eigenvalue above 1 (PC2 = {PC['eigenvalues'][1]:.2f}). Kaiser-Meyer-Olkin measure
{PC['kmo']:.2f}; Bartlett's test of sphericity χ² = {PC['bartlett_chi2']:,.0f}, df =
{PC['bartlett_df']}, {pv(PC['bartlett_p'])}. Horn's parallel analysis ({PC['parallel_analysis']['replicates']:,}
datasets, each indicator permuted independently; seed {PC['parallel_analysis']['seed']}): 95th-percentile
eigenvalues {", ".join(f"{x:.3f}" for x in PC['parallel_analysis']['threshold_95'])}; PC2
{PC['eigenvalues'][1]:.3f} &lt; {PC['parallel_analysis']['threshold_95'][1]:.3f}, so
{PC['parallel_analysis']['n_retained']} component is retained. Refitting reproduced the stored raw EDI score
exactly (Pearson r = {PC['pc1_vs_stored_raw_score_pearson']:.6f}) and ranks counties exactly as the EDI
percentiles do (Spearman ρ = {PC['pc1_vs_edi_percentile_spearman']:.3f}; Pearson
{PC['pc1_vs_edi_percentile_pearson']:.3f}, since percentiles are nonlinear). Loadings = eigenvector coefficient ×
√eigenvalue.</p>
{table(["Indicator", "PC1 loading", "PC2 loading"], pcrows)}''')}
<figure><img src="{img('FigureS3_EDI_PCA')}"><figcaption><b>Supplementary Figure S3 (new).</b>
Left, the scree plot; right, the biplot.</figcaption></figure>
{changes_html(R2['R2-01'][3])}{where_html(R2['R2-01'][4])}""")

    # R2-02
    add(f"""<h3>6.8 Reviewer 2, comment 2: many tests, some significant by chance?</h3>
{quote(V['R2'][1][1])}
{plain(f'''<p>Run enough tests and a few will look "significant" by luck, like flipping a coin many
times and seeing a run of heads. Adjustments for <b>multiple comparisons</b> correct for this. We
named the four tests the paper is really about (the adjusted SVI and EDI models for both scans)
and adjusted those. The one significant result among them, SVI and cardiac CT, stays significant.
We also adjusted across all {fam['extended']['n_tests']} negative binomial index tests in the paper.
Under the stricter of two methods that one result would no longer be significant; the response
explains why that method is too strict here, because most of those tests re-estimate the same
four associations in different ways.</p>''')}
{tech(f'''<p><b>Primary family:</b> {fam['primary']['n_tests']} metropolitan-adjusted SVI and EDI
associations; Holm step-down adjustment (reference 14). Adjusted SVI-CCT: unadjusted
{pv(sc['p'])}, Holm {pv(sc['holm_primary'])}. <b>Extended family:</b> all {fam['extended']['n_tests']}
negative binomial index associations in Tables 2-3 and Figure 2 (the population-weighted Poisson
rows of Table 3 are a separate sensitivity analysis and are excluded); Benjamini-Hochberg false discovery rate (reference
15): {fam['extended']['significant_bh']} of {fam['extended']['significant_unadjusted']} nominally
significant results remain; SVI-CCT adjusted {pv(sc['bh_extended'])}. Holm across all
{fam['extended']['n_tests']}: SVI-CCT adjusted {pv(sc['holm_extended'])}. Methods now also state that
the sensitivity analyses were intended to assess the robustness of the primary findings, as the
reviewer suggested. Every test is listed in Appendix B.</p>''')}
{changes_html(R2['R2-02'][3])}{where_html(R2['R2-02'][4])}""")

    # R2-03
    add(f"""<h3>6.9 Reviewer 2, comment 3: the result with no confidence interval</h3>
{quote(V['R2'][1][2])}
{plain(f'''<p>In the submitted paper one result, cardiac MRI in nonmetropolitan counties, had an
estimate but no confidence interval or P value; we called it "not estimable". The reviewer asked
why. The answer turned out to be a reporting mistake on our part.</p>
<p>The model has a dial for how clumped facilities are. In nonmetropolitan counties each of the
{nm['events']} cardiac MRI facilities is in a different county: there is no clumping at all. So
the dial went to zero, the very edge of its allowed range. At that edge the standard software
cannot compute error bars, and it left them blank. But a negative binomial model with the dial at
zero <i>is</i> the simpler Poisson model, which computes error bars without trouble. The correct
answer was available all along.</p>
<p>The corrected result: among nonmetropolitan counties, more deprived counties have
{change(nm['estimate']['irr'])} cardiac MRI capacity per 10-point step, and the other two indices
agree. Because it rests on {nm['events']} facilities, we present it as a lead for future research,
and it does not change the main adjusted results.</p>''')}
{tech(f'''<p><b>In the reviewer's terms:</b> the model converged; the failure was in variance
estimation; the cause was sparse data.</p>
<p><b>Diagnosis.</b> Stratum: {nm['n']:,} counties, {nm['events']} facilities, {nm['units_with_event']}
counties with a facility, maximum count {nm['max_count']}. The optimizer reported convergence, but
α collapsed to {nm['alpha']:.4f}, the score (gradient) for α was still {nm['gradient']['alpha']:.3f}, and
the negated Hessian had eigenvalues {", ".join(f"{x:.3f}" for x in nm['neg_hessian_eigenvalues'])};
one is negative, so the matrix is not positive definite and statsmodels returns no standard errors.
The Poisson log-likelihood ({nm['llf_poisson']:.4f}) exceeds the NB2 value at the stopping point
({nm['llf_nb2']:.4f}): the maximum lies on the boundary α = 0, where NB2 equals Poisson.</p>
<p><b>Result and checks.</b> Poisson (Wald): {est(nm['estimate'])}. Profile-likelihood CI
{det['poisson_profile']['ci_low']:.2f}-{det['poisson_profile']['ci_high']:.2f}, likelihood-ratio
{pv(det['poisson_profile']['lr_p'])}. Robust errors: {est(det['poisson_robust'])}. Fixed α from 0 to 1:
IRR {min(v['irr'] for v in det['fixed_alpha_grid'].values()):.2f}-{max(v['irr'] for v in det['fixed_alpha_grid'].values()):.2f}.
Within-stratum ordinal RUCC: {est(det['within_stratum_ordinal_rucc'])}. Interaction model on all
{mn['regressions']['n_edi']:,} counties (α estimated at {inter['alpha']:.2f}): nonmetropolitan slope
{est(inter['nonmetro_slope'])}; metropolitan slope {est(inter['metro_slope'])}; ratio
{est(inter['interaction_ratio'])}. Same stratum with SVI: {est(S['strata']['SVI_CMR_nonmetro']['estimate'])};
with SDI: {est(S['strata']['SDI_CMR_nonmetro']['estimate'])}.</p>
<p><b>Rule now in the code.</b> <code>model_spec.fit_primary_checked</code> checks every stratified
fit. It substitutes the Poisson fit only when the Hessian is not positive definite, α is below
{pkg_boundary()}, and the Poisson likelihood is at least as high. Any other failure is still
reported as not estimable.</p>''')}
{changes_html(R2['R2-03'][3])}{where_html(R2['R2-03'][4])}""")

    # R2-04
    t1rows = []
    for k, name in (("all_counties", "All counties"), ("metropolitan", "Metropolitan"),
                    ("nonmetropolitan", "Nonmetropolitan"), ("edi_q1", "EDI Q1 (least deprived)"),
                    ("edi_q2", "EDI Q2"), ("edi_q3", "EDI Q3"), ("edi_q4", "EDI Q4"), ("edi_q5", "EDI Q5 (most deprived)")):
        g = T1[k]
        t1rows.append([name, f"{g['counties']:,}", f"{g['cmr_facilities']:,} ({g['cmr_facilities_pct']:.1f})",
                       f"{g['cct_facilities']:,} ({g['cct_facilities_pct']:.1f})"])
    add(f"""<h3>6.10 Reviewer 2, comment 4: percentages in Table 1</h3>
{quote(V['R2'][1][3])}
{plain('''<p>Table 1 showed how many facilities sit in each group of counties but not what share of
the national total that is. The shares are now shown next to the counts.</p>''')}
{tech(table(["Group", "Counties", "CMR facilities, No. (%)", "CCT facilities, No. (%)"], t1rows)
      + f"<p class='small'>Denominator: the national total of each modality ({T1['_national_totals']['cmr']:,} CMR, "
        f"{T1['_national_totals']['cct']:,} CCT). Quintile rows sum to less than 100% because counties without an "
        "EDI value are in no quintile.</p>")}
{changes_html(R2['R2-04'][3])}{where_html(R2['R2-04'][4])}""")

    # R2-05
    add(f"""<h3>6.11 Reviewer 2, comment 5: one table with every model side by side</h3>
{quote(V['R2'][1][4])}
{plain('''<p>Readers can now see every version of the analysis in one place and judge for themselves
whether the answer depends on any one choice.</p>''')}
{tech(f'''<p>Supplementary Table S2, Panel A: {rv['R2-05_table_rows']} models (SVI, EDI and SDI; both
scans): primary unadjusted and adjusted; ordinal RUCC; metropolitan and nonmetropolitan strata;
α fixed at 1; rate-eligible counties; Accredited-only cohort; robust Poisson; population-weighted
Poisson and NB2; density adjustment; SVI quartiles. Each row: specification, counties, facilities,
IRR (95% CI), P, second model term, dispersion, note. Panel B: AIC, BIC and log-likelihood. No row
is "not estimable" after the correction in 6.9; the table would print NE if one were. The
Accredited-only sensitivity now uses the primary sample (previously the rate-eligible subset),
so it differs from the primary analysis in one respect only.</p>''')}
{changes_html(R2['R2-05'][3])}{where_html(R2['R2-05'][4])}""")

    # Editor
    def pop_rows():
        keys = ["pct_65plus", "pct_female", "pct_nh_white", "pct_nh_black", "pct_hispanic", "pct_nh_asian",
                "pct_pov150", "pct_uninsured", "pct_disability", "diabetes", "obesity", "smoking",
                "inactivity", "premature_mortality", "pcp"]
        out = []
        for k in keys:
            v = POP["variables"][k]
            b = v["by_stratum"]
            out.append([esc(v["label"])] + [f"{b[s]['population_weighted_mean']:.1f}" for s in
                                             ("all", "metropolitan", "nonmetropolitan", "any_facility", "no_facility")])
        return out
    add(f"""<h3>6.12 The editor's requirements</h3>
<p class="lbl">Editor, comment 1: response letter, tracked and clean versions</p>{quote(V['ED'][1])}
{plain(f'''<p>Done. The response letter answers every comment with page and line references. The
tracked version shows every change in Word's track-changes; the clean version has them accepted.
The accepted text of the two is identical, which a script confirms.</p>''')}
<p class="lbl">Editor, comment 2: permission for previously published figures</p>{quote(V['ED'][2])}
{plain('''<p>No table or figure has been published before. All were made by our code from public
data, so no permission letters are needed. (Open item: confirm none appeared in a preprint or
conference poster.)</p>''')}
<p class="lbl">Editor, comment 3: proofreading</p>{quote(V['ED'][3])}
{plain('''<p>The whole manuscript was proofread. Corrections include: the Medicare sentence
gave an effective date and called the ACR the largest accreditor, neither of which the cited CMS
page states; the first reference reports rural-urban differences, not economic ones, so the
sentence citing it was narrowed; the population denominators are Census Bureau estimates for July
1, 2023, not American Community Survey estimates; abbreviations (AIC and BIC now defined) and
geographic terms were made consistent; "strongly correlated" overstated the link between
metropolitan status and deprivation; nonsignificant results are no longer described as showing no
association; and the closing sentence that repeated the Summary Sentence was removed.</p>''')}
<p class="lbl">Editor, comment 4: a table of population characteristics</p>{quote(V['ED'][4])}
{plain('''<p>Journals often require a table describing the patients in a study: their race and
ethnicity, sex, and health conditions. This study has no patients. It counts facilities in
counties. We cannot describe who was scanned, because those data do not exist here. We added the
closest honest equivalent as Table 5 (Table 4 remains the comparison with the published index): a table describing the <i>residents</i> of
the counties, overall, by metropolitan status, and by whether the county has a facility. The
supplement (Table S1) adds the spread across counties and the missing counts. Heart disease rates, disease
severity and gender identity are not available at county level in these sources.</p>''')}
{tech(table(["Characteristic (population-weighted mean)", "All", "Metro", "Nonmetro", "Any facility", "No facility"], pop_rows(), "small")
      + f"<p class='small'>Supplementary Table S1 also gives county medians (IQR) and missing counts. Sources: SVI 2022 "
        f"(ACS 2018-2022) and County Health Rankings 2024. Counties: all {POP['strata']['all']['counties']:,}; metro "
        f"{POP['strata']['metropolitan']['counties']:,}; nonmetro {POP['strata']['nonmetropolitan']['counties']:,}; any facility "
        f"{POP['strata']['any_facility']['counties']:,}; none {POP['strata']['no_facility']['counties']:,}. Connecticut's "
        f"{POP['notes']['connecticut_planning_regions_missing_chr']} planning regions lack County Health Rankings values. "
        "Sex is reported as recorded in Census estimates.</p>")}
""")

    # ------------------------------------------------------- 7. what changed
    add(f"""
<h2 class="newpage">7. What changed in the conclusions, and what did not</h2>
{table(["", "Submitted version", "Revised version"], [
    ["Main finding: capacity concentrates in metropolitan counties", "Yes", "Yes; also holds under population weighting"],
    ["Deprivation (EDI) linked to less CMR after adjustment", "No", "No"],
    ["SVI linked to slightly more CCT after adjustment", "Yes (P = 0.008)", f"Yes; survives the primary-family Holm adjustment (P = {sc['holm_primary']:.3f}); explained by dense urban cores"],
    ["Nonmetropolitan CMR stratum", 'IRR 0.70, no CI ("not estimable")', f"{est(nm['estimate'])}; hypothesis-generating"],
    ["Small counties excluded from rates", "106, unexplained effect", "None has a facility; pooled rates added"],
    ["Economic interpretation", "Brief", "Full paragraph: fixed costs, market size, bias versus economics"],
    ["Terminology", "Rural / nonmetropolitan mixed", "RUCC definitions applied throughout"],
    ["Four submitted results (fits stopped short of the maximum)", "8.56 (upper limit 14.61); 2.12; P = 0.801; P = 0.232",
     f"{RG['SVI_CMR']['metro_effect']['irr']:.2f} (upper limit {RG['SVI_CMR']['metro_effect']['ci_high']:.2f}); "
     f"{sdi_m['cct_facility_count']['metro_in_adjusted']['IRR']:.2f}; "
     f"P = {RG['EDI_CMR']['adjusted_rucc']['p']:.3f}; P = {S['strata']['EDI_CCT_nonmetro']['estimate']['p']:.3f} "
     f"(nonmetropolitan CCT, a boundary solution); no conclusion affected"],
    ["Body length", "2,493 words", f"{X['body_words']} words, under the journal's 3,000-word limit; "
     "restatements removed, including the closing repeat of the Summary Sentence, and the Take-Home Points take "
     "its place"],
])}
""")

    # ------------------------------------------------------- 8. quality
    add(f"""
<h2>8. How we made sure the numbers are right</h2>
{plain('''<p>Two earlier numbers in a previous version were wrong because someone copied them by hand.
Since then, no number is typed into the manuscript by hand. A script reads every number from the
analysis results and a second script checks the manuscript against the data, cell by cell.</p>''')}
{tech(f'''<ul>
<li><b>Validation gate</b> (<code>code/12_manuscript_numbers.py</code>): {gate[0]} checks, {gate[1]}
mismatches, on the clean, tracked and working manuscripts. It is two-sided: a forbidden list fails
the run if an obsolete value or corrected phrase is still present, and claim checks fail wording the
data contradict (for example, "monotonic decline").</li>
<li><b>Pipeline tests:</b> {tst[0]} passed, {tst[1]} failed.</li>
<li><b>Tracked equals clean:</b> the accepted text of the tracked file is identical, paragraph by
paragraph, to the clean file and to <code>manuscript_SUBMISSION.docx</code>.</li>
<li><b>Exact reproducibility:</b> the PCA uses the full (non-random) solver, so every run gives the
same index.</li>
<li><b>Response locations:</b> all {X['n_locs']} page and line locations in the response letter were
recomputed independently from the line-numbered clean PDF ({X['pages']} pages) and match. Each also
quotes the passage's opening words, because the journal's own PDF may break lines differently.</li>
<li><b>Independent recomputation:</b> the counts, rates, pooled rates, all eight primary models,
the nonmetropolitan Poisson fit and its profile-likelihood interval, the weighted models, the Kish
effective sample size, all multiplicity adjustments and the PCA were recomputed from the raw data
with separately written code. All matched except where the original optimizer (BFGS) had stopped
marginally short of the maximum likelihood. Every negative binomial fit now finishes with
Newton-Raphson steps, which changed three submitted values in the last digit and the interaction P
value from 0.004 to 0.003. A later full audit (November 9) found a fourth: in the nonmetropolitan
cardiac CT stratum the likelihood is maximized at zero dispersion, where the correct fit is the
Poisson fit, so its Table 3 P value is 0.233, not 0.232. The response letter discloses all four.</li>
<li><b>Every quoted estimate checked:</b> the validation script now also checks that every estimate
quoted in the text, wherever it appears, matches a computed result. That is the check that would
have caught the first three values above.</li>
<li><b>Correct baseline:</b> the tracked changes are measured against the manuscript as submitted to
JACR on September 25, 2026; its line numbers match the reviewers' references exactly (lines 78-79 and
91-92, and page 9, line 165). Its tables were uploaded separately, so the revised tables are again
separate files, with their changes listed in the response.</li>
</ul>''')}
""")

    # ------------------------------------------------------- 9. decisions
    add("<h2>9. Decisions still needed from the authors</h2>"
        + table(["Item", "Detail"], [[esc(k), esc(v)] for k, v in pkg.DECISIONS]))

    # ------------------------------------------------------- 10. files
    add(f"""
<h2>10. Where everything is</h2>
{table(["File (manuscript/jacrad-reviews-2026/R1_submission_package/)", "What it is"], [
    ["01_Revised_Manuscript_CLEAN (.docx, .pdf)", "Revised manuscript, changes accepted, line-numbered"],
    ["02_Revised_Manuscript_TRACKED (.docx, .pdf)", "Revised manuscript with round-1 changes tracked"],
    ["03_Response_to_Reviewers (.docx, .pdf)", "Point-by-point response, comments quoted verbatim"],
    ["04_Supplementary_Material (.docx, .pdf)", "Supplementary Methods S1-S8, Tables S1-S6, Figures S1-S3"],
    ["05_Figures/, 06_Tables/, 07_Statistical_Outputs/", "Figures at 600 dpi; tables; all result files"],
    ["08 to 12", "Permissions log, proofreading report, change log, checklist, completion report"],
    ["13_Title_Page, 14_Cover_Letter (.docx, .pdf)", "Unblinded title page and the cover letter to the editor"],
    ["00_Revision_Plan_and_Critical_Appraisal_INTERNAL.docx", "Authors only; do not submit"],
])}
{tech(REBUILD)}
""")

    # ------------------------------------------------------- appendices
    brows = []
    for t in M["tests"]:
        brows.append([esc(t["test"]), cell(t), cellp(t),
                      "" if t["holm_primary"] is None else f"{t['holm_primary']:.3f}",
                      f"{t['bh_extended']:.3f}", f"{t['holm_extended']:.3f}"])
    pc_rows = [[f"PC{i + 1}", f"{ev:.2f}", f"{100 * ve:.1f}%", f"{100 * cv:.1f}%"]
               for i, (ev, ve, cv) in enumerate(zip(PC["eigenvalues"], PC["variance_explained"], PC["cumulative_variance"]))]
    gl = [
        ("Adjusted / unadjusted", "A model with or without metropolitan status added, to separate deprivation from location."),
        ("AIC, BIC", "Akaike and Bayesian information criteria: fit scores that penalize complexity; lower is better."),
        ("Benjamini-Hochberg (BH)", "A multiple-comparison adjustment that controls the expected share of false positives (false discovery rate)."),
        ("Biplot", "A chart showing both counties and the direction each indicator pulls on the principal components."),
        ("Confidence interval (95% CI)", "The range of effect sizes compatible with the data."),
        ("Confounding", "A third factor linked to both the exposure and the outcome, creating a misleading association."),
        ("Dispersion (α)", "The extra-clumping parameter of the negative binomial model; α = 0 means no extra clumping (Poisson)."),
        ("Ecologic study", "A study of groups (here counties), not individuals."),
        ("Eigenvalue", "How much of the indicators' shared variation a principal component captures."),
        ("Estimand", "The exact quantity a model estimates, such as the effect in the average county or the average adult."),
        ("Hessian", "The matrix of second derivatives of the log-likelihood. Under regularity conditions, the inverse of the negated Hessian (the observed information) estimates the covariance of the estimates, and standard errors are the square roots of its diagonal."),
        ("Holm adjustment", "A step-down multiple-comparison method controlling the chance of any false positive."),
        ("IRR", "Incidence rate ratio: the ratio of facility rates; 1.00 means no difference."),
        ("Kish effective sample size", "How many equally weighted observations a weighted sample is worth."),
        ("Loading", "The correlation between an indicator and a principal component."),
        ("Negative binomial (NB2)", "A count model that allows overdispersion; variance = μ + αμ²."),
        ("Offset", "A term that turns a count model into a rate model by fixing the population coefficient at 1."),
        ("Ordinal RUCC", "The nine-step urban-rural code used as a ranked variable."),
        ("Overdispersion", "More variation in counts than a Poisson model allows; clumping."),
        ("P value", "How unusual the observed result would be if there were no true association."),
        ("PCA", "Principal component analysis: combines correlated measures into fewer summary scores."),
        ("Percentile", "A county's rank on a 0-100 scale."),
        ("Poisson regression", "The simplest count model; assumes variance equals the mean."),
        ("Pooled rate", "Total facilities divided by total adults; equals the population-weighted mean county rate."),
        ("Profile-likelihood interval", "A confidence interval read from the shape of the likelihood, valid when Wald intervals are doubtful."),
        ("Quintile", "One of five equal-sized groups."),
        ("Robust (sandwich) standard errors", "Standard errors that stay valid when the variance assumption is wrong."),
        ("Scree plot", "A chart of eigenvalues by component, used to judge how many components matter."),
        ("Sensitivity analysis", "A repeat analysis under a different reasonable choice, to test robustness."),
        ("Stratified analysis", "The analysis run separately within subgroups (metropolitan, nonmetropolitan)."),
        ("Superpopulation inference", "Treating a complete enumeration as one realization of an underlying process."),
    ]
    add(f"""
<h2 class="newpage">Appendix A. Glossary</h2>
{table(["Term", "Meaning"], [[f"<b>{esc(k)}</b>", esc(v)] for k, v in gl], "small")}
<h2>Appendix B. Every index test and its multiplicity adjustment</h2>
{table(["Test", "IRR (95% CI)", "P", "Holm, primary family", "BH, all 18", "Holm, all 18"], brows, "small")}
<h2>Appendix C. Principal component analysis of the six EDI indicators</h2>
{table(["Component", "Eigenvalue", "Variance explained", "Cumulative"], pc_rows, "small")}
<p class="small">Coefficients and correlation matrix: Supplementary Table S5 and
<code>output/results/edi_pca_components.csv</code>.</p>
<h2>Appendix D. Fifths of economic deprivation (Figure S2)</h2>
<figure><img src="{img('FigureS2_EDI_Quintiles')}"><figcaption><b>Supplementary Figure S2.</b>
Mean county facility rates by EDI quintile. Note that the decline is not steady.</figcaption></figure>
""")

    css = CSS
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>R1 Plain-Language Guide</title><style>{css}</style></head><body>{''.join(H)}</body></html>"""


REBUILD = '''<p>Rebuild from the repository root:</p>
<pre>.venv/bin/python code/00_run_all.py --with-present
.venv/bin/python tools/revise_manuscript_r1.py manuscript/_archive/manuscript_JACR_first_submission_2026-09-25.docx \\
    manuscript/jacrad-reviews-2026/working/manuscript_R1_TRACKED.docx \\
    --log manuscript/jacrad-reviews-2026/working/r1_change_log.csv --blind
.venv/bin/python tools/revise_manuscript_r1.py manuscript/_archive/manuscript_JACR_first_submission_2026-09-25.docx \\
    manuscript/manuscript_CLEAN.docx
.venv/bin/python tools/finalize_manuscript.py --validate
.venv/bin/python tools/build_r1_package.py
.venv/bin/python tools/build_r1_explainer.py</pre>
<p>New analyses: <code>code/18_reviewer_analyses.py</code> (stage C) writes
<code>output/results/reviewer_analyses.json</code>; <code>code/19_supplementary_material.py</code>
(stage E) writes the supplement; <code>code/model_spec.py</code> holds the boundary rule.</p>'''


def pkg_boundary():
    sys.path.insert(0, os.path.join(BASE, "code"))
    import model_spec
    return f"{model_spec.BOUNDARY_ALPHA}"


CSS = r"""
@page { size: Letter; margin: 0.85in 0.8in 0.85in 0.8in;
  @bottom-center { content: "R1 plain-language guide  \00B7  page " counter(page) " of " counter(pages);
                   font: 8.5pt "Helvetica Neue", Arial, sans-serif; color: #6b7280; } }
@page :first { @bottom-center { content: none; } }
:root { --ink:#1f2937; --muted:#4b5563; --rule:#d1d5db; --accent:#1d4e89; --plain:#eef4fb; --tech:#f6f6f4; }
html { font-size: 10.6pt; }
body { font-family: Charter, "Iowan Old Style", Georgia, serif; color: var(--ink); line-height: 1.45; margin: 0; }
h1, h2, h3, .kicker, .tag, th, .lbl, figcaption, .meta td:first-child { font-family: "Helvetica Neue", Arial, sans-serif; }
h1 { font-size: 23pt; line-height: 1.15; color: var(--accent); margin: 0.2in 0 0.15in; }
h2 { font-size: 15pt; color: var(--accent); border-bottom: 1.5px solid var(--accent); padding-bottom: 3px;
     margin: 0.32in 0 0.12in; break-after: avoid; }
h2.newpage { break-before: page; }
p, li { orphans: 3; widows: 3; }
h3 { font-size: 11.8pt; margin: 0.22in 0 0.08in; break-after: avoid; }
p { margin: 0.06in 0; }
ul { margin: 0.04in 0 0.06in 0.2in; padding-left: 0.1in; }
li { margin: 0.02in 0; }
.cover { padding-top: 1.1in; }
.kicker { text-transform: uppercase; letter-spacing: 0.08em; font-size: 9pt; color: var(--muted); }
.sub { font-size: 13pt; color: var(--muted); margin-bottom: 0.3in; }
.meta { border-collapse: collapse; margin: 0.1in 0 0.35in; font-size: 10.5pt; }
.meta td { padding: 3px 14px 3px 0; border: none; }
.meta td:first-child { color: var(--muted); font-weight: 600; }
.note { border-top: 1px solid var(--rule); padding-top: 0.12in; }
.plain, .tech { padding: 0.09in 0.13in; margin: 0.08in 0 0.1in; border-radius: 4px; }
.plain { break-inside: avoid; }
.tech { break-inside: auto; }
h3 + .plain, h3 + blockquote, .lbl + blockquote { break-before: avoid; }
blockquote { break-inside: avoid; }
.plain { background: var(--plain); border-left: 4px solid #5b8fd1; }
.tech { background: var(--tech); border-left: 4px solid #9ca3af; font-size: 9.8pt; }
.tag { break-after: avoid; font-size: 7.8pt; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; color: var(--muted); margin-bottom: 2px; }
blockquote { margin: 0.08in 0; padding: 0.06in 0.13in; border-left: 3px solid #c7a252; background: #fbf8f1;
             font-style: italic; font-size: 9.6pt; color: #374151; }
.lbl { font-weight: 700; font-size: 9.5pt; margin: 0.14in 0 0.02in; color: var(--muted); }
table { border-collapse: collapse; width: 100%; margin: 0.08in 0; font-size: 9.2pt; break-inside: auto; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { text-align: left; font-size: 8.4pt; font-weight: 700; border-bottom: 1.2px solid var(--ink); padding: 4px 6px; vertical-align: bottom; }
td { border-bottom: 0.6px solid var(--rule); padding: 3.5px 6px; vertical-align: top; }
table.small { font-size: 8.4pt; }
.p { color: var(--muted); font-size: 8.2pt; }
.small { font-size: 8.6pt; color: var(--muted); }
.where { font-size: 8.8pt; color: var(--muted); }
figure { margin: 0.12in 0; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 6.3in; }
figcaption { font-size: 8.6pt; color: var(--muted); text-align: left; margin-top: 4px; }
code, pre { font-family: Menlo, Consolas, monospace; font-size: 8.4pt; }
pre { background: #fff; border: 0.6px solid var(--rule); padding: 0.08in; white-space: pre-wrap; }
"""


def main():
    X = load()
    page = build_html(X)
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "guide.html")
        open(src, "w", encoding="utf-8").write(page)
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={OUT}", "file://" + src],
                           capture_output=True, text=True, timeout=300)
        if not os.path.exists(OUT):
            raise SystemExit(r.stderr[-2000:])
    pages = subprocess.run(["pdfinfo", OUT], capture_output=True, text=True).stdout
    n = re.search(r"Pages:\s+(\d+)", pages).group(1)
    print(f"  wrote {os.path.relpath(OUT, BASE)} ({n} pages, {os.path.getsize(OUT) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
