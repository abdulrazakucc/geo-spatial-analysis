#!/usr/bin/env python3
"""
12_manuscript_numbers.py
========================
Single source of truth for every number quoted in the manuscript.

WHY THIS EXISTS
    An earlier submission contained two values that had been transcribed by hand
    from a narrative document and were wrong. This script removes the need for
    hand transcription entirely. It recomputes, at full precision and from the
    committed data, every quantity that appears in the manuscript text, tables,
    and figure legend, and writes them to a machine-readable and a
    human-readable file.

    If the manuscript .docx is present it is then CHECKED against those values
    and any mismatch is reported. Reviewers can run this script to confirm that
    the paper and the repository agree.

WHAT IT PRODUCES
    output/validation/manuscript_numbers.json   every value, full precision
    output/validation/manuscript_numbers.txt    the same, formatted for reading
    output/validation/manuscript_check.txt      docx vs data, if the docx exists

MODEL SPECIFICATION (identical in every script in this repository)
    facility_count ~ index_per10 [+ rurality] + offset(log adults 45+)
    Negative binomial (NB2), dispersion estimated from the data
    Fixed alpha = 1.0 retained as a labelled sensitivity
    Count regressions use every county with the index and population > 0;
    the <1,000-adult rule governs rate calculations only
    Indices are scaled per 10 percentile points

RUN
    python code/06_edi_sensitivity_analysis.py    (first, builds the EDI)
    python code/09_validated_index_sdi.py         (first, builds the SDI models)
    python code/12_manuscript_numbers.py
"""

import argparse
import json
import os
import sys
import re
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import statsmodels.api as sm

import model_spec
from statsmodels.genmod.families import NegativeBinomial
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE_DIR, "data", "processed")
RAW = os.path.join(BASE_DIR, "data", "raw")
OUT = os.path.join(BASE_DIR, "output", "validation")
RESULTS = os.path.join(BASE_DIR, "output", "results")
# MANUSCRIPT_OVERRIDE lets the gate run against the finalized submission file
# without editing this script. See tools/finalize_manuscript.py --validate.
MANUSCRIPT = os.environ.get(
    "MANUSCRIPT_OVERRIDE",
    os.path.join(BASE_DIR, "manuscript", "manuscript_CLEAN.docx"))
os.makedirs(OUT, exist_ok=True)

ALPHA = 1.0
MIN_ADULTS = 1000


# --------------------------------------------------------------------- loading
def load():
    df = pd.read_csv(os.path.join(PROC, "county_analytic_dataset.csv"),
                     dtype={"county_fips": str})
    df["county_fips"] = df["county_fips"].str.zfill(5)
    edi = pd.read_csv(os.path.join(PROC, "county_edi_constructed.csv"),
                      dtype={"fips": str})
    edi["fips"] = edi["fips"].str.zfill(5)
    m = df.merge(edi, left_on="county_fips", right_on="fips", how="left")
    m["svi_pct100"] = m["svi_percentile"] * 100.0
    return m


def nb(d, outcome, terms):
    X = sm.add_constant(d[terms], has_constant="add")
    return sm.GLM(d[outcome], X, family=NegativeBinomial(alpha=ALPHA),
                  offset=np.log(d["adult_pop_45plus"])).fit()


def est(model, term):
    lo, hi = np.exp(model.conf_int().loc[term])
    return {"irr": float(np.exp(model.params[term])),
            "ci_low": float(lo), "ci_high": float(hi),
            "p": float(model.pvalues[term])}


# ---------------------------------------------------------------- computations
def descriptives(m):
    el = m[m.rate_excluded == 0]
    metro, nonmetro = m[m.metro_indicator == 1], m[m.metro_indicator == 0]
    neither = (m.cmr_facility_count == 0) & (m.cct_facility_count == 0)
    neither_el = (el.cmr_facility_count == 0) & (el.cct_facility_count == 0)
    return {
        "total_counties": int(len(m)),
        "cmr_facilities": int(m.cmr_facility_count.sum()),
        "cct_facilities": int(m.cct_facility_count.sum()),
        "counties_with_cmr": int((m.cmr_facility_count > 0).sum()),
        "counties_with_cmr_pct": float(100 * (m.cmr_facility_count > 0).mean()),
        "counties_with_cct": int((m.cct_facility_count > 0).sum()),
        "counties_with_cct_pct": float(100 * (m.cct_facility_count > 0).mean()),
        "counties_neither": int(neither.sum()),
        "counties_neither_pct": float(100 * neither.mean()),
        "metro_counties": int(len(metro)),
        "metro_counties_pct": float(100 * len(metro) / len(m)),
        "nonmetro_counties": int(len(nonmetro)),
        "pct_cmr_in_metro": float(100 * metro.cmr_facility_count.sum() / m.cmr_facility_count.sum()),
        "pct_cct_in_metro": float(100 * metro.cct_facility_count.sum() / m.cct_facility_count.sum()),
        "adults_45plus_total_millions": float(m.adult_pop_45plus.sum() / 1e6),
        "rate_eligible_n": int(len(el)),
        "rate_excluded_n": int((m.rate_excluded == 1).sum()),
        "metro_cmr_mean_rate": float(el.loc[el.metro_indicator == 1, "cmr_rate_per_100k"].mean()),
        "nonmetro_cmr_mean_rate": float(el.loc[el.metro_indicator == 0, "cmr_rate_per_100k"].mean()),
        "metro_cct_mean_rate": float(el.loc[el.metro_indicator == 1, "cct_rate_per_100k"].mean()),
        "nonmetro_cct_mean_rate": float(el.loc[el.metro_indicator == 0, "cct_rate_per_100k"].mean()),
        "mean_edi_no_facility": float(el.loc[neither_el, "edi_national_percentile"].mean()),
        "mean_edi_has_facility": float(el.loc[~neither_el, "edi_national_percentile"].mean()),
    }


