"""
03_descriptive_analysis.py
==========================
Generates Table 1: Descriptive statistics by SVI quartile and rurality.
Computes Spearman correlations between facility rates and SVI.

Input:
    - data/processed/county_analytic_dataset.csv

Output:
    - output/tables/table1_descriptive.csv
    - output/tables/table1_formatted.txt
"""

import os
import numpy as np
import pandas as pd
from scipy import stats

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
TABLE_DIR = os.path.join(BASE_DIR, "output", "tables")
os.makedirs(TABLE_DIR, exist_ok=True)


def load_data():
    """Load the analytic dataset."""
    df = pd.read_csv(
        os.path.join(PROC_DIR, "county_analytic_dataset.csv"),
        dtype={'county_fips': str}
    )
    print(f"Loaded analytic dataset: {len(df)} counties")
    return df


def compute_stratum_stats(df, mask, label):
    """Compute summary statistics for a stratum of counties."""
    sub = df[mask].copy()
    sub_rate = sub[sub['rate_excluded'] == 0]
    
    n_counties = len(sub)
    adult_pop_millions = sub['adult_pop_45plus'].sum() / 1_000_000
    
    # CMR
    cmr_sites = sub['cmr_facility_count'].sum()
    cmr_counties_with = (sub['cmr_facility_count'] > 0).sum()
    cmr_pct = cmr_counties_with / n_counties * 100 if n_counties > 0 else 0
    cmr_rate_med = sub_rate['cmr_rate_per_100k'].median() if len(sub_rate) > 0 else np.nan
    cmr_rate_q1 = sub_rate['cmr_rate_per_100k'].quantile(0.25) if len(sub_rate) > 0 else np.nan
    cmr_rate_q3 = sub_rate['cmr_rate_per_100k'].quantile(0.75) if len(sub_rate) > 0 else np.nan
    
    # CCT
    cct_sites = sub['cct_facility_count'].sum()
    cct_rate_med = sub_rate['cct_rate_per_100k'].median() if len(sub_rate) > 0 else np.nan
    cct_rate_q1 = sub_rate['cct_rate_per_100k'].quantile(0.25) if len(sub_rate) > 0 else np.nan
    cct_rate_q3 = sub_rate['cct_rate_per_100k'].quantile(0.75) if len(sub_rate) > 0 else np.nan
    
    return {
        'Stratum': label,
        'n_counties': n_counties,
        'adult_45plus_millions': round(adult_pop_millions, 2),
        'cmr_sites': int(cmr_sites),
        'cmr_counties_with_pct': f"{cmr_counties_with} ({cmr_pct:.1f}%)",
        'cmr_rate_median_iqr': f"{cmr_rate_med:.2f} ({cmr_rate_q1:.2f}–{cmr_rate_q3:.2f})",
        'cct_sites': int(cct_sites),
        'cct_rate_median_iqr': f"{cct_rate_med:.2f} ({cct_rate_q1:.2f}–{cct_rate_q3:.2f})",
    }


def build_table1(df):
    """Build Table 1 with all strata."""
    print("\n" + "=" * 60)
    print("TABLE 1: Capacity by SVI Quartile and Rurality")
    print("=" * 60)
    
    rows = []
    
    # All counties
    rows.append(compute_stratum_stats(df, pd.Series(True, index=df.index), "All counties"))
    
    # By SVI quartile
    for q in [1, 2, 3, 4]:
        label_map = {1: "Q1 (least vulnerable)", 2: "Q2", 3: "Q3", 4: "Q4 (most vulnerable)"}
        mask = df['svi_quartile'] == q
        rows.append(compute_stratum_stats(df, mask, label_map[q]))
    
    # By rurality
    rows.append(compute_stratum_stats(df, df['metro_indicator'] == 1, "Metropolitan (RUCC 1–3)"))
    rows.append(compute_stratum_stats(df, df['metro_indicator'] == 0, "Nonmetropolitan (RUCC 4–9)"))
    
    table = pd.DataFrame(rows)
    return table


def compute_spearman(df):
    """Compute Spearman correlations between rates and SVI."""
    print("\n" + "=" * 60)
    print("SPEARMAN CORRELATIONS")
    print("=" * 60)
    
    # Use only non-rate-excluded counties
    sub = df[df['rate_excluded'] == 0].dropna(subset=['svi_percentile'])
    
    # CMR rate vs SVI
    rho_cmr, p_cmr = stats.spearmanr(sub['cmr_rate_per_100k'], sub['svi_percentile'])
    print(f"  CMR rate vs SVI: rho = {rho_cmr:.4f}, p = {p_cmr:.4e}")
    
    # CCT rate vs SVI
    rho_cct, p_cct = stats.spearmanr(sub['cct_rate_per_100k'], sub['svi_percentile'])
    print(f"  CCT rate vs SVI: rho = {rho_cct:.4f}, p = {p_cct:.4e}")
    
    return {
        'cmr_rho': rho_cmr, 'cmr_p': p_cmr,
        'cct_rho': rho_cct, 'cct_p': p_cct
    }


def main():
    df = load_data()
    
    # Build Table 1
    table1 = build_table1(df)
    
    # Spearman correlations
    spearman = compute_spearman(df)
    
    # Save Table 1
    table1_path = os.path.join(TABLE_DIR, "table1_descriptive.csv")
    table1.to_csv(table1_path, index=False)
    print(f"\n  ✓ Saved: {table1_path}")
    
    # Formatted output
    print("\n" + "=" * 60)
    print("TABLE 1 (Formatted)")
    print("=" * 60)
    print(table1.to_string(index=False))
    print(f"\nSpearman correlation (facility rate vs SVI percentile):")
    print(f"  CMR: rho = {spearman['cmr_rho']:.3f}, p = {spearman['cmr_p']:.4f}")
    print(f"  CCT: rho = {spearman['cct_rho']:.3f}, p = {spearman['cct_p']:.4f}")
    
    # Save formatted text
    txt_path = os.path.join(TABLE_DIR, "table1_formatted.txt")
    with open(txt_path, 'w') as f:
        f.write("Table 1. ACR-Accredited Cardiac Imaging Capacity by Social Vulnerability and Rurality\n")
        f.write("=" * 90 + "\n\n")
        f.write(table1.to_string(index=False))
        f.write(f"\n\n{'─' * 90}\n")
        f.write(f"Spearman rank correlation (facility rate vs SVI percentile, continuous):\n")
        f.write(f"  CMR: ρ = {spearman['cmr_rho']:.3f}, p = {spearman['cmr_p']:.4f}\n")
        f.write(f"  CCT: ρ = {spearman['cct_rho']:.3f}, p = {spearman['cct_p']:.4f}\n")
        f.write(f"\n{'─' * 90}\n")
        f.write("Notes: SVI from CDC/ATSDR 2022, overall percentile rank. RUCC from USDA ERS 2023.\n")
        f.write("Population denominators from ACS 5-year estimates 2019–2023.\n")
        f.write("Counties with <1,000 adults aged ≥45 excluded from rate calculations.\n")
    print(f"  ✓ Saved: {txt_path}")


if __name__ == "__main__":
    main()
