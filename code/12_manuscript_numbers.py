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
import datetime as _dt
import hashlib
import json
import os
import subprocess
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
        # The text reports this contrast with a P value; compute it rather than
        # carry it by hand (Mann-Whitney U, as for the other two-group tests).
        "mean_edi_contrast_mannwhitney_p": float(stats.mannwhitneyu(
            el.loc[neither_el, "edi_national_percentile"].dropna(),
            el.loc[~neither_el, "edi_national_percentile"].dropna()).pvalue),
    }


def table1(m):
    el = m[m.rate_excluded == 0].copy()
    rows = {}
    # Facility percentages use the national total of each modality as the
    # denominator (revision R2-04), so every row reads as a share of all
    # accredited capacity. County percentages keep the row's own county count.
    tot_cmr, tot_cct = int(m.cmr_facility_count.sum()), int(m.cct_facility_count.sum())

    def block(d):
        # Counts use every county in the stratum. Mean rates use only the
        # rate-eligible subset: a rate on fewer than 1,000 adults aged 45+ is
        # defined but unstable, so those counties are left out of the means.
        r = d[d.rate_excluded == 0]
        return {"counties": int(len(d)),
                "adults_millions": float(d.adult_pop_45plus.sum() / 1e6),
                "cmr_facilities": int(d.cmr_facility_count.sum()),
                "cmr_facilities_pct": float(100 * d.cmr_facility_count.sum() / tot_cmr),
                "counties_ge1_cmr": int((d.cmr_facility_count > 0).sum()),
                "counties_ge1_cmr_pct": float(100 * (d.cmr_facility_count > 0).mean()),
                "cmr_rate_mean": float(r.cmr_rate_per_100k.mean()),
                "cct_facilities": int(d.cct_facility_count.sum()),
                "cct_facilities_pct": float(100 * d.cct_facility_count.sum() / tot_cct),
                "counties_ge1_cct": int((d.cct_facility_count > 0).sum()),
                "counties_ge1_cct_pct": float(100 * (d.cct_facility_count > 0).mean()),
                "cct_rate_mean": float(r.cct_rate_per_100k.mean()),
                "rate_eligible": int(len(r))}

    rows["all_counties"] = block(m)
    rows["metropolitan"] = block(m[m.metro_indicator == 1])
    rows["nonmetropolitan"] = block(m[m.metro_indicator == 0])
    q = pd.qcut(el.edi_national_percentile, 5, labels=False)
    for i in range(5):
        rows[f"edi_q{i + 1}"] = block(el[q == i])
    rows["_note"] = ("Metropolitan strata use all counties. EDI quintiles are restricted to "
                     "rate-eligible counties with an EDI value. Facility percentages are of "
                     "the national total for each modality.")
    rows["_national_totals"] = {"cmr": tot_cmr, "cct": tot_cct}
    exc = m[m.rate_excluded == 1]
    rows["_rate_excluded_facilities"] = int(exc.cmr_facility_count.sum()
                                            + exc.cct_facility_count.sum())
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
                    # Diagnosed fit: a sparse stratum can put the dispersion on
                    # its boundary, where NB2 reduces to Poisson. See
                    # model_spec.fit_primary_checked and output/results/
                    # nonmetro_cmr_diagnostics.txt.
                    res, diag = model_spec.fit_primary_checked(sub, col, [term])
                    strat = est(res, term)
                    strat["estimable"] = bool(
                        not (pd.isna(strat["ci_low"]) or pd.isna(strat["ci_high"])
                             or pd.isna(strat["p"])))
                    strat["solution"] = diag["solution"]
                    strat["alpha_nb2"] = diag["alpha"]
                    out["models"][key][f"stratified_{lab}"] = strat
                    out["models"][key][f"stratified_{lab}_n"] = int(len(sub))
                    out["models"][key][f"stratified_{lab}_events"] = int(sub[col].sum())
    return out