def table1(m):
    el = m[m.rate_excluded == 0].copy()
    rows = {}

    def block(d):
        return {"counties": int(len(d)),
                "adults_millions": float(d.adult_pop_45plus.sum() / 1e6),
                "cmr_facilities": int(d.cmr_facility_count.sum()),
                "counties_ge1_cmr": int((d.cmr_facility_count > 0).sum()),
                "counties_ge1_cmr_pct": float(100 * (d.cmr_facility_count > 0).mean()),
                "cct_facilities": int(d.cct_facility_count.sum()),
                "counties_ge1_cct": int((d.cct_facility_count > 0).sum()),
                "counties_ge1_cct_pct": float(100 * (d.cct_facility_count > 0).mean())}

    rows["all_counties"] = block(m)
    rows["metropolitan"] = block(m[m.metro_indicator == 1])
    rows["nonmetropolitan"] = block(m[m.metro_indicator == 0])
    q = pd.qcut(el.edi_national_percentile, 5, labels=False)
    for i in range(5):
        rows[f"edi_q{i + 1}"] = block(el[q == i])
    rows["_note"] = ("Rurality strata use all counties. EDI quintiles are restricted to "
                     "rate-eligible counties with an EDI value.")
    return rows


def regressions(m):
    # Primary sample: every county with the index and a positive population.
    # The <1,000-adult rule governs rate calculations, not count regressions.
    svi = m[(m.adult_pop_45plus > 0)].copy()
    svi["svi_per10"] = svi.svi_pct100 / 10.0
    d_edi = svi.dropna(subset=["edi_national_percentile"]).copy()
    d_edi["edi_per10"] = d_edi.edi_national_percentile / 10.0
    # Sensitivity sample: the previous rate-eligible restriction.
    svi_re = svi[svi.rate_excluded == 0].copy()
    edi_re = d_edi[d_edi.rate_excluded == 0].copy()

    def prim(d, col, terms):
        return model_spec.fit_primary_terms(d, col, terms)

    out = {"n_svi": int(len(svi)), "n_edi": int(len(d_edi)),
           "n_svi_rate_eligible": int(len(svi_re)),
           "n_edi_rate_eligible": int(len(edi_re)),
           "specification": model_spec.PRIMARY_LABEL,
           "models": {}, "sensitivity_fixed_alpha": {},
           "sensitivity_rate_eligible": {}}
    for idx, d, dre, term in [("SVI", svi, svi_re, "svi_per10"),
                              ("EDI", d_edi, edi_re, "edi_per10")]:
        for mod, col in [("CMR", "cmr_facility_count"), ("CCT", "cct_facility_count")]:
            key = f"{idx}_{mod}"
            un = prim(d, col, [term])
            ad = prim(d, col, [term, "metro_indicator"])
            ru = prim(d, col, [term, "rucc_code"])
            out["models"][key] = {
                "unadjusted": est(un, term),
                "adjusted_metro": est(ad, term),
                "metro_effect": est(ad, "metro_indicator"),
                "adjusted_rucc": est(ru, term),
                "rucc_effect": est(ru, "rucc_code"),
                "alpha_adjusted": model_spec.alpha_of(ad),
            }
            out["sensitivity_fixed_alpha"][key] = {
                "unadjusted": est(nb(d, col, [term]), term),
                "adjusted_metro": est(nb(d, col, [term, "metro_indicator"]), term),
                "metro_effect": est(nb(d, col, [term, "metro_indicator"]), "metro_indicator"),
            }
            out["sensitivity_rate_eligible"][key] = {
                "unadjusted": est(prim(dre, col, [term]), term),
                "adjusted_metro": est(prim(dre, col, [term, "metro_indicator"]), term),
                "n": int(len(dre)),
            }
            if idx == "EDI":
                for lab, flag in [("metro", 1), ("nonmetro", 0)]:
                    sub = d[d.metro_indicator == flag]
                    strat = est(prim(sub, col, [term]), term)
                    strat["estimable"] = bool(
                        not (pd.isna(strat["ci_low"]) or pd.isna(strat["ci_high"])
                             or pd.isna(strat["p"])))
                    out["models"][key][f"stratified_{lab}"] = strat
                    out["models"][key][f"stratified_{lab}_n"] = int(len(sub))
                    out["models"][key][f"stratified_{lab}_events"] = int(sub[col].sum())
    return out


