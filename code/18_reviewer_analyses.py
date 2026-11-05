#!/usr/bin/env python3
"""
18_reviewer_analyses.py
=======================
Analyses added in response to peer review (first round).

Each block answers one reviewer or editor item and is labelled with its task
ID, so a reader can trace every new number in the revised manuscript back to
the code that produced it. Every model uses the single specification in
`model_spec.py`; nothing here changes the primary analysis.

    R1-02  Population weighting. County-weighted (primary) versus
           population-weighted estimates, the counties excluded from rates,
           and pooled rates that need no exclusion.
    R2-03  The sparse nonmetropolitan CMR stratum. Why the confidence interval
           was reported as not estimable, and what the likelihood supports.
    R2-02  Multiple comparisons. Holm and Benjamini-Hochberg adjustment within
           a declared primary family and across every index test reported.
    R1-04  The positive SVI-CCT association. Finer urbanicity (categorical
           RUCC, population density), metropolitan strata, and SVI themes.
           Exploratory.
    R2-01  The EDI principal component analysis, in full: every component,
           eigenvalues, loadings, county scores for the biplot.
    E-05   County population characteristics: demographic, socioeconomic and
           population-health measures by metropolitan status and capacity.
    R2-05  One long table of every primary and sensitivity model.

Inputs
    data/processed/county_analytic_dataset.csv, county_edi_constructed.csv
    data/raw/SVI_2022_US_county.csv, county_health_rankings_2024.csv,
             rgc_sdi_2015_2019_county.csv
    output/results/accredited_only_sensitivity.csv   (14_...)
    output/results/svi_quartile_regression.csv       (15_...)

Outputs (output/results/)
    reviewer_analyses.json              every value, full precision
    reviewer_analyses.txt               the same, for reading
    comprehensive_model_table.csv       source of Supplementary Table S1
    population_characteristics.csv      source of the population table
    edi_pca_components.csv              eigenvalues and loadings
    edi_pca_scores.csv                  county scores on PC1 and PC2
    nonmetro_cmr_diagnostics.txt        R2-03 in plain text

Run
    python code/18_reviewer_analyses.py
"""

from __future__ import annotations

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import statsmodels.api as sm
import statsmodels.discrete.discrete_model as dm
from scipy import optimize, stats
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from statsmodels.genmod.families import NegativeBinomial, Poisson
from statsmodels.stats.multitest import multipletests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_spec  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE_DIR, "data", "processed")
RAW = os.path.join(BASE_DIR, "data", "raw")
RESULTS = os.path.join(BASE_DIR, "output", "results")
os.makedirs(RESULTS, exist_ok=True)

INDICES = {"SVI": "svi_pct100", "EDI": "edi_national_percentile", "SDI": "SDI_score"}
OUTCOMES = {"CMR": "cmr_facility_count", "CCT": "cct_facility_count"}
MISSING = -999


# --------------------------------------------------------------------- loading
def load() -> pd.DataFrame:
    df = pd.read_csv(os.path.join(PROC, "county_analytic_dataset.csv"),
                     dtype={"county_fips": str})
    df["county_fips"] = df["county_fips"].str.zfill(5)

    edi = pd.read_csv(os.path.join(PROC, "county_edi_constructed.csv"), dtype={"fips": str})
    edi["fips"] = edi["fips"].str.zfill(5)
    m = df.merge(edi.rename(columns={"fips": "county_fips"}), on="county_fips", how="left")

    sdi = pd.read_csv(os.path.join(RAW, "rgc_sdi_2015_2019_county.csv"),
                      dtype={"COUNTY_FIPS": str})
    sdi["county_fips"] = sdi["COUNTY_FIPS"].str.zfill(5)
    m = m.merge(sdi[["county_fips", "SDI_score"]], on="county_fips", how="left")

    svi = pd.read_csv(os.path.join(RAW, "SVI_2022_US_county.csv"))
    svi["county_fips"] = svi["FIPS"].astype(str).str.zfill(5)
    keep = ["AREA_SQMI", "RPL_THEME1", "RPL_THEME2", "RPL_THEME3", "RPL_THEME4",
            "EP_AGE65", "EP_MINRTY", "EP_AFAM", "EP_HISP", "EP_ASIAN", "EP_AIAN",
            "EP_NHPI", "EP_TWOMORE", "EP_OTHERRACE", "EP_UNINSUR", "EP_DISABL",
            "EP_POV150", "EP_NOVEH", "EP_MUNIT", "EP_CROWD"]
    svi = svi[["county_fips"] + keep].replace(MISSING, np.nan)
    m = m.merge(svi, on="county_fips", how="left")

    chr_df = pd.read_csv(os.path.join(RAW, "county_health_rankings_2024.csv"),
                         encoding="latin1", low_memory=False).iloc[1:].copy()
    chr_df["county_fips"] = chr_df["5-digit FIPS Code"].astype(str).str.zfill(5)
    chr_df = chr_df[chr_df["County FIPS Code"] != "000"]
    chr_cols = {"% Female raw value": "chr_female",
                "Diabetes Prevalence raw value": "chr_diabetes",
                "Adult Obesity raw value": "chr_obesity",
                "Adult Smoking raw value": "chr_smoking",
                "Physical Inactivity raw value": "chr_inactivity",
                "Premature Age-Adjusted Mortality raw value": "chr_premature_mortality",
                "Primary Care Physicians raw value": "chr_pcp"}
    chr_df = chr_df[["county_fips"] + list(chr_cols)].rename(columns=chr_cols)
    for c in chr_cols.values():
        chr_df[c] = pd.to_numeric(chr_df[c], errors="coerce")
    m = m.merge(chr_df, on="county_fips", how="left")

    m["svi_pct100"] = m["svi_percentile"] * 100.0
    m["density"] = m["total_population"] / m["AREA_SQMI"]
    m["log_density"] = np.log(m["density"])
    for t in range(1, 5):
        m[f"svi_theme{t}"] = m[f"RPL_THEME{t}"] * 100.0
    return m


# --------------------------------------------------------------------- helpers
def est(res, term) -> dict:
    lo, hi = np.exp(res.conf_int().loc[term])
    return {"irr": float(np.exp(res.params[term])), "ci_low": float(lo),
            "ci_high": float(hi), "p": float(res.pvalues[term])}


def estimable(e) -> bool:
    return bool(e is not None and all(np.isfinite([e["irr"], e["ci_low"], e["ci_high"], e["p"]])))


def design(d, terms):
    return sm.add_constant(d[terms], has_constant="add"), np.log(d["adult_pop_45plus"])


def sample(m, index, restrict=False):
    """Primary regression sample for `index` (adds idx10 = index / 10)."""
    return model_spec.analytic_sample(m, INDICES[index], restrict_rate_eligible=restrict)


def pop_weights(d):
    """Weights proportional to adults aged 45+, normalised to mean 1."""
    return d["adult_pop_45plus"] / d["adult_pop_45plus"].mean()


def kish_ess(w):
    w = np.asarray(w, dtype=float)
    return float(w.sum() ** 2 / (w ** 2).sum())