def model_diagnostics(m):
    """
    Evidence for the modelling choices, on the primary analytic sample and the
    primary (estimated-dispersion, fully converged) NB2 fits: overdispersion of
    the outcomes, NB2 versus Poisson on AIC, and sensitivity to fixing the
    dispersion at alpha = 1. The interpretation is generated from these numbers,
    so it cannot drift from them.
    """
    from statsmodels.genmod.families import Poisson
    import statsmodels.discrete.discrete_model as dm

    m = m.copy()
    m["log_pop"] = np.log(m.adult_pop_45plus)
    out = {"overdispersion": {}, "aic_nb_vs_poisson": {}, "alpha_sensitivity": {},
           "_sample": "primary analytic sample (all counties with the index)"}
    for col in ["cmr_facility_count", "cct_facility_count"]:
        mu, var = float(m[col].mean()), float(m[col].var())
        out["overdispersion"][col] = {
            "mean": mu, "variance": var, "variance_to_mean_ratio": var / mu,
            "pct_zero": float(100 * (m[col] == 0).mean()),
        }
    for idx, col_idx in [("SVI", "svi_pct100"), ("EDI", "edi_national_percentile")]:
        d = model_spec.analytic_sample(m, col_idx)
        d["log_pop"] = np.log(d.adult_pop_45plus)
        for mod, col in [("CMR", "cmr_facility_count"), ("CCT", "cct_facility_count")]:
            for lab, terms in [("unadjusted", ["idx10"]), ("adjusted", ["idx10", "metro_indicator"])]:
                X = sm.add_constant(d[terms], has_constant="add")
                nbf = model_spec.fit_nb2(dm.NegativeBinomial(d[col], X, loglike_method="nb2",
                                                             offset=d.log_pop))
                pof = sm.GLM(d[col], X, family=Poisson(), offset=d.log_pop).fit()
                fix = sm.GLM(d[col], X, family=NegativeBinomial(alpha=ALPHA), offset=d.log_pop).fit()
                out["aic_nb_vs_poisson"][f"{idx}_{mod}_{lab}"] = {
                    "aic_negative_binomial": float(nbf.aic), "aic_poisson": float(pof.aic),
                    "poisson_pearson_dispersion": float(pof.pearson_chi2 / pof.df_resid),
                    "nb_irr": float(np.exp(nbf.params["idx10"])), "nb_p": float(nbf.pvalues["idx10"]),
                    "poisson_irr": float(np.exp(pof.params["idx10"])),
                    "poisson_p": float(pof.pvalues["idx10"]),
                }
                if lab == "adjusted":
                    out["alpha_sensitivity"][f"{idx}_{mod}_adjusted"] = {
                        "fixed_alpha_1": {"irr": float(np.exp(fix.params["idx10"])),
                                          "p": float(fix.pvalues["idx10"]),
                                          "metro_irr": float(np.exp(fix.params["metro_indicator"]))},
                        "estimated_alpha": {"irr": float(np.exp(nbf.params["idx10"])),
                                            "p": float(nbf.pvalues["idx10"]),
                                            "alpha": float(nbf.params["alpha"]),
                                            "metro_irr": float(np.exp(nbf.params["metro_indicator"]))},
                    }
    od = out["overdispersion"]
    wins = sum(v["aic_negative_binomial"] < v["aic_poisson"] for v in out["aic_nb_vs_poisson"].values())
    flips = [k.replace("_adjusted", "") for k, v in out["alpha_sensitivity"].items()
             if (v["fixed_alpha_1"]["p"] < 0.05) != (v["estimated_alpha"]["p"] < 0.05)]
    out["_interpretation"] = (
        f"Both outcomes are overdispersed (variance-to-mean ratio "
        f"{od['cmr_facility_count']['variance_to_mean_ratio']:.2f} for CMR and "
        f"{od['cct_facility_count']['variance_to_mean_ratio']:.2f} for CCT). The estimated-"
        f"dispersion NB2 model has lower AIC than Poisson in {wins} of "
        f"{len(out['aic_nb_vs_poisson'])} index models; output/results/"
        f"model_specification_comparison.csv compares all three specifications. With the "
        f"dispersion fixed at 1, the significance of an adjusted index association changes for: "
        f"{', '.join(flips) if flips else 'none'}.")
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
    # scipy returns NaN if either input contains NaN. The rate-eligible set
    # includes counties with no EDI value, so the EDI correlations must be
    # computed on the subset that has one; otherwise they silently come out NaN.
    el_edi = el.dropna(subset=["edi_national_percentile"])
    for lab, col in [("cmr", "cmr_rate_per_100k"), ("cct", "cct_rate_per_100k")]:
        r, p = stats.spearmanr(el[col], el.svi_percentile)
        out[f"svi_{lab}_spearman_rho"] = float(r)
        out[f"svi_{lab}_spearman_p"] = float(p)
        r, p = stats.spearmanr(el_edi[col], el_edi.edi_national_percentile)
        out[f"edi_{lab}_spearman_rho"] = float(r)
        out[f"edi_{lab}_spearman_p"] = float(p)
    out["svi_spearman_n"] = int(len(el))
    out["edi_spearman_n"] = int(len(el_edi))
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
    p = PCA(n_components=1, svd_solver="full").fit(StandardScaler().fit_transform(dd[feats]))
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
    a(f"  Estimated-dispersion NB2 vs Poisson on AIC: NB2 lower in "
      f"{nb_wins} of {len(md['aic_nb_vs_poisson'])} index models.")
    spec_csv = os.path.join(RESULTS, "model_specification_comparison.csv")
    if os.path.exists(spec_csv):
        t = pd.read_csv(spec_csv)
        combos = t.groupby(["index", "outcome"])
        wins = {c: sum("estimated alpha" in g.loc[g[c].idxmin(), "specification"]
                       for _, g in combos) for c in ("aic", "bic")}
        a(f"  PRIMARY specification (dispersion estimated) has the lowest AIC in "
          f"{wins['aic']} of {combos.ngroups} model/outcome combinations and the "
          f"lowest BIC in {wins['bic']} of {combos.ngroups}.")
        a(f"  Source: output/results/model_specification_comparison.csv")
    else:
        a("  Run code/13_model_specification.py for the AIC/BIC comparison.")
    a("  Sensitivity to fixing alpha at 1.0, adjusted index models:")
    for k, v in md["alpha_sensitivity"].items():
        a(f"    {k:<22} alpha=1.0 IRR {v['fixed_alpha_1']['irr']:.4f} "
          f"(P {v['fixed_alpha_1']['p']:.4f})   alpha estimated "
          f"IRR {v['estimated_alpha']['irr']:.4f} (P {v['estimated_alpha']['p']:.4f}, "
          f"alpha {v['estimated_alpha']['alpha']:.3f})")
    a(f"  {md['_interpretation']}")
    a("")
    if R.get("sdi"):
        s = R["sdi"]
        a("-" * 78)
        a("EXTERNAL VALIDATION  (manuscript Figure 2)")
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
    # The flattened prose supports substring checks; the paragraph list lets
    # section-aware checks (Summary Sentence, Abstract) address one block.
    # The submitted manuscript writes ranges and pairs with an en dash
    # ("0.96–1.04", "SVI–CCT"); every check here is written with a hyphen, so
    # the two are read alike.
    nd = lambda t: t.replace("\u2013", "-")
    prose_parts = [nd(t) for t in prose_parts]
    tables = [[[nd(c) for c in row] for row in tb] for tb in tables]
    return (re.sub(r"\s+", " ", " ".join(prose_parts)), tables,
            [re.sub(r"\s+", " ", t).strip() for t in prose_parts])


#: The tables, in manuscript order, when they are separate files (as submitted).
TABLE_FILES = ["Table1_Capacity_by_Rurality_and_EDI.docx", "Table2_Primary_Models.docx",
               "Table3_Sensitivity_EDI.docx", "Table4_Comparison_SDI.docx",
               "Table5_Population_Characteristics.docx"]


