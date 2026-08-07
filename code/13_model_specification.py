#!/usr/bin/env python3
"""
13_model_specification.py
=========================
Chooses the count-model specification from the data instead of assuming it.

The briefing asked for a negative binomial model, a dispersion parameter, and
an AIC comparison against Poisson. The pipeline previously fixed the negative
binomial dispersion at alpha = 1.0 without estimating it. That is a substantive
choice: alpha = 1.0 is roughly four times the value the data support, it
inflates standard errors, and for the SVI-CCT models it changes the significance
conclusion.

This script fits three specifications for every index/outcome pair:

    Poisson                 alpha -> 0, no overdispersion allowed
    NB2, estimated alpha    alpha estimated by maximum likelihood
    NB2, alpha = 1.0        the previously published specification

and reports alpha, AIC, IRR, 95% CI, P, and convergence for each.

Outputs
    output/results/model_specification_comparison.csv
    output/results/model_specification_comparison.txt

Run
    python code/13_model_specification.py
"""

import os
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import statsmodels.api as sm
import statsmodels.discrete.discrete_model as dm
from statsmodels.genmod.families import NegativeBinomial, Poisson

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE_DIR, "data", "processed")
RAW = os.path.join(BASE_DIR, "data", "raw")
OUT = os.path.join(BASE_DIR, "output", "results")
os.makedirs(OUT, exist_ok=True)

OUTCOMES = [("cmr_facility_count", "CMR"), ("cct_facility_count", "CCT")]


def load():
    df = pd.read_csv(os.path.join(PROC, "county_analytic_dataset.csv"),
                     dtype={"county_fips": str})
    edi = (pd.read_csv(os.path.join(PROC, "county_edi_constructed.csv"),
                       dtype={"fips": str}).rename(columns={"fips": "county_fips"}))
    m = df.merge(edi, on="county_fips", how="left")
    sdi_path = os.path.join(RAW, "rgc_sdi_2015_2019_county.csv")
    if os.path.exists(sdi_path):
        sdi = pd.read_csv(sdi_path, dtype={"COUNTY_FIPS": str})
        sdi["COUNTY_FIPS"] = sdi["COUNTY_FIPS"].str.zfill(5)
        m = m.merge(sdi[["COUNTY_FIPS", "SDI_score"]], left_on="county_fips",
                    right_on="COUNTY_FIPS", how="left")
    m["svi_100"] = m["svi_percentile"] * 100.0
    return m


def _row(index, outcome, spec, alpha, res, term, converged):
    irr = float(np.exp(res.params[term]))
    lo, hi = np.exp(res.conf_int().loc[term])
    return {"index": index, "outcome": outcome, "specification": spec,
            "alpha": alpha, "aic": float(res.aic), "irr": irr,
            "ci_low": float(lo), "ci_high": float(hi),
            "p_value": float(res.pvalues[term]), "converged": bool(converged),
            "n": int(res.nobs)}


def compare(d, index_col, index_name, adjusted):
    terms = ["idx10"] + (["metro_indicator"] if adjusted else [])
    sub = d[(d.rate_excluded == 0) & d[index_col].notna()
            & (d.adult_pop_45plus > 0)].copy()
    sub["idx10"] = sub[index_col] / 10.0
    X = sm.add_constant(sub[terms], has_constant="add")
    offset = np.log(sub["adult_pop_45plus"])
    label = f"{index_name} {'adjusted' if adjusted else 'unadjusted'}"
    rows = []

    for outcome, oname in OUTCOMES:
        y = sub[outcome]

        pois = sm.GLM(y, X, family=Poisson(), offset=offset).fit()
        rows.append(_row(label, oname, "Poisson", np.nan, pois, "idx10",
                         pois.converged))

        # NB2 with alpha estimated by MLE. statsmodels' discrete NegativeBinomial
        # estimates alpha jointly with the coefficients.
        mle = dm.NegativeBinomial(y, X, loglike_method="nb2",
                                  offset=offset).fit(disp=0, maxiter=300)
        rows.append(_row(label, oname, "NB2, estimated alpha",
                         float(mle.params["alpha"]), mle, "idx10",
                         getattr(mle.mle_retvals, "get", lambda *_: True)("converged", True)))

        fixed = sm.GLM(y, X, family=NegativeBinomial(alpha=1.0), offset=offset).fit()
        rows.append(_row(label, oname, "NB2, alpha = 1.0 (previous)", 1.0,
                         fixed, "idx10", fixed.converged))
    return rows


def main():
    d = load()
    indices = [("svi_100", "SVI"), ("edi_national_percentile", "EDI")]
    if "SDI_score" in d.columns:
        indices.append(("SDI_score", "SDI"))

    rows = []
    for col, name in indices:
        for adjusted in (False, True):
            rows.extend(compare(d, col, name, adjusted))
    tab = pd.DataFrame(rows)
    tab.to_csv(os.path.join(OUT, "model_specification_comparison.csv"), index=False)

    L = ["=" * 100,
         "COUNT-MODEL SPECIFICATION COMPARISON",
         "=" * 100,
         "Poisson vs negative binomial with alpha estimated vs alpha fixed at 1.0.",
         "IRR is per 10-point increase in the index. Lower AIC is better.",
         ""]
    hdr = (f"{'Model':<26}{'Outcome':<7}{'Specification':<30}"
           f"{'alpha':>7}{'AIC':>10}{'IRR':>8}{'95% CI':>18}{'P':>9}  ")
    for label, grp in tab.groupby("index", sort=False):
        L.append(hdr)
        L.append("-" * 100)
        for _, r in grp.iterrows():
            a = "  -  " if pd.isna(r.alpha) else f"{r.alpha:.3f}"
            ci = f"{r.ci_low:.3f}-{r.ci_high:.3f}"
            star = " *" if r.p_value < 0.05 else ""
            L.append(f"{r['index']:<26}{r.outcome:<7}{r.specification:<30}"
                     f"{a:>7}{r.aic:>10.1f}{r.irr:>8.3f}{ci:>18}{r.p_value:>9.4f}{star}")
        best = grp.loc[grp.groupby("outcome")["aic"].idxmin()]
        for _, b in best.iterrows():
            L.append(f"    best fit for {b.outcome}: {b.specification} (AIC {b.aic:.1f})")
        L.append("")

    # The conclusion this script exists to surface.
    L.append("=" * 100)
    L.append("SPECIFICATION-DEPENDENT CONCLUSIONS")
    L.append("=" * 100)
    flipped = []
    for (idx, out), grp in tab.groupby(["index", "outcome"]):
        sig = set(grp.p_value < 0.05)
        if len(sig) > 1:
            flipped.append((idx, out, grp))
    if not flipped:
        L.append("  None. Every index/outcome pair reaches the same significance")
        L.append("  conclusion under all three specifications.")
    else:
        for idx, out, grp in flipped:
            L.append(f"  {idx}, {out}: significance depends on the specification.")
            for _, r in grp.iterrows():
                verdict = "significant" if r.p_value < 0.05 else "not significant"
                L.append(f"      {r.specification:<30} P = {r.p_value:.4f}  {verdict}")
            L.append("")
    text = "\n".join(L)
    with open(os.path.join(OUT, "model_specification_comparison.txt"), "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
