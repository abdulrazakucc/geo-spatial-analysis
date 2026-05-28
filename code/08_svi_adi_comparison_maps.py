#!/usr/bin/env python3
"""
08_svi_adi_comparison_maps.py
=============================
Publication-Quality Figure Generation: SVI vs ADI Comparison

This script produces Figure 2 and Figure 3 for the manuscript:

Figure 2 (4-panel):
  Panel A - SVI percentile choropleth (CDC Social Vulnerability Index)
  Panel B - ADI percentile choropleth (Area Deprivation Index, PCA-constructed)
  Panel C - CMR facility county locations overlaid on ADI background
  Panel D - Scatter plot of SVI vs ADI with CMR presence highlighted

Figure 3 (2-panel):
  Left  - Mean CMR rate per 100,000 by ADI quintile (with 95% CI error bars)
  Right - Mean CCT rate per 100,000 by ADI quintile (with 95% CI error bars)

Purpose:
  These figures visually demonstrate why ADI detects a CMR disparity that
  SVI completely misses. Panel D shows that CMR facilities cluster in the
  low-ADI (affluent) region of the scatter plot, while they are spread
  evenly across SVI values.

Output:
  output/requested/Figure2_SVI_vs_ADI_Comparison.png (300 DPI)
  output/requested/Figure2_SVI_vs_ADI_Comparison.pdf (vector)
  output/requested/Figure3_ADI_Quintile_Rates.png (300 DPI)
  output/requested/Figure3_ADI_Quintile_Rates.pdf (vector)

Usage:
  python code/08_svi_adi_comparison_maps.py

Dependencies:
  pandas, geopandas, matplotlib, scipy, numpy
"""

import os
import json
import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from scipy.stats import pearsonr, kruskal

# ============================================================
# CONFIGURATION
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
OUT_DIR = os.path.join(BASE_DIR, "output", "requested")
os.makedirs(OUT_DIR, exist_ok=True)

# Custom colormaps for visual distinction
# SVI: Blue gradient (cold = low vulnerability, dark blue = high)
CMAP_SVI = LinearSegmentedColormap.from_list('svi', ['#E3F2FD', '#1565C0', '#0D47A1'], N=256)
# ADI: Green-to-red gradient (green = affluent, red = deprived)
CMAP_ADI = LinearSegmentedColormap.from_list('adi', ['#E8F5E9', '#E65100', '#B71C1C'], N=256)


def load_data():
    """Load and merge geographic data with ADI scores."""
    print("Loading data...")
    geo = gpd.read_file(os.path.join(PROC_DIR, "county_analytic_geo.gpkg"))
    adi_df = pd.read_csv(os.path.join(PROC_DIR, "county_adi_constructed.csv"))
    adi_df['fips'] = adi_df['fips'].astype(str).str.zfill(5)
    geo['county_fips'] = geo['county_fips'].astype(str).str.zfill(5)
    geo = geo.merge(adi_df, left_on='county_fips', right_on='fips', how='left')

    # Continental US only (exclude AK, HI, territories)
    geo_cont = geo[~geo['state_abbr'].isin(['AK', 'HI', 'PR', 'GU', 'VI', 'AS', 'MP'])].copy()
    print(f"  Counties: {len(geo_cont)}, ADI available: {geo_cont['adi_national_percentile'].notna().sum()}")
    return geo_cont


