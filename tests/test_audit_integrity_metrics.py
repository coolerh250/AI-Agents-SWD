"""Stage 34 -- audit integrity Prometheus counters are registered."""

from __future__ import annotations

from shared.sdk.observability import metrics as m


def test_stage34_counters_exist():
    assert hasattr(m, "AUDIT_INTEGRITY_RECORDS_TOTAL")
    assert hasattr(m, "AUDIT_INTEGRITY_MISSING_TOTAL")
    assert hasattr(m, "AUDIT_INTEGRITY_VERIFICATION_RUNS_TOTAL")
    assert hasattr(m, "AUDIT_INTEGRITY_VERIFICATION_FAILED_TOTAL")
    assert hasattr(m, "AUDIT_INTEGRITY_DEGRADED_TOTAL")
    assert hasattr(m, "AUDIT_TAMPER_DETECTED_TOTAL")


def test_counter_labels():
    assert m.AUDIT_INTEGRITY_RECORDS_TOTAL._labelnames == ("chain_version", "status")
    assert m.AUDIT_INTEGRITY_MISSING_TOTAL._labelnames == ("reason",)
    assert m.AUDIT_INTEGRITY_VERIFICATION_RUNS_TOTAL._labelnames == (
        "chain_version",
        "status",
    )
    assert m.AUDIT_INTEGRITY_VERIFICATION_FAILED_TOTAL._labelnames == ("reason",)
    assert m.AUDIT_INTEGRITY_DEGRADED_TOTAL._labelnames == ("reason",)
    assert m.AUDIT_TAMPER_DETECTED_TOTAL._labelnames == ("reason",)


def test_counters_can_increment_without_error():
    m.AUDIT_INTEGRITY_RECORDS_TOTAL.labels(chain_version="1", status="signed").inc()
    m.AUDIT_INTEGRITY_MISSING_TOTAL.labels(reason="backfill_required").inc()
    m.AUDIT_INTEGRITY_VERIFICATION_RUNS_TOTAL.labels(chain_version="1", status="passed").inc()
    m.AUDIT_INTEGRITY_VERIFICATION_FAILED_TOTAL.labels(
        reason="canonical_payload_hash_mismatch"
    ).inc()
    m.AUDIT_INTEGRITY_DEGRADED_TOTAL.labels(reason="integrity_write_failed").inc()
    m.AUDIT_TAMPER_DETECTED_TOTAL.labels(reason="canonical_payload_hash_mismatch").inc()
