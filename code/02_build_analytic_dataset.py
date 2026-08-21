"""
02_build_analytic_dataset.py
============================
Cleans the ACR facility data, links ZIP codes to counties,
merges all external data sources, and produces the final
county-level analytic dataset.

Inputs:
    - data/ACR_Cardiac_Imaging_Sites.xlsx (provided)
    - data/raw/zcta_county_crosswalk_2020.txt (downloaded)
    - data/raw/tiger_county_2023/ (downloaded)
    - data/raw/SVI_2022_US_county.csv (manual download required)
    - data/raw/ruralurbancodes2023.xls (manual download required)

Output:
    - data/processed/county_analytic_dataset.csv
"""

import os
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd

import facility_mapping

warnings.filterwarnings('ignore')

# ===========================================================================
# PATHS
# ===========================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROC_DIR = os.path.join(DATA_DIR, "processed")
os.makedirs(PROC_DIR, exist_ok=True)

# US territories to exclude (FIPS prefixes)
TERRITORY_FIPS = {'60', '66', '69', '72', '78'}


# ===========================================================================
# Production inputs must be real. See P1-7 in the implementation plan.
# ===========================================================================
#: FIPS code to USPS abbreviation, 50 states + DC.
STATE_FIPS_TO_ABBR = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}

DEMO_MODE = os.environ.get("PIPELINE_DEMO") == "1"


def require_input(path, what, where):
    """Fail loudly when a required production input is missing.

    Random proxy values used to be substituted silently here, which meant a
    missing SVI, RUCC, or ACS file produced a complete-looking dataset built on
    fabricated numbers. Demo behaviour is now opt-in via PIPELINE_DEMO=1.
    """
    if os.path.exists(path):
        return True
    if DEMO_MODE:
        print(f"  [DEMO] {what} missing; substituting synthetic values. "
              f"NOT VALID FOR ANALYSIS.")
        return False
    raise FileNotFoundError(
        f"Required input missing: {what}\n"
        f"  expected at : {path}\n"
        f"  obtain from : {where}\n"
        f"  Run 'python code/01_download_datasets.py' to fetch it. To exercise "
        f"the pipeline without real data, set PIPELINE_DEMO=1, which produces "
        f"synthetic values that must never be reported.")


# ===========================================================================
# STEP 1: Load and clean ACR facility data
# ===========================================================================
def load_acr_data():
    """Load the primary ACR Cardiac Imaging Sites dataset."""
    print("\n" + "=" * 60)
    print("STEP 1: Loading ACR Cardiac Imaging facility data")
    print("=" * 60)
    
    filepath = os.path.join(DATA_DIR, "ACR_Cardiac_Imaging_Sites.xlsx")
    df = pd.read_excel(filepath, sheet_name="Cardiac MRI + CT (PRIMARY)")
    print(f"  Loaded {len(df)} records from 'Cardiac MRI + CT (PRIMARY)' sheet")
    
    # Ensure ZIP codes are 5-digit strings
    df['Zip Code'] = df['Zip Code'].astype(str).str.zfill(5).str[:5]
    
    # Filter: keep only Accredited or Under Review
    valid_status = ['Accredited', 'Under Review']
    df = df[df['Status'].isin(valid_status)].copy()
    print(f"  After status filter (Accredited/Under Review): {len(df)} records")
    
    # Filter: remove expired accreditations (before May 20, 2026)
    df['Expiration Date'] = pd.to_datetime(df['Expiration Date'], errors='coerce')
    extraction_date = pd.Timestamp('2026-05-20')
    expired = df['Expiration Date'] < extraction_date
    n_expired = expired.sum()
    df = df[~expired | df['Expiration Date'].isna()].copy()
    print(f"  Removed {n_expired} expired records. Remaining: {len(df)}")
    
    # Modality breakdown
    print(f"\n  Modality breakdown:")
    print(f"    Cardiac MRI (MRAP): {(df['modality'] == 'MRAP').sum()}")
    print(f"    Cardiac CT  (CTAP): {(df['modality'] == 'CTAP').sum()}")
    
    # Status breakdown
    print(f"\n  Status breakdown:")
    for status, count in df['Status'].value_counts().items():
        print(f"    {status}: {count}")
    
    return df


