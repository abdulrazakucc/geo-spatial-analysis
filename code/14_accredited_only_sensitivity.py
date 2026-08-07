#!/usr/bin/env python3
"""
14_accredited_only_sensitivity.py
=================================
Sensitivity analysis restricting the cohort to Status == "Accredited".

The primary cohort defined in the briefing is `Accredited` OR `Under Review`.
That is deliberate and is not changed here. This script re-derives the county
facility counts from the Accredited-only subset and refits the primary SVI
models, so the effect of the 23 Under Review records can be seen directly.

Outputs
    output/results/accredited_only_sensitivity.csv
    output/results/accredited_only_sensitivity.txt

Run
    python code/14_accredited_only_sensitivity.py
"""

import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import statsmodels.api as sm
import statsmodels.discrete.discrete_model as dm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facility_mapping  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE_DIR, "data", "processed")
OUT = os.path.join(BASE_DIR, "output", "results")
os.makedirs(OUT, exist_ok=True)

OUTCOMES = [("cmr_facility_count", "CMR"), ("cct_facility_count", "CCT")]


def county_frame(counts):
    """County dataset with facility counts replaced by the given cohort's."""
    base = pd.read_csv(os.path.join(PROC, "county_analytic_dataset.csv"),
                       dtype={"county_fips": str})
    base = base.drop(columns=["cmr_facility_count", "cct_facility_count"])
    d = base.merge(counts, on="county_fips", how="left")
    for c in ("cmr_facility_count", "cct_facility_count"):
        d[c] = d[c].fillna(0).astype(int)
    return d


def fit(d, outcome, adjusted):
    """Primary SVI model. NB2 with alpha estimated, per 13_model_specification."""
    sub = d[(d.rate_excluded == 0) & (d.adult_pop_45plus > 0)].copy()
    sub["idx10"] = sub["svi_percentile"] * 100.0 / 10.0
    terms = ["idx10"] + (["metro_indicator"] if adjusted else [])
    X = sm.add_constant(sub[terms], has_constant="add")
    res = dm.NegativeBinomial(sub[outcome], X, loglike_method="nb2",
                              offset=np.log(sub["adult_pop_45plus"])
                              ).fit(disp=0, maxiter=300)
    out = {}
    for term, name in [("idx10", "SVI")] + ([("metro_indicator", "metro")] if adjusted else []):
        lo, hi = np.exp(res.conf_int().loc[term])
        out[name] = {"irr": float(np.exp(res.params[term])), "ci_low": float(lo),
                     "ci_high": float(hi), "p": float(res.pvalues[term])}
    out["_alpha"] = float(res.params["alpha"])
    out["_n"] = int(res.nobs)
    return out


def descriptives(d, label):
    el = d[d.rate_excluded == 0]
    return {
        "cohort": label,
        "cmr_facilities": int(d.cmr_facility_count.sum()),
        "cct_facilities": int(d.cct_facility_count.sum()),
        "counties_with_cmr": int((d.cmr_facility_count > 0).sum()),
        "counties_with_cct": int((d.cct_facility_count > 0).sum()),
        "counties_with_neither": int(((d.cmr_facility_count == 0)
                                      & (d.cct_facility_count == 0)).sum()),
        "pct_cmr_metro": float(d.loc[d.metro_indicator == 1, "cmr_facility_count"].sum()
                               / d.cmr_facility_count.sum() * 100),
        "pct_cct_metro": float(d.loc[d.metro_indicator == 1, "cct_facility_count"].sum()
                               / d.cct_facility_count.sum() * 100),
        "n_rate_eligible": int(len(el)),
    }


def main():
    universe = pd.read_csv(os.path.join(PROC, "county_analytic_dataset.csv"),
                           dtype={"county_fips": str})
    valid = set(universe.county_fips)

    _, primary_counts = facility_mapping.build(valid, write_audit=False)
    _, accred_counts = facility_mapping.build(valid, accredited_only=True,
                                              write_audit=False)

    cohorts = [("Primary (Accredited + Under Review)", county_frame(primary_counts)),
               ("Sensitivity (Accredited only)", county_frame(accred_counts))]

    desc_rows, model_rows = [], []
    for label, d in cohorts:
        desc_rows.append(descriptives(d, label))
        for outcome, oname in OUTCOMES:
            for adjusted in (False, True):
                r = fit(d, outcome, adjusted)
                spec = "adjusted" if adjusted else "unadjusted"
                for term in ("SVI", "metro"):
                    if term not in r:
                        continue
                    model_rows.append({
                        "cohort": label, "outcome": oname, "model": spec,
                        "term": term, "irr": r[term]["irr"],
                        "ci_low": r[term]["ci_low"], "ci_high": r[term]["ci_high"],
                        "p_value": r[term]["p"], "alpha": r["_alpha"], "n": r["_n"]})

    desc = pd.DataFrame(desc_rows)
    models = pd.DataFrame(model_rows)
    models.to_csv(os.path.join(OUT, "accredited_only_sensitivity.csv"), index=False)

    L = ["=" * 88, "ACCREDITED-ONLY SENSITIVITY ANALYSIS", "=" * 88,
         "Primary cohort keeps Accredited and Under Review, as specified in the",
         "briefing. This compares it with an Accredited-only cohort.", ""]
    L.append(f"  {'Quantity':<28}{'Primary':>16}{'Accredited only':>18}{'Difference':>13}")
    L.append("  " + "-" * 74)
    p, a = desc.iloc[0], desc.iloc[1]
    for key, lbl, fmt in [
            ("cmr_facilities", "CMR facilities", "{:,.0f}"),
            ("cct_facilities", "CCT facilities", "{:,.0f}"),
            ("counties_with_cmr", "counties with >=1 CMR", "{:,.0f}"),
            ("counties_with_cct", "counties with >=1 CCT", "{:,.0f}"),
            ("counties_with_neither", "counties with neither", "{:,.0f}"),
            ("pct_cmr_metro", "% CMR in metro", "{:.1f}"),
            ("pct_cct_metro", "% CCT in metro", "{:.1f}")]:
        diff = a[key] - p[key]
        L.append(f"  {lbl:<28}{fmt.format(p[key]):>16}{fmt.format(a[key]):>18}"
                 f"{fmt.format(diff):>13}")
    L.append("")
    L.append("  SVI models, negative binomial with alpha estimated")
    L.append("  " + "-" * 74)
    L.append(f"  {'Cohort':<34}{'Outcome':<6}{'Model':<12}{'IRR':>7}{'95% CI':>16}{'P':>9}")
    for _, r in models[models.term == "SVI"].iterrows():
        ci = f"{r.ci_low:.3f}-{r.ci_high:.3f}"
        star = " *" if r.p_value < 0.05 else ""
        short = "Primary" if r.cohort.startswith("Primary") else "Accredited only"
        L.append(f"  {short:<34}{r.outcome:<6}{r.model:<12}{r.irr:>7.3f}{ci:>16}"
                 f"{r.p_value:>9.4f}{star}")
    L.append("")
    same = all(
        (models[(models.cohort == cohorts[0][0]) & (models.term == "SVI")].p_value.values < 0.05)
        == (models[(models.cohort == cohorts[1][0]) & (models.term == "SVI")].p_value.values < 0.05))
    L.append("  Conclusion: the two cohorts reach the same significance conclusions."
             if same else
             "  Conclusion: significance differs between cohorts. Report both.")
    text = "\n".join(L)
    with open(os.path.join(OUT, "accredited_only_sensitivity.txt"), "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
