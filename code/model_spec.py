#!/usr/bin/env python3
"""
model_spec.py
=============
Single definition of the count-model specification and the regression analytic
sample, so every script reports the same primary model.

Primary specification
---------------------
Negative binomial (NB2) with the **dispersion parameter estimated from the
data**, a log(adults aged 45+) offset, and the index scaled per 10 points.

The project briefing asked for negative binomial regression, the dispersion
parameter, and an AIC comparison against Poisson. Estimating the dispersion is
what makes the first two of those reportable. Across all model/outcome
combinations the estimated-dispersion specification was better supported by both
AIC and BIC than the fixed alpha = 1.0 specification
(`output/results/model_specification_comparison.*`).

The fixed alpha = 1.0 specification is retained as a labelled sensitivity
analysis, not discarded.

Regression analytic sample
--------------------------
All counties with a non-missing index and adults aged 45+ greater than zero.

The briefing excludes counties with fewer than 1,000 adults aged 45+ from
*per-capita rate* calculations, while keeping them in count-based analyses. The
regressions here are count models with a population offset, so the restriction
does not apply to them; `rate_excluded` continues to govern rate calculations.
Restricting the regressions as well is available as a sensitivity.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import statsmodels.api as sm
import statsmodels.discrete.discrete_model as dm
from statsmodels.genmod.families import NegativeBinomial

__all__ = [
    "PRIMARY_LABEL", "SENSITIVITY_LABEL",
    "analytic_sample", "fit_primary", "fit_primary_terms",
    "fit_fixed_alpha", "estimates", "alpha_of",
]

PRIMARY_LABEL = "negative binomial, dispersion estimated"
SENSITIVITY_LABEL = "negative binomial, dispersion fixed at alpha = 1.0"

MAXITER = 300


def analytic_sample(df: pd.DataFrame, index_col: str,
                    restrict_rate_eligible: bool = False) -> pd.DataFrame:
    """Rows usable by a count regression on `index_col`.

    `restrict_rate_eligible=True` reproduces the previous behaviour, in which
    counties with fewer than 1,000 adults aged 45+ were also dropped from the
    regressions. That is the sensitivity analysis, not the primary sample.
    """
    keep = df[index_col].notna() & (df["adult_pop_45plus"] > 0)
    if restrict_rate_eligible:
        keep &= df["rate_excluded"] == 0
    out = df[keep].copy()
    out["idx10"] = out[index_col] / 10.0
    return out


def _design(d: pd.DataFrame, adjusted: bool):
    terms = ["idx10"] + (["metro_indicator"] if adjusted else [])
    return sm.add_constant(d[terms], has_constant="add"), np.log(d["adult_pop_45plus"])


def fit_primary(d: pd.DataFrame, outcome: str, adjusted: bool):
    """NB2 with dispersion estimated by maximum likelihood."""
    X, offset = _design(d, adjusted)
    return dm.NegativeBinomial(d[outcome], X, loglike_method="nb2",
                               offset=offset).fit(disp=0, maxiter=MAXITER)


def fit_fixed_alpha(d: pd.DataFrame, outcome: str, adjusted: bool, alpha: float = 1.0):
    """NB GLM with the dispersion held fixed. Sensitivity analysis only."""
    X, offset = _design(d, adjusted)
    return sm.GLM(d[outcome], X, family=NegativeBinomial(alpha=alpha),
                  offset=offset).fit()


def fit_primary_terms(d: pd.DataFrame, outcome: str, terms: list):
    """Primary specification with an explicit term list.

    Used where the adjustment set is not simply index +/- metro, such as the
    ordinal-RUCC and metro-stratified variants.
    """
    X = sm.add_constant(d[terms], has_constant="add")
    return dm.NegativeBinomial(d[outcome], X, loglike_method="nb2",
                               offset=np.log(d["adult_pop_45plus"])
                               ).fit(disp=0, maxiter=MAXITER)


def estimates(res, term: str) -> dict:
    """IRR, 95% CI and P for one term, in the shape the pipeline already uses."""
    lo, hi = np.exp(res.conf_int().loc[term])
    return {"IRR": float(np.exp(res.params[term])), "CI_low": float(lo),
            "CI_high": float(hi), "P": float(res.pvalues[term])}


def alpha_of(res) -> float | None:
    """Estimated dispersion, when the fit carries one."""
    try:
        return float(res.params["alpha"])
    except (KeyError, TypeError):
        return None