# ===========================================================================
# STEP 2: Map ZIP codes to county FIPS
# ===========================================================================
def load_zip_county_crosswalk():
    """Load the ZCTA-County crosswalk and prepare ZIP-to-FIPS mapping."""
    print("\n" + "=" * 60)
    print("STEP 2: Loading ZIP-County crosswalk")
    print("=" * 60)
    
    filepath = os.path.join(RAW_DIR, "zcta_county_crosswalk_2020.txt")
    
    # This file has pipe-delimited format
    df = pd.read_csv(filepath, sep='|', dtype=str)
    print(f"  Loaded {len(df)} ZCTA-county relationships")
    print(f"  Columns: {list(df.columns)}")
    
    # Key columns: GEOID_ZCTA5_20, GEOID_COUNTY_20, AREALAND_PART (or similar)
    # Identify relevant columns
    zcta_col = [c for c in df.columns if 'ZCTA' in c.upper() and 'GEOID' in c.upper()]
    county_col = [c for c in df.columns if 'COUNTY' in c.upper() and 'GEOID' in c.upper()]
    
    if zcta_col and county_col:
        zcta_col = zcta_col[0]
        county_col = county_col[0]
    else:
        # Fallback: try positional
        print(f"  Column names: {list(df.columns)}")
        zcta_col = df.columns[0]
        county_col = df.columns[2]
    
    print(f"  Using ZCTA column: '{zcta_col}', County column: '{county_col}'")
    
    # For multi-county ZCTAs, pick the one with largest area overlap
    # Use AREALAND columns if available
    area_col = [c for c in df.columns if 'AREALAND' in c.upper() and 'PART' in c.upper()]
    if area_col:
        area_col = area_col[0]
        df[area_col] = pd.to_numeric(df[area_col], errors='coerce')
        # For each ZCTA, keep the county with largest area share
        df_sorted = df.sort_values(area_col, ascending=False)
        crosswalk = df_sorted.drop_duplicates(subset=[zcta_col], keep='first')
    else:
        # Just take first occurrence
        crosswalk = df.drop_duplicates(subset=[zcta_col], keep='first')
    
    # Create clean mapping
    crosswalk = crosswalk[[zcta_col, county_col]].copy()
    crosswalk.columns = ['zip_code', 'county_fips']
    crosswalk['zip_code'] = crosswalk['zip_code'].str.zfill(5)
    crosswalk['county_fips'] = crosswalk['county_fips'].str.zfill(5)
    
    # Exclude territories
    crosswalk = crosswalk[~crosswalk['county_fips'].str[:2].isin(TERRITORY_FIPS)]
    
    print(f"  Final crosswalk: {len(crosswalk)} unique ZIP-to-county mappings")
    return crosswalk


def assign_counties(acr_df, crosswalk):
    """Assign county FIPS to each facility based on ZIP code."""
    print("\n  Assigning counties to facilities...")
    
    merged = acr_df.merge(
        crosswalk, left_on='Zip Code', right_on='zip_code', how='left'
    )
    
    unmatched = merged['county_fips'].isna().sum()
    print(f"  Matched: {len(merged) - unmatched} / {len(merged)}")
    if unmatched > 0:
        print(f"  ⚠ Unmatched ZIPs: {unmatched}")
        print(f"    Sample unmatched ZIPs: {merged[merged['county_fips'].isna()]['Zip Code'].unique()[:10]}")
    
    # Drop unmatched (usually very few)
    merged = merged.dropna(subset=['county_fips']).copy()
    return merged