# ------------------------------------------------------------------ R1-02
def weighting(m):
    """County-weighted (primary) and population-weighted estimates.

    The primary NB2 model carries log(adults 45+) as an OFFSET. An offset makes
    the model a model for the facility rate; it does not weight observations.
    Every county is one unit, so the primary estimand is the county-level
    association. Weighting by adults 45+ targets a different estimand, the
    association for the average adult. Both are reported; neither replaces the
    other.

    Weighted fits use Poisson quasi-likelihood with robust (HC0) standard
    errors, which is consistent for the mean model whatever the variance, and
    NB2 with alpha held at the unweighted estimate, also with robust errors.
    An unweighted robust Poisson fit is shown so the effect of weighting can be
    separated from the effect of the family.
    """
    out = {"models": {}, "weights": {}, "descriptive": {}}
    for index in INDICES:
        d = sample(m, index)
        w = pop_weights(d)
        top1 = w.sort_values(ascending=False).iloc[: max(1, int(round(len(w) * 0.01)))]
        out["weights"][index] = {
            "n": int(len(d)), "kish_effective_n": kish_ess(w),
            "share_of_weight_top_1pct_counties": float(top1.sum() / w.sum()),
            "share_of_weight_metropolitan": float(w[d.metro_indicator == 1].sum() / w.sum()),
        }
        for oname, ocol in OUTCOMES.items():
            for adjusted in (False, True):
                terms = ["idx10"] + (["metro_indicator"] if adjusted else [])
                X, off = design(d, terms)
                prim = model_spec.fit_primary_terms(d, ocol, terms)
                alpha = model_spec.alpha_of(prim)
                pu = sm.GLM(d[ocol], X, family=Poisson(), offset=off).fit(cov_type="HC0")
                pw = sm.GLM(d[ocol], X, family=Poisson(), offset=off,
                            var_weights=w).fit(cov_type="HC0")
                nw = sm.GLM(d[ocol], X, family=NegativeBinomial(alpha=alpha), offset=off,
                            var_weights=w).fit(cov_type="HC0")
                dr = sample(m, index, restrict=True)
                rr = model_spec.fit_primary_terms(dr, ocol, terms)
                key = f"{index}_{oname}_{'adjusted' if adjusted else 'unadjusted'}"
                blk = {"n": int(len(d)), "n_rate_eligible": int(len(dr)),
                       "alpha_unweighted": alpha,
                       "primary_nb2": est(prim, "idx10"),
                       "poisson_unweighted_robust": est(pu, "idx10"),
                       "poisson_population_weighted_robust": est(pw, "idx10"),
                       "nb2_population_weighted_robust": est(nw, "idx10"),
                       "rate_eligible_nb2": est(rr, "idx10")}
                if adjusted:
                    for lab, r in [("primary_nb2", prim), ("poisson_unweighted_robust", pu),
                                   ("poisson_population_weighted_robust", pw),
                                   ("nb2_population_weighted_robust", nw),
                                   ("rate_eligible_nb2", rr)]:
                        blk[f"metro_{lab}"] = est(r, "metro_indicator")
                out["models"][key] = blk

    # Largest change in any adjusted index IRR when the regressions are
    # restricted to rate-eligible counties. The manuscript describes this as
    # not material; the claim is checked against this value.
    diffs = [abs(v["rate_eligible_nb2"]["irr"] - v["primary_nb2"]["irr"])
             for k, v in out["models"].items() if k.endswith("_adjusted")]
    out["max_abs_irr_change_rate_eligible_adjusted"] = float(max(diffs))

    # Counties excluded from per-capita rates, and what including them does.
    exc = m[m.rate_excluded == 1]
    out["descriptive"]["excluded"] = {
        "n": int(len(exc)), "cmr_facilities": int(exc.cmr_facility_count.sum()),
        "cct_facilities": int(exc.cct_facility_count.sum()),
        "metropolitan": int(exc.metro_indicator.sum()),
        "max_adults_45plus": int(exc.adult_pop_45plus.max()),
        "adults_45plus_total": int(exc.adult_pop_45plus.sum()),
    }
    allr = m.copy()
    pos = allr.adult_pop_45plus > 0
    for oname, ocol in OUTCOMES.items():
        allr.loc[pos, f"{oname}_rate_all"] = 1e5 * allr.loc[pos, ocol] / allr.loc[pos, "adult_pop_45plus"]

    def pooled(g, ocol):
        return float(1e5 * g[ocol].sum() / g.adult_pop_45plus.sum())

    groups = {"all": allr, "metropolitan": allr[allr.metro_indicator == 1],
              "nonmetropolitan": allr[allr.metro_indicator == 0]}
    el = allr[(allr.rate_excluded == 0) & allr.edi_national_percentile.notna()]
    q = pd.qcut(el.edi_national_percentile, 5, labels=False)
    for i in range(5):
        groups[f"edi_q{i + 1}"] = el[q == i]
    rates = {}
    for g, frame in groups.items():
        rates[g] = {}
        for oname, ocol in OUTCOMES.items():
            rates[g][f"{oname}_pooled"] = pooled(frame, ocol)
            rates[g][f"{oname}_mean_all_counties"] = float(frame[f"{oname}_rate_all"].mean())
            r_el = frame[frame.rate_excluded == 0][f"{oname}_rate_all"]
            rates[g][f"{oname}_mean_rate_eligible"] = float(r_el.mean())
    out["descriptive"]["rates"] = rates
    for oname in OUTCOMES:
        a = allr.loc[pos & (allr.metro_indicator == 1), f"{oname}_rate_all"]
        b = allr.loc[pos & (allr.metro_indicator == 0), f"{oname}_rate_all"]
        out["descriptive"][f"{oname}_mannwhitney_p_all_counties"] = float(
            stats.mannwhitneyu(a, b).pvalue)
    return out


# ------------------------------------------------------------------ R2-03
def _profile_ci(d, outcome, terms, term, level=0.95):
    """Profile-likelihood CI for one coefficient of a Poisson rate model."""
    X, off = design(d, terms)
    full = sm.GLM(d[outcome], X, family=Poisson(), offset=off).fit()
    others = [c for c in X.columns if c != term]
    crit = full.llf - stats.chi2.ppf(level, 1) / 2.0

    def prof(b):
        return sm.GLM(d[outcome], X[others], family=Poisson(),
                      offset=off + b * d[term]).fit().llf - crit

    b, se = full.params[term], full.bse[term]
    lo_edge, hi_edge = b - 4 * se, b + 4 * se
    while prof(lo_edge) > 0:
        lo_edge -= 4 * se
    while prof(hi_edge) > 0:
        hi_edge += 4 * se
    lo = optimize.brentq(prof, lo_edge, b)
    hi = optimize.brentq(prof, b, hi_edge)
    restricted = sm.GLM(d[outcome], X[others], family=Poisson(), offset=off).fit()
    lr = 2.0 * (full.llf - restricted.llf)
    return {"ci_low": float(np.exp(lo)), "ci_high": float(np.exp(hi)),
            "lr_statistic": float(lr), "lr_p": float(stats.chi2.sf(lr, 1))}


def _interaction(d, outcome):
    """Index x metropolitan interaction in the full sample, NB2 alpha estimated.

    Gives stratum-specific slopes from one model whose dispersion is estimated
    from all counties, so it does not depend on the sparse stratum alone.
    """
    d = d.copy()
    d["idx10_x_metro"] = d["idx10"] * d["metro_indicator"]
    res = model_spec.fit_primary_terms(d, outcome, ["idx10", "metro_indicator", "idx10_x_metro"])
    V = res.cov_params()
    b = res.params["idx10"] + res.params["idx10_x_metro"]
    se = float(np.sqrt(V.loc["idx10", "idx10"] + V.loc["idx10_x_metro", "idx10_x_metro"]
                       + 2 * V.loc["idx10", "idx10_x_metro"]))
    z = stats.norm.ppf(0.975)
    return {"nonmetro_slope": est(res, "idx10"),
            "metro_slope": {"irr": float(np.exp(b)), "ci_low": float(np.exp(b - z * se)),
                            "ci_high": float(np.exp(b + z * se)),
                            "p": float(2 * stats.norm.sf(abs(b / se)))},
            "interaction_ratio": est(res, "idx10_x_metro"),
            "alpha": model_spec.alpha_of(res)}


