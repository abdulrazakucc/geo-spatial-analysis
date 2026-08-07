"""
07_publication_outputs.py
=========================
Generates all publication-quality deliverables per the project briefing:

1. Figure 1 — Two-panel choropleth (A: CMR, B: CCT) with state boundaries,
   quantile bins, proper legend, 600 DPI PNG + vector PDF
2. Table 1 — Formatted capacity by SVI quartile and rurality with Spearman
3. Regression results — Primary + all sensitivity analyses
4. Sensitivity analysis: Accredited-only cohort
5. PDF Workflow Document — Full methods documentation
6. PowerPoint Presentation — All results explained

Inputs:
    data/processed/county_analytic_dataset.csv
    data/processed/county_analytic_geo.gpkg
    data/ACR_Cardiac_Imaging_Sites.xlsx

Outputs:
    output/figures/figure1_choropleth.pdf  (vector, journal-ready)
    output/figures/figure1_choropleth.png  (600 DPI raster fallback)
    output/tables/table1_publication.csv
    output/tables/table1_publication.txt
    output/models/regression_results_full.txt
"""

import json
import os
import sys
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
import mapclassify
from scipy import stats
import statsmodels.api as sm
from statsmodels.genmod.families import NegativeBinomial, Poisson
import pickle

warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
FIG_DIR = os.path.join(BASE_DIR, "output", "figures")
TBL_DIR = os.path.join(BASE_DIR, "output", "tables")
MDL_DIR = os.path.join(BASE_DIR, "output", "models")

for d in [FIG_DIR, TBL_DIR, MDL_DIR]:
    os.makedirs(d, exist_ok=True)


# ===========================================================================
# DATA LOADING
# ===========================================================================
def load_data():
    """Load the analytic dataset."""
    df = pd.read_csv(
        os.path.join(PROC_DIR, "county_analytic_dataset.csv"),
        dtype={"county_fips": str}
    )
    print(f"✓ Loaded analytic dataset: {len(df)} counties, {len(df.columns)} variables")
    return df


def load_geodata():
    """Load geo-enabled dataset for mapping."""
    gdf = gpd.read_file(os.path.join(PROC_DIR, "county_analytic_geo.gpkg"))
    gdf = gdf.to_crs(epsg=5070)  # Albers Equal Area
    print(f"✓ Loaded geo-dataset: {len(gdf)} counties")
    return gdf