def read_table_files():
    """Tables 1-5 from their separate files: [rows] per table, plus the title
    and note paragraphs of each, read the same way as the manuscript."""
    tables, texts = [], []
    for name in TABLE_FILES:
        path = os.path.join(BASE_DIR, "output", "tables", name)
        if not os.path.exists(path):
            break
        prose, tb, paras = read_manuscript(path)
        tables.append(tb[0] if tb else [])
        texts.append(prose)
    return tables, texts


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
    (r"restored at revision", "Data Availability promises the URL 'at revision' in the revision itself"),
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
    # Scoped to the SVI-CMR estimate it replaced: 0.95-1.03 is also the correct
    # CI of the population-weighted EDI-CMR estimate added in revision R1-02.
    (r"1\.00 \(0\.95-1\.03\)|IRR 1\.00; 95% CI, 0\.95-1\.03", "pre-HUD SVI-CMR unadjusted CI"),
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
    (r"neither index (was|is) associated with capacity",
     "the adjusted SVI-CCT association is positive and significant"),
    (r"no association with capacity once metropolitan",
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
    # The two indices do NOT agree after adjustment: EDI is null for both
    # modalities, SVI is positive and significant for cardiac CT.
    (r"gave the same result|both indices gave the same|indices agreed after adjustment",
     "the SVI and EDI differ after adjustment for cardiac CT"),
    # ---- Revision round 1 (reviewer and editor items). Each entry is wording
    # that the revision removed; its return would undo a correction.
    (r"section 145\(a\)", "E-04: the MIPPA accreditation provision is section 135(a)"),
    (r"human subjects[\u2019'] research", "E-04: 'human subjects research', no possessive"),
    (r"Supplementary Figure S1\.for|\(Supplementary Figure S2\)a ",
     "E-04: misplaced figure-citation insertions"),
    (r"conclusions\.Accredited|\) ,", "E-04: spacing errors"),
    (r"\bthen a Poisson", "E-04: 'than a Poisson'"),
    (r"0\.70 \(NE\)|not estimable because the stratum",
     "R2-03: the nonmetropolitan CMR estimate is estimable at the NB2 boundary"),
    (r"rural-urban gradient|metropolitan-rural gradient|correlated with rural location"
     r"|rural populations within them|high-deprivation and rural counties",
     "R1-03: the binary RUCC classification is metropolitan/nonmetropolitan"),
    (r"Cardiac MRI Capacity", "E-04: the paper uses 'cardiac MR'"),
    (r"are strongly correlated, and a binary", "E-04: EDI-RUCC Spearman rho is 0.25"),
    (r"declined across EDI quintiles", "the quintile means are not monotonic"),
    (r"IRR \d+\.\d\d, 95% CI", "E-04: estimate punctuation is 'IRR x; 95% CI, a-b'"),
    (r"\(95% CI \d", "E-04: CI punctuation is '(95% CI, a-b)'"),
    (r"did not alter any estimate materially",
     "R1-01: the sensitivity finding moved to Results with its verified size"),
    # The denominators are Census Bureau estimates for July 1, 2023 (Vintage
    # 2023; they match that file exactly), not American Community Survey
    # estimates. The SVI's own ACS 2018-2022 attribution is correct and allowed.
    (r"derived from (the )?American Community Survey|American Community Survey 2019-2023"
     r"|American Community Survey 5-year estimates|ACS 2019-2023",
     "population denominators are Census Bureau estimates for July 1, 2023, not ACS"),
]



SUMMARY_WORD_LIMIT = 35
SUMMARY_CHAR_LIMIT = 250
ABSTRACT_WORD_LIMIT = 250


#: A sentence claiming both indices were independently null is wrong unless it
#: also names the cardiac CT exception. These words signal that qualification.
_NULL_QUALIFIERS = ("while", "whereas", "although", "except", "however",
                    "modestly", "higher cardiac CT", "positive")


def _check_blanket_null(prose, checks):
    """Flag unqualified claims that both indices were independently null.

    The adjusted SVI-CCT association is positive and significant, so a blanket
    statement contradicts Table 2. A sentence that states the null and then
    names the exception is accurate, and must not be flagged: an earlier,
    blunter regex fired on exactly those corrected sentences.
    """
    blanket = re.compile(
        r"(neither[^.]{0,220}?(not )?independently associated"
        r"|(deprivation ind\w+|SVI|EDI)[^.]{0,120}?(was|were) not independently "
        r"associated"
        r"|no (index|deprivation measure)[^.]{0,80}?associated with capacity)",
        re.I)
    offenders = []
    for sentence in re.split(r"(?<=[.;])\s+", prose):
        m = blanket.search(sentence)
        if not m:
            continue
        if any(q.lower() in sentence.lower() for q in _NULL_QUALIFIERS):
            continue          # qualified by modality/direction: accurate
        offenders.append(sentence.strip()[:120])
    checks.append(("no unqualified blanket-null claim", "absent",
                   f"FOUND {offenders[0]!r}" if offenders else "absent",
                   not offenders))


def _check_cohort_disclosure(prose, checks, audit_path):
    """The primary cohort includes Under Review records; readers must be told.

    The briefing defines the primary cohort as Accredited OR Under Review. The
    manuscript otherwise calls every counted record "accredited", so without an
    explicit sentence a reader would reasonably infer the stricter cohort.
    """
    checks.append(("Methods disclose the Under Review cohort", "present",
                   "present" if re.search(r"Under Review", prose) else "ABSENT",
                   bool(re.search(r"Under Review", prose))))
    if not os.path.exists(audit_path):
        return
    a = pd.read_csv(audit_path, dtype=str)
    inc = a[a.final_included == "True"]
    counts = inc.status.value_counts()
    for status in ("Accredited", "Under Review"):
        n = int(counts.get(status, 0))
        checks.append((f"cohort count, {status}", f"{n:,}",
                       "found in text" if re.search(rf"\b{n:,}\b", prose) else "NOT IN TEXT",
                       bool(re.search(rf"\b{n:,}\b", prose))))


def _check_information_criteria(prose, checks, spec_csv):
    """A claim about AIC and/or BIC must match the generated comparison.

    The manuscript states the estimated-dispersion specification was better
    supported by both criteria. That is only sayable if the comparison actually
    generates BIC and the estimated fit wins on it everywhere.
    """
    claims_bic = bool(re.search(r"AIC and BIC|BIC and AIC", prose, re.I))
    if not os.path.exists(spec_csv):
        checks.append(("AIC/BIC claim is backed by generated output",
                       "comparison present", "MISSING", not claims_bic))
        return
    t = pd.read_csv(spec_csv)
    has_bic = "bic" in t.columns and t["bic"].notna().all()
    combos = t.groupby(["index", "outcome"])
    def sweep(criterion):
        return all("estimated alpha" in g.loc[g[criterion].idxmin(), "specification"]
                   for _, g in combos)
    if claims_bic:
        ok = has_bic and sweep("aic") and sweep("bic")
        detail = ("supported" if ok else
                  "BIC not generated" if not has_bic else
                  "estimated dispersion does not win every comparison")
        checks.append(("manuscript AIC+BIC claim matches generated comparison",
                       "supported by AIC and BIC", detail, ok))
    else:
        checks.append(("manuscript AIC-only claim matches generated comparison",
                       "supported by AIC", "supported" if sweep("aic") else "not supported",
                       sweep("aic")))