def stratum_diagnostics(m):
    """Diagnose every stratified fit, then examine the boundary cases closely."""
    out = {"strata": {}, "detail": {}, "interaction": {}}
    for index in INDICES:
        d = sample(m, index)
        for oname, ocol in OUTCOMES.items():
            out["interaction"][f"{index}_{oname}"] = _interaction(d, ocol)
            for lab, flag in [("metro", 1), ("nonmetro", 0)]:
                sub = d[d.metro_indicator == flag]
                res, diag = model_spec.fit_primary_checked(sub, ocol, ["idx10"])
                e = est(res, "idx10")
                out["strata"][f"{index}_{oname}_{lab}"] = {**diag, "estimate": e,
                                                          "estimable": estimable(e)}

    # The case the reviewer asked about: EDI, cardiac MR, nonmetropolitan.
    for index in INDICES:
        d = sample(m, index)
        sub = d[d.metro_indicator == 0]
        key = f"{index}_CMR_nonmetro"
        if not out["strata"][key]["solution"].startswith("Poisson"):
            continue
        ocol = OUTCOMES["CMR"]
        X, off = design(sub, ["idx10"])
        pois = sm.GLM(sub[ocol], X, family=Poisson(), offset=off).fit()
        robust = sm.GLM(sub[ocol], X, family=Poisson(), offset=off).fit(cov_type="HC0")
        grid = {}
        for a in (1e-6, 0.1, 0.5, 1.0):
            g = sm.GLM(sub[ocol], X, family=NegativeBinomial(alpha=a), offset=off).fit()
            grid[str(a)] = {**est(g, "idx10"), "llf": float(g.llf)}
        rucc = sm.GLM(sub[ocol], *design(sub, ["idx10", "rucc_code"])[:1], family=Poisson(),
                      offset=off).fit()
        dens = sub.dropna(subset=["log_density"])
        dens_fit = sm.GLM(dens[ocol], sm.add_constant(dens[["idx10", "log_density"]]),
                          family=Poisson(), offset=np.log(dens.adult_pop_45plus)).fit()
        holders = sub[sub[ocol] > 0]
        out["detail"][key] = {
            "n_counties": int(len(sub)), "facilities": int(sub[ocol].sum()),
            "counties_with_facility": int((sub[ocol] > 0).sum()),
            "count_distribution": {str(int(k)): int(v)
                                   for k, v in sub[ocol].value_counts().sort_index().items()},
            "poisson_wald": est(pois, "idx10"),
            "poisson_profile": _profile_ci(sub, ocol, ["idx10"], "idx10"),
            "poisson_robust": est(robust, "idx10"),
            "poisson_pearson_dispersion": float(pois.pearson_chi2 / pois.df_resid),
            "fixed_alpha_grid": grid,
            "within_stratum_ordinal_rucc": est(rucc, "idx10"),
            "within_stratum_log_density": est(dens_fit, "idx10"),
            "mean_index_with_facility": float(holders[INDICES[index]].mean()),
            "mean_index_without_facility": float(sub.loc[sub[ocol] == 0, INDICES[index]].mean()),
            "rucc_of_counties_with_facility": {str(int(k)): int(v) for k, v in
                                               holders.rucc_code.value_counts().sort_index().items()},
            "facility_counties": [
                {"county": f"{r.county_name}, {r.state_abbr}", "fips": r.county_fips,
                 "rucc": int(r.rucc_code), "index_percentile": float(getattr(r, INDICES[index])),
                 "adults_45plus": int(r.adult_pop_45plus), "facilities": int(getattr(r, ocol))}
                for r in holders.sort_values(INDICES[index]).itertuples()],
        }
    return out


# ------------------------------------------------------------------ R2-02
def multiplicity(m, strata):
    """Holm (FWER) and Benjamini-Hochberg (FDR) adjustment.

    Primary family: the four metropolitan-adjusted index associations, which
    the manuscript designates as the primary analysis (SVI and EDI, each with
    CMR and CCT). An alternative two-test family (SVI only, the designated
    primary predictor) is also shown. The extended family is every index test
    reported in Tables 2 and 3 and Figure 2.
    """
    tests = []

    def add(label, family_tags, e):
        tests.append({"test": label, "families": family_tags, **e})

    for index in ("SVI", "EDI", "SDI"):
        d = sample(m, index)
        for oname, ocol in OUTCOMES.items():
            un = model_spec.fit_primary_terms(d, ocol, ["idx10"])
            ad = model_spec.fit_primary_terms(d, ocol, ["idx10", "metro_indicator"])
            fam_ad = ["extended"] + (["primary"] if index in ("SVI", "EDI") else []) \
                + (["primary_svi_only"] if index == "SVI" else [])
            loc = {"SVI": "Table 2", "EDI": "Table 2", "SDI": "Figure 2"}[index]
            add(f"{index}-{oname}, unadjusted ({loc})", ["extended"], est(un, "idx10"))
            add(f"{index}-{oname}, adjusted for metropolitan status ({loc})", fam_ad,
                est(ad, "idx10"))
            if index == "EDI":
                ru = model_spec.fit_primary_terms(d, ocol, ["idx10", "rucc_code"])
                add(f"EDI-{oname}, adjusted for ordinal RUCC (Table 3)", ["extended"],
                    est(ru, "idx10"))
                for lab, name in [("metro", "metropolitan"), ("nonmetro", "nonmetropolitan")]:
                    add(f"EDI-{oname}, {name} counties (Table 3)", ["extended"],
                        strata["strata"][f"EDI_{oname}_{lab}"]["estimate"])
    t = pd.DataFrame(tests)
    out = {"tests": [], "families": {}}
    for fam in ("primary", "primary_svi_only", "extended"):
        sel = t[t.families.apply(lambda f: fam in f)].copy()
        p = sel.p.values
        sel[f"holm_{fam}"] = multipletests(p, method="holm")[1]
        sel[f"bh_{fam}"] = multipletests(p, method="fdr_bh")[1]
        t.loc[sel.index, f"holm_{fam}"] = sel[f"holm_{fam}"]
        t.loc[sel.index, f"bh_{fam}"] = sel[f"bh_{fam}"]
        out["families"][fam] = {
            "n_tests": int(len(sel)),
            "significant_unadjusted": int((sel.p < 0.05).sum()),
            "significant_holm": int((sel[f"holm_{fam}"] < 0.05).sum()),
            "significant_bh": int((sel[f"bh_{fam}"] < 0.05).sum()),
            "changed_by_holm": sel.loc[(sel.p < 0.05) != (sel[f"holm_{fam}"] < 0.05), "test"].tolist(),
            "changed_by_bh": sel.loc[(sel.p < 0.05) != (sel[f"bh_{fam}"] < 0.05), "test"].tolist(),
        }
    out["tests"] = json.loads(t.to_json(orient="records"))
    return out


