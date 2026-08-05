#!/usr/bin/env python3
"""
06_edi_sensitivity_analysis.py
==============================
Economic Deprivation Index (EDI) as an alternative predictor to SVI.

Naming note
    This index was previously called "ADI" in earlier drafts. It was renamed to
    EDI (Economic Deprivation Index) for the JACR submission because "ADI"
    collides with the validated Singh / Wisconsin Area Deprivation Index, which
    is a different instrument that we do not use here. The construction is
    unchanged, only the label. See docs/PCA_Explanation.md.

The EDI is built in-repo via PCA of 6 ACS-derived socioeconomic indicators,
because no county-level deprivation index of this construction exists off the
shelf.

This script
    1. Constructs the county-level EDI via PCA.
    2. Fits the CMR and CCT negative binomial models, UNADJUSTED and ADJUSTED
       for metropolitan status, per 10-percentile of EDI.
    3. Fits the same models with ordinal RUCC in place of the binary metro flag,
       and stratified by metro status.
    4. Compares against the SVI models.

Key finding (JACR framing)
    The unadjusted EDI-CMR association (IRR 0.937, P 0.002) does not survive
    adjustment for rurality (IRR 0.983, P 0.43). Metropolitan status itself
    carries IRR 8.23. The substantive conclusion is that accredited capacity is
    concentrated in metropolitan counties, and that deprivation indices should
    not be used as proxies for imaging access without adjusting for rurality.

    The earlier framing, that the EDI detects a deprivation gradient the SVI
    misses, was the JACC submission's claim and did not survive review. It is
    retained here only as the unadjusted row, for transparency.

References
    Singh GK. Am J Public Health. 2003;93(7):1137-1143.
    Kind AJH, Buckingham W. N Engl J Med. 2018;378:2456-2458.
"""

import os
import json
import pandas as pd
import numpy as np
import statsmodels.api as sm
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
OUT_DIR = os.path.join(BASE_DIR, "output", "requested")
os.makedirs(OUT_DIR, exist_ok=True)


def construct_county_edi():
    """
    Construct the county-level EDI using Singh (2003) style methodology.
    Uses PCA on 6 ACS-derived socioeconomic indicators.
    """
    print("\n" + "=" * 70)
    print("  STEP 1: CONSTRUCTING COUNTY-LEVEL EDI")
    print("=" * 70)

    # Load SVI individual indicators
    svi = pd.read_csv(os.path.join(RAW_DIR, "SVI_2022_US_county.csv"))
    svi['fips'] = svi['FIPS'].astype(str).str.zfill(5)

    # Load County Health Rankings for income data
    chr_df = pd.read_csv(
        os.path.join(RAW_DIR, "county_health_rankings_2024.csv"),
        encoding='latin1', low_memory=False
    )
    chr_df = chr_df.iloc[1:].copy()  # Skip sub-header row
    chr_df['fips'] = chr_df['5-digit FIPS Code'].astype(str).str.zfill(5)
    chr_df = chr_df[chr_df['County FIPS Code'] != '000'].copy()

    # Extract variables
    chr_sub = chr_df[['fips', 'Median Household Income raw value', 'Children in Poverty raw value']].copy()
    chr_sub.columns = ['fips', 'median_income', 'child_poverty']
    for c in ['median_income', 'child_poverty']:
        chr_sub[c] = pd.to_numeric(chr_sub[c], errors='coerce')

    svi_sub = svi[['fips', 'EP_POV150', 'EP_UNEMP', 'EP_NOHSDP', 'EP_HBURD']].copy()

    # Merge
    merged = svi_sub.merge(chr_sub, on='fips', how='left')

    # EDI construction via PCA
    edi_vars = ['EP_POV150', 'EP_UNEMP', 'EP_NOHSDP', 'EP_HBURD', 'median_income', 'child_poverty']
    edi_data = merged[['fips'] + edi_vars].dropna().copy()

    # Invert income (higher = more deprived)
    edi_data['neg_income'] = -edi_data['median_income']

    features = ['EP_POV150', 'EP_UNEMP', 'EP_NOHSDP', 'EP_HBURD', 'neg_income', 'child_poverty']
    X = StandardScaler().fit_transform(edi_data[features])

    pca = PCA(n_components=1)
    scores = pca.fit_transform(X)

    edi_data['edi_raw'] = scores.flatten()
    edi_data['edi_national_percentile'] = edi_data['edi_raw'].rank(pct=True) * 100

    print(f"  Counties with EDI: {len(edi_data)}")
    print(f"  PCA variance explained: {pca.explained_variance_ratio_[0]:.1%}")
    print(f"  Loadings: {dict(zip(features, pca.components_[0].round(3)))}")

    # Save
    out_path = os.path.join(PROC_DIR, "county_edi_constructed.csv")
    edi_data[['fips', 'edi_raw', 'edi_national_percentile']].to_csv(out_path, index=False)
    print(f"  ✓ Saved: {out_path}")

    return edi_data[['fips', 'edi_national_percentile']]


