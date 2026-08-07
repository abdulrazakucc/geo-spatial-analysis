#!/usr/bin/env python3
"""
01c_fetch_hud_crosswalk.py
==========================
Downloads the HUD-USPS ZIP-County Crosswalk and writes it in the form the
facility mapping expects.

This is the ZIP-to-county linkage the project briefing specifies. Once
`data/raw/hud_zip_county.csv` exists, `code/facility_mapping.py` picks it up
automatically and switches from the Census ZCTA fallback to the HUD
residential-address-share method. Nothing else needs changing.

Why it matters
--------------
The Census fallback has two structural defects that this file removes:

1. It covers ZCTAs, not ZIPs. Post-office-box and unique ZIPs have no ZCTA, so
   64 eligible facilities cannot be placed at all.
2. The 2020 vintage predates Connecticut's 2022 replacement of counties with
   nine planning regions, so CT ZIPs resolve to retired FIPS and need a manual
   town table.

Authentication
--------------
Register at https://www.huduser.gov/portal/dataset/uspszip-api.html and create
a token. Supply it in either of these ways, in order of preference:

    export HUD_API_TOKEN="your token"            # environment variable
    echo "your token" > data/raw/.hud_api_token  # gitignored file

Or paste it into HUD_API_TOKEN_PLACEHOLDER below. Prefer one of the first two:
a token pasted into a tracked file will end up in git history.

Run
    python code/01c_fetch_hud_crosswalk.py                  # 2026 Q1, the default
    python code/01c_fetch_hud_crosswalk.py --year 2025 --quarter 4
    python code/01c_fetch_hud_crosswalk.py --dry-run        # check auth only

Then rebuild:
    python code/02_build_analytic_dataset.py
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Iterable

import pandas as pd
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
TOKEN_FILE = os.path.join(RAW_DIR, ".hud_api_token")
OUTPUT_CSV = os.path.join(RAW_DIR, "hud_zip_county.csv")

#: Paste a token here only if you cannot use the environment variable or the
#: token file. Leave as-is otherwise. This file IS tracked by git.
HUD_API_TOKEN_PLACEHOLDER = "PASTE_YOUR_HUD_API_TOKEN_HERE"

API_URL = "https://www.huduser.gov/hudapi/public/usps"
CROSSWALK_TYPE_ZIP_TO_COUNTY = 2

DEFAULT_YEAR = 2026
DEFAULT_QUARTER = 1

REQUEST_TIMEOUT = 60
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 3
THROTTLE_SECONDS = 0.34          # HUD permits well above this; stay polite.

#: The national crosswalk comes back in a single "All" request (~54,500 rows).
#: If that ever fails, the fetch falls back to querying state by state.
#: The API accepts USPS state abbreviations here; two-digit state FIPS codes
#: are rejected with HTTP 400.
STATE_ABBRS = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
]

EXPECTED_MIN_ROWS = 40_000       # A full national crosswalk is ~54k rows.


class HudApiError(RuntimeError):
    """The HUD API refused a request or returned something unusable."""


# --------------------------------------------------------------------- token
def resolve_token(explicit: str | None = None) -> str:
    """Find the API token, preferring sources that cannot be committed."""
    if explicit:
        return explicit.strip()
    env = os.environ.get("HUD_API_TOKEN", "").strip()
    if env:
        return env
    if os.path.exists(TOKEN_FILE):
        token = open(TOKEN_FILE).read().strip()
        if token:
            return token
    if HUD_API_TOKEN_PLACEHOLDER != "PASTE_YOUR_HUD_API_TOKEN_HERE":
        return HUD_API_TOKEN_PLACEHOLDER.strip()
    raise HudApiError(
        "No HUD API token found. Provide one of:\n"
        '  export HUD_API_TOKEN="your token"\n'
        f"  echo 'your token' > {os.path.relpath(TOKEN_FILE, BASE_DIR)}\n"
        "  or edit HUD_API_TOKEN_PLACEHOLDER in this file\n"
        "Register at https://www.huduser.gov/portal/dataset/uspszip-api.html")


# ----------------------------------------------------------------- transport
def _get(session: requests.Session, params: dict) -> dict:
    """One API call, with bounded retries on transient failures."""
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            last = exc
        else:
            if r.status_code == 200:
                return r.json()
            if r.status_code in (401, 403):
                raise HudApiError(
                    f"HUD rejected the token (HTTP {r.status_code}). Check that it "
                    "is current and has USPS Crosswalk access.")
            if r.status_code == 404:
                raise HudApiError(
                    f"HUD has no data for {params.get('year')} Q{params.get('quarter')}. "
                    "Try the previous quarter with --year/--quarter.")
            if r.status_code not in (429, 500, 502, 503, 504):
                raise HudApiError(f"HTTP {r.status_code} from HUD: {r.text[:200]}")
            last = HudApiError(f"HTTP {r.status_code}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise HudApiError(f"Giving up after {MAX_RETRIES} attempts: {last}")


def fetch_query(session: requests.Session, query: str,
                year: int, quarter: int) -> pd.DataFrame:
    """ZIP-to-county rows for one query: "All", a state abbreviation, or a ZIP."""
    payload = _get(session, {"type": CROSSWALK_TYPE_ZIP_TO_COUNTY,
                             "query": query, "year": year,
                             "quarter": quarter})
    results = (payload.get("data") or {}).get("results") or []
    if not results:
        return pd.DataFrame(columns=["ZIP", "COUNTY", "RES_RATIO",
                                     "BUS_RATIO", "OTH_RATIO", "TOT_RATIO"])
    df = pd.DataFrame(results)
    # HUD names the county column `geoid` for this crosswalk type.
    county_col = "geoid" if "geoid" in df.columns else "county"
    out = pd.DataFrame({
        "ZIP": df["zip"].astype(str).str.zfill(5),
        "COUNTY": df[county_col].astype(str).str.zfill(5),
    })
    for src, dst in (("res_ratio", "RES_RATIO"), ("bus_ratio", "BUS_RATIO"),
                     ("oth_ratio", "OTH_RATIO"), ("tot_ratio", "TOT_RATIO")):
        out[dst] = pd.to_numeric(df[src], errors="coerce") if src in df else pd.NA
    return out


def fetch_all(token: str, year: int, quarter: int,
              states: Iterable[str] = STATE_ABBRS) -> pd.DataFrame:
    """The national crosswalk, in one request where possible."""
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}",
                            "Accept": "application/json"})

    try:
        national = fetch_query(session, "All", year, quarter)
    except HudApiError as exc:
        print(f"  national request failed ({exc}); falling back to per-state")
    else:
        if len(national) >= EXPECTED_MIN_ROWS:
            print(f"  national request returned {len(national):,} rows")
            return national
        print(f"  national request returned only {len(national):,} rows; "
              f"falling back to per-state")

    frames, failures = [], []
    states = list(states)
    for i, abbr in enumerate(states, 1):
        try:
            df = fetch_query(session, abbr, year, quarter)
        except HudApiError as exc:
            failures.append((abbr, str(exc)))
            print(f"  [{i:>2}/{len(states)}] {abbr}  FAILED  {exc}")
        else:
            frames.append(df)
            print(f"  [{i:>2}/{len(states)}] {abbr}  {len(df):>6,} rows")
        time.sleep(THROTTLE_SECONDS)
    if failures:
        raise HudApiError(
            f"{len(failures)} state(s) failed: "
            + ", ".join(f for f, _ in failures)
            + ". Nothing written; rerun rather than build on a partial crosswalk.")
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------- validation
def validate(df: pd.DataFrame) -> None:
    """Refuse to write a crosswalk that would silently degrade the mapping."""
    if len(df) < EXPECTED_MIN_ROWS:
        raise HudApiError(
            f"Only {len(df):,} rows returned; a national crosswalk has roughly "
            f"54,000. Refusing to write a partial file.")
    if not df["ZIP"].str.fullmatch(r"\d{5}").all():
        raise HudApiError("malformed ZIP codes in the response")
    if not df["COUNTY"].str.fullmatch(r"\d{5}").all():
        raise HudApiError("malformed county FIPS in the response")
    if df["RES_RATIO"].isna().all():
        raise HudApiError(
            "no RES_RATIO values returned; the residential-address share is "
            "the field the mapping selects on.")

    # Connecticut is the reason this file is worth fetching: its planning
    # regions (09110-09190) must be present, not the retired counties.
    ct = set(df.loc[df["COUNTY"].str.startswith("09"), "COUNTY"])
    modern = {c for c in ct if c.startswith("091")}
    if not modern:
        raise HudApiError(
            f"Connecticut still resolves to retired county FIPS {sorted(ct)}. "
            "This vintage predates the 2022 planning regions; request a later "
            "year/quarter.")
    print(f"\n  Connecticut resolves to {len(modern)} planning regions: "
          f"{', '.join(sorted(modern))}")


def summarise(df: pd.DataFrame) -> None:
    best = (df.sort_values("RES_RATIO", ascending=False)
              .drop_duplicates("ZIP", keep="first"))
    multi = df.groupby("ZIP").size()
    print(f"  rows                        {len(df):>9,}")
    print(f"  distinct ZIPs               {df['ZIP'].nunique():>9,}")
    print(f"  ZIPs spanning >1 county     {int((multi > 1).sum()):>9,}")
    print(f"  distinct counties           {best['COUNTY'].nunique():>9,}")


# ------------------------------------------------------------------ pipeline
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=DEFAULT_YEAR)
    ap.add_argument("--quarter", type=int, default=DEFAULT_QUARTER, choices=[1, 2, 3, 4])
    ap.add_argument("--token", default=None,
                    help="API token; prefer HUD_API_TOKEN in the environment")
    ap.add_argument("--output", default=OUTPUT_CSV)
    ap.add_argument("--dry-run", action="store_true",
                    help="verify the token against one state, write nothing")
    args = ap.parse_args()

    print("=" * 70)
    print(f"  HUD-USPS ZIP-COUNTY CROSSWALK   {args.year} Q{args.quarter}")
    print("=" * 70)

    try:
        token = resolve_token(args.token)
    except HudApiError as exc:
        print(f"\n{exc}")
        return 2
    print(f"  token: ...{token[-6:]} ({len(token)} chars)\n")

    try:
        if args.dry_run:
            session = requests.Session()
            session.headers.update({"Authorization": f"Bearer {token}"})
            probe = fetch_query(session, "CT", args.year, args.quarter)
            print(f"  Connecticut probe returned {len(probe):,} rows")
            if not probe.empty:
                print("  sample:")
                print(probe.head(5).to_string(index=False))
            print("\n  Dry run: nothing written.")
            return 0

        df = fetch_all(token, args.year, args.quarter)
        print()
        validate(df)
        print()
        summarise(df)
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        df.to_csv(args.output, index=False)
    except HudApiError as exc:
        print(f"\n  FAILED: {exc}")
        return 1

    rel = os.path.relpath(args.output, BASE_DIR)
    print(f"\n  Written to {rel}")
    print("\n  facility_mapping.py will now use hud_res_ratio automatically.")
    print("  Rebuild and re-validate:")
    print("    python code/02_build_analytic_dataset.py")
    print("    python code/00_run_all.py --with-present")
    print("    python tests/test_pipeline.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