# ===========================================================================
# STEP 3: Aggregate to county level
# ===========================================================================
def aggregate_to_county(facility_df):
    """Count facilities per county by modality."""
    print("\n" + "=" * 60)
    print("STEP 3: Aggregating facility counts to county level")
    print("=" * 60)
    
    # Count CMR (MRAP) facilities per county
    cmr = facility_df[facility_df['modality'] == 'MRAP'].groupby('county_fips').size()
    cmr.name = 'cmr_facility_count'
    
    # Count CCT (CTAP) facilities per county
    cct = facility_df[facility_df['modality'] == 'CTAP'].groupby('county_fips').size()
    cct.name = 'cct_facility_count'
    
    counts = pd.DataFrame({'cmr_facility_count': cmr, 'cct_facility_count': cct})
    counts = counts.fillna(0).astype(int)
    
    print(f"  Counties with ≥1 CMR facility: {(counts['cmr_facility_count'] > 0).sum()}")
    print(f"  Counties with ≥1 CCT facility: {(counts['cct_facility_count'] > 0).sum()}")
    print(f"  Total CMR facilities assigned: {counts['cmr_facility_count'].sum()}")
    print(f"  Total CCT facilities assigned: {counts['cct_facility_count'].sum()}")
    
    return counts


# ===========================================================================
# STEP 4: Load county master list from TIGER/Line shapefile
# ===========================================================================
def load_county_master():
    """Load all US counties from TIGER/Line shapefile."""
    print("\n" + "=" * 60)
    print("STEP 4: Loading county master list from TIGER/Line")
    print("=" * 60)
    
    tiger_dir = os.path.join(RAW_DIR, "tiger_county_2023")
    shp_files = [f for f in os.listdir(tiger_dir) if f.endswith('.shp')]
    
    if not shp_files:
        raise FileNotFoundError(f"No .shp file found in {tiger_dir}")
    
    gdf = gpd.read_file(os.path.join(tiger_dir, shp_files[0]))
    print(f"  Loaded {len(gdf)} county geometries")
    print(f"  Columns: {list(gdf.columns)}")
    
    # Standard TIGER columns: GEOID, STATEFP, COUNTYFP, NAME, NAMELSAD
    gdf['county_fips'] = gdf['GEOID'].str.zfill(5)
    gdf['state_fips'] = gdf['STATEFP'].str.zfill(2)
    
    # Exclude territories
    gdf = gdf[~gdf['state_fips'].isin(TERRITORY_FIPS)].copy()
    print(f"  After excluding territories: {len(gdf)} counties (50 states + DC)")
    
    return gdf


# ===========================================================================
# STEP 5: Load or generate SVI data
# ===========================================================================
def load_svi_data(county_fips_list):
    """Load CDC SVI data, or generate proxy if file not available."""
    print("\n" + "=" * 60)
    print("STEP 5: Loading Social Vulnerability Index (SVI) data")
    print("=" * 60)
    
    svi_path = os.path.join(RAW_DIR, "SVI_2022_US_county.csv")
    
    if os.path.exists(svi_path):
        print(f"  Loading real SVI data from: {svi_path}")
        svi = pd.read_csv(svi_path, dtype={'FIPS': str})
        # Standardize FIPS column
        fips_col = [c for c in svi.columns if 'FIPS' in c.upper()][0]
        svi['county_fips'] = svi[fips_col].str.zfill(5)
        svi = svi[['county_fips', 'RPL_THEMES']].copy()
        svi.columns = ['county_fips', 'svi_percentile']
        svi['svi_percentile'] = pd.to_numeric(svi['svi_percentile'], errors='coerce')
        # Handle -999 (missing values in SVI)
        svi.loc[svi['svi_percentile'] < 0, 'svi_percentile'] = np.nan
    else:
        require_input(svi_path, "CDC/ATSDR SVI county file",
                      "https://www.atsdr.cdc.gov/place-health/php/svi/")
        np.random.seed(42)
        svi = pd.DataFrame({
            'county_fips': county_fips_list,
            'svi_percentile': np.random.beta(2, 2, size=len(county_fips_list))
        })
    
    print(f"  SVI data: {len(svi)} counties")
    print(f"  SVI range: {svi['svi_percentile'].min():.3f} - {svi['svi_percentile'].max():.3f}")
    return svi