# ===========================================================================
# FIGURE 1: PUBLICATION-QUALITY CHOROPLETH
# ===========================================================================
def create_figure1(gdf):
    """
    Create Figure 1: Two-panel US county choropleth.
    Panel A: CMR rate per 100k adults ≥45
    Panel B: CCT rate per 100k adults ≥45
    
    Specifications per briefing:
    - Sequential blue palette, 5 quantile bins + gray (zero) + white (excluded)
    - State boundaries: thin dark gray overlay
    - County boundaries: hairline lighter gray
    - Albers USA projection
    - Vector PDF + 600 DPI PNG
    """
    print("\n" + "="*70)
    print("FIGURE 1: Two-Panel Choropleth Map")
    print("="*70)
    
    # Set up figure - vertical layout (A above B) for portrait journal
    fig, axes = plt.subplots(2, 1, figsize=(12, 18), facecolor='white')
    plt.subplots_adjust(hspace=0.08)
    
    rate_cols = ['cmr_rate_per_100k', 'cct_rate_per_100k']
    panel_labels = ['A', 'B']
    panel_titles = [
        'ACR-Accredited Cardiac MRI Facilities per 100,000 Adults Aged ≥45 Years',
        'ACR-Accredited Cardiac CT Facilities per 100,000 Adults Aged ≥45 Years'
    ]
    
    # Blue sequential palette (colorblind-safe)
    blues = ['#c6dbef', '#9ecae1', '#6baed6', '#2171b5', '#08306b']
    
    for idx, (col, label, title) in enumerate(zip(rate_cols, panel_labels, panel_titles)):
        ax = axes[idx]
        
        # Classify counties
        excluded = gdf[gdf['rate_excluded'] == 1]
        zero = gdf[(gdf['rate_excluded'] == 0) & (gdf[col] == 0)]
        has_data = gdf[(gdf['rate_excluded'] == 0) & (gdf[col] > 0)]
        
        # Plot excluded (white with thin border)
        if len(excluded) > 0:
            excluded.plot(ax=ax, color='white', edgecolor='#cccccc', linewidth=0.15)
        
        # Plot zero-facility counties (light gray)
        if len(zero) > 0:
            zero.plot(ax=ax, color='#f0f0f0', edgecolor='#cccccc', linewidth=0.15)
        
        # Plot rated counties with quantile classification
        if len(has_data) > 0:
            classifier = mapclassify.Quantiles(has_data[col].values, k=5)
            bins = classifier.bins
            bin_labels = []
            prev = 0
            for b in bins:
                bin_labels.append(f"{prev:.1f}–{b:.1f}")
                prev = b
            
            cmap = ListedColormap(blues)
            bounds = [0] + list(bins)
            norm = BoundaryNorm(bounds, cmap.N)
            
            has_data.plot(
                column=col, ax=ax, cmap=cmap, norm=norm,
                edgecolor='#cccccc', linewidth=0.15
            )
        
        # State boundaries overlay
        state_gdf = gdf.dissolve(by='state_abbr')
        state_gdf.boundary.plot(ax=ax, color='#333333', linewidth=0.6)
        
        # Formatting
        ax.set_axis_off()
        ax.set_title(f"{label}. {title}", fontsize=11, fontweight='bold', 
                     loc='left', pad=12, fontfamily='serif')
        
        # Set extent to continental US (Albers bounds)
        ax.set_xlim([-2.5e6, 2.5e6])
        ax.set_ylim([-1.5e6, 1.6e6])
        
        # Legend
        legend_patches = []
        for i, (color, lbl) in enumerate(zip(blues, bin_labels)):
            legend_patches.append(mpatches.Patch(facecolor=color, edgecolor='#999', 
                                                  linewidth=0.5, label=f"Q{i+1}: {lbl}"))
        legend_patches.append(mpatches.Patch(facecolor='#f0f0f0', edgecolor='#999',
                                             linewidth=0.5, label='Zero facilities'))
        legend_patches.append(mpatches.Patch(facecolor='white', edgecolor='#999',
                                             linewidth=0.5, label='Excluded (pop. <1,000)'))
        
        leg = ax.legend(
            handles=legend_patches,
            title='Facilities per 100,000\nadults aged ≥45',
            loc='lower right',
            fontsize=7.5,
            title_fontsize=8,
            framealpha=0.95,
            edgecolor='#999',
            fancybox=False,
            borderpad=0.8
        )
        leg.get_title().set_fontweight('bold')
    
    # Figure annotation
    fig.text(
        0.5, 0.02,
        "Figure 1. Geographic distribution of ACR-accredited cardiac imaging capacity by US county.\n"
        "Color intensity indicates facility density (quantile-binned among counties with ≥1 facility).\n"
        "Light gray = zero accredited facilities; white = excluded from rate calculation (adult ≥45 population <1,000).\n"
        "State boundaries overlaid. County boundaries: US Census TIGER/Line 2023. Projection: Albers Equal Area (EPSG:5070).\n"
        "Alaska and Hawaii included in analysis; insets omitted for clarity.",
        ha='center', fontsize=7.5, color='#444', style='italic', fontfamily='serif',
        linespacing=1.5
    )
    
    # Save
    pdf_path = os.path.join(FIG_DIR, "figure1_choropleth.pdf")
    png_path = os.path.join(FIG_DIR, "figure1_choropleth.png")
    
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight', dpi=300)
    fig.savefig(png_path, format='png', bbox_inches='tight', dpi=600)
    plt.close()
    
    print(f"  ✓ PDF (vector): {pdf_path}")
    print(f"  ✓ PNG (600 DPI): {png_path}")
    
    # Print bin info
    for col, title in zip(rate_cols, ['CMR', 'CCT']):
        has = gdf[(gdf['rate_excluded'] == 0) & (gdf[col] > 0)]
        print(f"\n  {title} bins (quantile): {mapclassify.Quantiles(has[col].values, k=5).bins}")
        print(f"  Counties with data: {len(has)}, Zero: {len(gdf[(gdf['rate_excluded']==0) & (gdf[col]==0)])}, Excluded: {len(gdf[gdf['rate_excluded']==1])}")


