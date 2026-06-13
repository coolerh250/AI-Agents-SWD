"""Stage 43 -- audit_log restore metrics are registered."""

from __future__ import annotations

from prometheus_client import REGISTRY

from shared.sdk.observability import metrics

EXPECTED = [
    "audit_log_restore_precheck_total",
    "audit_log_restore_dry_run_total",
    "audit_log_restore_approval_required_total",
    "audit_log_restore_runs_total",
    "audit_log_restore_failures_total",
    "audit_log_restore_verified_total",
    "audit_log_restore_records_modified_total",
]


def test_metric_objects_exist():
    assert hasattr(metrics, "AUDIT_LOG_RESTORE_RUNS_TOTAL")
    assert hasattr(metrics, "AUDIT_LOG_RESTORE_PRECHECK_TOTAL")
    assert hasattr(metrics, "AUDIT_LOG_RESTORE_RECORDS_MODIFIED_TOTAL")


def test_metrics_registered():
    names = set(REGISTRY._names_to_collectors.keys())
    for m in EXPECTED:
        assert m in names, f"{m} not registered"


def test_metrics_labels():
    metrics.AUDIT_LOG_RESTORE_PRECHECK_TOTAL.labels(
        status="passed", root_cause="test_tamper_not_restored"
    ).inc(0)
    metrics.AUDIT_LOG_RESTORE_RUNS_TOTAL.labels(status="completed", approved="true").inc(0)
    metrics.AUDIT_LOG_RESTORE_RECORDS_MODIFIED_TOTAL.labels(status="completed").inc(0)
    metrics.AUDIT_LOG_RESTORE_APPROVAL_REQUIRED_TOTAL.labels(
        root_cause="test_tamper_not_restored"
    ).inc(0)


def test_metrics_render():
    body, _ = metrics.metrics_response()
    text = body.decode("utf-8")
    assert "audit_log_restore_runs_total" in text
    assert "audit_log_restore_precheck_total" in text