def _check_table_geometry(path, checks):
    """Every table must fit the page, and its grid must describe its cells.

    Inserting a column copies the width of the cell it follows and leaves
    w:tblGrid untouched, so a table can end up with more cells than grid
    columns and a total width past the right margin. Word renders that off the
    page. The cell-by-cell value checks cannot see it, because every value is
    still correct -- Table 1 overflowed by two inches while passing 167 checks.
    """
    import zipfile
    from lxml import etree
    root = etree.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    sect = root.findall(".//" + _W("sectPr"))[-1]
    pg, mar = sect.find(_W("pgSz")), sect.find(_W("pgMar"))
    usable = (int(pg.get(_W("w"))) - int(mar.get(_W("left")))
              - int(mar.get(_W("right"))))

    for n, tbl in enumerate(root.find(_W("body")).iter(_W("tbl")), start=1):
        rows = tbl.findall(_W("tr"))
        grid = tbl.find(_W("tblGrid"))
        if grid is None or not rows:
            continue
        ncols = max(len(r.findall(_W("tc"))) for r in rows)
        ngrid = len(grid.findall(_W("gridCol")))
        checks.append((f"Table {n} grid matches cells", f"{ncols} columns",
                       f"{ngrid} gridCol", ngrid == ncols))
        widest = max(rows, key=lambda r: len(r.findall(_W("tc"))))
        total = 0
        for tc in widest.findall(_W("tc")):
            el = tc.find(_W("tcPr") + "/" + _W("tcW"))
            if el is not None and el.get(_W("type")) == "dxa":
                total += int(el.get(_W("w")))
        if total:
            checks.append((f"Table {n} fits the page",
                           f"<= {usable} twips", f"{total} twips",
                           total <= usable))


def _check_lengths(paragraphs, checks):
    """Summary Sentence and Abstract must meet the journal's stated limits.

    Both are measured from the document rather than trusted from the bracketed
    notes the manuscript carries, because those notes do not update themselves
    when the text is revised.
    """
    def after(heading, count=1):
        for i, t in enumerate(paragraphs):
            if t.strip().lower() == heading.lower():
                out = []
                for nxt in paragraphs[i + 1:]:
                    nxt = nxt.strip()
                    if not nxt or nxt.startswith("["):
                        continue
                    out.append(nxt)
                    if len(out) == count:
                        break
                return out
        return []

    summary = after("Summary Sentence")
    if summary:
        words, chars = len(summary[0].split()), len(summary[0])
        checks.append(("Summary Sentence word count",
                       f"<= {SUMMARY_WORD_LIMIT}", str(words),
                       words <= SUMMARY_WORD_LIMIT))
        checks.append(("Summary Sentence character count",
                       f"<= {SUMMARY_CHAR_LIMIT}", str(chars),
                       chars <= SUMMARY_CHAR_LIMIT))
        # JACR: the summary sentence is "taken word-for-word from the manuscript".
        others = [t for t in paragraphs if t.strip() != summary[0]]
        found = any(summary[0] in t for t in others)
        checks.append(("Summary Sentence taken word for word from the manuscript",
                       "present elsewhere", "found" if found else "NOT FOUND", found))

    # Body word count, under the definition the manuscript states for itself.
    # This drifted once already: the note said 2,646 after edits had reduced the
    # text, and no plausible definition produced that figure.
    # The submitted manuscript's definition: Introduction through Data
    # Availability, without headings, subheadings, bracketed notes, or the
    # AI-use declaration that follows Data Availability.
    HEADINGS = {"INTRODUCTION", "METHODS", "RESULTS", "DISCUSSION",
                "STUDY LIMITATIONS", "CONCLUSION", "DATA AVAILABILITY",
                "REFERENCES"}
    SUBHEADINGS = {"Study Design and Data Sources", "Measures of Area Disadvantage",
                   "Metropolitan Status and Statistical Analysis",
                   "Distribution of Accredited Capacity", "Social Vulnerability Index",
                   "Economic Deprivation Index", "External Validation With a Published Index",
                   "Comparison With a Published Index", "Sensitivity and Exploratory Analyses"}
    try:
        lo = next(i for i, t in enumerate(paragraphs)
                  if t.strip().upper() == "INTRODUCTION")
        hi = next(i for i, t in enumerate(paragraphs)
                  if t.strip().upper() == "REFERENCES"
                  or t.strip().startswith("Declaration of generative AI"))
    except StopIteration:
        lo = hi = None
    if lo is not None:
        body = [t for t in paragraphs[lo:hi]
                if t.strip() and t.strip().upper() not in HEADINGS
                and t.strip() not in SUBHEADINGS and not t.strip().startswith("[")]
        words = sum(len(t.split()) for t in body)
        for t in paragraphs:
            m = re.search(r"Word count[^:]*:\s*([\d,]+)", t)
            if m:
                stated = int(m.group(1).replace(",", ""))
                checks.append(("body word count note matches the text",
                               f"{words:,}", f"{stated:,}", stated == words))
                break

    abstract = after("Abstract", count=4)
    if abstract:
        # Section labels ("Objective:", ...) are not counted, as in the
        # submitted manuscript's own abstract count.
        words = sum(len((t.split(":", 1)[1] if ":" in t[:12] else t).split()) for t in abstract)
        checks.append(("Abstract word count", f"<= {ABSTRACT_WORD_LIMIT}",
                       str(words), words <= ABSTRACT_WORD_LIMIT))
        for t in paragraphs:
            m = re.search(r"Abstract(?: word count)?:\s*(\d+)( words)?", t)
            if m:
                stated = int(m.group(1))
                checks.append(("Abstract note matches actual count",
                               str(words), str(stated), stated == words))
                break
        for t in paragraphs:
            m = re.search(r"(\d+)\s+words;\s*(\d+)\s+characters", t)
            if m and summary:
                ok = (int(m.group(1)) == len(summary[0].split())
                      and int(m.group(2)) == len(summary[0]))
                checks.append(("Summary note matches actual counts",
                               f"{len(summary[0].split())} words; {len(summary[0])} characters",
                               f"{m.group(1)} words; {m.group(2)} characters", ok))
                break


def _estimate_index(R):
    """Every estimate the pipeline produced, at printed precision.

    Returns (full, no_p, irr_only): sets of (IRR, CI low, CI high, P), of
    (IRR, CI low, CI high), and of IRR alone, all formatted as the paper prints
    them. Built from the gate's own results plus the reviewer analyses.
    """
    full, no_p, irr_only = set(), set(), set()

    def ptxt(v):
        return None if v is None else ("< 0.001" if v < 0.001 else f"= {v:.3f}")

    def walk(o):
        if isinstance(o, dict):
            low = {str(k).lower(): v for k, v in o.items()}
            if all(isinstance(low.get(k), (int, float)) and not isinstance(low.get(k), bool)
                   for k in ("irr", "ci_low", "ci_high")):
                trip = (f"{low['irr']:.2f}", f"{low['ci_low']:.2f}", f"{low['ci_high']:.2f}")
                no_p.add(trip)
                irr_only.add(trip[0])
                pv = low.get("p", low.get("p_value"))
                if isinstance(pv, (int, float)):
                    full.add(trip + (ptxt(pv),))
            elif isinstance(low.get("irr"), (int, float)):
                irr_only.add(f"{low['irr']:.2f}")
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(R)
    return full, no_p, irr_only