# ------------------------------------------------------------------ R1-04
def urban_core(m):
    """Exploratory: is the positive SVI-CCT association an urbanicity artefact?

    A binary metropolitan indicator puts a dense central county and an exurban
    county in the same category. If accredited CCT clusters in dense urban
    cores, and the SVI is high there for reasons unrelated to economic
    deprivation (minority status, multiunit housing, households without a
    vehicle), a residual positive association would remain after binary
    adjustment and shrink under finer adjustment. This block tests that.
    """
    out = {"models": {}, "themes": {}, "descriptive": {}}
    d = sample(m, "SVI").dropna(subset=["log_density"])
    dummies = pd.get_dummies(d.rucc_code.astype(int), prefix="rucc", drop_first=True).astype(float)
    d = pd.concat([d, dummies], axis=1)
    rucc_cat = list(dummies.columns)
    specs = [("metropolitan status (primary)", ["metro_indicator"]),
             ("ordinal RUCC", ["rucc_code"]),
             ("categorical RUCC", rucc_cat),
             ("metropolitan status + log population density", ["metro_indicator", "log_density"]),
             ("categorical RUCC + log population density", rucc_cat + ["log_density"])]
    for oname, ocol in OUTCOMES.items():
        for label, extra in specs:
            res, diag = model_spec.fit_primary_checked(d, ocol, ["idx10"] + extra)
            e = est(res, "idx10")
            blk = {"estimate": e, "estimable": estimable(e), "n": int(len(d)),
                   "solution": diag["solution"]}
            if "log_density" in extra:
                blk["log_density"] = est(res, "log_density")
            out["models"][f"SVI_{oname}: {label}"] = blk
        for lab, flag in [("metropolitan counties only", 1), ("nonmetropolitan counties only", 0)]:
            sub = d[d.metro_indicator == flag]
            res, diag = model_spec.fit_primary_checked(sub, ocol, ["idx10"])
            e = est(res, "idx10")
            out["models"][f"SVI_{oname}: {lab}"] = {"estimate": e, "estimable": estimable(e),
                                                    "n": int(len(sub)),
                                                    "solution": diag["solution"]}
        for t in range(1, 5):
            dt = d.dropna(subset=[f"svi_theme{t}"]).copy()
            dt["theme10"] = dt[f"svi_theme{t}"] / 10.0
            res = model_spec.fit_primary_terms(dt, ocol, ["theme10", "metro_indicator"])
            res2 = model_spec.fit_primary_terms(dt, ocol, ["theme10", "metro_indicator", "log_density"])
            out["themes"][f"SVI_{oname}_theme{t}"] = {
                "adjusted_metro": est(res, "theme10"),
                "adjusted_metro_density": est(res2, "theme10"), "n": int(len(dt))}
    met = d[d.metro_indicator == 1]
    out["descriptive"]["by_metro_rucc"] = {
        str(int(k)): {"counties": int(len(g)), "cct_facilities": int(g.cct_facility_count.sum()),
                      "cmr_facilities": int(g.cmr_facility_count.sum()),
                      "mean_svi": float(g.svi_pct100.mean()),
                      "median_density": float(g.density.median())}
        for k, g in met.groupby("rucc_code")}
    out["descriptive"]["cct_share_rucc1"] = float(
        d.loc[d.rucc_code == 1, "cct_facility_count"].sum() / d.cct_facility_count.sum())
    rho, p = stats.spearmanr(met.svi_pct100, met.log_density)
    out["descriptive"]["spearman_svi_density_metro"] = {"rho": float(rho), "p": float(p), "n": int(len(met))}
    for t in range(1, 5):
        r, p = stats.spearmanr(met[f"svi_theme{t}"], met.log_density, nan_policy="omit")
        out["descriptive"][f"spearman_theme{t}_density_metro"] = {"rho": float(r), "p": float(p)}
    return out


# ------------------------------------------------------------------ R2-01
PCA_LABELS = {
    "EP_POV150": "Persons below 150% of the federal poverty level",
    "EP_UNEMP": "Civilian labor force unemployed",
    "EP_NOHSDP": "Adults aged ≥25 years without a high-school diploma",
    "EP_HBURD": "Housing cost-burdened households",
    "neg_income": "Median household income (sign reversed)",
    "child_poverty": "Children in poverty",
}
PCA_SOURCES = {
    "EP_POV150": "CDC/ATSDR SVI 2022 (ACS 2018-2022)",
    "EP_UNEMP": "CDC/ATSDR SVI 2022 (ACS 2018-2022)",
    "EP_NOHSDP": "CDC/ATSDR SVI 2022 (ACS 2018-2022)",
    "EP_HBURD": "CDC/ATSDR SVI 2022 (ACS 2018-2022)",
    "neg_income": "County Health Rankings 2024",
    "child_poverty": "County Health Rankings 2024",
}


def pca_full(m):
    """Every component of the EDI PCA, on exactly the published input.

    The published index retains PC1 only (06_edi_sensitivity_analysis.py).
    This refits the same standardised matrix with every component so the scree
    plot and biplot can be drawn, and confirms that its PC1 reproduces the
    published index.
    """
    svi = pd.read_csv(os.path.join(RAW, "SVI_2022_US_county.csv"))
    svi["fips"] = svi["FIPS"].astype(str).str.zfill(5)
    chr_df = pd.read_csv(os.path.join(RAW, "county_health_rankings_2024.csv"),
                         encoding="latin1", low_memory=False).iloc[1:].copy()
    chr_df["fips"] = chr_df["5-digit FIPS Code"].astype(str).str.zfill(5)
    chr_df = chr_df[chr_df["County FIPS Code"] != "000"]
    cs = chr_df[["fips", "Median Household Income raw value", "Children in Poverty raw value"]].copy()
    cs.columns = ["fips", "median_income", "child_poverty"]
    for c in ["median_income", "child_poverty"]:
        cs[c] = pd.to_numeric(cs[c], errors="coerce")
    mg = svi[["fips", "EP_POV150", "EP_UNEMP", "EP_NOHSDP", "EP_HBURD"]].merge(cs, on="fips", how="left")
    dd = mg.dropna().copy()
    dd["neg_income"] = -dd.median_income
    feats = ["EP_POV150", "EP_UNEMP", "EP_NOHSDP", "EP_HBURD", "neg_income", "child_poverty"]
    Z = StandardScaler().fit_transform(dd[feats])
    p = PCA(svd_solver="full").fit(Z)
    scores = p.transform(Z)

    # Align signs so PC1 increases with deprivation, as the published EDI does.
    pub = pd.read_csv(os.path.join(PROC, "county_edi_constructed.csv"), dtype={"fips": str})
    pub["fips"] = pub["fips"].str.zfill(5)
    chk = dd[["fips"]].assign(pc1=scores[:, 0]).merge(pub, on="fips")
    r = float(np.corrcoef(chk.pc1, chk.edi_raw)[0, 1])
    sign = np.ones(len(feats))
    if r < 0:
        sign[0] = -1
    if p.components_[1].sum() < 0:
        sign[1] = -1      # orientation of PC2 is arbitrary; fix it for reproducibility
    comps = p.components_ * sign[:, None]
    scores = scores * sign[None, :]

    R = np.corrcoef(Z.T)
    eig = np.sort(np.linalg.eigvalsh(R))[::-1]
    n, k = Z.shape
    bartlett = -(n - 1 - (2 * k + 5) / 6.0) * np.log(np.linalg.det(R))
    Rinv = np.linalg.inv(R)
    partial = -Rinv / np.sqrt(np.outer(np.diag(Rinv), np.diag(Rinv)))
    off = ~np.eye(k, dtype=bool)
    kmo = float((R[off] ** 2).sum() / ((R[off] ** 2).sum() + (partial[off] ** 2).sum()))

    comp_rows = []
    for j in range(k):
        for i, f in enumerate(feats):
            comp_rows.append({"component": f"PC{j + 1}", "indicator": f, "label": PCA_LABELS[f],
                              "eigenvector_coefficient": float(comps[j, i]),
                              "loading_correlation": float(comps[j, i] * np.sqrt(eig[j])),
                              "eigenvalue": float(eig[j]),
                              "variance_explained": float(p.explained_variance_ratio_[j])})
    pd.DataFrame(comp_rows).to_csv(os.path.join(RESULTS, "edi_pca_components.csv"), index=False)
    sc = dd[["fips"]].copy()
    sc["pc1"], sc["pc2"] = scores[:, 0], scores[:, 1]
    meta = m[["county_fips", "metro_indicator"]].rename(columns={"county_fips": "fips"})
    sc.merge(meta, on="fips", how="left").to_csv(os.path.join(RESULTS, "edi_pca_scores.csv"), index=False)

    return {"n_counties": int(n), "features": feats,
            "labels": PCA_LABELS, "sources": PCA_SOURCES,
            "eigenvalues": [float(x) for x in eig],
            "variance_explained": [float(x) for x in p.explained_variance_ratio_],
            "cumulative_variance": [float(x) for x in np.cumsum(p.explained_variance_ratio_)],
            "n_components_eigenvalue_gt_1": int((eig > 1).sum()),
            "pc1_coefficients": dict(zip(feats, map(float, comps[0]))),
            "pc2_coefficients": dict(zip(feats, map(float, comps[1]))),
            "pc1_loadings": dict(zip(feats, map(float, comps[0] * np.sqrt(eig[0])))),
            "pc2_loadings": dict(zip(feats, map(float, comps[1] * np.sqrt(eig[1])))),
            "correlation_matrix": {f: dict(zip(feats, map(float, R[i]))) for i, f in enumerate(feats)},
            "kmo": kmo,
            "bartlett_chi2": float(bartlett), "bartlett_df": int(k * (k - 1) / 2),
            "bartlett_p": float(stats.chi2.sf(bartlett, k * (k - 1) / 2)),
            "pc1_vs_published_edi_pearson": abs(r),
            "pc1_vs_published_n": int(len(chk)),
            "standardisation": "z-scores, population standard deviation (scikit-learn StandardScaler)",
            "software": "scikit-learn PCA, full SVD; published index uses PC1 only"}


