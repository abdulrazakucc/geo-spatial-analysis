#!/usr/bin/env python3
"""
13_model_specification.py
=========================
Chooses the count-model specification from the data instead of assuming it.

The briefing asked for a negative binomial model, a dispersion parameter, and
an AIC comparison against Poisson. This script supplies that comparison, and it
is the evidence on which the primary specification was chosen: NB2 with the
dispersion estimated (see model_spec.py). The previously used fixed alpha = 1.0
is retained here and reported as a labelled sensitivity.

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

import model_spec

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


def _bic(res):
    """BIC computed the same way for every specification.

    statsmodels reports BIC inconsistently across model classes: GLM exposes a
    deviance-based `bic` while the discrete models expose a likelihood-based
    one, so the two are not comparable as returned. Both are recomputed here
    from the log-likelihood and the number of estimated parameters, counting
    the dispersion parameter for the estimated-alpha fit.
    """
    k = len(res.params)          # includes alpha for the discrete NB2 fit
    return float(-2.0 * res.llf + k * np.log(res.nobs))


def _row(index, outcome, spec, alpha, res, term, converged):
    irr = float(np.exp(res.params[term]))
    lo, hi = np.exp(res.conf_int().loc[term])
    return {"index": index, "outcome": outcome, "specification": spec,
            "alpha": alpha, "aic": float(res.aic), "bic": _bic(res),
            "log_likelihood": float(res.llf), "irr": irr,
            "ci_low": float(lo), "ci_high": float(hi),
            "p_value": float(res.pvalues[term]), "converged": bool(converged),
            "n": int(res.nobs)}


def compare(d, index_col, index_name, adjusted):
    terms = ["idx10"] + (["metro_indicator"] if adjusted else [])
    # Same analytic sample as the primary models, so the comparison describes
    # the specification actually in use. See model_spec.analytic_sample.
    sub = model_spec.analytic_sample(d, index_col)
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
        rows.append(_row(label, oname, "NB2, alpha = 1.0 (sensitivity)", 1.0,
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
           f"{'alpha':>7}{'logLik':>10}{'AIC':>10}{'BIC':>10}"
           f"{'IRR':>8}{'95% CI':>18}{'P':>9}  ")
    for label, grp in tab.groupby("index", sort=False):
        L.append(hdr)
        L.append("-" * 100)
        for _, r in grp.iterrows():
            a = "  -  " if pd.isna(r.alpha) else f"{r.alpha:.3f}"
            ci = f"{r.ci_low:.3f}-{r.ci_high:.3f}"
            star = " *" if r.p_value < 0.05 else ""
            L.append(f"{r['index']:<26}{r.outcome:<7}{r.specification:<30}"
                     f"{a:>7}{r.log_likelihood:>10.1f}{r.aic:>10.1f}{r.bic:>10.1f}"
                     f"{r.irr:>8.3f}{ci:>18}{r.p_value:>9.4f}{star}")
        for criterion in ("aic", "bic"):
            best = grp.loc[grp.groupby("outcome")[criterion].idxmin()]
            for _, b in best.iterrows():
                L.append(f"    best fit for {b.outcome} by {criterion.upper()}: "
                         f"{b.specification} ({criterion.upper()} "
                         f"{b[criterion]:.1f})")
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
    L.append("=" * 100)
    L.append("SPECIFICATION CHOSEN BY INFORMATION CRITERIA")
    L.append("=" * 100)
    wins = {"aic": 0, "bic": 0}
    total = 0
    for (idx, oc), grp in tab.groupby(["index", "outcome"]):
        total += 1
        for criterion in ("aic", "bic"):
            best = grp.loc[grp[criterion].idxmin(), "specification"]
            if "estimated alpha" in best:
                wins[criterion] += 1
    L.append(f"  Estimated-dispersion NB2 has the lowest AIC in "
             f"{wins['aic']} of {total} model/outcome combinations,")
    L.append(f"  and the lowest BIC in {wins['bic']} of {total}.")
    if wins["aic"] == total and wins["bic"] == total:
        L.append("  The estimated-dispersion specification is better supported by both")
        L.append("  AIC and BIC in every comparison.")
    else:
        L.append("  NOTE: the estimated-dispersion specification does NOT win every")
        L.append("  comparison. Do not claim it is better supported by both criteria.")
    L.append("")

    text = "\n".join(L)
    with open(os.path.join(OUT, "model_specification_comparison.txt"), "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
