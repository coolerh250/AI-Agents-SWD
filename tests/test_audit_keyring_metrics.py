"""Stage 39 -- audit-integrity keyring metrics are registered."""

from __future__ import annotations

from shared.sdk.observability import metrics as M


def test_stage39_metrics_registered():
    for name in (
        "AUDIT_HMAC_KEYRING_LOAD_TOTAL",
        "AUDIT_HMAC_KEYRING_INVALID_TOTAL",
        "AUDIT_SIGNATURE_VERIFIED_TOTAL",
        "AUDIT_SIGNATURE_FAILED_TOTAL",
        "AUDIT_SIGNATURE_KEY_MISSING_TOTAL",
        "AUDIT_DIRECT_POST_INTEGRITY_CREATED_TOTAL",
        "AUDIT_DIRECT_POST_INTEGRITY_FAILURES_TOTAL",
        "AUDIT_INTEGRITY_SEQUENCE_LOCK_WAIT_SECONDS",
        "AUDIT_INTEGRITY_CONCURRENCY_RETRIES_TOTAL",
    ):
        assert hasattr(M, name), f"metrics module missing {name}"


def test_stage39_counter_labels():
    assert "mode" in M.AUDIT_SIGNATURE_VERIFIED_TOTAL._labelnames
    assert "signing_key_id" in M.AUDIT_SIGNATURE_VERIFIED_TOTAL._labelnames
    assert "mode" in M.AUDIT_SIGNATURE_FAILED_TOTAL._labelnames
    assert "reason" in M.AUDIT_SIGNATURE_FAILED_TOTAL._labelnames
    assert "mode" in M.AUDIT_SIGNATURE_KEY_MISSING_TOTAL._labelnames
    assert "status" in M.AUDIT_DIRECT_POST_INTEGRITY_CREATED_TOTAL._labelnames
    assert "reason" in M.AUDIT_DIRECT_POST_INTEGRITY_FAILURES_TOTAL._labelnames


def test_counters_increment():
    before = float(M.AUDIT_DIRECT_POST_INTEGRITY_CREATED_TOTAL.labels(status="signed")._value.get())
    M.AUDIT_DIRECT_POST_INTEGRITY_CREATED_TOTAL.labels(status="signed").inc()
    after = float(M.AUDIT_DIRECT_POST_INTEGRITY_CREATED_TOTAL.labels(status="signed")._value.get())
    assert after == before + 1.0