# ------------------------------------------------------------------ E-05
#: (key, label, column, scale, source). Scale converts the stored value to the
#: printed unit. Population-weighted means use total population as the weight.
CHARACTERISTICS = [
    ("pct_65plus", "Aged ≥65 years, %", "EP_AGE65", 1, "SVI 2022 (ACS 2018-2022)"),
    ("pct_female", "Female, %", "chr_female", 100, "County Health Rankings 2024 (Census population estimates)"),
    ("pct_nh_white", "Non-Hispanic White, %", "pct_nh_white", 1, "SVI 2022 (100 minus racial and ethnic minority %)"),
    ("pct_nh_black", "Non-Hispanic Black or African American, %", "EP_AFAM", 1, "SVI 2022"),
    ("pct_hispanic", "Hispanic or Latino, %", "EP_HISP", 1, "SVI 2022"),
    ("pct_nh_asian", "Non-Hispanic Asian, %", "EP_ASIAN", 1, "SVI 2022"),
    ("pct_nh_aian", "Non-Hispanic American Indian or Alaska Native, %", "EP_AIAN", 1, "SVI 2022"),
    ("pct_nh_nhpi", "Non-Hispanic Native Hawaiian or Other Pacific Islander, %", "EP_NHPI", 1, "SVI 2022"),
    ("pct_nh_multi_other", "Non-Hispanic multiracial or other race, %", "pct_multi_other", 1, "SVI 2022"),
    ("pct_pov150", "Below 150% of the federal poverty level, %", "EP_POV150", 1, "SVI 2022"),
    ("pct_uninsured", "Without health insurance, %", "EP_UNINSUR", 1, "SVI 2022"),
    ("pct_disability", "With a disability, %", "EP_DISABL", 1, "SVI 2022"),
    ("density", "Population density, persons per square mile", "density", 1, "ACS 2019-2023 population / SVI 2022 land area"),
    ("diabetes", "Diagnosed diabetes, adults, %", "chr_diabetes", 100, "County Health Rankings 2024 (CDC model-based estimate)"),
    ("obesity", "Obesity, adults, %", "chr_obesity", 100, "County Health Rankings 2024 (CDC model-based estimate)"),
    ("smoking", "Current smoking, adults, %", "chr_smoking", 100, "County Health Rankings 2024 (BRFSS model-based estimate)"),
    ("inactivity", "Physical inactivity, adults, %", "chr_inactivity", 100, "County Health Rankings 2024 (CDC model-based estimate)"),
    ("premature_mortality", "Premature age-adjusted mortality, deaths per 100,000 aged <75 y",
     "chr_premature_mortality", 1, "County Health Rankings 2024 (NCHS mortality files)"),
    ("pcp", "Primary care physicians per 100,000", "chr_pcp", 1e5, "County Health Rankings 2024 (AMA Physician Masterfile)"),
]


def population_characteristics(m):
    """County-level aggregate characteristics. No patient-level data exist in
    this study; every value describes county residents, not imaging users."""
    d = m.copy()
    d["pct_nh_white"] = 100.0 - d["EP_MINRTY"]
    d["pct_multi_other"] = d["EP_TWOMORE"] + d["EP_OTHERRACE"]
    any_fac = (d.cmr_facility_count + d.cct_facility_count) > 0
    strata = {"all": d, "metropolitan": d[d.metro_indicator == 1],
              "nonmetropolitan": d[d.metro_indicator == 0],
              "any_facility": d[any_fac], "no_facility": d[~any_fac]}
    rows, out = [], {"strata": {}, "variables": {}}
    for s, g in strata.items():
        out["strata"][s] = {"counties": int(len(g)),
                            "population_millions": float(g.total_population.sum() / 1e6),
                            "adults_45plus_millions": float(g.adult_pop_45plus.sum() / 1e6)}
    for key, label, col, scale, source in CHARACTERISTICS:
        out["variables"][key] = {"label": label, "source": source, "by_stratum": {}}
        for s, g in strata.items():
            v = g[[col, "total_population"]].dropna()
            x = v[col] * scale
            res = {"n_available": int(len(v)), "n_missing": int(len(g) - len(v)),
                   "median": float(x.median()), "q1": float(x.quantile(0.25)),
                   "q3": float(x.quantile(0.75)),
                   "population_weighted_mean": float(np.average(x, weights=v.total_population))}
            out["variables"][key]["by_stratum"][s] = res
            rows.append({"variable": key, "label": label, "source": source, "stratum": s, **res})
    pd.DataFrame(rows).to_csv(os.path.join(RESULTS, "population_characteristics.csv"), index=False)
    ct = d[d.county_fips.str.startswith("09")]
    out["notes"] = {
        "connecticut_planning_regions_missing_chr": int(ct.chr_diabetes.isna().sum()),
        "unit": "county; no patient-level data",
        "weights": "population-weighted means use total county population (ACS 2019-2023)",
        "not_available": ["cardiovascular disease prevalence or severity",
                          "characteristics of patients imaged at accredited facilities",
                          "gender identity"],
    }
    return out


