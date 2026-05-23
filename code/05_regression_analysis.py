"""
05_regression_analysis.py
=========================
Runs negative binomial regression models and sensitivity analyses.

Primary model:
    Facility count ~ SVI percentile (per 10-percentile) + offset(log(adult_pop_45plus))

Sensitivity:
    1. Exclude "Under Review" facilities
    2. SVI quartile dummies instead of continuous
    3. Stratified by metro/non-metro

Input:
    - data/processed/county_analytic_dataset.csv

Output:
    - output/models/regression_results.txt
    - output/models/model_objects.pkl
"""

import os
import pickle
import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.genmod.generalized_linear_model import GLM
from statsmodels.genmod.families import Poisson, NegativeBinomial

warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
MODEL_DIR = os.path.join(BASE_DIR, "output", "models")
os.makedirs(MODEL_DIR, exist_ok=True)


def load_data():
    """Load analytic dataset and prepare for regression."""
    df = pd.read_csv(
        os.path.join(PROC_DIR, "county_analytic_dataset.csv"),
        dtype={'county_fips': str}
    )
    # Exclude rate-excluded counties from regression
    df = df[df['rate_excluded'] == 0].copy()
    df = df.dropna(subset=['svi_percentile', 'adult_pop_45plus']).copy()
    
    # Create SVI per 10-percentile (0-10 scale)
    df['svi_per10'] = df['svi_percentile'] * 10
    
    # Log offset
    df['log_offset'] = np.log(df['adult_pop_45plus'])
    
    # SVI quartile dummies
    df['svi_q2'] = (df['svi_quartile'] == 2).astype(int)
    df['svi_q3'] = (df['svi_quartile'] == 3).astype(int)
    df['svi_q4'] = (df['svi_quartile'] == 4).astype(int)
    
    print(f"Regression sample: {len(df)} counties (after excluding rate-excluded and missing)")
    return df


def fit_negbin(endog, exog, offset, label=""):
    """Fit a negative binomial regression model."""
    try:
        model = sm.GLM(
            endog, exog, family=sm.families.NegativeBinomial(alpha=1.0),
            offset=offset
        )
        result = model.fit(maxiter=100)
        return result
    except Exception as e:
        print(f"  ⚠ NegBin failed for {label}: {e}")
        # Fallback: try Poisson
        model = sm.GLM(endog, exog, family=sm.families.Poisson(), offset=offset)
        result = model.fit()
        return result


def fit_poisson(endog, exog, offset):
    """Fit a Poisson regression model (for AIC comparison)."""
    model = sm.GLM(endog, exog, family=sm.families.Poisson(), offset=offset)
    result = model.fit()
    return result


def report_model(result, model_name, output_lines):
    """Extract and report key results from a model."""
    output_lines.append(f"\n{'─' * 70}")
    output_lines.append(f"Model: {model_name}")
    output_lines.append(f"{'─' * 70}")
    
    params = result.params
    conf = result.conf_int()
    pvalues = result.pvalues
    
    # IRR = exp(coefficient)
    output_lines.append(f"{'Variable':<20} {'IRR':>8} {'95% CI':>20} {'p-value':>10}")
    output_lines.append(f"{'─' * 60}")
    
    for i, name in enumerate(result.model.exog_names):
        irr = np.exp(params.iloc[i])
        ci_lo = np.exp(conf.iloc[i, 0])
        ci_hi = np.exp(conf.iloc[i, 1])
        p = pvalues.iloc[i]
        output_lines.append(
            f"{name:<20} {irr:>8.4f} ({ci_lo:.4f}–{ci_hi:.4f}) {p:>10.4f}"
        )
    
    output_lines.append(f"\nAIC: {result.aic:.1f}")
    output_lines.append(f"Deviance: {result.deviance:.1f}")
    output_lines.append(f"Pearson chi2: {result.pearson_chi2:.1f}")
    output_lines.append(f"N: {result.nobs:.0f}")
    
    return output_lines