def _check_all_estimates(prose, R, checks):
    """Safety net: every estimate quoted in the prose must be one the pipeline
    computed. The value checks elsewhere cover named quantities only; three
    submitted values (an SVI metropolitan IRR in the Table 2 note, an SDI
    metropolitan IRR in Results, and an ordinal-RUCC P value) went stale without
    any check failing, because no check named them."""
    full, no_p, irr_only = _estimate_index(R)
    pat = re.compile(r"IRR (\d+\.\d{2}); 95% CI, (\d+\.\d{2})-(\d+\.\d{2})"
                     r"(?:; P (= \d\.\d{3}|< 0\.001))?")
    for m in pat.finditer(prose):
        irr, lo, hi, pp = m.groups()
        ok = ((irr, lo, hi, pp) in full) if pp else ((irr, lo, hi) in no_p)
        checks.append((f"estimate in text: {m.group(0)}", "computed by the pipeline",
                       "matches a result" if ok else "NO MATCHING RESULT", ok))
    for m in re.finditer(r"(\d+\.\d{2}) \(95% CI, (\d+\.\d{2})-(\d+\.\d{2})\)", prose):
        ok = m.groups() in no_p
        checks.append((f"estimate in text: {m.group(0)}", "computed by the pipeline",
                       "matches a result" if ok else "NO MATCHING RESULT", ok))
    for m in re.finditer(r"IRR (\d+\.\d{2})(?!; 95% CI)", prose):
        ok = m.group(1) in irr_only
        checks.append((f"IRR in text: {m.group(0)}", "computed by the pipeline",
                       "matches a result" if ok else "NO MATCHING RESULT", ok))


def _fe(e, p=True):
    """Estimate in the manuscript's prose format."""
    t = f"IRR {e['irr']:.2f}; 95% CI, {e['ci_low']:.2f}-{e['ci_high']:.2f}"
    if p:
        t += "; P < 0.001" if e["p"] < 0.001 else f"; P = {e['p']:.3f}"
    return t