# ===========================================================================
# TABLE 1: PUBLICATION-QUALITY
# ===========================================================================
def create_table1(df):
    """
    Create Table 1: ACR-Accredited Cardiac Imaging Capacity by SVI Quartile and Rurality.
    
    Per briefing:
    - Rows: All, Q1-Q4, Metro, Nonmetro
    - Columns: n counties, adult ≥45 pop, CMR sites, CMR counties, CMR rate median/IQR,
               CCT sites, CCT counties, CCT rate median/IQR
    - Spearman correlation at bottom
    - Proper footnotes
    """
    print("\n" + "="*70)
    print("TABLE 1: Capacity by SVI Quartile and Rurality")
    print("="*70)
    
    # Rate-eligible subset
    df_rates = df[df['rate_excluded'] == 0].copy()
    
    def compute_stratum(subset, subset_rates, label):
        n = len(subset)
        pop45 = subset['adult_pop_45plus'].sum()
        
        cmr_sites = int(subset['cmr_facility_count'].sum())
        cmr_counties = int((subset['cmr_facility_count'] > 0).sum())
        cmr_pct = f"{cmr_counties/n*100:.1f}" if n > 0 else "0.0"
        
        cct_sites = int(subset['cct_facility_count'].sum())
        cct_counties = int((subset['cct_facility_count'] > 0).sum())
        cct_pct = f"{cct_counties/n*100:.1f}" if n > 0 else "0.0"
        
        # Rates (from rate-eligible only)
        sr = subset_rates
        cmr_med = sr['cmr_rate_per_100k'].median()
        cmr_q1 = sr['cmr_rate_per_100k'].quantile(0.25)
        cmr_q3 = sr['cmr_rate_per_100k'].quantile(0.75)
        
        cct_med = sr['cct_rate_per_100k'].median()
        cct_q1 = sr['cct_rate_per_100k'].quantile(0.25)
        cct_q3 = sr['cct_rate_per_100k'].quantile(0.75)
        
        # Mean rates for comparison
        cmr_mean = sr['cmr_rate_per_100k'].mean()
        cct_mean = sr['cct_rate_per_100k'].mean()
        
        return {
            'Stratum': label,
            'Counties (n)': n,
            'Adults ≥45 (millions)': f"{pop45/1e6:.2f}",
            'CMR Sites': cmr_sites,
            'CMR Counties (%)': f"{cmr_counties} ({cmr_pct}%)",
            'CMR Rate Median (IQR)': f"{cmr_med:.2f} ({cmr_q1:.2f}–{cmr_q3:.2f})",
            'CMR Rate Mean': f"{cmr_mean:.2f}",
            'CCT Sites': cct_sites,
            'CCT Counties (%)': f"{cct_counties} ({cct_pct}%)",
            'CCT Rate Median (IQR)': f"{cct_med:.2f} ({cct_q1:.2f}–{cct_q3:.2f})",
            'CCT Rate Mean': f"{cct_mean:.2f}",
        }
    
    rows = []
    
    # All counties
    rows.append(compute_stratum(df, df_rates, 'All counties'))
    
    # By SVI quartile
    for q in range(1, 5):
        label = {1: 'Q1 (least vulnerable)', 2: 'Q2', 3: 'Q3', 4: 'Q4 (most vulnerable)'}[q]
        subset = df[df['svi_quartile'] == q]
        subset_r = df_rates[df_rates['svi_quartile'] == q]
        rows.append(compute_stratum(subset, subset_r, label))
    
    # By metro status
    metro = df[df['metro_indicator'] == 1]
    metro_r = df_rates[df_rates['metro_indicator'] == 1]
    rows.append(compute_stratum(metro, metro_r, 'Metropolitan (RUCC 1–3)'))
    
    nonmetro = df[df['metro_indicator'] == 0]
    nonmetro_r = df_rates[df_rates['metro_indicator'] == 0]
    rows.append(compute_stratum(nonmetro, nonmetro_r, 'Nonmetropolitan (RUCC 4–9)'))
    
    table_df = pd.DataFrame(rows)
    
    # Spearman correlations
    cmr_rho, cmr_p = stats.spearmanr(df_rates['cmr_rate_per_100k'], df_rates['svi_percentile'])
    cct_rho, cct_p = stats.spearmanr(df_rates['cct_rate_per_100k'], df_rates['svi_percentile'])
    
    # Format for output
    print("\n" + table_df.to_string(index=False))
    print(f"\n  Spearman ρ (CMR rate vs SVI): {cmr_rho:.4f}, p = {cmr_p:.4f}")
    print(f"  Spearman ρ (CCT rate vs SVI): {cct_rho:.4f}, p = {cct_p:.4f}")
    
    # Save CSV
    table_df.to_csv(os.path.join(TBL_DIR, "table1_publication.csv"), index=False)
    
    # Save formatted text
    with open(os.path.join(TBL_DIR, "table1_publication.txt"), 'w') as f:
        f.write("Table 1. ACR-Accredited Cardiac Imaging Capacity by Social Vulnerability Quartile and Rurality\n")
        f.write("=" * 120 + "\n\n")
        f.write(table_df.to_string(index=False))
        f.write("\n\n" + "─" * 120 + "\n")
        f.write("Spearman Rank Correlation (facility rate vs. SVI percentile, continuous):\n")
        f.write(f"  Cardiac MRI: ρ = {cmr_rho:.4f}, p = {cmr_p:.4f}\n")
        f.write(f"  Cardiac CT:  ρ = {cct_rho:.4f}, p = {cct_p:.4f}\n")
        f.write("\n" + "─" * 120 + "\n")
        f.write("Notes:\n")
        f.write("  SVI = Social Vulnerability Index (CDC/ATSDR 2022, overall percentile rank RPL_THEMES).\n")
        f.write("  RUCC = Rural-Urban Continuum Code (USDA ERS 2023). Metropolitan = RUCC 1–3.\n")
        f.write("  Population denominators from American Community Survey 5-year estimates 2019–2023.\n")
        f.write(f"  Counties with <1,000 adults aged ≥45 excluded from rate calculations (n={int(df['rate_excluded'].sum())}).\n")
        f.write("  Rate = accredited facilities per 100,000 adults aged ≥45 years.\n")
        f.write("  IQR = interquartile range.\n")
    
    print(f"\n  ✓ {os.path.join(TBL_DIR, 'table1_publication.csv')}")
    print(f"  ✓ {os.path.join(TBL_DIR, 'table1_publication.txt')}")
    
    return {'cmr_rho': cmr_rho, 'cmr_p': cmr_p, 'cct_rho': cct_rho, 'cct_p': cct_p}


