"""
04_choropleth_map.py
====================
Creates Figure 1: Two-panel US county choropleth map showing
ACR-accredited cardiac imaging facilities per 100,000 adults ≥45.

Panel A: Cardiac MRI (CMR) rate
Panel B: Cardiac CT (CCT) rate

Input:
    - data/processed/county_analytic_geo.gpkg

Output:
    - output/figures/figure1_choropleth.pdf
    - output/figures/figure1_choropleth.png
"""

import os
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import BoundaryNorm, ListedColormap
import mapclassify

warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
FIG_DIR = os.path.join(BASE_DIR, "output", "figures")
os.makedirs(FIG_DIR, exist_ok=True)


def load_geodata():
    """Load the geo-enabled analytic dataset."""
    gdf = gpd.read_file(os.path.join(PROC_DIR, "county_analytic_geo.gpkg"))
    print(f"Loaded geo-dataset: {len(gdf)} counties")
    
    # Reproject to Albers Equal Area (EPSG:5070) for contiguous US
    gdf = gdf.to_crs(epsg=5070)
    return gdf


def create_choropleth(gdf):
    """Create the two-panel choropleth figure."""
    print("\nCreating Figure 1: Two-panel choropleth...")
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 16))
    
    rate_cols = ['cmr_rate_per_100k', 'cct_rate_per_100k']
    titles = [
        'A. ACR-Accredited Cardiac MRI Facilities per 100,000 Adults ≥45',
        'B. ACR-Accredited Cardiac CT Facilities per 100,000 Adults ≥45'
    ]
    
    for idx, (col, title) in enumerate(zip(rate_cols, titles)):
        ax = axes[idx]
        
        # Separate counties into categories
        excluded = gdf[gdf['rate_excluded'] == 1]
        zero = gdf[(gdf['rate_excluded'] == 0) & (gdf[col] == 0)]
        has_data = gdf[(gdf['rate_excluded'] == 0) & (gdf[col] > 0)]
        
        # Plot excluded counties (white)
        if len(excluded) > 0:
            excluded.plot(ax=ax, color='white', edgecolor='#d0d0d0', linewidth=0.2)
        
        # Plot zero-facility counties (light gray)
        if len(zero) > 0:
            zero.plot(ax=ax, color='#e8e8e8', edgecolor='#d0d0d0', linewidth=0.2)
        
        # Plot counties with facilities (blue sequential palette, quantile bins)
        if len(has_data) > 0:
            # Create 5 quantile bins
            try:
                classifier = mapclassify.Quantiles(has_data[col].values, k=5)
                bins = classifier.bins
            except:
                bins = np.percentile(has_data[col].dropna(), [20, 40, 60, 80, 100])
            
            # Blue sequential palette
            blues = ['#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#08519c']
            cmap = ListedColormap(blues)
            
            # Normalize
            bounds = [0] + list(bins)
            norm = BoundaryNorm(bounds, cmap.N)
            
            has_data.plot(
                column=col, ax=ax, cmap=cmap,
                edgecolor='#d0d0d0', linewidth=0.2,
                scheme='quantiles', k=5,
                legend=False
            )
        
        # Overlay state boundaries
        # Dissolve counties to states for state boundaries
        state_boundaries = gdf.dissolve(by='state_abbr').boundary
        state_boundaries.plot(ax=ax, color='#404040', linewidth=0.5)
        
        # Title and formatting
        ax.set_title(title, fontsize=13, fontweight='bold', pad=10, loc='left')
        ax.set_axis_off()
        
        # Legend
        legend_elements = [
            mpatches.Patch(facecolor='#08519c', label='Highest quintile'),
            mpatches.Patch(facecolor='#6baed6', label='Middle quintiles'),
            mpatches.Patch(facecolor='#c6dbef', label='Lowest quintile'),
            mpatches.Patch(facecolor='#e8e8e8', edgecolor='#aaa', label='Zero facilities'),
            mpatches.Patch(facecolor='white', edgecolor='#aaa', label='Excluded (<1,000 adults ≥45)'),
        ]
        ax.legend(
            handles=legend_elements, loc='lower right',
            fontsize=9, framealpha=0.9, edgecolor='#ccc'
        )
    
    plt.tight_layout(pad=2)
    
    # Add figure note
    fig.text(
        0.5, 0.01,
        "Note: Color intensity indicates facility density (quantile-binned among counties with ≥1 facility).\n"
        "County boundaries: US Census TIGER/Line 2023. Projection: Albers Equal Area (EPSG:5070).",
        ha='center', fontsize=8, color='#666', style='italic'
    )
    
    # Save
    pdf_path = os.path.join(FIG_DIR, "figure1_choropleth.pdf")
    png_path = os.path.join(FIG_DIR, "figure1_choropleth.png")
    
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight', dpi=300)
    fig.savefig(png_path, format='png', bbox_inches='tight', dpi=600)
    plt.close()
    
    print(f"  ✓ Saved: {pdf_path}")
    print(f"  ✓ Saved: {png_path}")


def main():
    gdf = load_geodata()
    create_choropleth(gdf)
    print("\n  Figure 1 complete.")


if __name__ == "__main__":
    main()
