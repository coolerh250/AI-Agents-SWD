"""Stage 44 -- run_full_regression audit lock + serialization (static)."""

from __future__ import annotations

from pathlib import Path

RUNNER = Path("scripts/run_full_regression.sh")


def _text():
    return RUNNER.read_text(encoding="utf-8")


def test_runner_sources_lock_helper():
    assert "audit_verification_lock.sh" in _text()


def test_full_mode_acquires_lock_and_exports_inheritance():
    t = _text()
    assert 'MODE" = "full"' in t
    assert "acquire_audit_exclusive_lock" in t
    assert "AUDIT_VERIFICATION_LOCK_HELD_BY_RUNNER=true" in t


def test_runner_releases_lock_via_trap():
    t = _text()
    assert "trap '_runner_release_audit_lock' EXIT" in t
    assert "release_audit_lock" in t


def test_report_carries_audit_lock_fields():
    t = _text()
    for field in (
        "audit_lock_used",
        "audit_lock_acquired_at",
        "audit_lock_released",
        "audit_touching_scripts_serialized",
    ):
        assert field in t


def test_runner_has_audit_failure_classes():
    t = _text()
    assert "audit_serialization_failure" in t
    assert "audit_tamper_residue_failure" in t
    assert "audit_lock_timeout" in t


def test_runner_runs_residue_detector_pre_and_post():
    t = _text()
    assert "Pre-run audit tamper residue detector" in t
    assert "Post-run audit tamper residue detector" in t


def test_quick_mode_documented_no_lock():
    t = _text()
    # The lock is gated on full mode only.
    assert 'if [ "$MODE" = "full" ] && command -v acquire_audit_exclusive_lock' in t