def _fit(analysis, count_col, terms):
    """Fit one negative binomial rate model and return the IRR block for each term."""
    y = analysis[count_col].values
    X = sm.add_constant(analysis[terms], has_constant='add')
    offset = analysis['log_pop'].values
    res = sm.GLM(y, X, family=sm.families.NegativeBinomial(), offset=offset).fit(maxiter=100)
    out = {'n': int(len(analysis)), 'aic': float(res.aic),
           'events': int(y.sum()), 'counties_with_facility': int((y > 0).sum())}
    for t in terms:
        ci = np.exp(res.conf_int().loc[t])
        out[t] = {
            'irr': float(np.exp(res.params[t])),
            'ci_low': float(ci.iloc[0]), 'ci_high': float(ci.iloc[1]),
            'p': float(res.pvalues[t]),
        }
    return out


def run_edi_regressions(edi_df):
    """
    Fit the primary EDI models, unadjusted and adjusted for rurality.

    Rurality is handled three ways so that a reviewer can see the result is not
    an artifact of how rurality is coded:
      - binary metropolitan indicator (RUCC 1-3 vs 4-9), the primary adjustment
      - ordinal RUCC code, 1-9
      - stratified fits within metro and within nonmetro counties
    """
    print("\n" + "=" * 70)
    print("  STEP 2: NEGATIVE BINOMIAL REGRESSION — EDI PREDICTOR")
    print("=" * 70)

    # Load analytic dataset
    df = pd.read_csv(os.path.join(PROC_DIR, "county_analytic_dataset.csv"))
    df['fips'] = df['county_fips'].astype(str).str.zfill(5)
    df = df.merge(edi_df, on='fips', how='left')

    # Filter
    analysis = df[(df['rate_excluded'] == 0) & df['edi_national_percentile'].notna()].copy()
    analysis['edi_per10'] = analysis['edi_national_percentile'] / 10.0
    analysis['log_pop'] = np.log(analysis['adult_pop_45plus'])

    print(f"  Analysis sample: n = {len(analysis)}")

    results = {}
    for modality, col in [('CMR', 'cmr_facility_count'), ('CCT', 'cct_facility_count')]:
        unadj = _fit(analysis, col, ['edi_per10'])
        adj_metro = _fit(analysis, col, ['edi_per10', 'metro_indicator'])
        adj_rucc = _fit(analysis, col, ['edi_per10', 'rucc_code'])

        # Poisson comparison on the unadjusted model, to justify negative binomial
        pois = sm.GLM(analysis[col].values,
                      sm.add_constant(analysis[['edi_per10']], has_constant='add'),
                      family=sm.families.Poisson(),
                      offset=analysis['log_pop'].values).fit(maxiter=100)

        strat = {}
        for label, flag in [('metro', 1), ('nonmetro', 0)]:
            sub = analysis[analysis['metro_indicator'] == flag]
            strat[label] = _fit(sub, col, ['edi_per10'])

        u, a = unadj['edi_per10'], adj_metro['edi_per10']
        m = adj_metro['metro_indicator']
        print(f"\n  {modality}")
        print(f"    EDI unadjusted        IRR = {u['irr']:.4f} "
              f"(95% CI {u['ci_low']:.4f}-{u['ci_high']:.4f}), p = {u['p']:.4f}")
        print(f"    EDI adjusted (metro)  IRR = {a['irr']:.4f} "
              f"(95% CI {a['ci_low']:.4f}-{a['ci_high']:.4f}), p = {a['p']:.4f}")
        print(f"    Metropolitan status   IRR = {m['irr']:.4f} "
              f"(95% CI {m['ci_low']:.2f}-{m['ci_high']:.2f}), p = {m['p']:.2e}")
        print(f"    NegBin AIC = {unadj['aic']:.1f} | Poisson AIC = {pois.aic:.1f}")

        results[modality] = {
            # Back-compatible flat keys describe the UNADJUSTED model, as before
            'irr': u['irr'], 'ci_low': u['ci_low'], 'ci_high': u['ci_high'],
            'p': u['p'], 'n': unadj['n'],
            'aic_nb': unadj['aic'], 'aic_pois': float(pois.aic),
            'unadjusted': u,
            'adjusted_metro': a,
            'metro_effect': m,
            'adjusted_rucc': {'edi': adj_rucc['edi_per10'], 'rucc': adj_rucc['rucc_code']},
            'stratified': {k: v['edi_per10'] for k, v in strat.items()},
            'stratified_n': {k: v['n'] for k, v in strat.items()},
            'stratified_events': {k: {'events': v['events'],
                                      'counties_with_facility': v['counties_with_facility']}
                                  for k, v in strat.items()},
        }

    # Spearman
    cmr_rho, cmr_p = stats.spearmanr(analysis['cmr_rate_per_100k'], analysis['edi_national_percentile'])
    cct_rho, cct_p = stats.spearmanr(analysis['cct_rate_per_100k'], analysis['edi_national_percentile'])
    results['spearman'] = {
        'cmr_rho': float(cmr_rho), 'cmr_p': float(cmr_p),
        'cct_rho': float(cct_rho), 'cct_p': float(cct_p)
    }
    print(f"\n  Spearman: CMR rho={cmr_rho:.4f} | CCT rho={cct_rho:.4f}")

    # How strongly does the EDI itself track rurality? This is the confounding path.
    rucc_rho, rucc_p = stats.spearmanr(analysis['edi_national_percentile'], analysis['rucc_code'])
    metro_mean = analysis.loc[analysis['metro_indicator'] == 1, 'edi_national_percentile'].mean()
    nonmetro_mean = analysis.loc[analysis['metro_indicator'] == 0, 'edi_national_percentile'].mean()
    results['edi_vs_rurality'] = {
        'spearman_rho': float(rucc_rho), 'spearman_p': float(rucc_p),
        'metro_mean': float(metro_mean), 'nonmetro_mean': float(nonmetro_mean),
        'gap': float(nonmetro_mean - metro_mean)
    }
    print(f"  EDI vs RUCC: rho={rucc_rho:.4f} | metro mean {metro_mean:.1f} "
          f"vs nonmetro mean {nonmetro_mean:.1f}")

    # Save JSON
    json_path = os.path.join(PROC_DIR, "edi_regression_results.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  ✓ Saved: {json_path}")

    return results