# ------------------------------------------------------------------ R2-05
def comprehensive_table(m, W, S, U):
    """Every primary and sensitivity model in one long table."""
    rows = []
    acc = pd.read_csv(os.path.join(RESULTS, "accredited_only_sensitivity.csv"))
    acc_desc = pd.read_csv(os.path.join(RESULTS, "accredited_only_descriptives.csv"))
    acc_desc = acc_desc[acc_desc.cohort.str.startswith("Sensitivity")].iloc[0]
    quart = pd.read_csv(os.path.join(RESULTS, "svi_quartile_regression.csv"))

    def add(index, oname, group, model, spec, n, events, e, term2=None, alpha=None, note="",
            term2_label=""):
        rows.append({"index": index, "outcome": oname, "group": group, "model": model,
                     "specification": spec, "n_counties": n, "facilities": events,
                     "irr": e["irr"] if e else np.nan, "ci_low": e["ci_low"] if e else np.nan,
                     "ci_high": e["ci_high"] if e else np.nan, "p": e["p"] if e else np.nan,
                     "estimable": estimable(e) if e else False,
                     "second_term": term2_label,
                     "second_irr": term2["irr"] if term2 else np.nan,
                     "second_ci_low": term2["ci_low"] if term2 else np.nan,
                     "second_ci_high": term2["ci_high"] if term2 else np.nan,
                     "second_p": term2["p"] if term2 else np.nan,
                     "alpha": alpha, "note": note})

    NB = "NB2, dispersion estimated"
    for index in INDICES:
        d = sample(m, index)
        dr = sample(m, index, restrict=True)
        for oname, ocol in OUTCOMES.items():
            ev = int(d[ocol].sum())
            un = model_spec.fit_primary_terms(d, ocol, ["idx10"])
            ad = model_spec.fit_primary_terms(d, ocol, ["idx10", "metro_indicator"])
            ru = model_spec.fit_primary_terms(d, ocol, ["idx10", "rucc_code"])
            add(index, oname, "Primary", "Unadjusted", NB, len(d), ev, est(un, "idx10"),
                alpha=model_spec.alpha_of(un))
            add(index, oname, "Primary", "Adjusted for metropolitan status", NB, len(d), ev,
                est(ad, "idx10"), est(ad, "metro_indicator"), model_spec.alpha_of(ad),
                "Primary analysis" if index in ("SVI", "EDI") else "External index (Figure 2)",
                "Metropolitan status")
            add(index, oname, "Rurality coding", "Adjusted for ordinal RUCC (1-9)", NB, len(d), ev,
                est(ru, "idx10"), est(ru, "rucc_code"), model_spec.alpha_of(ru),
                "Second term is per 1-code increase in RUCC", "Ordinal RUCC")
            inter = S["interaction"][f"{index}_{oname}"]
            for lab, name in [("metro", "Metropolitan counties only"),
                              ("nonmetro", "Nonmetropolitan counties only")]:
                s = S["strata"][f"{index}_{oname}_{lab}"]
                note = ""
                if s["solution"].startswith("Poisson"):
                    note = (f"NB2 dispersion estimate on its boundary (alpha = {s['alpha']:.3g}); "
                            "the maximum-likelihood fit is the Poisson fit, shown here. ")
                    det = S["detail"].get(f"{index}_{oname}_{lab}")
                    if det:
                        pr = det["poisson_profile"]
                        note += (f"Profile-likelihood 95% CI {pr['ci_low']:.2f}-{pr['ci_high']:.2f}; "
                                 f"likelihood-ratio P = {pr['lr_p']:.3f}. ")
                elif not s["estimable"]:
                    note = "Not estimable: information matrix not invertible. "
                if lab == "nonmetro":
                    note += (f"Index x metropolitan interaction P = "
                             f"{inter['interaction_ratio']['p']:.3f}. ")
                note += f"{s['events']} facilities in {s['units_with_event']} counties."
                spec = "Poisson (boundary of NB2)" if s["solution"].startswith("Poisson") else NB
                add(index, oname, "Stratified", name, spec, s["n"], s["events"],
                    s["estimate"] if s["estimable"] else {**s["estimate"], "ci_low": np.nan,
                                                          "ci_high": np.nan, "p": np.nan},
                    alpha=s["alpha"] if spec == NB else 0.0, note=note.strip())
            fx = model_spec.fit_fixed_alpha(d, ocol, adjusted=True)
            add(index, oname, "Dispersion", "Adjusted; dispersion fixed at alpha = 1.0",
                "NB2, alpha fixed at 1.0", len(d), ev, est(fx, "idx10"),
                est(fx, "metro_indicator"), 1.0, "Retained from the original specification",
                "Metropolitan status")
            rr = model_spec.fit_primary_terms(dr, ocol, ["idx10", "metro_indicator"])
            add(index, oname, "Sample", "Adjusted; counties with ≥1,000 adults aged ≥45 y",
                NB, len(dr), int(dr[ocol].sum()), est(rr, "idx10"), est(rr, "metro_indicator"),
                model_spec.alpha_of(rr), "Same restriction as the per-capita rates",
                "Metropolitan status")
            if index in ("SVI", "EDI"):
                a = acc[(acc.cohort.str.startswith("Sensitivity")) & (acc["index"] == index)
                        & (acc.outcome == oname) & (acc.model == "adjusted")]
                ai = a[a.term == index].iloc[0]
                am = a[a.term == "metro"].iloc[0]
                # Facility totals are national; the EDI sample omits the
                # counties without an EDI value, so its total is lower.
                acc_ev = int(acc_desc[f"{oname.lower()}_facilities"]) if index == "SVI" else None
                add(index, oname, "Cohort", "Adjusted; Accredited status only (Under Review excluded)",
                    NB, int(ai.n), acc_ev,
                    {"irr": ai.irr, "ci_low": ai.ci_low, "ci_high": ai.ci_high, "p": ai.p_value},
                    {"irr": am.irr, "ci_low": am.ci_low, "ci_high": am.ci_high, "p": am.p_value},
                    float(ai.alpha), "Cohort excludes the Under Review records", "Metropolitan status")
            wb = W["models"][f"{index}_{oname}_adjusted"]
            add(index, oname, "Family and weighting", "Adjusted; Poisson, robust SE",
                "Poisson QMLE, HC0", len(d), ev, wb["poisson_unweighted_robust"],
                wb["metro_poisson_unweighted_robust"], None,
                "Unweighted reference for the weighted Poisson fit", "Metropolitan status")
            add(index, oname, "Family and weighting",
                "Adjusted; population-weighted Poisson, robust SE",
                "Poisson QMLE, weights = adults aged ≥45 y, HC0", len(d), ev,
                wb["poisson_population_weighted_robust"],
                wb["metro_poisson_population_weighted_robust"], None,
                "Estimand: association for the average adult, not the average county",
                "Metropolitan status")
            add(index, oname, "Family and weighting",
                "Adjusted; population-weighted NB2, robust SE",
                "NB2, alpha fixed at unweighted estimate, weights = adults aged ≥45 y, HC0",
                len(d), ev, wb["nb2_population_weighted_robust"],
                wb["metro_nb2_population_weighted_robust"], wb["alpha_unweighted"],
                "Estimand: association for the average adult", "Metropolitan status")
            dd = d.dropna(subset=["log_density"])
            dn = model_spec.fit_primary_terms(dd, ocol, ["idx10", "metro_indicator", "log_density"])
            add(index, oname, "Exploratory", "Adjusted for metropolitan status and log population density",
                NB, len(dd), int(dd[ocol].sum()), est(dn, "idx10"), est(dn, "log_density"),
                model_spec.alpha_of(dn), "Second term is per 1-unit increase in log density "
                "(about 2.7-fold)", "Log population density")
        if index == "SVI":
            for oname in OUTCOMES:
                for _, r in quart[(quart.outcome == oname) & (quart.model != "unadjusted")].iterrows():
                    add("SVI", oname, "Index coding", f"Adjusted; {r.term}", NB, int(r.n),
                        int(d[OUTCOMES[oname]].sum()),
                        {"irr": r.irr, "ci_low": r.ci_low, "ci_high": r.ci_high, "p": r.p_value},
                        alpha=float(r.alpha), note="IRR versus the least vulnerable quartile (Q1)")
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(RESULTS, "comprehensive_model_table.csv"), index=False)
    return t


