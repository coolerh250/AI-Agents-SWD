"""Stage 44 -- restore exception scripts acquire the audit lock (static)."""

from __future__ import annotations

from pathlib import Path

RESTORE = Path("scripts/restore_audit_log_test_tamper_residue.sh")
VERIFY = Path("scripts/verify_audit_log_restore_exception.sh")


def test_restore_script_sources_lock_helper():
    assert "audit_verification_lock.sh" in RESTORE.read_text(encoding="utf-8")


def test_restore_script_acquires_lock():
    t = RESTORE.read_text(encoding="utf-8")
    assert "acquire_audit_exclusive_lock" in t
    assert "AUDIT_LOG_RESTORE_LOCK: TIMEOUT" in t


def test_verify_restore_exception_holds_lock_for_children():
    t = VERIFY.read_text(encoding="utf-8")
    assert "acquire_audit_exclusive_lock" in t
    # It owns the lock and lets children (restore + downstream verifiers) inherit.
    assert "AUDIT_VERIFICATION_LOCK_HELD_BY_RUNNER=true" in t


def test_verify_restore_exception_lock_timeout_marker():
    t = VERIFY.read_text(encoding="utf-8")
    assert "AUDIT_LOG_RESTORE_LOCK: TIMEOUT" in t


def test_restore_still_summary_only_and_no_integrity_change():
    t = RESTORE.read_text(encoding="utf-8")
    # The serialization change must not have introduced integrity mutation.
    assert "UPDATE audit_integrity_records" not in t
