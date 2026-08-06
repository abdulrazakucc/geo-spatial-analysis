"""
Fetch county-level population data from Census ACS 5-Year API.
Pulls total population and adults aged 45+ for all US counties.
"""

import os
import requests
import pandas as pd
import numpy as np

API_KEY = "6b96038c5dfd62de3ca34c33de2560ae2c235137"
BASE_URL = "https://api.census.gov/data/2023/acs/acs5"

# B01001: Sex by Age
# Male 45+: variables 014-025 (45-49, 50-54, ..., 85+)
# Female 45+: variables 038-049
MALE_45PLUS = [f"B01001_{i:03d}E" for i in range(14, 26)]
FEMALE_45PLUS = [f"B01001_{i:03d}E" for i in range(38, 50)]
TOTAL_POP = "B01001_001E"

ALL_VARS = [TOTAL_POP] + MALE_45PLUS + FEMALE_45PLUS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")


def fetch_acs_data():
    print("Fetching ACS 5-Year population data from Census API...")
    
    # Fetch all counties: for=county:*&in=state:*
    var_str = ",".join(ALL_VARS)
    url = f"{BASE_URL}?get={var_str}&for=county:*&in=state:*&key={API_KEY}"
    
    print(f"  URL: {BASE_URL}?get=...&for=county:*&in=state:*")
    resp = requests.get(url, timeout=120)
    
    if resp.status_code != 200:
        print(f"  ERROR: Status {resp.status_code}")
        print(f"  Response: {resp.text[:500]}")
        
        # Try 2022 ACS if 2023 not available yet
        print("\n  Trying 2022 ACS 5-year instead...")
        alt_url = url.replace("/2023/", "/2022/")
        resp = requests.get(alt_url, timeout=120)
        if resp.status_code != 200:
            print(f"  ERROR: Status {resp.status_code}")
            print(f"  Response: {resp.text[:500]}")
            return None
    
    data = resp.json()
    header = data[0]
    rows = data[1:]
    
    df = pd.DataFrame(rows, columns=header)
    print(f"  Received {len(df)} county records")
    
    # Build county FIPS
    df['county_fips'] = df['state'] + df['county']
    
    # Convert numeric columns
    for col in ALL_VARS:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Calculate totals
    df['total_population'] = df[TOTAL_POP]
    df['adult_pop_45plus'] = df[MALE_45PLUS + FEMALE_45PLUS].sum(axis=1).astype(int)
    
    # Keep only needed columns
    result = df[['county_fips', 'total_population', 'adult_pop_45plus']].copy()
    result['total_population'] = result['total_population'].astype(int)
    
    # Exclude territories (FIPS starting with 60, 66, 69, 72, 78)
    territory_fips = {'60', '66', '69', '72', '78'}
    result = result[~result['county_fips'].str[:2].isin(territory_fips)]
    
    print(f"  After excluding territories: {len(result)} counties")
    print(f"  Total pop range: {result['total_population'].min():,} – {result['total_population'].max():,}")
    print(f"  Adult 45+ range: {result['adult_pop_45plus'].min():,} – {result['adult_pop_45plus'].max():,}")
    
    return result


def main():
    result = fetch_acs_data()
    if result is not None:
        out_path = os.path.join(RAW_DIR, "acs_county_population.csv")
        result.to_csv(out_path, index=False)
        print(f"\n  ✓ Saved: {out_path}")
    else:
        print("\n  ✗ Failed to fetch data.")


if __name__ == "__main__":
    main()
