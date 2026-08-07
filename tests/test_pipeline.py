#!/usr/bin/env python3
"""
Pipeline integrity tests.

These encode the guarantees the analysis depends on: that every source record
is accounted for, that no facility is silently dropped, that Connecticut
reconciles to current geography, and that the model-specification and
sensitivity outputs exist.

Run
    python -m pytest tests/ -v
    python tests/test_pipeline.py       # no pytest required
"""

import os
import subprocess
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "code"))

PROC = os.path.join(BASE_DIR, "data", "processed")
RESULTS = os.path.join(BASE_DIR, "output", "results")

AUDIT = os.path.join(PROC, "facility_mapping_audit.csv")
COUNTY = os.path.join(PROC, "county_analytic_dataset.csv")


def _audit():
    return pd.read_csv(AUDIT, dtype={"assigned_county_fips": str, "zip5": str})


def _county():
    return pd.read_csv(COUNTY, dtype={"county_fips": str})


# ------------------------------------------------------------ reconciliation
def test_source_record_reconciliation():
    """eligible == included + explicitly excluded, with nothing unaccounted."""
    a = _audit()
    included = int(a.final_included.sum())
    excluded = int(a.final_exclusion_reason.notna().sum())
    assert included + excluded == len(a), (
        f"{included} + {excluded} != {len(a)} source records")


def test_no_silent_unmatched_facilities():
    """Every excluded record carries a reason."""
    a = _audit()
    silent = a[~a.final_included & a.final_exclusion_reason.isna()]
    assert silent.empty, f"{len(silent)} records dropped without a reason"


def test_valid_current_fips():
    """Every included record maps into the current county universe."""
    a = _audit()
    valid = set(_county().county_fips)
    inc = a[a.final_included]
    bad = inc[~inc.assigned_county_fips.isin(valid)]
    assert bad.empty, f"{len(bad)} records mapped outside the county universe"


def test_no_duplicate_source_row_ids():
    a = _audit()
    assert a.source_row_id.is_unique, "duplicate source_row_id"


def test_connecticut_reconciliation():
    """All 32 eligible CT records resolve to planning regions, none dropped."""
    a = _audit()
    ct = a[(a.state == "CT") & a.protocol_eligible]
    assert len(ct) == 32, f"expected 32 eligible CT records, found {len(ct)}"
    assert int(ct.final_included.sum()) == 32, (
        f"only {int(ct.final_included.sum())} of 32 CT records included")
    assert ct.loc[ct.final_included, "assigned_county_fips"].notna().all()
    regions = set(ct.loc[ct.final_included, "assigned_county_fips"])
    assert all(r.startswith("091") for r in regions), (
        f"CT mapped to non-planning-region FIPS: {sorted(regions)}")


def test_facility_counts_match_audit():
    """County totals equal the facility-level audit, by modality."""
    a = _audit()
    c = _county()
    inc = a[a.final_included]
    for label, column in (("CMR", "cmr_facility_count"), ("CCT", "cct_facility_count")):
        assert int((inc.modality_label == label).sum()) == int(c[column].sum()), (
            f"{label}: audit and county totals disagree")


def test_primary_status_definition():
    """The primary cohort is Accredited + Under Review, as specified."""
    a = _audit()
    statuses = set(a.loc[a.protocol_eligible, "status"].dropna())
    assert statuses.issubset({"Accredited", "Under Review"}), statuses
    assert "Under Review" in statuses, (
        "Under Review records are part of the primary cohort by design")


# ------------------------------------------------------------ county dataset
def test_unique_county_rows():
    c = _county()
    assert c.county_fips.is_unique, "duplicate county_fips"
    assert len(c) == 3144, f"expected 3,144 counties, found {len(c)}"
    assert c.county_fips.str.fullmatch(r"\d{5}").all(), "malformed county_fips"


def test_all_states_present():
    c = _county()
    assert c.state_abbr.nunique() == 51, (
        f"expected 50 states + DC, found {c.state_abbr.nunique()}")


# ------------------------------------------------------------------- outputs
def test_model_comparison_output():
    """Poisson and estimated-NB results must exist for every model."""
    path = os.path.join(RESULTS, "model_specification_comparison.csv")
    assert os.path.exists(path), "model specification comparison not generated"
    t = pd.read_csv(path)
    specs = set(t.specification)
    assert "Poisson" in specs and "NB2, estimated alpha" in specs, specs
    assert t.alpha.notna().any(), "no estimated dispersion recorded"
    assert t.converged.all(), "a model failed to converge"


def test_accredited_only_sensitivity_exists():
    path = os.path.join(RESULTS, "accredited_only_sensitivity.csv")
    assert os.path.exists(path), "accredited-only sensitivity not generated"
    assert len(pd.read_csv(path)) > 0


def test_no_random_production_fallback():
    """A missing required input must raise, not fabricate values."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_mod", os.path.join(BASE_DIR, "code", "02_build_analytic_dataset.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.DEMO_MODE is False, "demo mode must be off by default"
    try:
        mod.require_input("/nonexistent/path.csv", "test input", "nowhere")
    except FileNotFoundError:
        return
    raise AssertionError("require_input did not raise on a missing input")


def test_manuscript_numbers():
    """The validation gate must run clean."""
    check = os.path.join(BASE_DIR, "output", "validation", "manuscript_check.txt")
    if not os.path.exists(check):
        import pytest
        pytest.skip("validation report not generated yet")
    head = open(check).read()
    assert "Mismatches: 0" in head, (
        "manuscript does not match the generated outputs; see " + check)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {name}\n          {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  ERROR {name}\n          {type(exc).__name__}: {exc}")
    print(f"\n  {failures} failure(s)")
    sys.exit(1 if failures else 0)