def main():
    print("=" * 60)
    print("REGRESSION ANALYSIS")
    print("=" * 60)
    
    df = load_data()
    output_lines = []
    output_lines.append("=" * 70)
    output_lines.append("REGRESSION RESULTS: ACR Cardiac Imaging Geographic Disparities")
    output_lines.append("=" * 70)
    
    model_objects = {}
    
    for modality, count_col in [('CMR', 'cmr_facility_count'), ('CCT', 'cct_facility_count')]:
        output_lines.append(f"\n\n{'═' * 70}")
        output_lines.append(f"MODALITY: {modality}")
        output_lines.append(f"{'═' * 70}")
        
        endog = df[count_col].values
        offset = df['log_offset'].values
        
        # --- Primary Model: Continuous SVI ---
        X = sm.add_constant(df[['svi_per10']])
        
        # Poisson (for comparison)
        pois_result = fit_poisson(endog, X, offset)
        model_objects[f'{modality}_poisson_continuous'] = pois_result
        
        # Negative Binomial
        nb_result = fit_negbin(endog, X, offset, label=f"{modality} primary")
        model_objects[f'{modality}_negbin_continuous'] = nb_result
        
        output_lines = report_model(nb_result, f"{modality} — Primary (SVI continuous, per 10-percentile)", output_lines)
        output_lines.append(f"\nPoisson AIC: {pois_result.aic:.1f} vs NegBin AIC: {nb_result.aic:.1f}")
        output_lines.append(f"→ {'Negative Binomial preferred' if nb_result.aic < pois_result.aic else 'Poisson preferred'}")
        
        # --- Sensitivity 1: SVI Quartile Dummies ---
        X_q = sm.add_constant(df[['svi_q2', 'svi_q3', 'svi_q4']])
        nb_q = fit_negbin(endog, X_q, offset, label=f"{modality} quartile")
        model_objects[f'{modality}_negbin_quartile'] = nb_q
        output_lines = report_model(nb_q, f"{modality} — Sensitivity: SVI Quartile Dummies (ref=Q1)", output_lines)
        
        # --- Sensitivity 2: Stratified by Metro ---
        for metro_val, metro_label in [(1, "Metropolitan"), (0, "Nonmetropolitan")]:
            sub = df[df['metro_indicator'] == metro_val]
            if len(sub) > 10:
                X_s = sm.add_constant(sub[['svi_per10']])
                endog_s = sub[count_col].values
                offset_s = sub['log_offset'].values
                nb_s = fit_negbin(endog_s, X_s, offset_s, label=f"{modality} {metro_label}")
                model_objects[f'{modality}_negbin_{metro_label.lower()}'] = nb_s
                output_lines = report_model(nb_s, f"{modality} — Stratified: {metro_label} only", output_lines)
    
    # Print results
    print("\n".join(output_lines))
    
    # Save
    txt_path = os.path.join(MODEL_DIR, "regression_results.txt")
    with open(txt_path, 'w') as f:
        f.write("\n".join(output_lines))
    print(f"\n  ✓ Saved: {txt_path}")
    
    pkl_path = os.path.join(MODEL_DIR, "model_objects.pkl")
    with open(pkl_path, 'wb') as f:
        pickle.dump(model_objects, f)
    print(f"  ✓ Saved: {pkl_path}")
    
    # Summary for manuscript
    print("\n" + "=" * 60)
    print("MANUSCRIPT SUMMARY (for inline reporting)")
    print("=" * 60)
    
    for modality in ['CMR', 'CCT']:
        key = f'{modality}_negbin_continuous'
        if key in model_objects:
            r = model_objects[key]
            # SVI coefficient (index 1, after constant)
            irr = np.exp(r.params.iloc[1])
            ci = np.exp(r.conf_int().iloc[1])
            p = r.pvalues.iloc[1]
            print(f"\n  {modality}: For each 10-percentile increase in social vulnerability,")
            print(f"  the incidence rate ratio of accredited facilities was")
            print(f"  {irr:.3f} (95% CI: {ci.iloc[0]:.3f}–{ci.iloc[1]:.3f}, p={p:.4f}).")


if __name__ == "__main__":
    main()
