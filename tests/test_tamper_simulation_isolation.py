"""Stage 44 -- tamper simulation isolation (static guarantees)."""

from __future__ import annotations

from pathlib import Path

SIM = Path("scripts/simulate_audit_tamper_detection.sh")


def _text():
    return SIM.read_text(encoding="utf-8")


def test_simulation_sources_lock_helper():
    assert "audit_verification_lock.sh" in _text()


def test_simulation_acquires_exclusive_lock():
    t = _text()
    assert "acquire_audit_exclusive_lock" in t
    assert "AUDIT_TAMPER_SIMULATION_LOCKED: PASS" in t


def test_simulation_has_isolation_markers():
    t = _text()
    assert "AUDIT_TAMPER_SIMULATION_RESTORE: PASS" in t
    assert "AUDIT_TAMPER_SIMULATION_NO_RESIDUE: PASS" in t
    assert "AUDIT_TAMPER_SIMULATION_NO_RESIDUE: FAIL" in t


def test_simulation_restore_in_finally():
    t = _text()
    # The python keeps a try/finally restore; confirm the finally restore path.
    assert "finally:" in t
    assert "UPDATE audit_logs SET summary" in t


def test_simulation_pre_checks_residue():
    t = _text()
    assert "assert_no_audit_tamper_residue" in t


def test_simulation_points_to_restore_exception_on_residue():
    t = _text()
    assert "controlled audit_log restore exception" in t
    assert "Do not manually update DB" in t


def test_simulation_does_not_auto_repair():
    t = _text()
    # It must not invoke the restore script itself (no silent auto-repair).
    assert "restore_audit_log_test_tamper_residue.sh" not in t