def write_report(results):
    """Write the supplementary results table as plain text."""
    L = []
    a = L.append
    a("=" * 78)
    a("EDI SENSITIVITY ANALYSIS — UNADJUSTED AND RURALITY-ADJUSTED MODELS")
    a("=" * 78)
    a("Economic Deprivation Index (EDI), county-level, PCA of 6 ACS indicators.")
    a("Negative binomial regression, offset log(adults 45+), IRR per 10 percentile points.")
    a("")
    for modality in ['CMR', 'CCT']:
        r = results[modality]
        a("-" * 78)
        a(f"{modality}   (n = {r['n']} rate-eligible counties)")
        a("-" * 78)
        a(f"{'Model':<40}{'IRR':>8}{'   95% CI':>20}{'P':>10}")
        a("." * 78)
        rows = [
            ("EDI, unadjusted", r['unadjusted']),
            ("EDI, adjusted for metropolitan status", r['adjusted_metro']),
            ("EDI, adjusted for ordinal RUCC", r['adjusted_rucc']['edi']),
            ("EDI, metropolitan counties only", r['stratified']['metro']),
            ("EDI, nonmetropolitan counties only", r['stratified']['nonmetro']),
            ("Metropolitan status (from adjusted model)", r['metro_effect']),
        ]
        for label, e in rows:
            ci = f"{e['ci_low']:.3f}-{e['ci_high']:.3f}"
            star = " *" if e['p'] < 0.05 else ""
            a(f"{label:<40}{e['irr']:>8.4f}{ci:>20}{e['p']:>10.4f}{star}")
        se = r['stratified_events']
        a("")
        a(f"  Stratum sizes. Metropolitan, {r['stratified_n']['metro']} counties carrying "
          f"{se['metro']['events']} facilities in {se['metro']['counties_with_facility']} counties. "
          f"Nonmetropolitan, {r['stratified_n']['nonmetro']} counties carrying "
          f"{se['nonmetro']['events']} facilities in "
          f"{se['nonmetro']['counties_with_facility']} counties.")
        if se['nonmetro']['events'] < 30:
            a(f"  CAUTION. The nonmetropolitan {modality} stratum contains only "
              f"{se['nonmetro']['events']} facilities. Any estimate from it is unstable and")
            a("  should be read as exploratory, not as evidence of an independent gradient.")
        a("")
    rl = results['edi_vs_rurality']
    a("-" * 78)
    a("WHY THE UNADJUSTED SIGNAL APPEARS")
    a("-" * 78)
    a(f"The EDI itself tracks rurality. Spearman rho vs RUCC = {rl['spearman_rho']:.3f}, "
      f"mean EDI {rl['metro_mean']:.1f} in metropolitan counties versus "
      f"{rl['nonmetro_mean']:.1f} in nonmetropolitan counties, a gap of {rl['gap']:.1f} points.")
    a("Because accredited capacity is concentrated in metropolitan counties, an")
    a("unadjusted deprivation model absorbs that rurality signal. Once metropolitan")
    a("status is in the model the deprivation term is no longer associated with capacity.")
    a("")
    a("* P < 0.05")

    report = "\n".join(L)
    for d in [os.path.join(BASE_DIR, "output", "supplementary_data"), OUT_DIR]:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "EDI_Regression_Results.txt"), "w") as f:
            f.write(report + "\n")
    print(report)
    print("\n  ✓ Saved: output/supplementary_data/EDI_Regression_Results.txt")


if __name__ == "__main__":
    print("\n" + "█" * 70)
    print("  EDI SENSITIVITY ANALYSIS")
    print("  Economic Deprivation Index, with rurality adjustment")
    print("█" * 70)

    edi_df = construct_county_edi()
    results = run_edi_regressions(edi_df)
    write_report(results)

    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    for modality in ['CMR', 'CCT']:
        u = results[modality]['unadjusted']
        a = results[modality]['adjusted_metro']
        m = results[modality]['metro_effect']
        print(f"  {modality}: EDI unadjusted IRR={u['irr']:.4f} (p={u['p']:.4f})"
              f"  →  adjusted IRR={a['irr']:.4f} (p={a['p']:.4f})"
              f"  |  metro IRR={m['irr']:.2f}")
    print("\n  → The deprivation association does not survive adjustment for rurality.")
    print("    Metropolitan concentration is the dominant correlate of accredited capacity.")
    print("\n  ✅ Analysis complete.")