# ===========================================================================
# STEP 6: Load or generate RUCC data
# ===========================================================================
def load_rucc_data(county_fips_list):
    """Load USDA RUCC data, or generate proxy if file not available."""
    print("\n" + "=" * 60)
    print("STEP 6: Loading Rural-Urban Continuum Codes (RUCC) data")
    print("=" * 60)
    
    rucc_path = os.path.join(RAW_DIR, "ruralurbancodes2023.xls")
    rucc_path2 = os.path.join(RAW_DIR, "ruralurbancodes2023.xlsx")
    
    if os.path.exists(rucc_path) or os.path.exists(rucc_path2):
        path = rucc_path if os.path.exists(rucc_path) else rucc_path2
        print(f"  Loading real RUCC data from: {path}")
        rucc = pd.read_excel(path, dtype={'FIPS': str})
        fips_col = [c for c in rucc.columns if 'FIPS' in c.upper()][0]
        rucc_col = [c for c in rucc.columns if 'RUCC' in c.upper() and '2023' in c][0]
        rucc['county_fips'] = rucc[fips_col].str.zfill(5)
        rucc = rucc[['county_fips', rucc_col]].copy()
        rucc.columns = ['county_fips', 'rucc_code']
        rucc['rucc_code'] = pd.to_numeric(rucc['rucc_code'], errors='coerce')
    else:
        require_input(rucc_path2, "USDA Rural-Urban Continuum Codes",
                      "https://www.ers.usda.gov/data-products/rural-urban-continuum-codes")
        np.random.seed(123)
        # Realistic distribution: ~37% metro (1-3), ~63% non-metro (4-9)
        rucc_codes = np.random.choice(
            [1, 2, 3, 4, 5, 6, 7, 8, 9],
            size=len(county_fips_list),
            p=[0.06, 0.15, 0.16, 0.10, 0.12, 0.15, 0.12, 0.08, 0.06]
        )
        rucc = pd.DataFrame({
            'county_fips': county_fips_list,
            'rucc_code': rucc_codes
        })
    
    rucc['metro_indicator'] = (rucc['rucc_code'] <= 3).astype(int)
    
    print(f"  RUCC data: {len(rucc)} counties")
    print(f"  Metropolitan (RUCC 1-3): {rucc['metro_indicator'].sum()}")
    print(f"  Nonmetropolitan (RUCC 4-9): {(rucc['metro_indicator'] == 0).sum()}")
    return rucc


# ===========================================================================
# STEP 7: Generate population data (proxy from TIGER land area)
# ===========================================================================
def load_population_data(gdf):
    """Generate or load county population data."""
    print("\n" + "=" * 60)
    print("STEP 7: Loading population data")
    print("=" * 60)
    
    pop_path = os.path.join(RAW_DIR, "acs_county_population.csv")
    
    if os.path.exists(pop_path):
        print(f"  Loading real ACS population data from: {pop_path}")
        pop = pd.read_csv(pop_path, dtype={'county_fips': str})
    else:
        require_input(pop_path, "ACS 2019-2023 5-year county population",
                      "Census API; run code/01b_fetch_census_population.py")
        
        # Generate realistic population using land area as a rough proxy
        np.random.seed(456)
        n = len(gdf)
        
        # Log-normal distribution mimics US county population distribution
        # Median US county pop ~26k, range from hundreds to millions
        log_pop = np.random.normal(10.2, 1.3, size=n)  # log scale
        total_pop = np.exp(log_pop).astype(int)
        total_pop = np.clip(total_pop, 500, 10_000_000)
        
        # Adults 45+ are roughly 38-42% of total population
        pct_45plus = np.random.uniform(0.35, 0.50, size=n)
        adult_45plus = (total_pop * pct_45plus).astype(int)
        
        pop = pd.DataFrame({
            'county_fips': gdf['county_fips'].values,
            'total_population': total_pop,
            'adult_pop_45plus': adult_45plus
        })
    
    print(f"  Population data: {len(pop)} counties")
    print(f"  Total pop range: {pop['total_population'].min():,} - {pop['total_population'].max():,}")
    print(f"  Adult 45+ range: {pop['adult_pop_45plus'].min():,} - {pop['adult_pop_45plus'].max():,}")
    print(f"  Counties with <1,000 adults 45+: {(pop['adult_pop_45plus'] < 1000).sum()}")
    return pop