def _check_revision_r1(prose, paragraphs, R, checks):
    """Values and claims added in revision round 1, checked against
    output/results/reviewer_analyses.json (18_reviewer_analyses.py).

    Every number the revision added to the text is rebuilt here from the
    generated results, and every qualitative claim it added ("no index was
    associated", "confined to metropolitan counties", "attenuated") is tested
    against the estimates that would contradict it.
    """
    rv = R.get("reviewer")
    if rv is None:
        checks.append(("reviewer analyses present", "present", "MISSING", False))
        return

    def has(label, expected, want=True):
        found = expected in prose
        checks.append((label, expected, "found in text" if found else "NOT IN TEXT",
                       found == want))

    def claim(label, phrase, holds):
        present = phrase in prose
        checks.append((f"claim: {label}", "supported" if present else "not claimed",
                       ("supported" if holds else "CONTRADICTED BY DATA") if present
                       else "not claimed", (not present) or holds))

    W = rv["R1-02_weighting"]
    rates = W["descriptive"]["rates"]
    has("pooled CMR rate, metro vs nonmetro",
        f"{rates['metropolitan']['CMR_pooled']:.2f} versus {rates['nonmetropolitan']['CMR_pooled']:.2f}")
    has("pooled CCT rate, metro vs nonmetro",
        f"{rates['metropolitan']['CCT_pooled']:.2f} versus {rates['nonmetropolitan']['CCT_pooled']:.2f}")
    exc = W["descriptive"]["excluded"]
    has("rate-excluded county count", f"{exc['n']} counties")
    claim("no facility in the rate-excluded counties",
          f"none of the {exc['n']} counties", exc["cmr_facilities"] + exc["cct_facilities"] == 0)
    claim("rate-eligible restriction changed no IRR by more than 0.001",
          "by more than 0.001", W["max_abs_irr_change_rate_eligible_adjusted"] < 0.001)
    wm = W["models"]
    has("weighted SVI-CCT adjusted", _fe(wm["SVI_CCT_adjusted"]["poisson_population_weighted_robust"]))
    # The weighted metropolitan terms are Table 3 cells, checked there.
    has("weighted EDI-CMR adjusted", _fe(wm["EDI_CMR_adjusted"]["poisson_population_weighted_robust"]))
    # Population weighting is Poisson with the offset (rates weighted by N). The
    # earlier var_weights = N fit weighted rates by N squared; its "no index
    # association significant" claim must not return.
    # "Same conclusions" must hold for every SVI and EDI model, unadjusted and
    # adjusted: same direction and same side of P = 0.05. (It does not hold for
    # the adjusted SDI-CMR model, so the text claims it for the SVI and EDI only.)
    def _same(m):
        a, b = m["primary_nb2"], m["poisson_population_weighted_robust"]
        return ((a["p"] < 0.05) == (b["p"] < 0.05)
                and (a["p"] >= 0.05 or (a["irr"] > 1) == (b["irr"] > 1)))
    claim("weighted SVI and EDI estimates lead to the same conclusions as the primary ones",
          "Population-weighted SVI and EDI estimates led to the same conclusions",
          all(_same(m) for k, m in wm.items() if k.startswith(("SVI_", "EDI_"))))
    claim("weighted estimates not said to agree for every index (SDI-CMR differs)",
          "Population-weighted estimates agreed with the primary estimates",
          all(_same(m) for m in wm.values()))
    claim("no 'none significant under weighting' claim", "none of the index associations was "
          "significant", False)
    fa = R["regressions"]["sensitivity_fixed_alpha"]["SVI_CCT"]["adjusted_metro"]["p"]
    has("SVI-CCT with dispersion fixed at 1", f"dispersion fixed at 1 (P = {fa:.3f})")
    claim("rate-eligible bound stated for index IRRs", "no adjusted index IRR by more than 0.001",
          W["max_abs_irr_change_rate_eligible_adjusted"] < 0.001)
    sv_int = rv["R2-03_strata"]["interaction"]["SVI_CCT"]["interaction_ratio"]["p"]
    has("SVI-CCT index-by-metro interaction P", f"interaction P = {sv_int:.3f}")
    claim("SVI-CCT not called 'confined' to metropolitan counties (interaction not significant)",
          "confined to metropolitan", sv_int < 0.05)

    spec_csv = os.path.join(RESULTS, "model_specification_comparison.csv")
    if os.path.exists(spec_csv):
        t = pd.read_csv(spec_csv)
        combos = t.groupby(["index", "outcome"])
        wins = [sum("estimated alpha" in g.loc[g[c].idxmin(), "specification"]
                    for _, g in combos) for c in ("aic", "bic")]
        ok = wins[0] == wins[1] == combos.ngroups
        claim(f"estimated dispersion wins AIC and BIC in all {combos.ngroups} models",
              f"in all {combos.ngroups} index-outcome models", ok)

    M = rv["R2-02_multiplicity"]
    tests = {t["test"]: t for t in M["tests"]}
    sc = tests["SVI-CCT, adjusted for metropolitan status (Table 2)"]
    has("Holm-adjusted SVI-CCT, primary family", f"within the primary family (P = {sc['holm_primary']:.3f})")
    has("BH-adjusted SVI-CCT, all tests", f"index associations (P = {sc['bh_extended']:.3f})")
    # The extended family is the negative binomial associations only; Table 3 also
    # reports population-weighted ones, so "all N index associations" would be wrong.
    has("size of the extended family", f"{M['families']['extended']['n_tests']} negative binomial index associations")
    claim("extended family not described as all associations reported",
          f"all {M['families']['extended']['n_tests']} index associations", False)
    for name, short in [("SVI-CMR", "SVI, cardiac MR"), ("SVI-CCT", "SVI, cardiac CT"),
                        ("EDI-CMR", "EDI, cardiac MR"), ("EDI-CCT", "EDI, cardiac CT")]:
        tt = tests[f"{name}, adjusted for metropolitan status (Table 2)"]
        has(f"Table 2 note Holm {name}", f"{tt['holm_primary']:.3f} ({short})")

    S = rv["R2-03_strata"]
    nm = S["strata"]["EDI_CMR_nonmetro"]
    det = S["detail"]["EDI_CMR_nonmetro"]
    inter = S["interaction"]["EDI_CMR"]
    has("nonmetro EDI-CMR estimate", _fe(nm["estimate"]))
    has("nonmetro EDI-CMR interaction P", f"interaction P = {inter['interaction_ratio']['p']:.3f}")
    has("nonmetro profile-likelihood CI",
        f"{det['poisson_profile']['ci_low']:.2f}-{det['poisson_profile']['ci_high']:.2f}")
    has("nonmetro RUCC-adjusted estimate", f"IRR {det['within_stratum_ordinal_rucc']['irr']:.2f}")
    has("nonmetro facility count", f"{nm['events']} accredited CMR facilities")
    claim("each nonmetro CMR facility in a different county", "each in a different county",
          nm["events"] == nm["units_with_event"])
    others = [S["strata"][f"{i}_CMR_nonmetro"]["estimate"] for i in ("SVI", "SDI")]
    has("nonmetro SVI and SDI estimates",
        f"SVI (IRR {others[0]['irr']:.2f}) and SDI (IRR {others[1]['irr']:.2f})")
    claim("nonmetro CMR inverse for all three indices", "consistent across all three indices",
          all(S["strata"][f"{i}_CMR_nonmetro"]["estimate"]["irr"] < 1
              and S["strata"][f"{i}_CMR_nonmetro"]["estimate"]["p"] < 0.05
              for i in ("SVI", "EDI", "SDI")))
    cct_inter = S["interaction"]["EDI_CCT"]["interaction_ratio"]["p"]
    has("Table 3 note, CCT interaction P", f"interaction P = {cct_inter:.3f}")

    U = rv["R1-04_urban_core"]
    um = U["models"]
    prim = um["SVI_CCT: metropolitan status (primary)"]["estimate"]
    has("SVI-CCT, metropolitan stratum", _fe(um["SVI_CCT: metropolitan counties only"]["estimate"], p=False))
    has("SVI-CCT, nonmetropolitan stratum",
        _fe(um["SVI_CCT: nonmetropolitan counties only"]["estimate"], p=False))
    dens = um["SVI_CCT: metropolitan status + log population density"]["estimate"]
    has("SVI-CCT, density-adjusted", _fe(dens))
    claim("SVI-CCT attenuated by density", "no longer significant after adjustment for population density",
          dens["p"] >= 0.05 and abs(dens["irr"] - 1) < abs(prim["irr"] - 1))
    claim("SVI-CCT confined to metropolitan counties", "confined to metropolitan counties",
          um["SVI_CCT: metropolitan counties only"]["estimate"]["p"] < 0.05
          and um["SVI_CCT: nonmetropolitan counties only"]["estimate"]["p"] >= 0.05)
    th = U["themes"]
    has("SVI theme 4, CCT", _fe(th["SVI_CCT_theme4"]["adjusted_metro"], p=False))
    has("SVI theme 3, CCT", _fe(th["SVI_CCT_theme3"]["adjusted_metro"], p=False))
    # The density-adjusted SVI-CMR estimate and the RUCC 1 facility count are
    # reported in Supplementary Table S6 and the results files, not in the text.
    dsc = U["descriptive"]
    has("themes 4 and 3 vs density, metro",
        f"ρ = {dsc['spearman_theme4_density_metro']['rho']:.2f} and "
        f"{dsc['spearman_theme3_density_metro']['rho']:.2f}")
    # Theme 1 is also positive (P < 0.05), so the themes are "strongest", not the
    # only carriers of the association.
    claim("themes 3-4 strongest, not sole carriers", "carried by those two themes", False)

    P = rv["R2-01_pca"]
    has("PC1 eigenvalue", f"eigenvalue {P['eigenvalues'][0]:.2f}")
    lo, hi = min(P["pc1_loadings"].values()), max(P["pc1_loadings"].values())
    has("PC1 loading range", f"loadings, {lo:.2f}-{hi:.2f}")
    claim("all six indicators load positively on PC1", "all six indicators loaded positively",
          lo > 0)
    has("PC2 eigenvalue and variance",
        f"eigenvalue {P['eigenvalues'][1]:.2f}; {100 * P['variance_explained'][1]:.1f}% of variance")
    top2 = max(P["pc2_loadings"], key=lambda k: abs(P["pc2_loadings"][k]))
    claim("PC2 reflects mainly housing cost burden", "reflected mainly housing cost burden",
          top2 == "EP_HBURD")
    pa = P.get("parallel_analysis", {})
    claim("parallel analysis retained one component", "parallel analysis retained one component",
          pa.get("n_retained") == 1)

    g = R["quintiles"]
    has("pooled Q1/Q5 ratio", f"{g['q1_over_q5_ratio_pooled']:.1f}-fold")