def model_diagnostics(m):
    """
    Evidence for the modelling choices, so they can be checked rather than taken
    on trust: overdispersion of the outcomes, negative binomial versus Poisson,
    and sensitivity to fixing the dispersion parameter at alpha = 1.
    """
    from statsmodels.genmod.families import Poisson
    from statsmodels.discrete.discrete_model import NegativeBinomial as NBMLE

    el = m[m.rate_excluded == 0].copy()
    el["svi_per10"] = el.svi_pct100 / 10.0
    el["log_pop"] = np.log(el.adult_pop_45plus)
    d_edi = el.dropna(subset=["edi_national_percentile"]).copy()
    d_edi["edi_per10"] = d_edi.edi_national_percentile / 10.0

    out = {"overdispersion": {}, "aic_nb_vs_poisson": {}, "alpha_sensitivity": {}}

    for col in ["cmr_facility_count", "cct_facility_count"]:
        mu, var = float(el[col].mean()), float(el[col].var())
        out["overdispersion"][col] = {
            "mean": mu, "variance": var, "variance_to_mean_ratio": var / mu,
            "pct_zero": float(100 * (el[col] == 0).mean()),
        }

    for idx, d, term in [("SVI", el, "svi_per10"), ("EDI", d_edi, "edi_per10")]:
        for mod, col in [("CMR", "cmr_facility_count"), ("CCT", "cct_facility_count")]:
            for lab, terms in [("unadjusted", [term]), ("adjusted", [term, "metro_indicator"])]:
                X = sm.add_constant(d[terms], has_constant="add")
                nbf = sm.GLM(d[col], X, family=NegativeBinomial(alpha=ALPHA),
                             offset=d.log_pop).fit()
                pof = sm.GLM(d[col], X, family=Poisson(), offset=d.log_pop).fit()
                out["aic_nb_vs_poisson"][f"{idx}_{mod}_{lab}"] = {
                    "aic_negative_binomial": float(nbf.aic),
                    "aic_poisson": float(pof.aic),
                    "poisson_pearson_dispersion": float(pof.pearson_chi2 / pof.df_resid),
                    "nb_irr": float(np.exp(nbf.params[term])),
                    "nb_p": float(nbf.pvalues[term]),
                    "poisson_irr": float(np.exp(pof.params[term])),
                    "poisson_p": float(pof.pvalues[term]),
                }

    # Fixed alpha = 1 versus alpha estimated by maximum likelihood, primary models
    for lab, terms in [("unadjusted", ["edi_per10"]),
                       ("adjusted", ["edi_per10", "metro_indicator"])]:
        X = sm.add_constant(d_edi[terms], has_constant="add")
        fixed = sm.GLM(d_edi.cmr_facility_count, X,
                       family=NegativeBinomial(alpha=ALPHA), offset=d_edi.log_pop).fit()
        mle = NBMLE(d_edi.cmr_facility_count, X, offset=d_edi.log_pop.values).fit(disp=0)
        block = {
            "fixed_alpha_1": {"irr": float(np.exp(fixed.params["edi_per10"])),
                              "p": float(fixed.pvalues["edi_per10"])},
            "estimated_alpha": {"irr": float(np.exp(mle.params["edi_per10"])),
                                "p": float(mle.pvalues["edi_per10"]),
                                "alpha": float(mle.params["alpha"])},
        }
        if "metro_indicator" in terms:
            block["fixed_alpha_1"]["metro_irr"] = float(np.exp(fixed.params["metro_indicator"]))
            block["estimated_alpha"]["metro_irr"] = float(np.exp(mle.params["metro_indicator"]))
        out["alpha_sensitivity"][f"EDI_CMR_{lab}"] = block

    out["_interpretation"] = (
        "Both outcomes are overdispersed (variance-to-mean ratio well above 1), which "
        "is why negative binomial is used. The Poisson Pearson dispersion statistic is "
        "below 1 here because most fitted means are far below 1; it is unreliable for "
        "sparse counts and the AIC comparison is the informative one. Negative binomial "
        "wins on AIC in six of eight models, decisively for the primary CMR outcome. "
        "For the two adjusted CCT models Poisson has marginally lower AIC and yields "
        "nominally significant deprivation terms, but those estimates are above 1, that "
        "is, more capacity with more deprivation, so they do not support a "
        "deprivation-disadvantage reading under either family. Conclusions are unchanged "
        "when alpha is estimated rather than fixed at 1."
    )
    return out


def correlations(m):
    el = m[m.rate_excluded == 0]
    v = m[["svi_percentile", "edi_national_percentile"]].dropna()
    pr, pp = stats.pearsonr(v.svi_percentile, v.edi_national_percentile)
    sr, sp = stats.spearmanr(v.svi_percentile, v.edi_national_percentile)
    out = {
        "svi_edi_pearson_r": float(pr), "svi_edi_pearson_p": float(pp),
        "svi_edi_spearman_rho": float(sr), "svi_edi_spearman_p": float(sp),
        "svi_edi_n": int(len(v)),
    }
    for lab, col in [("cmr", "cmr_rate_per_100k"), ("cct", "cct_rate_per_100k")]:
        r, p = stats.spearmanr(el[col], el.svi_percentile)
        out[f"svi_{lab}_spearman_rho"] = float(r)
        out[f"svi_{lab}_spearman_p"] = float(p)
        r, p = stats.spearmanr(el[col], el.edi_national_percentile)
        out[f"edi_{lab}_spearman_rho"] = float(r)
        out[f"edi_{lab}_spearman_p"] = float(p)
    mw_cmr = stats.mannwhitneyu(el.loc[el.metro_indicator == 1, "cmr_rate_per_100k"],
                                el.loc[el.metro_indicator == 0, "cmr_rate_per_100k"])
    mw_cct = stats.mannwhitneyu(el.loc[el.metro_indicator == 1, "cct_rate_per_100k"],
                                el.loc[el.metro_indicator == 0, "cct_rate_per_100k"])
    out["metro_vs_nonmetro_cmr_mannwhitney_p"] = float(mw_cmr.pvalue)
    out["metro_vs_nonmetro_cct_mannwhitney_p"] = float(mw_cct.pvalue)
    return out


def quintile_gradient(m):
    el = m[m.rate_excluded == 0].dropna(subset=["edi_national_percentile"]).copy()
    q = pd.qcut(el.edi_national_percentile, 5, labels=False)
    means = [float(el.loc[q == i, "cmr_rate_per_100k"].mean()) for i in range(5)]
    cct = [float(el.loc[q == i, "cct_rate_per_100k"].mean()) for i in range(5)]
    kw = stats.kruskal(*[el.loc[q == i, "cmr_rate_per_100k"].values for i in range(5)])
    return {"cmr_rate_by_edi_quintile": means,
            "cct_rate_by_edi_quintile": cct,
            "q1_over_q5_ratio": float(means[0] / means[4]),
            "kruskal_p_cmr": float(kw.pvalue),
            # Q1 > Q2 > Q3 > Q4 > Q5 at every step. The manuscript must not
            # describe the decline as monotonic unless this is True; it is not,
            # because Q3 exceeds Q2.
            "cmr_monotonic_decreasing": all(means[i] > means[i + 1] for i in range(4)),
            # Unweighted mean of county-level rates, which is what the paper
            # reports. The population-weighted (pooled) ratio is much smaller
            # because most counties with any facility are small.
            "q1_over_q5_ratio_pooled": float(
                (el.loc[q == 0, "cmr_facility_count"].sum()
                 / el.loc[q == 0, "adult_pop_45plus"].sum())
                / (el.loc[q == 4, "cmr_facility_count"].sum()
                   / el.loc[q == 4, "adult_pop_45plus"].sum())),
            "quintile_rate_definition": "unweighted mean of county-level rates"}