# ===========================================================================
# STEP 8: Build final analytic dataset
# ===========================================================================
def build_analytic_dataset(gdf, facility_counts, svi, rucc, pop):
    """Merge everything into the final county-level analytic dataset."""
    print("\n" + "=" * 60)
    print("STEP 8: Building final county-level analytic dataset")
    print("=" * 60)
    
    # Start with county master
    df = gdf[['county_fips', 'state_fips', 'NAME', 'STUSPS' if 'STUSPS' in gdf.columns else 'STATEFP']].copy()
    
    # Get state abbreviation
    if 'STUSPS' in gdf.columns:
        df = df.rename(columns={'STUSPS': 'state_abbr', 'NAME': 'county_name'})
    else:
        # Static FIPS-to-abbreviation table. Inlined rather than imported from
        # the `us` package: it is a fixed 51-entry constant, and a missing
        # optional dependency should not be able to break the build.
        df['state_abbr'] = df['state_fips'].map(STATE_FIPS_TO_ABBR)
        df = df.rename(columns={'NAME': 'county_name'})
    
    df = df[['county_fips', 'state_abbr', 'county_name']].copy()
    
    # Merge facility counts
    df = df.merge(facility_counts, on='county_fips', how='left')
    df['cmr_facility_count'] = df['cmr_facility_count'].fillna(0).astype(int)
    df['cct_facility_count'] = df['cct_facility_count'].fillna(0).astype(int)
    
    # Merge SVI
    df = df.merge(svi, on='county_fips', how='left')
    
    # Create SVI quartiles (1=least vulnerable, 4=most vulnerable)
    df['svi_quartile'] = pd.qcut(
        df['svi_percentile'], q=4, labels=[1, 2, 3, 4]
    ).astype(float).astype('Int64')
    
    # Merge RUCC
    df = df.merge(rucc[['county_fips', 'rucc_code', 'metro_indicator']], on='county_fips', how='left')
    
    # Merge population
    df = df.merge(pop, on='county_fips', how='left')
    
    # Calculate rates per 100,000 adults 45+
    df['rate_excluded'] = (df['adult_pop_45plus'] < 1000).astype(int)
    
    df['cmr_rate_per_100k'] = np.where(
        df['rate_excluded'] == 0,
        (df['cmr_facility_count'] / df['adult_pop_45plus']) * 100_000,
        np.nan
    )
    df['cct_rate_per_100k'] = np.where(
        df['rate_excluded'] == 0,
        (df['cct_facility_count'] / df['adult_pop_45plus']) * 100_000,
        np.nan
    )
    
    # Summary
    print(f"  Final dataset: {len(df)} counties")
    print(f"  Counties with ≥1 CMR: {(df['cmr_facility_count'] > 0).sum()}")
    print(f"  Counties with ≥1 CCT: {(df['cct_facility_count'] > 0).sum()}")
    print(f"  Counties excluded from rates: {df['rate_excluded'].sum()}")
    print(f"  CMR rate (median, non-excluded): {df.loc[df['rate_excluded']==0, 'cmr_rate_per_100k'].median():.2f}")
    print(f"  CCT rate (median, non-excluded): {df.loc[df['rate_excluded']==0, 'cct_rate_per_100k'].median():.2f}")
    
    return df


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("=" * 60)
    print("ACR CARDIAC IMAGING - BUILDING ANALYTIC DATASET")
    print("=" * 60)
    
    # Step 1: County master from TIGER. This comes first because the facility
    # mapping needs the current county universe to validate every assignment
    # against, which is how retired FIPS are caught instead of silently dropped.
    gdf = load_county_master()
    county_fips_list = gdf['county_fips'].tolist()

    # Steps 2-3: Cohort, county assignment, and the facility-level audit trail.
    # facility_mapping guarantees that eligible == included + explicitly
    # excluded, and writes data/processed/facility_mapping_audit.csv.
    county_names = dict(zip(gdf['county_fips'], gdf['NAME']))
    audit, facility_counts = facility_mapping.build(
        valid_fips=set(county_fips_list), county_names=county_names)
    report = facility_mapping.reconciliation_report(audit)
    print(report)
    os.makedirs(os.path.join(BASE_DIR, "output", "validation"), exist_ok=True)
    with open(os.path.join(BASE_DIR, "output", "validation",
                           "facility_reconciliation.txt"), "w") as fh:
        fh.write(report + "\n")
    
    # Step 5: SVI
    svi = load_svi_data(county_fips_list)
    
    # Step 6: RUCC
    rucc = load_rucc_data(county_fips_list)
    
    # Step 7: Population
    pop = load_population_data(gdf)
    
    # Step 8: Build final dataset
    analytic_df = build_analytic_dataset(gdf, facility_counts, svi, rucc, pop)
    
    # Save
    output_path = os.path.join(PROC_DIR, "county_analytic_dataset.csv")
    analytic_df.to_csv(output_path, index=False)
    print(f"\n  ✓ Saved analytic dataset to: {output_path}")
    print(f"    Shape: {analytic_df.shape}")
    
    # Also save the geo-enabled version for mapping
    geo_df = gdf[['county_fips', 'geometry']].merge(analytic_df, on='county_fips', how='right')
    geo_path = os.path.join(PROC_DIR, "county_analytic_geo.gpkg")
    geo_gdf = gpd.GeoDataFrame(geo_df, geometry='geometry')
    geo_gdf.to_file(geo_path, driver='GPKG')
    print(f"  ✓ Saved geo-dataset to: {geo_path}")

    _save_display_geometry(geo_gdf)

    return analytic_df