def _check_references(paragraphs, checks):
    """References are numbered in order of first citation, every reference is
    cited, and the count in the front-matter note matches the list (E-04)."""
    try:
        lo = next(i for i, t in enumerate(paragraphs) if t.strip().upper() == "INTRODUCTION")
        hi = next(i for i, t in enumerate(paragraphs) if t.strip().upper() == "REFERENCES")
    except StopIteration:
        return
    refs = []
    for t in paragraphs[hi + 1:]:
        mm = re.match(r"^(\d+)\.\s", t.strip())
        if not mm:
            break
        refs.append(int(mm.group(1)))
    n = len(refs)
    checks.append(("reference list numbered 1..N", f"1..{n}",
                   "sequential" if refs == list(range(1, n + 1)) else f"{refs}",
                   refs == list(range(1, n + 1))))
    order = []
    for t in paragraphs[lo:hi]:
        for grp in re.findall(r"\((\d+(?:\s*[-–,]\s*\d+)*)\)", t):
            nums = []
            for part in re.split(r"\s*,\s*", grp):
                if re.search(r"[-–]", part):
                    a, b = (int(x) for x in re.split(r"\s*[-–]\s*", part))
                    nums += list(range(a, b + 1))
                else:
                    nums.append(int(part))
            if not nums or min(nums) < 1 or max(nums) > n:
                continue
            for x in nums:
                if x not in order:
                    order.append(x)
    ok = order == list(range(1, n + 1))
    checks.append(("references cited in order of first appearance", f"1..{n}",
                   "in order" if ok else f"first-cited order {order}", ok))
    for t in paragraphs:
        mm = re.search(r"References:\s*(\d+)", t)
        if mm:
            checks.append(("front-matter reference count", str(n), mm.group(1),
                           int(mm.group(1)) == n))
            break


