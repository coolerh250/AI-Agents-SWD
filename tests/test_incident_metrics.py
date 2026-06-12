"""Stage 40 -- incident metrics registration tests."""


def test_incident_metrics_registered():
    from shared.sdk.observability.metrics import (
        INCIDENT_ACKNOWLEDGED_TOTAL,
        INCIDENT_ALERTS_RECEIVED_TOTAL,
        INCIDENT_ALERTS_REJECTED_TOTAL,
        INCIDENT_CLOSED_TOTAL,
        INCIDENT_CREATED_TOTAL,
        INCIDENT_DEDUPLICATED_TOTAL,
        INCIDENT_ESCALATION_DRY_RUN_TOTAL,
        INCIDENT_POSTMORTEM_REQUIRED_TOTAL,
        INCIDENT_RESOLVED_TOTAL,
    )

    for metric in (
        INCIDENT_ALERTS_RECEIVED_TOTAL,
        INCIDENT_ALERTS_REJECTED_TOTAL,
        INCIDENT_CREATED_TOTAL,
        INCIDENT_DEDUPLICATED_TOTAL,
        INCIDENT_ACKNOWLEDGED_TOTAL,
        INCIDENT_RESOLVED_TOTAL,
        INCIDENT_CLOSED_TOTAL,
        INCIDENT_ESCALATION_DRY_RUN_TOTAL,
        INCIDENT_POSTMORTEM_REQUIRED_TOTAL,
    ):
        assert metric is not None


def test_metric_names_in_metrics_file():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "shared" / "sdk" / "observability" / "metrics.py").read_text(
        encoding="utf-8"
    )
    expected = [
        "incident_alerts_received_total",
        "incident_alerts_rejected_total",
        "incident_created_total",
        "incident_deduplicated_total",
        "incident_acknowledged_total",
        "incident_resolved_total",
        "incident_closed_total",
        "incident_escalation_dry_run_total",
        "incident_postmortem_required_total",
    ]
    for name in expected:
        assert name in src, f"missing metric: {name}"
