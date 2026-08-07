#!/usr/bin/env python3
"""
facility_mapping.py
===================
Builds the facility cohort and maps every facility to a county, keeping a
complete per-record audit trail.

Design rule: **no silent drops.** Every row of the source extract leaves this
module with either an assigned county FIPS or an explicit exclusion reason.
The two counts are asserted to reconcile against the source total.

Cohort definition (from the project briefing)
---------------------------------------------
    50 states + DC
    modality MRAP (cardiac MR) or CTAP (cardiac CT), cardiac module present
    status "Accredited" or "Under Review"
    not expired as of the extraction date, 2026-05-20

"Under Review" is part of the primary cohort by design. An Accredited-only
cohort is available via `cohort(accredited_only=True)` for the sensitivity
analysis; it is not the primary definition.

ZIP-to-county mapping
---------------------
Two methods, tried in order, recorded per record in `mapping_method`:

1. ``hud_res_ratio`` — the specified method. A HUD-USPS ZIP–County crosswalk
   at `data/raw/hud_zip_county.csv`, assigning each ZIP to the county holding
   the largest residential-address share (`RES_RATIO`). Used automatically
   whenever that file is present.

2. ``census_zcta_arealand`` — fallback. The Census 2020 ZCTA-county
   relationship file, assigning by largest land-area overlap. This is *not*
   equivalent to the specified method: it is a different vintage and a
   different tie-break rule.

Because the 2020 vintage predates Connecticut's 2022 replacement of counties
with nine planning regions, CT ZIPs resolve to retired FIPS (09001-09015) that
match nothing in the current county universe (09110-09190). Under the fallback,
CT records are therefore resolved by an explicit town-to-planning-region table
(`CT_TOWN_TO_PLANNING_REGION`), recorded as ``ct_town_manual`` with
``manual_review = True``. Supplying the HUD file removes the need for it.
"""

from __future__ import annotations

import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROC_DIR = os.path.join(DATA_DIR, "processed")

#: Registry extract supplied by the investigators, and its extraction date.
SOURCE_WORKBOOK = os.path.join(DATA_DIR, "download.xlsx")
EXTRACTION_DATE = pd.Timestamp("2026-05-20")

#: Optional, and preferred when present. See module docstring.
HUD_CROSSWALK = os.path.join(RAW_DIR, "hud_zip_county.csv")
CENSUS_CROSSWALK = os.path.join(RAW_DIR, "zcta_county_crosswalk_2020.txt")

AUDIT_CSV = os.path.join(PROC_DIR, "facility_mapping_audit.csv")

MODALITY_LABEL = {"MRAP": "CMR", "CTAP": "CCT"}

STATES_50_DC = frozenset("""
AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT
NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC
""".split())

#: Connecticut adopted nine planning regions as county equivalents in 2022.
#: Membership is by town. Only towns appearing in the supplied extract need to
#: be listed; an unlisted town raises rather than being dropped.
CT_TOWN_TO_PLANNING_REGION = {
    "bloomfield": "09110",       # Capitol
    "farmington": "09110",
    "hartford": "09110",
    "manchester": "09110",
    "new britain": "09110",
    "west hartford": "09110",
    "bridgeport": "09120",       # Greater Bridgeport
    "trumbull": "09120",
    "derby": "09140",            # Naugatuck Valley
    "shelton": "09140",
    "waterbury": "09140",
    "meriden": "09170",          # South Central Connecticut
    "new haven": "09170",
    "wallingford": "09170",
    "mystic": "09180",           # Southeastern Connecticut
    "new london": "09180",
    "danbury": "09190",          # Western Connecticut
    "greenwich": "09190",
    "norwalk": "09190",
    "stamford": "09190",
}

AUDIT_COLUMNS = [
    "source_row_id", "facility_name", "modality", "modality_label", "status",
    "expiration_date", "state", "city", "zip_original", "zip5",
    "protocol_eligible", "protocol_exclusion_reason", "zip_crosswalk_match",
    "assigned_county_fips", "assigned_county_name", "mapping_share",
    "mapping_method", "manual_review", "final_included", "final_exclusion_reason",
]