# ===========================================================================
# REGRESSION MODELS (ALL PER BRIEFING)
# ===========================================================================
def run_regressions(df):
    """Write the regression summary from the CANONICAL results.

    This script previously refitted the models itself with a fixed dispersion
    of alpha = 1.0, on the rate-eligible subset, and with the SVI predictor
    divided by 10 when the percentile is already on a 0-1 scale, so its IRRs
    were per 0.1 percentile points. It also reported a "Accredited-only"
    sensitivity that reused the primary dataframe unchanged.

    None of that is refitted here. Every estimate is read from the outputs the
    rest of the pipeline generates, so this file cannot disagree with Table 2:

        output/validation/manuscript_numbers.json   primary + sensitivities
        output/results/accredited_only_sensitivity.csv
        output/results/svi_quartile_regression.csv
        output/results/model_specification_comparison.csv
    """
    print("\n" + "=" * 70)
    print("REGRESSION SUMMARY (read from canonical results)")
    print("=" * 70)

    vpath = os.path.join(BASE_DIR, "output", "validation", "manuscript_numbers.json")
    if not os.path.exists(vpath):
        raise FileNotFoundError(
            f"{vpath} not found. Run code/12_manuscript_numbers.py first; this "
            "script no longer fits its own regressions.")
    with open(vpath) as f:
        R = json.load(f)["regressions"]

    def line(label, e):
        return (f"{label:<52} {e['irr']:>7.3f} "
                f"({e['ci_low']:.3f}-{e['ci_high']:.3f}) "
                f"{'<0.001' if e['p'] < 0.001 else format(e['p'], '.4f'):>8}")

    L = ["=" * 92,
         "REGRESSION RESULTS: ACR Cardiac Imaging Geographic Disparities",
         "=" * 92,
         f"Specification: {R.get('specification', 'see model_spec.py')}",
         "Offset: log(adults aged 45 and older). IRR per 10-percentile increment.",
         f"Analytic sample: SVI n = {R['n_svi']:,}; EDI n = {R['n_edi']:,}.",
         "Counties with <1,000 adults aged 45+ are excluded from rate",
         "calculations but retained in these count models.",
         "",
         f"{'Model':<52} {'IRR':>7} {'95% CI':>17} {'P':>8}",
         "-" * 92]
    for pred in ("SVI", "EDI"):
        for mod in ("CMR", "CCT"):
            m = R["models"][f"{pred}_{mod}"]
            L.append(line(f"{pred} - {mod}, unadjusted", m["unadjusted"]))
            L.append(line(f"{pred} - {mod}, adjusted for metropolitan status",
                          m["adjusted_metro"]))
            L.append(line(f"{pred} - {mod}, adjusted for ordinal RUCC",
                          m["adjusted_rucc"]))
            L.append(line(f"{pred} - {mod}, metropolitan status term",
                          m["metro_effect"]))
    L.append("")
    L.append("SENSITIVITY: fixed dispersion, alpha = 1.0")
    L.append("-" * 92)
    for key, block in R.get("sensitivity_fixed_alpha", {}).items():
        pred, mod = key.split("_")
        L.append(line(f"{pred} - {mod}, adjusted (alpha = 1.0)", block["adjusted_metro"]))
    L.append("")
    L.append("SENSITIVITY: restricted to rate-eligible counties (>= 1,000 adults 45+)")
    L.append("-" * 92)
    for key, block in R.get("sensitivity_rate_eligible", {}).items():
        pred, mod = key.split("_")
        L.append(line(f"{pred} - {mod}, adjusted (n = {block.get('n', 0):,})",
                      block["adjusted_metro"]))

    for path, title in (
            (os.path.join(BASE_DIR, "output", "results",
                          "accredited_only_sensitivity.csv"),
             "SENSITIVITY: Accredited-only cohort (real cohort, from 14_*)"),
            (os.path.join(BASE_DIR, "output", "results",
                          "svi_quartile_regression.csv"),
             "SENSITIVITY: SVI quartile indicators (from 15_*)")):
        L.append("")
        L.append(title)
        L.append("-" * 92)
        if not os.path.exists(path):
            L.append("  not generated; run the corresponding script")
            continue
        t = pd.read_csv(path)
        for _, r in t.iterrows():
            lbl = " ".join(str(r[c]) for c in t.columns
                           if c in ("cohort", "outcome", "model", "term"))
            L.append(f"{lbl[:52]:<52} {r['irr']:>7.3f} "
                     f"({r['ci_low']:.3f}-{r['ci_high']:.3f}) "
                     f"{r['p_value']:>8.4f}")

    text = "\n".join(L)
    out = os.path.join(MDL_DIR, "regression_results_full.txt")
    with open(out, "w") as f:
        f.write(text + "\n")
    print(text)
    print(f"\n  Wrote {out}")
    return None


# ===========================================================================
# PDF WORKFLOW DOCUMENT
# ===========================================================================
# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("\n" + "█"*70)
    print("  ACR CARDIAC IMAGING — PUBLICATION-QUALITY OUTPUTS")
    print("█"*70 + "\n")
    
    # Load data
    df = load_data()
    gdf = load_geodata()
    
    # Generate Figure 1
    create_figure1(gdf)
    
    # Generate Table 1
    create_table1(df)
    
    # Run all regression models
    run_regressions(df)
    
    print("\n" + "█"*70)
    print("  ALL PUBLICATION OUTPUTS COMPLETE")
    print("█"*70)
    print("\n  Outputs:")
    print("  ├── output/figures/figure1_choropleth.pdf  (vector, journal-ready)")
    print("  ├── output/figures/figure1_choropleth.png  (600 DPI)")
    print("  ├── output/tables/table1_publication.csv")
    print("  ├── output/tables/table1_publication.txt")
    print("  ├── output/models/regression_results_full.txt")
    print("  └── output/models/model_objects.pkl")


if __name__ == "__main__":
    main()
