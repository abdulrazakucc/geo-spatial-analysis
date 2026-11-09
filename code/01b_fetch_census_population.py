"""
Fetch county population totals and adults aged 45+ (stage A).

Source: US Census Bureau, Vintage 2023 county population estimates by age and
sex (cc-est2023-agesex-all.csv), the July 1, 2023 estimate (YEAR = 5). The
frozen file data/raw/acs_county_population.csv is this vintage: every county's
total population and count aged 45+ match it exactly. The file name is
historical; its values are Census Bureau population estimates, not American
Community Survey estimates.

The download is a public file, so no API key is needed. Connecticut appears by
its nine planning regions (FIPS 09110-09190), as in the rest of the pipeline.

Run
    python code/01b_fetch_census_population.py [OUT.csv]
"""
import io
import os
import sys

import pandas as pd
import requests

URL = ("https://www2.census.gov/programs-surveys/popest/datasets/2020-2023/counties/asrh/"
       "cc-est2023-agesex-all.csv")
YEAR_JULY_2023 = 5          # 1 = April 1, 2020 base; 2-5 = July 1, 2020-2023

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")


def fetch():
    print(f"Downloading {URL} ...")
    resp = requests.get(URL, timeout=300)
    resp.raise_for_status()
    p = pd.read_csv(io.BytesIO(resp.content), encoding="latin-1",
                    dtype={"STATE": str, "COUNTY": str})
    p = p[p["YEAR"] == YEAR_JULY_2023]
    out = pd.DataFrame({
        "county_fips": p["STATE"].str.zfill(2) + p["COUNTY"].str.zfill(3),
        "total_population": p["POPESTIMATE"].astype(int),
        "adult_pop_45plus": (p["AGE4564_TOT"] + p["AGE65PLUS_TOT"]).astype(int),
    })
    return out.sort_values("county_fips").reset_index(drop=True)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAW_DIR, "acs_county_population.csv")
    df = fetch()
    assert len(df) == 3144 and df.county_fips.is_unique, len(df)
    assert not df.county_fips.str.match(r"^090(0[1-9]|1[0-5])$").any(), "retired Connecticut counties"
    df.to_csv(out_path, index=False)
    print(f"  {len(df):,} counties; {df.adult_pop_45plus.sum() / 1e6:.1f} million adults aged 45+")
    print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()