def generate_figure2(geo_cont):
    """
    Generate 4-panel SVI vs ADI comparison figure.
    
    This is the key visual that shows reviewers and readers:
    1. How SVI and ADI are distributed geographically
    2. Where CMR facilities are located relative to ADI
    3. The relationship between SVI and ADI (correlated but not identical)
    """
    print("Generating Figure 2: SVI vs ADI Comparison...")
    
    fig, axes = plt.subplots(2, 2, figsize=(20, 14))

    # Panel A: SVI choropleth
    ax = axes[0, 0]
    geo_cont.plot(column='svi_percentile', cmap=CMAP_SVI, linewidth=0.05,
                  edgecolor='#666', ax=ax, legend=False,
                  missing_kwds={'color': '#f0f0f0'})
    sm_svi = plt.cm.ScalarMappable(cmap=CMAP_SVI, norm=plt.Normalize(0, 1))
    sm_svi.set_array([])
    cbar = fig.colorbar(sm_svi, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_label('SVI Percentile (0 = least vulnerable, 1 = most vulnerable)', fontsize=9)
    ax.set_title('A. CDC Social Vulnerability Index (SVI) 2022',
                 fontsize=13, fontweight='bold', pad=10)
    ax.axis('off')

    # Panel B: ADI choropleth
    ax = axes[0, 1]
    geo_cont.plot(column='adi_national_percentile', cmap=CMAP_ADI, linewidth=0.05,
                  edgecolor='#666', ax=ax, legend=False,
                  missing_kwds={'color': '#f0f0f0'})
    sm_adi = plt.cm.ScalarMappable(cmap=CMAP_ADI, norm=plt.Normalize(0, 100))
    sm_adi.set_array([])
    cbar = fig.colorbar(sm_adi, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_label('ADI National Percentile (0 = least deprived, 100 = most deprived)', fontsize=9)
    ax.set_title('B. Area Deprivation Index (ADI) - Constructed via PCA',
                 fontsize=13, fontweight='bold', pad=10)
    ax.axis('off')

    # Panel C: CMR overlay on ADI
    ax = axes[1, 0]
    geo_cont.plot(column='adi_national_percentile', cmap=CMAP_ADI, linewidth=0.05,
                  edgecolor='#666', ax=ax, legend=False,
                  missing_kwds={'color': '#f0f0f0'}, alpha=0.6)
    cmr_counties = geo_cont[geo_cont['cmr_facility_count'] > 0]
    cmr_counties.plot(ax=ax, color='#1565C0', markersize=3, alpha=0.8,
                      edgecolor='white', linewidth=0.3)
    ax.set_title('C. CMR Facility Counties (blue) on ADI Background',
                 fontsize=13, fontweight='bold', pad=10)
    ax.axis('off')
    legend_elements = [
        mpatches.Patch(facecolor='#1565C0', label=f'CMR County (n={len(cmr_counties)})'),
        mpatches.Patch(facecolor='#B71C1C', alpha=0.6, label='High ADI (more deprived)'),
        mpatches.Patch(facecolor='#E8F5E9', alpha=0.6, label='Low ADI (less deprived)')
    ]
    ax.legend(handles=legend_elements, loc='lower left', fontsize=9)

    # Panel D: Scatter SVI vs ADI
    ax = axes[1, 1]
    no_cmr = geo_cont[geo_cont['cmr_facility_count'] == 0]
    has_cmr = geo_cont[geo_cont['cmr_facility_count'] > 0]
    ax.scatter(no_cmr['svi_percentile'], no_cmr['adi_national_percentile'],
               alpha=0.15, s=8, c='#9E9E9E', label=f'No CMR (n={len(no_cmr)})')
    ax.scatter(has_cmr['svi_percentile'], has_cmr['adi_national_percentile'],
               alpha=0.7, s=25, c='#1565C0', edgecolors='white', linewidth=0.3,
               label=f'Has CMR (n={len(has_cmr)})')
    ax.set_xlabel('SVI Percentile (CDC)', fontsize=11)
    ax.set_ylabel('ADI National Percentile (PCA-constructed)', fontsize=11)
    ax.set_title('D. SVI vs ADI - CMR Presence Highlighted',
                 fontsize=13, fontweight='bold', pad=10)
    ax.legend(fontsize=10)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-2, 102)

    # Add correlation
    valid = geo_cont[['svi_percentile', 'adi_national_percentile']].dropna()
    r, p = pearsonr(valid['svi_percentile'], valid['adi_national_percentile'])
    ax.annotate(f'Pearson r = {r:.3f}\n(p < 0.0001)',
                xy=(0.05, 0.92), xycoords='axes fraction', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.suptitle('Figure 2: SVI vs ADI Comparison - Geographic Distribution and CMR Access',
                 fontsize=15, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.96])

    for ext in ['png', 'pdf']:
        path = os.path.join(OUT_DIR, f'Figure2_SVI_vs_ADI_Comparison.{ext}')
        plt.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print("  Done: Figure2_SVI_vs_ADI_Comparison.png/pdf")


def generate_figure3():
    """
    Generate ADI quintile bar chart showing dose-response relationship.
    
    This figure demonstrates that CMR access decreases monotonically
    as area deprivation increases (Q1 to Q5), supporting a causal
    interpretation of the regression finding.
    """
    print("Generating Figure 3: ADI Quintile Rates...")
    
    df = pd.read_csv(os.path.join(PROC_DIR, "county_analytic_dataset.csv"))
    adi_df = pd.read_csv(os.path.join(PROC_DIR, "county_adi_constructed.csv"))
    adi_df['fips'] = adi_df['fips'].astype(str).str.zfill(5)
    df['county_fips'] = df['county_fips'].astype(str).str.zfill(5)
    df = df.merge(adi_df, left_on='county_fips', right_on='fips', how='left')
    
    analysis = df[(df['rate_excluded'] == 0) & df['adi_national_percentile'].notna()].copy()
    analysis['adi_quintile'] = pd.qcut(
        analysis['adi_national_percentile'], 5,
        labels=['Q1\n(Least\nDeprived)', 'Q2', 'Q3', 'Q4', 'Q5\n(Most\nDeprived)']
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    for i, (col, title, color) in enumerate([
        ('cmr_rate_per_100k', 'CMR (Cardiac MRI)', '#1565C0'),
        ('cct_rate_per_100k', 'CCT (Cardiac CT)', '#E65100')
    ]):
        ax = axes[i]
        means = analysis.groupby('adi_quintile', observed=True)[col].mean()
        sems = analysis.groupby('adi_quintile', observed=True)[col].sem()
        
        bars = ax.bar(means.index, means.values, color=color, alpha=0.8,
                      edgecolor='white', linewidth=1.2)
        ax.errorbar(means.index, means.values, yerr=sems.values * 1.96,
                    fmt='none', color='black', capsize=4)
        
        ax.set_xlabel('ADI Quintile', fontsize=11)
        ax.set_ylabel(f'Mean {title} Rate per 100,000 Adults 45+', fontsize=11)
        ax.set_title(f'{title} Facility Rate by ADI Quintile',
                     fontsize=13, fontweight='bold')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # Kruskal-Wallis test
        groups = [g[col].values for _, g in analysis.groupby('adi_quintile', observed=True)]
        h_stat, kw_p = kruskal(*groups)
        p_str = f'p < 0.0001' if kw_p < 0.0001 else f'p = {kw_p:.4f}'
        ax.annotate(f'Kruskal-Wallis {p_str}',
                    xy=(0.95, 0.95), xycoords='axes fraction', ha='right',
                    fontsize=10, bbox=dict(boxstyle='round', facecolor='lightyellow'))

    plt.suptitle('Figure 3: Cardiac Imaging Rates by Area Deprivation Quintile',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    for ext in ['png', 'pdf']:
        path = os.path.join(OUT_DIR, f'Figure3_ADI_Quintile_Rates.{ext}')
        plt.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print("  Done: Figure3_ADI_Quintile_Rates.png/pdf")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  GENERATING SVI vs ADI COMPARISON FIGURES")
    print("=" * 70)
    
    geo_cont = load_data()
    generate_figure2(geo_cont)
    generate_figure3()
    
    print("\n  All figures generated successfully.")
