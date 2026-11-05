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
    "fit_fixed_alpha", "fit_primary_checked", "estimates", "alpha_of",
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


#: Below this, an estimated NB2 dispersion is treated as lying on the boundary
#: of the parameter space (alpha = 0), where NB2 reduces to Poisson.
BOUNDARY_ALPHA = 0.05


def fit_primary_checked(d: pd.DataFrame, outcome: str, terms: list) -> tuple:
    """Primary specification, with the fit diagnosed rather than trusted.

    Returns ``(result, diagnostics)``.

    Why this exists
        In a sparse stratum (14 accredited CMR facilities, each in a different
        nonmetropolitan county) the dispersion estimate collapses towards zero.
        The optimiser then stops at a point where the negated Hessian is not
        positive definite, statsmodels declines to invert it, and the fit carries
        a point estimate with no standard errors. That was previously reported
        as "not estimable".

        It is not a failure of the data. When the likelihood is maximised at
        alpha = 0, the maximum-likelihood NB2 fit *is* the Poisson fit, which
        has a well-defined information matrix for the regression coefficients.
        This function detects exactly that situation and returns the Poisson
        fit, labelled as the boundary solution. Nothing is substituted when the
        Hessian is usable, and nothing is substituted when the failure has any
        other cause: that case keeps its missing inference and is reported NE.

    Diagnostics recorded
        converged, gradient norm, eigenvalues of the negated Hessian, alpha,
        log-likelihood of NB2 and of Poisson, and which solution was returned.
    """
    X = sm.add_constant(d[terms], has_constant="add")
    offset = np.log(d["adult_pop_45plus"])
    model = dm.NegativeBinomial(d[outcome], X, loglike_method="nb2", offset=offset)
    res = model.fit(disp=0, maxiter=MAXITER)
    neg_h = -model.hessian(res.params.values)
    eig = np.linalg.eigvalsh(neg_h) if np.all(np.isfinite(neg_h)) else np.array([np.nan])
    grad = model.score(res.params.values)
    diag = {
        "solution": "NB2",
        "converged": bool(res.mle_retvals.get("converged", False)),
        "gradient_max_abs": float(np.max(np.abs(grad))),
        "gradient": {k: float(v) for k, v in zip(res.params.index, grad)},
        "neg_hessian_eigenvalues": [float(v) for v in eig],
        "hessian_positive_definite": bool(np.all(eig > 0)),
        "alpha": float(res.params["alpha"]),
        "llf_nb2": float(res.llf),
        "events": int(d[outcome].sum()),
        "units_with_event": int((d[outcome] > 0).sum()),
        "max_count": int(d[outcome].max()),
        "n": int(len(d)),
    }
    if diag["hessian_positive_definite"]:
        return res, diag
    pois = sm.GLM(d[outcome], X, family=sm.families.Poisson(), offset=offset).fit()
    diag["llf_poisson"] = float(pois.llf)
    # The boundary case: alpha near zero, and Poisson (alpha = 0 exactly) fits
    # at least as well as the point the optimiser stopped at.
    if diag["alpha"] < BOUNDARY_ALPHA and pois.llf >= res.llf - 1e-6:
        diag["solution"] = "Poisson (NB2 dispersion on the boundary, alpha = 0)"
        return pois, diag
    diag["solution"] = "NB2, information matrix not invertible (not estimable)"
    return res, diag


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
