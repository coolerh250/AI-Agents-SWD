"""Stage 42 -- audit chain forensics/repair metrics are registered."""

from __future__ import annotations

from prometheus_client import REGISTRY

from shared.sdk.observability import metrics

EXPECTED_METRICS = [
    "audit_chain_forensics_runs_total",
    "audit_chain_forensics_failures_total",
    "audit_chain_failed_records_total",
    "audit_chain_repair_dry_run_total",
    "audit_chain_repair_skipped_unsafe_total",
    "audit_chain_repair_runs_total",
    "audit_chain_repair_failures_total",
    "audit_chain_repair_records_changed_total",
]


def test_metric_objects_exist():
    assert hasattr(metrics, "AUDIT_CHAIN_FORENSICS_RUNS_TOTAL")
    assert hasattr(metrics, "AUDIT_CHAIN_REPAIR_RUNS_TOTAL")
    assert hasattr(metrics, "AUDIT_CHAIN_REPAIR_RECORDS_CHANGED_TOTAL")


def test_metrics_registered_in_default_registry():
    names = set(REGISTRY._names_to_collectors.keys())
    for metric in EXPECTED_METRICS:
        # Counters expose <name>_total plus a <name> sample family name.
        assert metric in names or f"{metric}" in names, f"{metric} not registered"


def test_metrics_have_expected_labels():
    metrics.AUDIT_CHAIN_FORENSICS_RUNS_TOTAL.labels(
        root_cause="test_tamper_not_restored", status="completed"
    ).inc(0)
    metrics.AUDIT_CHAIN_REPAIR_RUNS_TOTAL.labels(
        root_cause="test_tamper_not_restored", status="completed"
    ).inc(0)
    metrics.AUDIT_CHAIN_REPAIR_RECORDS_CHANGED_TOTAL.labels(
        root_cause="test_tamper_not_restored"
    ).inc(0)
    metrics.AUDIT_CHAIN_REPAIR_SKIPPED_UNSAFE_TOTAL.labels(status="approval_required").inc(0)
    # No exception => label sets are correct.


def test_metrics_render_in_output():
    body, _ = metrics.metrics_response()
    text = body.decode("utf-8")
    assert "audit_chain_forensics_runs_total" in text
    assert "audit_chain_repair_runs_total" in text