def pca_variance():
    svi = pd.read_csv(os.path.join(RAW, "SVI_2022_US_county.csv"))
    svi["fips"] = svi["FIPS"].astype(str).str.zfill(5)
    chr_df = pd.read_csv(os.path.join(RAW, "county_health_rankings_2024.csv"),
                         encoding="latin1", low_memory=False).iloc[1:]
    chr_df["fips"] = chr_df["5-digit FIPS Code"].astype(str).str.zfill(5)
    chr_df = chr_df[chr_df["County FIPS Code"] != "000"]
    cs = chr_df[["fips", "Median Household Income raw value",
                 "Children in Poverty raw value"]].copy()
    cs.columns = ["fips", "median_income", "child_poverty"]
    for c in ["median_income", "child_poverty"]:
        cs[c] = pd.to_numeric(cs[c], errors="coerce")
    mg = svi[["fips", "EP_POV150", "EP_UNEMP", "EP_NOHSDP", "EP_HBURD"]].merge(cs, on="fips", how="left")
    dd = mg.dropna().copy()
    dd["neg_income"] = -dd.median_income
    feats = ["EP_POV150", "EP_UNEMP", "EP_NOHSDP", "EP_HBURD", "neg_income", "child_poverty"]
    p = PCA(n_components=1).fit(StandardScaler().fit_transform(dd[feats]))
    return {"pca_variance_explained": float(p.explained_variance_ratio_[0]),
            "pca_n_counties": int(len(dd)),
            "pca_features": feats}


# ------------------------------------------------------------------- reporting
NOT_ESTIMABLE = "NE"


def _estimable(e):
    """A fit can return a point estimate with no usable CI when events are very
    sparse. Report that honestly rather than printing nan or borrowing a CI
    from a different specification."""
    return not (pd.isna(e.get("ci_low")) or pd.isna(e.get("ci_high"))
                or pd.isna(e.get("p")))


def fmt_est(e, dp=2):
    if pd.isna(e["irr"]):
        return NOT_ESTIMABLE
    if not _estimable(e):
        return f"{e['irr']:.{dp}f} ({NOT_ESTIMABLE})"
    return f"{e['irr']:.{dp}f} ({e['ci_low']:.{dp}f}-{e['ci_high']:.{dp}f})"


def fmt_p(p):
    if pd.isna(p):
        return NOT_ESTIMABLE
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def write_report(R):
    L = []
    a = L.append
    a("=" * 78)
    a("MANUSCRIPT NUMBERS, RECOMPUTED FROM THE COMMITTED DATA")
    a("=" * 78)
    a("Primary model: negative binomial (NB2), dispersion ESTIMATED from the data,")
    a("offset log(adults 45+), index per 10 percentile points.")
    a("Count regressions retain every county with the index and a positive")
    a("population. The <1,000-adult rule governs per-capita RATE calculations only.")
    a("Fixed alpha = 1.0 and the rate-eligible restriction are reported as")
    a("sensitivities under regressions.sensitivity_* in the JSON.")
    a("NE = not estimable (sparse events; point estimate shown without inference).")
    a("")
    d = R["descriptives"]
    a("-" * 78)
    a("DESCRIPTIVES")
    a("-" * 78)
    a(f"  Counties                                  {d['total_counties']:,}")
    a(f"  Accredited CMR facilities                 {d['cmr_facilities']:,}")
    a(f"  Accredited CCT facilities                 {d['cct_facilities']:,}")
    a(f"  Counties with >=1 CMR                     {d['counties_with_cmr']:,} ({d['counties_with_cmr_pct']:.1f}%)")
    a(f"  Counties with >=1 CCT                     {d['counties_with_cct']:,} ({d['counties_with_cct_pct']:.1f}%)")
    a(f"  Counties with neither modality            {d['counties_neither']:,} ({d['counties_neither_pct']:.1f}%)")
    a(f"  Metropolitan counties                     {d['metro_counties']:,} ({d['metro_counties_pct']:.1f}%)")
    a(f"  Share of CMR facilities in metro          {d['pct_cmr_in_metro']:.1f}%")
    a(f"  Share of CCT facilities in metro          {d['pct_cct_in_metro']:.1f}%")
    a(f"  Adults aged 45+                           {d['adults_45plus_total_millions']:.1f} million")
    a(f"  Rate-eligible counties                    {d['rate_eligible_n']:,} "
      f"(excluded {d['rate_excluded_n']:,})")
    a(f"  Mean CMR rate, metro vs nonmetro          {d['metro_cmr_mean_rate']:.4f} vs {d['nonmetro_cmr_mean_rate']:.4f}")
    a(f"  Mean CCT rate, metro vs nonmetro          {d['metro_cct_mean_rate']:.4f} vs {d['nonmetro_cct_mean_rate']:.4f}")
    a(f"  Mean EDI, no facility vs facility         {d['mean_edi_no_facility']:.1f} vs {d['mean_edi_has_facility']:.1f}")
    a("")
    a("-" * 78)
    a("REGRESSION MODELS  (manuscript Tables 2 and 3)")
    a("-" * 78)
    a(f"  Analytic sample: SVI n = {R['regressions']['n_svi']:,}, EDI n = {R['regressions']['n_edi']:,}")
    a("")
    a(f"  {'Model':<44}{'IRR (95% CI)':>22}{'P':>10}")
    a("  " + "." * 74)
    for key in ["SVI_CMR", "EDI_CMR", "SVI_CCT", "EDI_CCT"]:
        blk = R["regressions"]["models"][key]
        idx, mod = key.split("_")
        for lab, sub in [("unadjusted", "unadjusted"),
                         ("adjusted for metropolitan status", "adjusted_metro"),
                         ("adjusted for ordinal RUCC", "adjusted_rucc")]:
            a(f"  {idx + ', ' + mod + ', ' + lab:<44}{fmt_est(blk[sub]):>22}{fmt_p(blk[sub]['p']):>10}")
        a(f"  {idx + ', ' + mod + ', metropolitan status term':<44}"
          f"{fmt_est(blk['metro_effect']):>22}{fmt_p(blk['metro_effect']['p']):>10}")
        a(f"  {idx + ', ' + mod + ', ordinal RUCC term':<44}"
          f"{fmt_est(blk['rucc_effect']):>22}{fmt_p(blk['rucc_effect']['p']):>10}")
        for lab in ["metro", "nonmetro"]:
            if f"stratified_{lab}" in blk:
                e = blk[f"stratified_{lab}"]
                a(f"  {idx + ', ' + mod + ', ' + lab + ' counties only':<44}{fmt_est(e):>22}{fmt_p(e['p']):>10}"
                  f"   n={blk[f'stratified_{lab}_n']:,}, {blk[f'stratified_{lab}_events']} facilities")
        a("")
    c = R["correlations"]
    a("-" * 78)
    a("CORRELATIONS")
    a("-" * 78)
    a(f"  SVI vs EDI, Pearson r                     {c['svi_edi_pearson_r']:.4f} (n = {c['svi_edi_n']:,})")
    a(f"  SVI vs EDI, Spearman rho                  {c['svi_edi_spearman_rho']:.4f}")
    a(f"  SVI vs CMR rate, Spearman rho             {c['svi_cmr_spearman_rho']:.4f} (P = {c['svi_cmr_spearman_p']:.3f})")
    a(f"  SVI vs CCT rate, Spearman rho             {c['svi_cct_spearman_rho']:.4f} (P = {c['svi_cct_spearman_p']:.3f})")
    a("")
    g = R["quintiles"]
    a("-" * 78)
    a("EDI QUINTILE GRADIENT")
    a("-" * 78)
    a("  Mean CMR rate per 100,000 by EDI quintile, Q1 (least deprived) to Q5:")
    a("    " + "  ".join(f"{x:.4f}" for x in g["cmr_rate_by_edi_quintile"]))
    a(f"  Q1 / Q5 ratio                             {g['q1_over_q5_ratio']:.2f}-fold")
    a(f"  Kruskal-Wallis P                          {fmt_p(g['kruskal_p_cmr'])}")
    a("")
    p = R["pca"]
    a("-" * 78)
    a("EDI CONSTRUCTION")
    a("-" * 78)
    a(f"  First principal component explains        {p['pca_variance_explained'] * 100:.1f}% of variance")
    a(f"  Counties with a complete indicator set    {p['pca_n_counties']:,}")
    a("")
    md = R["model_diagnostics"]
    a("-" * 78)
    a("MODEL DIAGNOSTICS  (justification for the specification)")
    a("-" * 78)
    for col, v in md["overdispersion"].items():
        a(f"  {col:<26} mean {v['mean']:.4f}, variance {v['variance']:.4f}, "
          f"ratio {v['variance_to_mean_ratio']:.2f}, {v['pct_zero']:.1f}% zero")
    nb_wins = sum(1 for v in md["aic_nb_vs_poisson"].values()
                  if v["aic_negative_binomial"] < v["aic_poisson"])
    a(f"  Negative binomial beats Poisson on AIC in {nb_wins} of "
      f"{len(md['aic_nb_vs_poisson'])} models.")
    a("  Sensitivity to fixing alpha at 1.0, primary EDI-CMR models:")
    for k, v in md["alpha_sensitivity"].items():
        a(f"    {k:<22} alpha=1.0 IRR {v['fixed_alpha_1']['irr']:.4f} "
          f"(P {v['fixed_alpha_1']['p']:.4f})   alpha estimated "
          f"IRR {v['estimated_alpha']['irr']:.4f} (P {v['estimated_alpha']['p']:.4f}, "
          f"alpha {v['estimated_alpha']['alpha']:.3f})")
    a("")
    if R.get("sdi"):
        s = R["sdi"]
        a("-" * 78)
        a("EXTERNAL VALIDATION  (manuscript Table 4)")
        a("-" * 78)
        a(f"  SDI matched {s['sdi_matched_counties']:,} of {s['total_counties']:,} counties")
        a(f"  SDI vs EDI agreement, Spearman rho        {s['agreement_with_EDI']['spearman_rho']:.4f}")
        a(f"  EDI tracks rurality, Spearman vs RUCC     {s['rurality_link']['EDI']['spearman_vs_rucc']:.4f}"
          f"  (gap {s['rurality_link']['EDI']['gap']:.1f} points)")
        a(f"  SDI tracks rurality, Spearman vs RUCC     {s['rurality_link']['SDI']['spearman_vs_rucc']:.4f}"
          f"  (gap {s['rurality_link']['SDI']['gap']:.1f} points)")
        a("")
    return "\n".join(L)


