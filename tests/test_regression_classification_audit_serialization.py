"""Stage 44 -- runner classification for audit serialization/residue (static)."""

from __future__ import annotations

from pathlib import Path

RUNNER = Path("scripts/run_full_regression.sh")


def _text():
    return RUNNER.read_text(encoding="utf-8")


def test_lock_timeout_classified():
    t = _text()
    assert 'AUDIT_VERIFICATION_LOCK: TIMEOUT' in t
    assert 'result_class="audit_lock_timeout"' in t


def test_residue_classified_separately():
    t = _text()
    assert "AUDIT_TAMPER_RESIDUE_DETECTOR: FAIL" in t
    assert "AUDIT_TAMPER_SIMULATION_NO_RESIDUE: FAIL" in t
    assert 'result_class="audit_tamper_residue_failure"' in t


def test_serialization_failures_counted_as_disallowed():
    t = _text()
    # The DISALLOWED_FAIL sum must include the serialization + residue counts.
    assert "AUDIT_SERIALIZATION_FAIL_COUNT + AUDIT_RESIDUE_FAIL_COUNT" in t


def test_residue_failure_outranks_generic_in_result_class():
    t = _text()
    # The residue/serialization branches come before generic in the final
    # RESULT_CLASS determination.
    idx_residue = t.index('RESULT_CLASS="audit_tamper_residue_failure"')
    idx_regression = t.index('RESULT_CLASS="regression_failure"')
    assert idx_residue < idx_regression


def test_residue_not_treated_as_allowed_gap():
    t = _text()
    # Only backup readiness is an allowed gap; residue must never be one.
    assert "audit_tamper_residue" not in t.split("ALLOWED_GAPS_SCRIPTS=(")[1].split(")")[0]


def test_lock_timeout_not_skipped_pass():
    t = _text()
    # audit_lock_timeout must not be classified as skipped_pass.
    assert 'result_class="audit_lock_timeout"' in t
    assert 'result_class="skipped_pass"\n        AUDIT_LOCK_TIMEOUT' not in t
