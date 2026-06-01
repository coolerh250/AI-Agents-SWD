"""Stage 27 — Prometheus counters for the flexible task execution loop."""

from __future__ import annotations

from shared.sdk.observability.metrics import (
    AGENT_DISCUSSIONS_TOTAL,
    CLARIFICATION_REQUESTS_TOTAL,
    TASK_BLOCKED_TOTAL,
    TASK_EXECUTION_MODE_TOTAL,
    TASK_READY_FOR_DEVELOPMENT_TOTAL,
    TASK_WORK_ITEMS_TOTAL,
    metrics_response,
)


def test_metrics_export_carries_new_counters():
    # Trigger one observation per counter so the Prometheus exposition
    # has a sample line — without that, .name/.help is rendered but
    # the body may be empty.
    TASK_WORK_ITEMS_TOTAL.labels(execution_mode="simple_task", status="intake_received").inc()
    TASK_EXECUTION_MODE_TOTAL.labels(execution_mode="delivery_task", request_type="dev.test").inc()
    CLARIFICATION_REQUESTS_TOTAL.labels(status="requested").inc()
    TASK_READY_FOR_DEVELOPMENT_TOTAL.labels(execution_mode="delivery_task").inc()
    TASK_BLOCKED_TOTAL.labels(reason="manual").inc()
    AGENT_DISCUSSIONS_TOTAL.labels(agent="requirement-agent", message_type="analysis").inc()

    body, content_type = metrics_response()
    text = body.decode()
    assert "text/plain" in content_type
    for series in (
        "task_work_items_total",
        "task_execution_mode_total",
        "clarification_requests_total",
        "task_ready_for_development_total",
        "task_blocked_total",
        "agent_discussions_total",
    ):
        assert series in text, f"missing series: {series}"


def test_labels_match_spec():
    # Sanity: the label sets pinned in the spec must be the ones the
    # counters actually accept.
    TASK_WORK_ITEMS_TOTAL.labels(execution_mode="x", status="y").inc()
    TASK_EXECUTION_MODE_TOTAL.labels(execution_mode="x", request_type="y").inc()
    CLARIFICATION_REQUESTS_TOTAL.labels(status="x").inc()
    TASK_READY_FOR_DEVELOPMENT_TOTAL.labels(execution_mode="x").inc()
    TASK_BLOCKED_TOTAL.labels(reason="x").inc()
    AGENT_DISCUSSIONS_TOTAL.labels(agent="x", message_type="y").inc()