# ------------------------------------------------------------- manuscript check
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = lambda t: f"{{{W_NS}}}{t}"


def _accepted_para(p):
    """
    Text of one paragraph with all tracked changes accepted.

    The manuscript carries tracked changes, so the raw text python-docx returns
    would include deleted words. What the paper actually says is the accepted
    state: keep w:t (including inside w:ins), drop anything inside w:del.
    """
    buf = []
    for node in p.iter(_W("t")):
        if any(a.tag == _W("del") for a in node.iterancestors()):
            continue
        buf.append(node.text or "")
    return re.sub(r"\s+", " ", "".join(buf)).strip()


def read_manuscript(path):
    """Return (prose, tables) in the accepted state, reading the XML directly."""
    import zipfile
    from lxml import etree
    root = etree.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    body = root.find(_W("body"))

    prose_parts, tables = [], []
    for el in body.iter(_W("p"), _W("tbl")):
        if el.tag == _W("p"):
            # skip paragraphs whose paragraph mark is deleted, and table cells
            if any(a.tag == _W("tbl") for a in el.iterancestors()):
                continue
            pPr = el.find(_W("pPr"))
            rPr = pPr.find(_W("rPr")) if pPr is not None else None
            if rPr is not None and rPr.find(_W("del")) is not None:
                continue
            t = _accepted_para(el)
            if t:
                prose_parts.append(t)
        else:
            rows = []
            for tr in el.findall(_W("tr")):
                trPr = tr.find(_W("trPr"))
                if trPr is not None and trPr.find(_W("del")) is not None:
                    continue  # row deleted
                cells = []
                for tc in tr.findall(_W("tc")):
                    cells.append(" ".join(filter(None,
                                 (_accepted_para(p) for p in tc.findall(_W("p"))))).strip())
                rows.append(cells)
            tables.append(rows)
    return re.sub(r"\s+", " ", " ".join(prose_parts)), tables


def _parse_table(rows):
    """
    Return {(section, row_label): [cell texts]} for a manuscript table.

    Section headers are rows whose only non-empty cell is the first one, e.g.
    "Cardiac MR". They are needed because row labels such as
    "SVI, per 10 percentile" appear once under each modality.
    """
    out, section = {}, ""
    for cells in rows:
        if not cells:
            continue
        label = cells[0].strip()
        rest = [c.strip() for c in cells[1:]]
        if label and not any(rest):
            section = label
            continue
        if label:
            out[(section, label)] = [c.strip() for c in cells]
    return out