# ------------------------------------------------------------------ report
def _f(e, dp=2):
    if not e or not np.isfinite(e.get("irr", np.nan)):
        return "NE"
    if not estimable(e):
        return f"{e['irr']:.{dp}f} (NE)"
    return f"{e['irr']:.{dp}f} ({e['ci_low']:.{dp}f}-{e['ci_high']:.{dp}f})"


def _p(p):
    if p is None or not np.isfinite(p):
        return "NE"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def write_report(R):
    L = []
    a = L.append
    a("=" * 86)
    a("ANALYSES ADDED IN RESPONSE TO PEER REVIEW (ROUND 1)")
    a("=" * 86)
    a("Every model uses model_spec.py. IRRs per 10 percentile points of the index.")
    a("")
    W = R["R1-02_weighting"]
    a("-" * 86)
    a("R1-02  COUNTY-WEIGHTED (PRIMARY) VERSUS POPULATION-WEIGHTED ESTIMATES")
    a("-" * 86)
    a("The log(adults 45+) offset makes each model a rate model; it does not weight")
    a("counties. The primary estimand is the county-level association.")
    a("")
    a(f"  {'Model':<22}{'Primary NB2':>20}{'Poisson robust':>20}{'Pop-wt Poisson':>20}{'Pop-wt NB2':>20}{'Rate-eligible':>20}")
    for k, v in W["models"].items():
        a(f"  {k:<22}{_f(v['primary_nb2']):>20}{_f(v['poisson_unweighted_robust']):>20}"
          f"{_f(v['poisson_population_weighted_robust']):>20}{_f(v['nb2_population_weighted_robust']):>20}"
          f"{_f(v['rate_eligible_nb2']):>20}")
        a(f"  {'  P':<22}{_p(v['primary_nb2']['p']):>20}{_p(v['poisson_unweighted_robust']['p']):>20}"
          f"{_p(v['poisson_population_weighted_robust']['p']):>20}{_p(v['nb2_population_weighted_robust']['p']):>20}"
          f"{_p(v['rate_eligible_nb2']['p']):>20}")
        if "metro_primary_nb2" in v:
            a(f"  {'  metropolitan term':<22}{_f(v['metro_primary_nb2']):>20}"
              f"{_f(v['metro_poisson_unweighted_robust']):>20}"
              f"{_f(v['metro_poisson_population_weighted_robust']):>20}"
              f"{_f(v['metro_nb2_population_weighted_robust']):>20}{_f(v['metro_rate_eligible_nb2']):>20}")
    a("")
    for idx, w in W["weights"].items():
        a(f"  {idx}: n = {w['n']:,}; Kish effective n under population weights = "
          f"{w['kish_effective_n']:.0f}; top 1% of counties carry "
          f"{100 * w['share_of_weight_top_1pct_counties']:.1f}% of the weight; metropolitan "
          f"counties {100 * w['share_of_weight_metropolitan']:.1f}%.")
    a(f"  Largest change in an adjusted index IRR under the rate-eligible restriction: "
      f"{W['max_abs_irr_change_rate_eligible_adjusted']:.4f}")
    e = W["descriptive"]["excluded"]
    a(f"  Counties excluded from rates: {e['n']} ({e['metropolitan']} metropolitan), "
      f"{e['cmr_facilities']} CMR and {e['cct_facilities']} CCT facilities, "
      f"largest has {e['max_adults_45plus']:,} adults aged 45+.")
    for g, r in W["descriptive"]["rates"].items():
        a(f"    {g:<16} CMR pooled {r['CMR_pooled']:.3f}  mean(all) {r['CMR_mean_all_counties']:.3f}  "
          f"mean(eligible) {r['CMR_mean_rate_eligible']:.3f} | CCT pooled {r['CCT_pooled']:.3f}  "
          f"mean(all) {r['CCT_mean_all_counties']:.3f}  mean(eligible) {r['CCT_mean_rate_eligible']:.3f}")
    a("")

    S = R["R2-03_strata"]
    a("-" * 86)
    a("R2-03  STRATIFIED FITS, DIAGNOSED")
    a("-" * 86)
    for k, s in S["strata"].items():
        eig = ", ".join(f"{x:.3g}" for x in s["neg_hessian_eigenvalues"])
        a(f"  {k:<22} {s['events']:>4} facilities/{s['units_with_event']:>4} counties  "
          f"alpha {s['alpha']:.3g}  -H eig [{eig}]  -> {s['solution']}")
        a(f"  {'':<22} IRR {_f(s['estimate'])}  P {_p(s['estimate']['p'])}")
    a("")
    for k, v in S["interaction"].items():
        a(f"  {k:<8} interaction: nonmetro slope {_f(v['nonmetro_slope'])}, metro slope "
          f"{_f(v['metro_slope'])}, ratio {_f(v['interaction_ratio'])} P {_p(v['interaction_ratio']['p'])}")
    a("")
    for k, det in S["detail"].items():
        a(f"  DETAIL {k}: {det['facilities']} facilities in {det['counties_with_facility']} of "
          f"{det['n_counties']:,} counties; distribution {det['count_distribution']}")
        a(f"    Poisson Wald {_f(det['poisson_wald'])} P {_p(det['poisson_wald']['p'])}; profile "
          f"{det['poisson_profile']['ci_low']:.3f}-{det['poisson_profile']['ci_high']:.3f}, LR P "
          f"{_p(det['poisson_profile']['lr_p'])}; robust {_f(det['poisson_robust'])}")
        a(f"    Pearson dispersion {det['poisson_pearson_dispersion']:.3f}; within-stratum RUCC-adjusted "
          f"{_f(det['within_stratum_ordinal_rucc'])}; density-adjusted {_f(det['within_stratum_log_density'])}")
        for al, g in det["fixed_alpha_grid"].items():
            a(f"    alpha fixed {al:<6} IRR {_f(g)}  P {_p(g['p'])}  llf {g['llf']:.4f}")
    a("")

    M = R["R2-02_multiplicity"]
    a("-" * 86)
    a("R2-02  MULTIPLE COMPARISONS")
    a("-" * 86)
    for t in M["tests"]:
        cols = [f"{fam}: Holm {_p(t.get('holm_' + fam))} BH {_p(t.get('bh_' + fam))}"
                for fam in ("primary", "extended") if t.get("holm_" + fam) is not None
                and np.isfinite(t.get("holm_" + fam))]
        a(f"  {t['test']:<62} P {_p(t['p'])}  " + "; ".join(cols))
    for fam, f in M["families"].items():
        a(f"  family {fam}: {f['n_tests']} tests, significant unadjusted {f['significant_unadjusted']}, "
          f"Holm {f['significant_holm']}, BH {f['significant_bh']}; changed by Holm "
          f"{f['changed_by_holm']}; by BH {f['changed_by_bh']}")
    a("")

    U = R["R1-04_urban_core"]
    a("-" * 86)
    a("R1-04  EXPLORATORY: THE POSITIVE SVI ASSOCIATION AND URBANICITY")
    a("-" * 86)
    for k, v in U["models"].items():
        a(f"  {k:<62} {_f(v['estimate']):>20} P {_p(v['estimate']['p'])}")
    for k, v in U["themes"].items():
        a(f"  {k:<40} +metro {_f(v['adjusted_metro'])} P {_p(v['adjusted_metro']['p'])};"
          f" +density {_f(v['adjusted_metro_density'])} P {_p(v['adjusted_metro_density']['p'])}")
    for k, v in U["descriptive"]["by_metro_rucc"].items():
        a(f"  RUCC {k}: {v['counties']} counties, {v['cct_facilities']} CCT, {v['cmr_facilities']} CMR, "
          f"mean SVI {v['mean_svi']:.1f}, median density {v['median_density']:.0f}")
    s = U["descriptive"]["spearman_svi_density_metro"]
    a(f"  Spearman SVI vs log density, metropolitan counties: rho {s['rho']:.3f} (n = {s['n']})")
    a("")

    P = R["R2-01_pca"]
    a("-" * 86)
    a("R2-01  EDI PRINCIPAL COMPONENT ANALYSIS")
    a("-" * 86)
    a(f"  n = {P['n_counties']:,}; KMO = {P['kmo']:.3f}; Bartlett chi2 = {P['bartlett_chi2']:.1f}, "
      f"df {P['bartlett_df']}, P {_p(P['bartlett_p'])}; PC1 vs published EDI r = "
      f"{P['pc1_vs_published_edi_pearson']:.6f}")
    for j, (ev, ve, cv) in enumerate(zip(P["eigenvalues"], P["variance_explained"], P["cumulative_variance"])):
        a(f"  PC{j + 1}: eigenvalue {ev:.3f}, variance {100 * ve:.1f}%, cumulative {100 * cv:.1f}%")
    for f in P["features"]:
        a(f"  {P['labels'][f]:<52} PC1 loading {P['pc1_loadings'][f]:.3f}  PC2 loading {P['pc2_loadings'][f]:.3f}")
    a("")
    C = R["E-05_population"]
    a("-" * 86)
    a("E-05  COUNTY POPULATION CHARACTERISTICS (population-weighted mean; county median [IQR])")
    a("-" * 86)
    strata = list(C["strata"])
    a("  " + " " * 44 + "".join(f"{s:>26}" for s in strata))
    for k, v in C["variables"].items():
        cells = []
        for s in strata:
            b = v["by_stratum"][s]
            cells.append(f"{b['population_weighted_mean']:.1f}; {b['median']:.1f} [{b['q1']:.1f}-{b['q3']:.1f}]")
        a(f"  {v['label'][:44]:<44}" + "".join(f"{c:>26}" for c in cells))
    return "\n".join(L)


