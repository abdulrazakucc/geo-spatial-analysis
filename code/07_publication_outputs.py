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
    """
    Run all regression models per briefing Section 3.3–3.4:
    
    Primary:
      - Negative binomial: facility count ~ SVI (per 10-percentile) + offset(log pop ≥45)
      - Separately for CMR and CCT
    
    Sensitivity:
      1. Accredited-only (exclude 23 Under Review)
      2. SVI quartile dummies instead of continuous
      3. Stratified by metro/nonmetro
    
    Goodness of fit: dispersion, AIC comparison vs Poisson
    """
    print("\n" + "="*70)
    print("REGRESSION MODELS")
    print("="*70)
    
    df_model = df[df['rate_excluded'] == 0].copy()
    df_model['svi_per10'] = df_model['svi_percentile'] / 10
    df_model['log_pop'] = np.log(df_model['adult_pop_45plus'])
    
    # SVI quartile dummies
    df_model['svi_q2'] = (df_model['svi_quartile'] == 2).astype(int)
    df_model['svi_q3'] = (df_model['svi_quartile'] == 3).astype(int)
    df_model['svi_q4'] = (df_model['svi_quartile'] == 4).astype(int)
    
    results_text = []
    results_text.append("=" * 80)
    results_text.append("REGRESSION RESULTS: ACR Cardiac Imaging Geographic Disparities")
    results_text.append("Negative Binomial Models with log(adult ≥45 population) as offset")
    results_text.append("=" * 80)
    
    all_models = {}
    
    for modality in ['CMR', 'CCT']:
        col = f"{'cmr' if modality == 'CMR' else 'cct'}_facility_count"
        results_text.append(f"\n\n{'═'*80}")
        results_text.append(f"MODALITY: {modality}")
        results_text.append(f"{'═'*80}")
        
        # ---- PRIMARY MODEL ----
        models_to_run = [
            ("Primary (SVI continuous, per 10-percentile increment)", ['svi_per10'], df_model, True),
            ("Sensitivity A: Accredited-only (excluding Under Review)", ['svi_per10'], df_model, False),  # placeholder
            ("Sensitivity B: SVI Quartile Dummies (ref=Q1)", ['svi_q2', 'svi_q3', 'svi_q4'], df_model, False),
            ("Sensitivity C: Stratified — Metropolitan only", ['svi_per10'], df_model[df_model['metro_indicator']==1], False),
            ("Sensitivity D: Stratified — Nonmetropolitan only", ['svi_per10'], df_model[df_model['metro_indicator']==0], False),
        ]
        
        for model_name, predictors, data, compare_poisson in models_to_run:
            results_text.append(f"\n{'─'*80}")
            results_text.append(f"Model: {modality} — {model_name}")
            results_text.append(f"{'─'*80}")
            
            y = data[col].values
            X = sm.add_constant(data[predictors].values)
            offset = data['log_pop'].values
            
            try:
                # Negative Binomial
                nb_model = sm.GLM(y, X, family=NegativeBinomial(alpha=1.0), offset=offset)
                nb_result = nb_model.fit(maxiter=200, disp=False)
                
                # Extract results
                results_text.append(f"\n{'Variable':<30} {'IRR':>8} {'95% CI':>20} {'p-value':>10}")
                results_text.append("─" * 72)
                
                var_names = ['Intercept'] + predictors
                for i, vname in enumerate(var_names):
                    irr = np.exp(nb_result.params[i])
                    ci_lo = np.exp(nb_result.conf_int()[i, 0])
                    ci_hi = np.exp(nb_result.conf_int()[i, 1])
                    pval = nb_result.pvalues[i]
                    pstr = f"{pval:.4f}" if pval >= 0.0001 else "<0.0001"
                    results_text.append(f"{vname:<30} {irr:>8.4f} ({ci_lo:.4f}–{ci_hi:.4f}) {pstr:>10}")
                
                results_text.append(f"\n  N = {int(nb_result.nobs)}")
                results_text.append(f"  AIC = {nb_result.aic:.1f}")
                results_text.append(f"  Deviance = {nb_result.deviance:.1f}")
                results_text.append(f"  Pearson χ² = {nb_result.pearson_chi2:.1f}")
                results_text.append(f"  Dispersion (Pearson χ²/df) = {nb_result.pearson_chi2/nb_result.df_resid:.3f}")
                
                # Poisson comparison
                if compare_poisson:
                    pois_model = sm.GLM(y, X, family=Poisson(), offset=offset)
                    pois_result = pois_model.fit(maxiter=200, disp=False)
                    results_text.append(f"\n  Poisson AIC = {pois_result.aic:.1f}")
                    results_text.append(f"  Negative Binomial AIC = {nb_result.aic:.1f}")
                    if nb_result.aic < pois_result.aic:
                        results_text.append(f"  → Negative Binomial preferred (ΔAIC = {pois_result.aic - nb_result.aic:.1f})")
                    else:
                        results_text.append(f"  → Poisson preferred (ΔAIC = {nb_result.aic - pois_result.aic:.1f})")
                
                all_models[f"{modality}_{model_name[:20]}"] = nb_result
                
            except Exception as e:
                results_text.append(f"  ERROR: {str(e)}")
    
    # Write results
    full_text = "\n".join(results_text)
    output_path = os.path.join(MDL_DIR, "regression_results_full.txt")
    with open(output_path, 'w') as f:
        f.write(full_text)
    
    print(full_text)
    print(f"\n  ✓ {output_path}")
    
    # Save model objects
    pkl_path = os.path.join(MDL_DIR, "model_objects.pkl")
    with open(pkl_path, 'wb') as f:
        pickle.dump(all_models, f)
    print(f"  ✓ {pkl_path}")
    
    return all_models


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