# ---------------------------------------------------------------------------
# Obsolete values and statements that must NOT appear in the manuscript.
#
# The gate previously checked only that each correct value appeared somewhere.
# That is a one-sided test: a stale duplicate elsewhere in the document passed
# unnoticed, and eight pre-HUD values survived a "0 mismatches" run. Each entry
# below is a value or phrase that was correct at some earlier stage and is now
# wrong, so its presence anywhere in the text is a failure.
#
# Add to this list whenever a published value changes.
# ---------------------------------------------------------------------------
FORBIDDEN = [
    # Pre-HUD facility and county counts
    (r"\b687\b", "pre-HUD CMR facility total (now 722)"),
    (r"\b1,481\b", "pre-HUD CCT facility total (now 1,542)"),
    (r"\b701\b", "intermediate CMR facility total (now 722)"),
    (r"\b1,499\b", "intermediate CCT facility total (now 1,542)"),
    (r"\b289 of|\b289 counties", "pre-HUD counties with >=1 CMR (now 300)"),
    (r"\b532 \(16\.9|\b532 counties", "pre-HUD counties with >=1 CCT (now 552)"),
    (r"\b2,583\b", "pre-HUD counties-with-neither (now 2,570)"),
    (r"\b2,577\b", "intermediate counties-with-neither (now 2,570)"),
    (r"\b289 \(9\.2", "pre-HUD counties with >=1 CMR"),
    (r"\b532 \(16\.9", "pre-HUD counties with >=1 CCT"),
    (r"82\.2%", "pre-HUD share with neither modality"),
    (r"92\.4%", "pre-HUD share of CCT in metropolitan counties"),
    # Pre-HUD EDI quintile results
    (r"4\.4-fold", "pre-HUD Q1/Q5 ratio (now 2.9-fold)"),
    (r"fell monotonically|monotonic (decline|decrease|gradient)",
     "the EDI quintile means are not monotonic"),
    # Superseded model values
    (r"0\.95-1\.03", "pre-HUD SVI-CMR unadjusted CI"),
    (r"P = 0\.665", "pre-HUD Spearman CMR P value"),
    (r"P = 0\.268", "pre-HUD Spearman CCT P value"),
    # Categorical null language the estimated-dispersion result does not support
    (r"SVI was not associated with capacity for either modality",
     "categorical null claim; SVI-CCT is associated under the primary model"),
    # Superseded provenance
    (r"accessed 2024", "ACR registry was extracted 2026-05-20"),
    (r"SciPy 1\.11", "results were produced under SciPy 1.13"),
    (r"\bADI\b", "the index was renamed EDI"),
    # Superseded analytic sample and specification
    (r"n = 3,038|3,038 counties", "pre-decision SVI sample (count models now n = 3,144)"),
    (r"n = 3,029|3,029 \(EDI\)|Analytic sample: 3,029",
     "pre-decision EDI regression sample (count models now n = 3,134). "
     "3,029 remains correct as the quintile/rate-eligible denominator"),
    (r"3,027 \(SDI\)|3,027 counties", "pre-decision SDI sample (now 3,133)"),
    (r"≥48 years|>=48 years", "typo; the denominator is adults aged 45 and older"),
    # Categorical null claims the primary model does not support
    (r"neither index was associated with capacity",
     "the adjusted SVI-CCT association is positive and significant"),
    (r"SDI was not associated with (CMR|CCT) capacity either before adjustment",
     "the adjusted SDI associations are significant; see Table 4"),
    # Non-estimable inference must never be published as nan
    (r"\bnan\b|nan-nan", "non-estimable inference must be reported as NE"),
    # Superseded stratified and metropolitan estimates
    (r"0\.57-0\.92", "fixed-alpha nonmetropolitan CI; that row is not estimable"),
    (r"8\.44 \(95% CI 4\.80-14\.83\)|1\.94 \(95% CI 1\.55-2\.42\)",
     "pre-decision SVI metropolitan estimates"),
    (r"8\.23, 95% CI, 4\.65-14\.56|1\.96, 95% CI, 1\.56-2\.47",
     "pre-decision EDI metropolitan estimates"),
    (r"13 accredited CMR facilities|only 13 accredited",
     "the nonmetropolitan CMR stratum contains 14 facilities"),
    # Blanket null claims anywhere in the paper. The adjusted SVI-CCT
    # association is positive and significant under the primary model, so a
    # statement that deprivation indices were not associated with capacity
    # "either way" or "independently" contradicts Table 2 wherever it appears.
    (r"(deprivation|SVI|EDI|indices?)[^.]{0,80}not independently associated",
     "adjusted SVI-CCT is positive and significant; qualify by modality"),
    (r"neither (index|the SVI nor)[^.]{0,60}associated with capacity",
     "adjusted SVI-CCT is positive and significant; qualify by modality"),
    (r"no (index|deprivation measure) was associated with capacity",
     "adjusted SVI-CCT is positive and significant; qualify by modality"),
]