#: Columns the choropleths actually read. Everything else is already in the CSV.
DISPLAY_COLS = ['county_fips', 'state_abbr', 'cmr_rate_per_100k',
                'cct_rate_per_100k', 'rate_excluded', 'geometry']

#: Simplification tolerance in metres, applied in EPSG:5070. One pixel spans
#: roughly 570 m on the printed map, so this sits well inside a pixel.
DISPLAY_TOLERANCE_M = 100


def _save_display_geometry(geo_gdf):
    """Write a small, committable copy of the geometry for redrawing the maps.

    The full GeoPackage is 132 MB of TIGER geometry and is gitignored, and the
    shapefiles behind it are gitignored too, so a fresh clone cannot redraw the
    choropleths without re-downloading from the Census. This layer closes that
    gap: 8.1 million vertices reduce to about 355,000, which fits in ordinary
    git at roughly 7.6 MB.

    Deliberately *not* in LFS. The reason it exists is to survive a clone by
    someone who has not configured LFS, which is precisely how the published
    figures became unreachable for a coauthor.

    It is display resolution, not a bit-exact source: redrawing from it lands
    about 96% pixel-identical, with the differences along county borders. The
    published PNG and TIFF remain the citable artifacts.
    """
    cols = [c for c in DISPLAY_COLS if c in geo_gdf.columns]
    slim = geo_gdf[cols].to_crs(epsg=5070)
    slim['geometry'] = slim.geometry.simplify(DISPLAY_TOLERANCE_M)
    slim = slim.to_crs(geo_gdf.crs)
    path = os.path.join(PROC_DIR, "county_analytic_geo_display.gpkg")
    slim.to_file(path, driver='GPKG')
    size_mb = os.path.getsize(path) / 1e6
    print(f"  ✓ Saved display geometry to: {path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    df = main()