def _sha256(path):
    """Hash of the exact file checked, so a report cannot be attributed to a
    different document than the one that was validated."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR,
                           capture_output=True, text=True, timeout=10)
        sha = r.stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=BASE_DIR,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return f"{sha}{' (working tree modified)' if dirty else ''}" if sha else "unknown"
    except Exception:
        return "unknown"


def check_manuscript(R):
    """
    Compare the .docx against the recomputed values, cell by cell.

    Table values are located by (section, row label, column) rather than by
    searching the whole document, because a substring search reports a value as
    present when the identical string happens to occur in a different table.
    """
    if not os.path.exists(MANUSCRIPT):
        return (f"Manuscript not found at {MANUSCRIPT}\n"
                "ANALYSIS-ONLY RUN: no manuscript was checked (the manuscript/ folder is "
                "not tracked in git). This is not a manuscript pass.\n")

    prose, doc_tables, prose_paragraphs = read_manuscript(MANUSCRIPT)
    # The submitted manuscript carries no tables: they are separate files, and
    # are checked there, cell by cell, in manuscript order.
    table_texts = []
    if not doc_tables:
        doc_tables, table_texts = read_table_files()
        # Table titles and notes are part of the submission, so the text checks
        # (named values, forbidden phrases, every quoted estimate) cover them too.
        prose = prose + " " + " ".join(table_texts)

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
    ck_prose("mean EDI contrast", f"{d['mean_edi_no_facility']:.1f} vs {d['mean_edi_has_facility']:.1f}"
             f"; {'P < 0.001' if d['mean_edi_contrast_mannwhitney_p'] < 0.001 else 'P = ' + format(d['mean_edi_contrast_mannwhitney_p'], '.3f')})")
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

    # Journal limits. These were previously asserted only by a bracketed note
    # in the manuscript, which drifted out of date as the text was revised.
    # Every correlation must be computable. NaN here means an input carried
    # missing values, which once produced silently NaN Spearman results that
    # no other check would have caught.
    nan_corr = [k for k, v in R["correlations"].items()
                if isinstance(v, float) and pd.isna(v)]
    checks.append(("all correlations are computable", "no NaN",
                   f"NaN in {nan_corr}" if nan_corr else "no NaN", not nan_corr))

    _check_blanket_null(prose, checks)
    _check_cohort_disclosure(prose, checks,
                             os.path.join(PROC, "facility_mapping_audit.csv"))
    _check_information_criteria(
        prose, checks,
        os.path.join(RESULTS, "model_specification_comparison.csv"))
    _check_lengths(prose_paragraphs, checks)
    _check_table_geometry(MANUSCRIPT, checks)
    _check_revision_r1(prose, prose_paragraphs, R, checks)
    _check_all_estimates(prose, R, checks)
    _check_references(prose_paragraphs, checks)

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
    # Layout since revision R2-04: facility counts carry the share of the
    # national total in parentheses, and the binary stratum is headed
    # "Metropolitan status" (R1-03) rather than "Rurality".
    if len(doc_tables) >= 1:
        t1 = _parse_table(doc_tables[0])
        strat_head = "Metropolitan status"
        spec = [("", "All counties", "all_counties"),
                (strat_head, "Metropolitan (RUCC 1-3)", "metropolitan"),
                (strat_head, "Nonmetropolitan (RUCC 4-9)", "nonmetropolitan"),
                ("EDI quintile", "Q1 (least deprived)", "edi_q1"),
                ("EDI quintile", "Q2", "edi_q2"),
                ("EDI quintile", "Q3", "edi_q3"),
                ("EDI quintile", "Q4", "edi_q4"),
                ("EDI quintile", "Q5 (most deprived)", "edi_q5")]
        header = [c.strip() for c in doc_tables[0][0]] if doc_tables[0] else []
        ck("T1 header, CMR facilities", "CMR facilities, No. (%)",
           header[3] if len(header) > 3 else "HEADER NOT FOUND")
        ck("T1 header, CCT facilities", "CCT facilities, No. (%)",
           header[6] if len(header) > 6 else "HEADER NOT FOUND")
        for sect, label, key in spec:
            cells = t1.get((sect, label))
            if cells is None:
                ck(f"T1 {label}", "row present", "ROW NOT FOUND")
                continue
            b = T1[key]
            ck(f"T1 {label} counties", f"{b['counties']:,}", cells[1])
            ck(f"T1 {label} adults", f"{b['adults_millions']:.1f}", cells[2])
            ck(f"T1 {label} CMR fac", f"{b['cmr_facilities']:,} ({b['cmr_facilities_pct']:.1f})", cells[3])
            ck(f"T1 {label} cty>=1 CMR", f"{b['counties_ge1_cmr']:,} ({b['counties_ge1_cmr_pct']:.1f})", cells[4])
            ck(f"T1 {label} CMR rate", f"{b['cmr_rate_mean']:.2f}", cells[5])
            ck(f"T1 {label} CCT fac", f"{b['cct_facilities']:,} ({b['cct_facilities_pct']:.1f})", cells[6])
            ck(f"T1 {label} cty>=1 CCT",
               f"{b['counties_ge1_cct']:,} ({b['counties_ge1_cct_pct']:.1f})", cells[7])
            ck(f"T1 {label} CCT rate", f"{b['cct_rate_mean']:.2f}", cells[8])

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
        wsect = "Population-weighted, adjusted for metropolitan status"
        rv = R.get("reviewer")
        for label, mod in [("Cardiac MR", "CMR"), ("Cardiac CT", "CCT")]:
            cells = t3.get((wsect, label))
            if rv is None:
                break
            w = rv["R1-02_weighting"]["models"][f"EDI_{mod}_adjusted"]
            if cells is None:
                ck(f"T3 weighted {label}", "row present", "ROW NOT FOUND")
                continue
            ck(f"T3 weighted {label} n", f"{w['n']:,}", cells[1])
            ck(f"T3 weighted {label} EDI", fmt_est(w["poisson_population_weighted_robust"]), cells[2])
            ck(f"T3 weighted {label} P", fmt_p(w["poisson_population_weighted_robust"]["p"]), cells[3])
            ck(f"T3 weighted {label} metro",
               fmt_est(w["metro_poisson_population_weighted_robust"]), cells[4])
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

    # ---- Table 4: comparison with a published index (EDI versus SDI), as in
    # the submitted manuscript. Figure 2 plots the same estimates.
    sdi_blk = R.get("sdi") or {}
    if len(doc_tables) >= 4 and sdi_blk.get("SDI_models"):
        t4 = _parse_table(doc_tables[3])
        E4, D4 = sdi_blk["EDI_models"]["outcomes"], sdi_blk["SDI_models"]["outcomes"]
        up = lambda e: {"irr": e["IRR"], "ci_low": e["CI_low"], "ci_high": e["CI_high"], "p": e["P"]}
        for sect, y in (("Cardiac MR", "cmr_facility_count"), ("Cardiac CT", "cct_facility_count")):
            for lab, k in (("Index, unadjusted", "unadjusted"),
                           ("Index, adjusted for metropolitan status", "adjusted"),
                           ("Metropolitan status", "metro_in_adjusted")):
                cells = t4.get((sect, lab))
                if cells is None:
                    ck(f"T4 {sect} {lab}", "row present", "ROW NOT FOUND")
                    continue
                ck(f"T4 {sect} {lab} EDI", fmt_est(up(E4[y][k])), cells[1])
                ck(f"T4 {sect} {lab} EDI P", fmt_p(E4[y][k]["P"]), cells[2])
                ck(f"T4 {sect} {lab} SDI", fmt_est(up(D4[y][k])), cells[3])
                ck(f"T4 {sect} {lab} SDI P", fmt_p(D4[y][k]["P"]), cells[4])
        ck_prose("Table 4 cited with Figure 2", "(Table 4; Figure 2)")

    # ---- Table 5: characteristics of county residents (revision E-05).
    C = (R.get("reviewer") or {}).get("E-05_population")
    if len(doc_tables) >= 6:
        checks.append(("at most five tables", "5 tables", f"{len(doc_tables)} tables found", False))
    if len(doc_tables) >= 5 and C:
        title5 = table_texts[4] if len(table_texts) >= 5 else prose
        checks.append(("Table 5 title", "Table 5. Characteristics of county residents",
                       "found" if "Table 5. Characteristics of county residents" in title5 else "NOT FOUND",
                       "Table 5. Characteristics of county residents" in title5))
        ck_prose("Table 5 cited in Methods", "are summarized in Table 5")
        t5 = _parse_table(doc_tables[4])
        strata = ["all", "metropolitan", "nonmetropolitan", "any_facility", "no_facility"]
        cells = t5.get(("", "Counties, No."))
        ck("T5 counties", " / ".join(f"{C['strata'][k]['counties']:,}" for k in strata),
           " / ".join(cells[1:6]) if cells else "ROW NOT FOUND")
        for key, v in C["variables"].items():
            if key == "density":
                continue
            row = next((c for (sec, lab), c in t5.items() if lab == v["label"]), None)
            dp = 0 if key == "premature_mortality" else 1
            want = " / ".join(f"{v['by_stratum'][k]['population_weighted_mean']:.{dp}f}" for k in strata)
            ck(f"T5 {v['label']}", want, " / ".join(row[1:6]) if row else "ROW NOT FOUND")
    elif len(doc_tables) >= 5:
        checks.append(("Table 5 has population results to check against", "reviewer_analyses.json",
                       "missing", False))

    # The Figure 1 caption must state the finding, not just describe the panels.
    # A caption that lists the null EDI rows without naming the positive
    # SVI-CCT association reads as a blanket null, which is what a coauthor
    # took it to mean. The estimate is rebuilt from the fitted model here, so
    # the caption cannot keep a value the model no longer produces.
    cap = next((p for p in prose_paragraphs if p.strip().upper().startswith("FIGURE 1")), "")
    svi_cct = M["SVI_CCT"]["adjusted_metro"]
    want = (f"IRR {svi_cct['irr']:.2f}; 95% CI, "
            f"{svi_cct['ci_low']:.2f}-{svi_cct['ci_high']:.2f}; "
            f"P = {svi_cct['p']:.3f}")
    checks.append(("Fig 1 caption states SVI-CCT", want,
                   want if want in cap else
                   ("NOT IN CAPTION" if cap else "CAPTION NOT FOUND"),
                   want in cap))
    checks.append(("Fig 1 caption names the gradient", "present",
                   "present" if "inverse deprivation gradient" in cap else "ABSENT",
                   "inverse deprivation gradient" in cap))

    bad = [x for x in checks if not x[3]]
    L = ["=" * 78, "MANUSCRIPT vs DATA, CELL BY CELL", "=" * 78,
         f"Document: {os.path.relpath(MANUSCRIPT, BASE_DIR)}",
         f"SHA256:   {_sha256(MANUSCRIPT)}",
         f"Checked:  {_dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
         f"Code:     {_git_commit()}",
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
    explicit = args.manuscript != MANUSCRIPT
    globals()["MANUSCRIPT"] = args.manuscript
    if not os.path.exists(args.manuscript) and (args.strict or explicit):
        print(f"FAILED: manuscript not found: {args.manuscript}")
        return 2

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
    rv_path = os.path.join(RESULTS, "reviewer_analyses.json")
    if os.path.exists(rv_path):
        with open(rv_path) as f:
            R["reviewer"] = json.load(f)
    sdi_path = os.path.join(RESULTS, "index_comparison_results.json")
    if os.path.exists(sdi_path):
        with open(sdi_path) as f:
            R["sdi"] = json.load(f)

    with open(os.path.join(OUT, "manuscript_numbers.json"), "w") as f:
        # The reviewer analyses have their own file; keep this one to the
        # values the gate itself computes.
        json.dump({k: v for k, v in R.items() if k != "reviewer"}, f, indent=2)
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