# --------------------------------------------------------------------- source
def load_source() -> pd.DataFrame:
    """The full registry extract, one row per facility-modality record."""
    if not os.path.exists(SOURCE_WORKBOOK):
        raise FileNotFoundError(
            f"Registry extract not found at {SOURCE_WORKBOOK}. This file is "
            "supplied by the investigators and is required; the pipeline does "
            "not substitute any other facility source.")
    df = pd.read_excel(SOURCE_WORKBOOK)
    df = df.reset_index(drop=True)
    df["source_row_id"] = df.index.map(lambda i: f"SRC{i + 1:06d}")
    return df


def _zip5(series: pd.Series) -> pd.Series:
    return (series.astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.extract(r"(\d+)", expand=False)
            .fillna("")
            .str.zfill(5).str[:5])


def classify_eligibility(df: pd.DataFrame, accredited_only: bool = False) -> pd.DataFrame:
    """Tag each source row eligible, or give the reason it is not.

    Reasons are evaluated in a fixed order so each row gets one stable reason.
    """
    out = df.copy()
    out["zip_original"] = out["Zip Code"]
    out["zip5"] = _zip5(out["Zip Code"])
    out["modality_label"] = out["modality"].map(MODALITY_LABEL)
    exp = pd.to_datetime(out["Expiration Date"], errors="coerce")
    out["expiration_date"] = exp

    is_cardiac_modality = out["modality"].isin(MODALITY_LABEL)
    has_cardiac_module = (out["modules"].astype(str)
                          .str.contains("cardiac", case=False, na=False))
    allowed_status = ["Accredited"] if accredited_only else ["Accredited", "Under Review"]
    ok_status = out["Status"].isin(allowed_status)
    ok_state = out["state"].isin(STATES_50_DC)
    expired = exp.notna() & (exp < EXTRACTION_DATE)
    ok_zip = out["zip5"].str.fullmatch(r"\d{5}").fillna(False)

    reason = pd.Series(pd.NA, index=out.index, dtype="object")
    reason = reason.mask(~is_cardiac_modality & reason.isna(), "modality not MRAP or CTAP")
    reason = reason.mask(~has_cardiac_module & reason.isna(), "no cardiac module")
    reason = reason.mask(~ok_status & reason.isna(),
                         "status not " + " or ".join(allowed_status))
    reason = reason.mask(expired & reason.isna(),
                         f"accreditation expired before {EXTRACTION_DATE.date()}")
    reason = reason.mask(~ok_state & reason.isna(), "outside 50 states and DC")
    reason = reason.mask(~ok_zip & reason.isna(), "missing or malformed ZIP code")

    out["protocol_exclusion_reason"] = reason
    out["protocol_eligible"] = reason.isna()
    return out


# ----------------------------------------------------------------- crosswalks
def load_crosswalk():
    """(mapping DataFrame, method name). Prefers HUD when available."""
    if os.path.exists(HUD_CROSSWALK):
        hud = pd.read_csv(HUD_CROSSWALK, dtype=str)
        cols = {c.upper(): c for c in hud.columns}
        zip_c, cty_c = cols["ZIP"], cols["COUNTY"]
        ratio_c = cols.get("RES_RATIO")
        if ratio_c is None:
            raise ValueError(f"{HUD_CROSSWALK} has no RES_RATIO column; "
                             "the residential-address share is required.")
        hud["zip5"] = _zip5(hud[zip_c])
        hud["county_fips"] = hud[cty_c].str.zfill(5)
        hud["share"] = pd.to_numeric(hud[ratio_c], errors="coerce").fillna(0.0)
        best = (hud.sort_values("share", ascending=False)
                   .drop_duplicates("zip5", keep="first")
                   [["zip5", "county_fips", "share"]])
        return best.reset_index(drop=True), "hud_res_ratio"

    cw = pd.read_csv(CENSUS_CROSSWALK, sep="|", dtype=str)
    cw["zip5"] = cw["GEOID_ZCTA5_20"].str.zfill(5)
    cw["county_fips"] = cw["GEOID_COUNTY_20"].str.zfill(5)
    cw["share"] = pd.to_numeric(cw["AREALAND_PART"], errors="coerce").fillna(0.0)
    total = cw.groupby("zip5")["share"].transform("sum")
    cw["share"] = (cw["share"] / total.where(total > 0)).fillna(0.0)
    best = (cw.sort_values("share", ascending=False)
              .drop_duplicates("zip5", keep="first")
              [["zip5", "county_fips", "share"]])
    return best.reset_index(drop=True), "census_zcta_arealand"


