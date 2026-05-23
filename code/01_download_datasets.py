"""
01_download_datasets.py
=======================
Downloads all external datasets required for the ACR Cardiac Imaging
geographic disparities analysis.

Datasets downloaded:
1. CDC/ATSDR Social Vulnerability Index (SVI) 2022 - county level
2. USDA ERS Rural-Urban Continuum Codes (RUCC) 2023
3. US Census TIGER/Line 2023 county shapefiles
4. HUD USPS ZIP-County Crosswalk Q1 2025 (latest publicly available)

Census ACS population data is pulled via API in a separate step.
"""

import os
import requests
import zipfile
import io

# Project paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)


def download_file(url, dest_path, description):
    """Download a file with progress indication."""
    print(f"\n{'='*60}")
    print(f"Downloading: {description}")
    print(f"URL: {url}")
    print(f"Destination: {dest_path}")
    print(f"{'='*60}")
    
    if os.path.exists(dest_path):
        print(f"  ✓ Already exists, skipping.")
        return True
    
    try:
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"  ✓ Downloaded successfully ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def download_and_extract_zip(url, extract_dir, description):
    """Download a ZIP file and extract it."""
    print(f"\n{'='*60}")
    print(f"Downloading & Extracting: {description}")
    print(f"URL: {url}")
    print(f"Extract to: {extract_dir}")
    print(f"{'='*60}")
    
    if os.path.exists(extract_dir) and os.listdir(extract_dir):
        print(f"  ✓ Already extracted, skipping.")
        return True
    
    os.makedirs(extract_dir, exist_ok=True)
    try:
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(resp.content))
        z.extractall(extract_dir)
        print(f"  ✓ Extracted {len(z.namelist())} files")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


def main():
    print("=" * 60)
    print("ACR CARDIAC IMAGING - EXTERNAL DATASET DOWNLOAD")
    print("=" * 60)
    
    # 1. CDC SVI 2022 - County Level CSV
    # Direct download link for the 2022 county-level SVI
    svi_url = "https://svi.cdc.gov/Documents/Data/2022/csv/states/SVI_2022_US_county.csv"
    svi_path = os.path.join(RAW_DIR, "SVI_2022_US_county.csv")
    download_file(svi_url, svi_path, "CDC/ATSDR Social Vulnerability Index 2022 (County)")
    
    # 2. USDA RUCC 2023
    rucc_url = "https://www.ers.usda.gov/webdocs/DataFiles/53251/ruralurbancodes2023.xls?v=5765.3"
    rucc_path = os.path.join(RAW_DIR, "ruralurbancodes2023.xls")
    download_file(rucc_url, rucc_path, "USDA ERS Rural-Urban Continuum Codes 2023")
    
    # 3. TIGER/Line 2023 County Shapefiles
    tiger_url = "https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip"
    tiger_dir = os.path.join(RAW_DIR, "tiger_county_2023")
    download_and_extract_zip(tiger_url, tiger_dir, "US Census TIGER/Line 2023 County Shapefiles")
    
    # 4. HUD USPS ZIP-County Crosswalk
    # Note: HUD crosswalk requires a token. We'll use an alternative approach
    # with the free HUD crosswalk data or Census ZCTA-County relationship file.
    # Using Census Gazetteer as a reliable free alternative for ZIP-County mapping
    zcta_url = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt"
    zcta_path = os.path.join(RAW_DIR, "zcta_county_crosswalk_2020.txt")
    download_file(zcta_url, zcta_path, "Census 2020 ZCTA-County Relationship File")
    
    # Summary
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    print(f"\nFiles in {RAW_DIR}:")
    for f in sorted(os.listdir(RAW_DIR)):
        fpath = os.path.join(RAW_DIR, f)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath) / (1024 * 1024)
            print(f"  {f} ({size:.1f} MB)")
        elif os.path.isdir(fpath):
            nfiles = len(os.listdir(fpath))
            print(f"  {f}/ ({nfiles} files)")


if __name__ == "__main__":
    main()