def write_nonmetro(R):
    S = R["R2-03_strata"]
    k = "EDI_CMR_nonmetro"
    s, det, inter = S["strata"][k], S["detail"].get(k), S["interaction"]["EDI_CMR"]
    L = ["=" * 78, "R2-03  WHY THE NONMETROPOLITAN CMR ESTIMATE HAD NO CONFIDENCE INTERVAL",
         "=" * 78, ""]
    L += [f"Stratum: {s['n']:,} nonmetropolitan counties, {s['events']} accredited CMR facilities,",
          f"each in a different county (counts: {det['count_distribution']}).", "",
          "Primary specification (NB2, dispersion estimated), as originally fitted:",
          f"  optimiser reported converged = {s['converged']}",
          "  score at the stopping point: " + ", ".join(f"{k} {v:.2e}" for k, v in s["gradient"].items()),
          f"  estimated alpha = {s['alpha']:.4g}",
          f"  eigenvalues of the negated Hessian = {[round(x, 4) for x in s['neg_hessian_eigenvalues']]}",
          f"  log-likelihood NB2 = {s['llf_nb2']:.4f}; Poisson (alpha = 0) = {s['llf_poisson']:.4f}", "",
          "Diagnosis:",
          "  The negated Hessian has a negative eigenvalue, so it is not positive",
          "  definite. statsmodels inverts it only when it is, and otherwise returns no",
          "  standard errors; the confidence interval and P value were therefore",
          "  missing. The cause is the dispersion parameter. With every county holding",
          "  zero or one facility there is no overdispersion to estimate, the likelihood",
          "  is maximised at the boundary alpha = 0, and the optimiser stopped just",
          "  inside it. The Poisson log-likelihood is higher than the NB2 value at that",
          "  point, which confirms the boundary maximum.", "",
          "  At alpha = 0 the NB2 model is the Poisson model, so the maximum-likelihood",
          "  NB2 fit is the Poisson fit, whose information matrix is well conditioned:", "",
          f"  Poisson Wald          IRR {_f(det['poisson_wald'])}, P {_p(det['poisson_wald']['p'])}",
          f"  Profile likelihood    95% CI {det['poisson_profile']['ci_low']:.2f}-{det['poisson_profile']['ci_high']:.2f}, "
          f"LR P {_p(det['poisson_profile']['lr_p'])}",
          f"  Robust (HC0)          IRR {_f(det['poisson_robust'])}, P {_p(det['poisson_robust']['p'])}",
          f"  Pearson dispersion    {det['poisson_pearson_dispersion']:.3f} (no overdispersion)", ""]
    L.append("  Holding alpha fixed instead of estimating it barely moves the estimate:")
    for al, g in det["fixed_alpha_grid"].items():
        L.append(f"    alpha = {al:<6} IRR {_f(g)}, P {_p(g['p'])}")
    L += ["",
          "  Interaction model, all 3,134 counties, NB2 with alpha estimated from all",
          "  counties (does not depend on the sparse stratum's dispersion):",
          f"    nonmetropolitan EDI slope {_f(inter['nonmetro_slope'])}, P {_p(inter['nonmetro_slope']['p'])}",
          f"    metropolitan EDI slope    {_f(inter['metro_slope'])}, P {_p(inter['metro_slope']['p'])}",
          f"    ratio of slopes           {_f(inter['interaction_ratio'])}, P {_p(inter['interaction_ratio']['p'])}",
          "",
          "  Within the stratum, adjusting for ordinal RUCC (4-9) or log population",
          f"  density: {_f(det['within_stratum_ordinal_rucc'])} and {_f(det['within_stratum_log_density'])}.",
          "",
          "Counties holding the 14 facilities (sorted by EDI percentile):"]
    for c in det["facility_counties"]:
        L.append(f"    {c['county']:<26} RUCC {c['rucc']}  EDI {c['index_percentile']:5.1f}  "
                 f"adults 45+ {c['adults_45plus']:>8,}")
    L += ["", "Interpretation: estimable, but resting on 14 single-facility counties; it is",
          "hypothesis-generating. Nothing here is imputed: each interval is a standard",
          "likelihood-based interval for a fitted model."]
    return "\n".join(L)


def main():
    m = load()
    W = weighting(m)
    S = stratum_diagnostics(m)
    M = multiplicity(m, S)
    U = urban_core(m)
    P = pca_full(m)
    C = population_characteristics(m)
    T = comprehensive_table(m, W, S, U)
    R = {"R1-02_weighting": W, "R2-03_strata": S, "R2-02_multiplicity": M,
         "R1-04_urban_core": U, "R2-01_pca": P, "E-05_population": C,
         "R2-05_table_rows": int(len(T))}
    with open(os.path.join(RESULTS, "reviewer_analyses.json"), "w") as f:
        json.dump(R, f, indent=2, default=float)
    report = write_report(R)
    with open(os.path.join(RESULTS, "reviewer_analyses.txt"), "w") as f:
        f.write(report + "\n")
    nm = write_nonmetro(R)
    with open(os.path.join(RESULTS, "nonmetro_cmr_diagnostics.txt"), "w") as f:
        f.write(nm + "\n")
    print(report)
    print()
    print(nm)
    print(f"\n  wrote reviewer_analyses.json/.txt, comprehensive_model_table.csv "
          f"({len(T)} rows), population_characteristics.csv, edi_pca_*.csv, "
          f"nonmetro_cmr_diagnostics.txt")


if __name__ == "__main__":
    main()