def _resolve_connecticut(row):
    town = str(row.get("city", "")).strip().lower()
    fips = CT_TOWN_TO_PLANNING_REGION.get(town)
    if fips is None:
        raise KeyError(
            f"Connecticut town {row.get('city')!r} (ZIP {row.get('zip5')}) is not in "
            "CT_TOWN_TO_PLANNING_REGION. Add it, or supply the HUD crosswalk, "
            "rather than letting the record drop.")
    return fips


def assign_counties(eligible: pd.DataFrame, valid_fips: set[str]) -> pd.DataFrame:
    """Attach county FIPS to eligible records, with method and share recorded."""
    crosswalk, method = load_crosswalk()
    out = eligible.merge(crosswalk, on="zip5", how="left")
    out["mapping_method"] = method
    out["zip_crosswalk_match"] = out["county_fips"].notna()
    out["manual_review"] = False

    # Connecticut needs the town table in two distinct cases: the ZIP resolved
    # to a retired county FIPS (09001-09015), or it is absent from the 2020
    # ZCTA file altogether, which happens for PO-box-only ZIPs. Both leave the
    # record unusable, so both are routed through the same resolution.
    unusable = out["county_fips"].isna() | ~out["county_fips"].isin(valid_fips)
    needs_ct = unusable & (out["state"] == "CT")
    if needs_ct.any():
        out.loc[needs_ct, "county_fips"] = out.loc[needs_ct].apply(_resolve_connecticut, axis=1)
        out.loc[needs_ct, "mapping_method"] = "ct_town_manual"
        out.loc[needs_ct, "manual_review"] = True
        out.loc[needs_ct, "share"] = pd.NA

    still_bad = out["county_fips"].isna() | ~out["county_fips"].isin(valid_fips)
    out["final_included"] = ~still_bad
    out["final_exclusion_reason"] = pd.Series(pd.NA, index=out.index, dtype="object")
    out.loc[out["county_fips"].isna(), "final_exclusion_reason"] = (
        "ZIP not found in the " + method + " crosswalk")
    out.loc[out["county_fips"].notna() & still_bad, "final_exclusion_reason"] = (
        "mapped to a FIPS absent from the current county universe")
    out = out.rename(columns={"county_fips": "assigned_county_fips",
                              "share": "mapping_share"})
    return out


# ------------------------------------------------------------------- pipeline
def build(valid_fips, county_names=None, accredited_only=False, write_audit=True):
    """Cohort, county assignment, audit table, and reconciliation assertions.

    Returns (audit DataFrame, facility counts per county DataFrame).
    """
    valid_fips = set(valid_fips)
    source = load_source()
    tagged = classify_eligibility(source, accredited_only=accredited_only)

    eligible = tagged[tagged["protocol_eligible"]].copy()
    ineligible = tagged[~tagged["protocol_eligible"]].copy()
    mapped = assign_counties(eligible, valid_fips)

    for frame in (ineligible,):
        frame["assigned_county_fips"] = pd.NA
        frame["mapping_share"] = pd.NA
        frame["mapping_method"] = pd.NA
        frame["zip_crosswalk_match"] = pd.NA
        frame["manual_review"] = False
        frame["final_included"] = False
        frame["final_exclusion_reason"] = frame["protocol_exclusion_reason"]

    audit = pd.concat([mapped, ineligible], ignore_index=True)
    audit = audit.rename(columns={"Facility Name": "facility_name",
                                  "Status": "status"})
    if county_names is not None:
        audit["assigned_county_name"] = audit["assigned_county_fips"].map(county_names)
    else:
        audit["assigned_county_name"] = pd.NA
    audit = audit.reindex(columns=AUDIT_COLUMNS).sort_values("source_row_id")

    _assert_reconciles(audit, len(source))

    if write_audit:
        os.makedirs(PROC_DIR, exist_ok=True)
        audit.to_csv(AUDIT_CSV, index=False)

    inc = audit[audit["final_included"]]
    counts = (inc.pivot_table(index="assigned_county_fips", columns="modality_label",
                              values="source_row_id", aggfunc="count")
                 .reindex(columns=["CMR", "CCT"]).fillna(0).astype(int)
                 .rename(columns={"CMR": "cmr_facility_count",
                                  "CCT": "cct_facility_count"})
                 .rename_axis("county_fips").reset_index())
    return audit, counts