def check_manuscript(R):
    """
    Compare the .docx against the recomputed values, cell by cell.

    Table values are located by (section, row label, column) rather than by
    searching the whole document, because a substring search reports a value as
    present when the identical string happens to occur in a different table.
    """
    if not os.path.exists(MANUSCRIPT):
        return (f"Manuscript not found at {MANUSCRIPT}\n"
                "(The manuscript/ folder is not tracked in git. Check skipped.)\n")

    prose, doc_tables = read_manuscript(MANUSCRIPT)

    d, reg, c, g, pc = (R["descriptives"], R["regressions"], R["correlations"],
                        R["quintiles"], R["pca"])
    M, T1 = reg["models"], R["table1"]
    checks = []

    def ck(label, expected, actual):
        checks.append((label, str(expected), str(actual), str(expected) == str(actual)))

    def ck_prose(label, expected, pattern=None):
        pat = pattern or re.escape(str(expected))
        checks.append((label, str(expected), "found in text" if re.search(pat, prose) else "NOT IN TEXT",
                       bool(re.search(pat, prose))))

    # ---- obsolete values and statements that must be absent
    for pattern, why in FORBIDDEN:
        hit = re.search(pattern, prose, re.I)
        checks.append((f"absent: {why}", "absent",
                       f"FOUND {hit.group(0)!r}" if hit else "absent",
                       not hit))

    # ---- prose values
    ck_prose("CMR facilities", d["cmr_facilities"], rf"\b{d['cmr_facilities']}\b")
    ck_prose("CCT facilities", f"{d['cct_facilities']:,}")
    ck_prose("counties with neither",
             f"{d['counties_neither']:,} counties ({d['counties_neither_pct']:.1f}%)",
             rf"{d['counties_neither']:,} counties \({d['counties_neither_pct']:.1f}%\)")
    ck_prose("share CMR in metro", f"{d['pct_cmr_in_metro']:.1f}%")
    ck_prose("share CCT in metro", f"{d['pct_cct_in_metro']:.1f}%")
    ck_prose("mean EDI contrast", f"{d['mean_edi_no_facility']:.1f} vs {d['mean_edi_has_facility']:.1f}")
    ck_prose("SVI analytic n", f"{reg['n_svi']:,}")
    ck_prose("EDI analytic n", f"{reg['n_edi']:,}")
    ck_prose("PCA variance", f"{pc['pca_variance_explained'] * 100:.1f}%")
    ck_prose("SVI-EDI Pearson r", f"{c['svi_edi_pearson_r']:.2f}",
             rf"Pearson r = {c['svi_edi_pearson_r']:.2f}")
    # Mean rates by rurality are quoted in the Results but were never checked,
    # so they silently went stale when the facility mapping was corrected.
    ck_prose("mean CMR rate, metro vs nonmetro",
             f"{d['metro_cmr_mean_rate']:.2f} versus {d['nonmetro_cmr_mean_rate']:.2f}",
             rf"{d['metro_cmr_mean_rate']:.2f} versus {d['nonmetro_cmr_mean_rate']:.2f}")
    ck_prose("mean CCT rate, metro vs nonmetro",
             f"{d['metro_cct_mean_rate']:.2f} versus {d['nonmetro_cct_mean_rate']:.2f}",
             rf"{d['metro_cct_mean_rate']:.2f} versus {d['nonmetro_cct_mean_rate']:.2f}")

    # The Table 1 footnote must quote the quintile denominator, which is the
    # rate-eligible EDI sample, not the larger count-regression sample.
    q_denom = sum(R["table1"][f"edi_q{i}"]["counties"] for i in range(1, 6))
    ck_prose("Table 1 quintile denominator", f"{q_denom:,} counties",
             rf"{q_denom:,} counties with")

    ck_prose("Q1/Q5 gradient", f"{g['q1_over_q5_ratio']:.1f}-fold")
    ck_prose("Q1 CMR rate", f"{g['cmr_rate_by_edi_quintile'][0]:.2f}")
    ck_prose("Q5 CMR rate", f"{g['cmr_rate_by_edi_quintile'][4]:.2f}")

    # Wording check, not a value check. The quintile means are not monotonic
    # (Q3 exceeds Q2), so the paper must not claim that they are. A wrong claim
    # here would pass every numeric check above, which is how it survived an
    # earlier round of review.
    # Matches an affirmative claim ("rates fell monotonically", "a monotonic
    # decline") but not a correct negative one, such as the Spearman result
    # reporting the *absence* of a monotonic relationship.
    if not g["cmr_monotonic_decreasing"]:
        affirmative = re.search(
            r"(fell|declined|decreased|dropped|rose|increased)\s+monotonic"
            r"|monotonic(ally)?\s+(decline|decrease|gradient|reduction)",
            prose, re.I)
        checks.append(("no unsupported monotonicity claim", "absent",
                       f"claims: {affirmative.group(0)!r}" if affirmative else "absent",
                       not affirmative))

    # ---- Table 1
    if len(doc_tables) >= 1:
        t1 = _parse_table(doc_tables[0])
        spec = [("", "All counties", "all_counties"),
                ("Rurality", "Metropolitan (RUCC 1-3)", "metropolitan"),
                ("Rurality", "Nonmetropolitan (RUCC 4-9)", "nonmetropolitan"),
                ("EDI quintile", "Q1 (least deprived)", "edi_q1"),
                ("EDI quintile", "Q2", "edi_q2"),
                ("EDI quintile", "Q3", "edi_q3"),
                ("EDI quintile", "Q4", "edi_q4"),
                ("EDI quintile", "Q5 (most deprived)", "edi_q5")]
        for sect, label, key in spec:
            cells = t1.get((sect, label))
            if cells is None:
                ck(f"T1 {label}", "row present", "ROW NOT FOUND")
                continue
            b = T1[key]
            ck(f"T1 {label} counties", f"{b['counties']:,}", cells[1])
            ck(f"T1 {label} adults", f"{b['adults_millions']:.1f}", cells[2])
            ck(f"T1 {label} CMR fac", f"{b['cmr_facilities']:,}", cells[3])
            ck(f"T1 {label} cty>=1 CMR", f"{b['counties_ge1_cmr']:,} ({b['counties_ge1_cmr_pct']:.1f})", cells[4])
            ck(f"T1 {label} CCT fac", f"{b['cct_facilities']:,}", cells[5])
            ck(f"T1 {label} cty>=1 CCT", f"{b['counties_ge1_cct']:,} ({b['counties_ge1_cct_pct']:.1f})", cells[6])

    # ---- Table 2
    if len(doc_tables) >= 2:
        t2 = _parse_table(doc_tables[1])
        for sect, mod in [("Cardiac MR", "CMR"), ("Cardiac CT", "CCT")]:
            for label, idx in [("SVI, per 10 percentile", "SVI"), ("EDI, per 10 percentile", "EDI")]:
                cells = t2.get((sect, label))
                if cells is None:
                    ck(f"T2 {sect} {idx}", "row present", "ROW NOT FOUND")
                    continue
                blk = M[f"{idx}_{mod}"]
                ck(f"T2 {sect} {idx} unadj", fmt_est(blk["unadjusted"]), cells[1])
                ck(f"T2 {sect} {idx} unadj P", fmt_p(blk["unadjusted"]["p"]), cells[2])
                ck(f"T2 {sect} {idx} adj", fmt_est(blk["adjusted_metro"]), cells[3])
                ck(f"T2 {sect} {idx} adj P", fmt_p(blk["adjusted_metro"]["p"]), cells[4])
            cells = t2.get((sect, "Metropolitan status"))
            if cells:
                ck(f"T2 {sect} metro term", fmt_est(M[f"EDI_{mod}"]["metro_effect"]), cells[3])

    # ---- Table 3
    if len(doc_tables) >= 3:
        t3 = _parse_table(doc_tables[2])
        rucc = "Rurality as ordinal RUCC (1-9)"
        strat = "Stratified by metropolitan status"
        for label, mod in [("Cardiac MR", "CMR"), ("Cardiac CT", "CCT")]:
            cells = t3.get((rucc, label))
            if cells:
                blk = M[f"EDI_{mod}"]
                ck(f"T3 RUCC {label} n", f"{reg['n_edi']:,}", cells[1])
                ck(f"T3 RUCC {label} EDI", fmt_est(blk["adjusted_rucc"]), cells[2])
                ck(f"T3 RUCC {label} P", fmt_p(blk["adjusted_rucc"]["p"]), cells[3])
                ck(f"T3 RUCC {label} term", fmt_est(blk["rucc_effect"]), cells[4])
        for label, mod, lay in [("Cardiac MR, metropolitan", "CMR", "metro"),
                                ("Cardiac MR, nonmetropolitan", "CMR", "nonmetro"),
                                ("Cardiac CT, metropolitan", "CCT", "metro"),
                                ("Cardiac CT, nonmetropolitan", "CCT", "nonmetro")]:
            cells = t3.get((strat, label))
            if cells:
                blk = M[f"EDI_{mod}"]
                ck(f"T3 {label} n", f"{blk[f'stratified_{lay}_n']:,}", cells[1])
                ck(f"T3 {label} EDI", fmt_est(blk[f"stratified_{lay}"]), cells[2])
                ck(f"T3 {label} P", fmt_p(blk[f"stratified_{lay}"]["p"]), cells[3])

    # ---- Table 4
    if len(doc_tables) >= 4 and R.get("sdi"):
        t4 = _parse_table(doc_tables[3])
        E = R["sdi"]["EDI_models"]["outcomes"]
        S = R["sdi"]["SDI_models"]["outcomes"]
        f2 = lambda e: f"{e['IRR']:.2f} ({e['CI_low']:.2f}-{e['CI_high']:.2f})"
        p2 = lambda e: "<0.001" if e["P"] < 0.001 else f"{e['P']:.3f}"
        for sect, oc in [("Cardiac MR", "cmr_facility_count"), ("Cardiac CT", "cct_facility_count")]:
            for label, key in [("Index, unadjusted", "unadjusted"),
                               ("Index, adjusted for metropolitan status", "adjusted"),
                               ("Metropolitan status", "metro_in_adjusted")]:
                cells = t4.get((sect, label))
                if cells is None:
                    ck(f"T4 {sect} {label}", "row present", "ROW NOT FOUND")
                    continue
                ck(f"T4 {sect} {label} EDI", f2(E[oc][key]), cells[1])
                ck(f"T4 {sect} {label} EDI P", p2(E[oc][key]), cells[2])
                ck(f"T4 {sect} {label} SDI", f2(S[oc][key]), cells[3])
                ck(f"T4 {sect} {label} SDI P", p2(S[oc][key]), cells[4])

    bad = [x for x in checks if not x[3]]
    L = ["=" * 78, "MANUSCRIPT vs DATA, CELL BY CELL", "=" * 78,
         f"Document: {os.path.relpath(MANUSCRIPT, BASE_DIR)}",
         f"Checks:   {len(checks)}     Mismatches: {len(bad)}", ""]
    if bad:
        L.append("MISMATCHES")
        L.append("-" * 78)
        for label, exp, act, _ in bad:
            L.append(f"  {label}")
            L.append(f"      data says       : {exp}")
            L.append(f"      manuscript says : {act}")
        L.append("")
    else:
        L.append("  Every checked value in the manuscript matches the data exactly.")
        L.append("")
    L.append("ALL CHECKS")
    L.append("-" * 78)
    for label, exp, act, ok in checks:
        L.append(f"  {'ok  ' if ok else 'FAIL'}  {label:<34} {exp}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="Recompute every manuscript number and check a manuscript "
                    "against the data.")
    ap.add_argument("manuscript", nargs="?", default=MANUSCRIPT,
                    help="path to the .docx to check. Defaults to the working "
                         "file, or MANUSCRIPT_OVERRIDE if set. Point this at "
                         "manuscript_SUBMISSION.docx to prove the submitted "
                         "file passes.")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if any check fails")
    args = ap.parse_args()
    globals()["MANUSCRIPT"] = args.manuscript

    m = load()
    R = {
        "descriptives": descriptives(m),
        "table1": table1(m),
        "regressions": regressions(m),
        "correlations": correlations(m),
        "model_diagnostics": model_diagnostics(m),
        "quintiles": quintile_gradient(m),
        "pca": pca_variance(),
    }
    sdi_path = os.path.join(RESULTS, "index_comparison_results.json")
    if os.path.exists(sdi_path):
        with open(sdi_path) as f:
            R["sdi"] = json.load(f)

    with open(os.path.join(OUT, "manuscript_numbers.json"), "w") as f:
        json.dump(R, f, indent=2)
    report = write_report(R)
    with open(os.path.join(OUT, "manuscript_numbers.txt"), "w") as f:
        f.write(report + "\n")
    print(report)

    check = check_manuscript(R)
    with open(os.path.join(OUT, "manuscript_check.txt"), "w") as f:
        f.write(check)
    print(check)
    print(f"Wrote {os.path.relpath(OUT, BASE_DIR)}/manuscript_numbers.json, .txt and manuscript_check.txt")

    mismatches = int(re.search(r"Mismatches:\s+(\d+)", check).group(1)) \
        if "Mismatches:" in check else 0
    if args.strict and mismatches:
        print(f"\nFAILED: {mismatches} mismatch(es) against "
              f"{os.path.relpath(MANUSCRIPT, BASE_DIR)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
