#!/usr/bin/env python3
"""
15_svi_quartile_sensitivity.py
==============================
Sensitivity analysis replacing continuous SVI with SVI quartile indicators,
requested in the project briefing (section 3.4).

Quartiles are national distribution-based, Q1 = least vulnerable and the
reference category. Same primary specification as every other model: negative
binomial with the dispersion estimated, log(adults 45+) offset, fitted
unadjusted and adjusted for metropolitan status.

Outputs
    output/results/svi_quartile_regression.csv
    output/results/svi_quartile_regression.txt

Run
    python code/15_svi_quartile_sensitivity.py
"""

import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import statsmodels.api as sm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_spec  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE_DIR, "data", "processed")
OUT = os.path.join(BASE_DIR, "output", "results")
os.makedirs(OUT, exist_ok=True)

OUTCOMES = [("cmr_facility_count", "CMR"), ("cct_facility_count", "CCT")]


def main():
    df = pd.read_csv(os.path.join(PROC, "county_analytic_dataset.csv"),
                     dtype={"county_fips": str})
    d = df[df.adult_pop_45plus > 0].reset_index(drop=True).copy()
    d["svi_q"] = pd.qcut(d.svi_percentile, 4, labels=[1, 2, 3, 4]).astype(int)

    rows = []
    for outcome, oname in OUTCOMES:
        for adjusted in (False, True):
            dummies = pd.get_dummies(d.svi_q, prefix="Q", drop_first=True).astype(float)
            cols = [dummies] + ([d[["metro_indicator"]]] if adjusted else [])
            X = sm.add_constant(pd.concat(cols, axis=1), has_constant="add")
            res = model_spec.fit_primary_terms(
                pd.concat([d[[outcome, "adult_pop_45plus"]], X.drop(columns="const")],
                          axis=1),
                outcome, [c for c in X.columns if c != "const"])
            for term in [c for c in X.columns if c.startswith("Q_")]:
                lo, hi = np.exp(res.conf_int().loc[term])
                rows.append({
                    "outcome": oname,
                    "model": "adjusted for metropolitan status" if adjusted else "unadjusted",
                    "term": f"SVI {term.replace('Q_', 'Q')} vs Q1",
                    "irr": float(np.exp(res.params[term])),
                    "ci_low": float(lo), "ci_high": float(hi),
                    "p_value": float(res.pvalues[term]),
                    "n": int(res.nobs),
                    "alpha": model_spec.alpha_of(res)})

    tab = pd.DataFrame(rows)
    tab.to_csv(os.path.join(OUT, "svi_quartile_regression.csv"), index=False)

    counts = d.groupby("svi_q").size()
    L = ["=" * 84,
         "SVI QUARTILE REGRESSION SENSITIVITY",
         "=" * 84,
         "Continuous SVI replaced by quartile indicators (briefing section 3.4).",
         f"Specification: {model_spec.PRIMARY_LABEL}, log(adults 45+) offset.",
         "Q1 (least vulnerable) is the reference category.",
         "",
         "  Counties per quartile: " + ", ".join(f"Q{k} {v:,}" for k, v in counts.items()),
         "",
         f"  {'Outcome':<8}{'Model':<36}{'Term':<18}{'IRR':>7}{'95% CI':>16}{'P':>9}"]
    L.append("  " + "-" * 92)
    for _, r in tab.iterrows():
        star = " *" if r.p_value < 0.05 else ""
        L.append(f"  {r.outcome:<8}{r.model:<36}{r.term:<18}{r.irr:>7.3f}"
                 f"{f'{r.ci_low:.3f}-{r.ci_high:.3f}':>16}{r.p_value:>9.4f}{star}")
    sig = tab[tab.p_value < 0.05]
    L += ["", "  Quartile contrasts significant at P < 0.05: "
          + (", ".join(f"{r.outcome} {r.term} ({r.model})" for _, r in sig.iterrows())
             if len(sig) else "none")]
    text = "\n".join(L)
    with open(os.path.join(OUT, "svi_quartile_regression.txt"), "w") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