def _assert_reconciles(audit: pd.DataFrame, n_source: int) -> None:
    """The guarantees this module exists to provide."""
    assert len(audit) == n_source, (
        f"audit has {len(audit)} rows, source had {n_source}")
    assert audit["source_row_id"].is_unique, "duplicate source_row_id in audit"

    included = int(audit["final_included"].sum())
    excluded = int(audit["final_exclusion_reason"].notna().sum())
    assert included + excluded == n_source, (
        f"{included} included + {excluded} excluded != {n_source} source rows")

    silent = audit[~audit["final_included"] & audit["final_exclusion_reason"].isna()]
    assert silent.empty, f"{len(silent)} records dropped without a reason"

    inc = audit[audit["final_included"]]
    assert inc["assigned_county_fips"].notna().all(), "included record without a FIPS"
    assert inc["assigned_county_fips"].str.fullmatch(r"\d{5}").all(), "malformed FIPS"


def reconciliation_report(audit: pd.DataFrame) -> str:
    """Human-readable reconciliation, saved beside the numeric outputs."""
    L = []
    a = L.append
    n = len(audit)
    elig = audit[audit["protocol_eligible"]]
    inc = audit[audit["final_included"]]
    a("=" * 78)
    a("FACILITY MAPPING RECONCILIATION")
    a("=" * 78)
    a(f"  Source extract, {EXTRACTION_DATE.date()}            {n:>7,} records")
    a(f"  Protocol-eligible                        {len(elig):>7,}")
    a(f"  Included in the county dataset           {len(inc):>7,}")
    a(f"  Excluded, with a stated reason           {n - len(inc):>7,}")
    a("")
    a("  Eligibility exclusions")
    a("  " + "-" * 74)
    counts = audit.loc[~audit["protocol_eligible"], "protocol_exclusion_reason"].value_counts()
    for reason, k in counts.items():
        a(f"    {reason:<62} {k:>7,}")
    post = audit[audit["protocol_eligible"] & ~audit["final_included"]]
    a("")
    a("  Eligible but unmappable")
    a("  " + "-" * 74)
    if post.empty:
        a("    none")
    else:
        for reason, k in post["final_exclusion_reason"].value_counts().items():
            a(f"    {reason:<62} {k:>7,}")
    a("")
    a("  Mapping method, included records")
    a("  " + "-" * 74)
    for method, k in inc["mapping_method"].value_counts().items():
        a(f"    {method:<62} {k:>7,}")
    a(f"    flagged for manual review{'':<37} {int(inc['manual_review'].sum()):>7,}")
    a("")
    a("  Included by modality")
    a("  " + "-" * 74)
    for label, k in inc["modality_label"].value_counts().items():
        a(f"    {label:<62} {k:>7,}")
    a("")
    a("  Connecticut")
    a("  " + "-" * 74)
    ct = audit[(audit["state"] == "CT") & audit["protocol_eligible"]]
    ct_inc = ct[ct["final_included"]]
    a(f"    eligible records{'':<46} {len(ct):>7,}")
    a(f"    included{'':<54} {len(ct_inc):>7,}")
    for label, k in ct_inc["modality_label"].value_counts().items():
        a(f"      {label:<60} {k:>7,}")
    a(f"    distinct planning regions{'':<37} {ct_inc['assigned_county_fips'].nunique():>7,}")
    return "\n".join(L)
