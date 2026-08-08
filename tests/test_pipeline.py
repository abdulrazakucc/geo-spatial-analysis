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

import json
import os
import re
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
def test_no_unexpected_nan_in_results():
    """Correlations and descriptives must all be computable.

    scipy propagates NaN when an input contains missing values, which produced
    silently NaN EDI Spearman correlations. The only NaN the pipeline may emit
    is a non-estimable model term, which is reported as NE and flagged with an
    `estimable` key.
    """
    path = os.path.join(BASE_DIR, "output", "validation", "manuscript_numbers.json")
    if not os.path.exists(path):
        import pytest
        pytest.skip("run the pipeline first")
    with open(path) as f:
        R = json.load(f)
    for block in ("correlations", "descriptives", "quintiles"):
        bad = [k for k, v in R[block].items()
               if isinstance(v, float) and v != v]
        assert not bad, f"NaN in {block}: {bad}"


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


def test_hud_crosswalk_selection():
    """When a HUD crosswalk is present it wins, and it selects on RES_RATIO."""
    import tempfile
    import facility_mapping as fm

    original = fm.HUD_CROSSWALK
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "hud_zip_county.csv")
    pd.DataFrame({
        "ZIP": ["06106", "06106"],
        "COUNTY": ["09110", "09190"],
        "RES_RATIO": [0.95, 0.05],
        # Deliberately opposed to RES_RATIO: selecting on the wrong column
        # would pick 09190 and this test would fail.
        "BUS_RATIO": [0.05, 0.95],
    }).to_csv(path, index=False)
    try:
        fm.HUD_CROSSWALK = path
        crosswalk, method = fm.load_crosswalk()
        assert method == "hud_res_ratio", method
        chosen = crosswalk.loc[crosswalk.zip5 == "06106", "county_fips"].iloc[0]
        assert chosen == "09110", f"expected largest RES_RATIO, got {chosen}"
    finally:
        fm.HUD_CROSSWALK = original


def test_hud_fetcher_rejects_bad_vintage():
    """The fetcher must not write a crosswalk with retired CT geography."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hud_fetch", os.path.join(BASE_DIR, "code", "01c_fetch_hud_crosswalk.py"))
    hud = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hud)

    retired = pd.DataFrame({"ZIP": [f"{i:05d}" for i in range(45_000)],
                            "COUNTY": ["09003"] * 45_000,
                            "RES_RATIO": [1.0] * 45_000})
    for frame, what in ((retired, "retired CT FIPS"),
                        (retired.head(10), "partial download")):
        try:
            hud.validate(frame)
        except hud.HudApiError:
            continue
        raise AssertionError(f"validate() accepted a {what}")


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


def _run_gate(manuscript):
    """Execute the validator against a named manuscript and return its report.

    Reading a previously written manuscript_check.txt would pass on a stale
    file, and would say nothing about which document was checked. This runs the
    gate for real, in strict mode, against the path given.
    """
    proc = subprocess.run(
        [sys.executable, os.path.join(BASE_DIR, "code", "12_manuscript_numbers.py"),
         manuscript, "--strict"],
        cwd=BASE_DIR, capture_output=True, text=True, timeout=900)
    report = os.path.join(BASE_DIR, "output", "validation", "manuscript_check.txt")
    text = open(report).read() if os.path.exists(report) else ""
    return proc.returncode, text


def _mismatches(text):
    m = re.search(r"Mismatches:\s+(\d+)", text)
    return int(m.group(1)) if m else -1


def test_manuscript_numbers():
    """The working manuscript must pass the gate, executed live."""
    working = os.path.join(BASE_DIR, "manuscript", "manuscript_CLEAN.docx")
    if not os.path.exists(working):
        import pytest
        pytest.skip("manuscript not present (it is not tracked in git)")
    code, text = _run_gate(working)
    assert os.path.relpath(working, BASE_DIR) in text, (
        "the report does not name the manuscript that was checked")
    assert _mismatches(text) == 0, f"{_mismatches(text)} mismatch(es); see the report"
    assert code == 0, f"validator exited {code}"


def test_submission_manuscript_passes_gate():
    """The file that would actually be submitted must pass, by name."""
    submission = os.path.join(BASE_DIR, "manuscript", "manuscript_SUBMISSION.docx")
    if not os.path.exists(submission):
        import pytest
        pytest.skip("submission manuscript not built; run tools/finalize_manuscript.py")
    code, text = _run_gate(submission)
    assert "manuscript_SUBMISSION.docx" in text, (
        "the report must record that the submission file was the one checked")
    assert _mismatches(text) == 0, f"{_mismatches(text)} mismatch(es); see the report"
    assert code == 0, f"validator exited {code}"


def test_submission_manuscript_is_clean():
    """No tracked changes, comments, or dangling package references."""
    import zipfile
    submission = os.path.join(BASE_DIR, "manuscript", "manuscript_SUBMISSION.docx")
    if not os.path.exists(submission):
        import pytest
        pytest.skip("submission manuscript not built")
    with zipfile.ZipFile(submission) as z:
        names = z.namelist()
        assert z.testzip() is None, "corrupt package"
        xml = z.read("word/document.xml").decode("utf8")
        assert not re.findall(r"<w:ins[ >]", xml), "tracked insertions remain"
        assert not re.findall(r"<w:del[ >]", xml), "tracked deletions remain"
        assert "commentReference" not in xml, "comment references remain"
        rels = z.read("word/_rels/document.xml.rels").decode("utf8")
        dangling = [t for t in re.findall(r'Target="([^"]+)"', rels)
                    if not t.startswith("http")
                    and "word/" + t.lstrip("./") not in names]
        assert not dangling, f"dangling relationship targets: {dangling}"


def test_publication_outputs_consume_canonical_results():
    """07_publication_outputs.py must not fit its own regressions.

    It previously refitted with a fixed dispersion, on the wrong sample, with a
    mis-scaled predictor, and reported a placeholder sensitivity. Its output
    must now agree with the canonical results file.
    """
    src = open(os.path.join(BASE_DIR, "code", "07_publication_outputs.py")).read()
    for pattern, why in (
            (r"NegativeBinomial\(alpha\s*=", "refits with a fixed dispersion"),
            (r"svi_percentile\s*/\s*10", "mis-scales the SVI predictor"),
            (r"Accredited-only \(excluding Under Review\)", "placeholder sensitivity")):
        assert not re.search(pattern, src), f"07_publication_outputs.py {why}"

    report = os.path.join(BASE_DIR, "output", "models", "regression_results_full.txt")
    numbers = os.path.join(BASE_DIR, "output", "validation", "manuscript_numbers.json")
    if not (os.path.exists(report) and os.path.exists(numbers)):
        import pytest
        pytest.skip("run the pipeline first")
    text = open(report).read()
    with open(numbers) as f:
        R = json.load(f)["regressions"]
    assert f"{R['n_svi']:,}" in text, "publication output disagrees on the SVI sample"
    e = R["models"]["SVI_CCT"]["adjusted_metro"]
    assert f"{e['irr']:.3f}" in text, (
        "publication output does not carry the canonical SVI-CCT estimate")


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
