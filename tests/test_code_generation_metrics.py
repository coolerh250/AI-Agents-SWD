"""Stage 28 — code-generation Prometheus counter shape tests."""

from __future__ import annotations

from shared.sdk.observability.metrics import (
    CODE_GENERATION_ATTEMPTS_TOTAL,
    CODE_GENERATION_BLOCKED_TOTAL,
    CODE_GENERATION_SUCCESS_TOTAL,
    CODE_VALIDATION_FAILURES_TOTAL,
    CODE_WORKSPACES_TOTAL,
    PR_DRAFT_ARTIFACTS_TOTAL,
)


def _read(counter, **labels) -> float:
    sample = counter.labels(**labels)
    return float(sample._value.get())  # type: ignore[attr-defined]


def test_code_workspaces_counter_accepts_three_labels():
    before = _read(
        CODE_WORKSPACES_TOTAL,
        execution_mode="delivery_task",
        generator_mode="deterministic_template",
        status="created",
    )
    CODE_WORKSPACES_TOTAL.labels(
        execution_mode="delivery_task",
        generator_mode="deterministic_template",
        status="created",
    ).inc()
    after = _read(
        CODE_WORKSPACES_TOTAL,
        execution_mode="delivery_task",
        generator_mode="deterministic_template",
        status="created",
    )
    assert after == before + 1


def test_code_generation_attempts_counter_inc():
    before = _read(
        CODE_GENERATION_ATTEMPTS_TOTAL,
        execution_mode="delivery_task",
        generator_mode="deterministic_template",
    )
    CODE_GENERATION_ATTEMPTS_TOTAL.labels(
        execution_mode="delivery_task",
        generator_mode="deterministic_template",
    ).inc()
    after = _read(
        CODE_GENERATION_ATTEMPTS_TOTAL,
        execution_mode="delivery_task",
        generator_mode="deterministic_template",
    )
    assert after == before + 1


def test_code_generation_success_counter_includes_risk_level():
    before = _read(
        CODE_GENERATION_SUCCESS_TOTAL,
        execution_mode="delivery_task",
        generator_mode="deterministic_template",
        risk_level="low",
    )
    CODE_GENERATION_SUCCESS_TOTAL.labels(
        execution_mode="delivery_task",
        generator_mode="deterministic_template",
        risk_level="low",
    ).inc()
    after = _read(
        CODE_GENERATION_SUCCESS_TOTAL,
        execution_mode="delivery_task",
        generator_mode="deterministic_template",
        risk_level="low",
    )
    assert after == before + 1


def test_code_generation_blocked_counter_records_reason():
    before = _read(CODE_GENERATION_BLOCKED_TOTAL, reason="unclassifiable_description")
    CODE_GENERATION_BLOCKED_TOTAL.labels(reason="unclassifiable_description").inc()
    after = _read(CODE_GENERATION_BLOCKED_TOTAL, reason="unclassifiable_description")
    assert after == before + 1


def test_validation_failures_counter_by_check():
    before = _read(CODE_VALIDATION_FAILURES_TOTAL, check="py_compile")
    CODE_VALIDATION_FAILURES_TOTAL.labels(check="py_compile").inc()
    after = _read(CODE_VALIDATION_FAILURES_TOTAL, check="py_compile")
    assert after == before + 1


def test_pr_draft_artifacts_counter_records_status_and_risk():
    before = _read(
        PR_DRAFT_ARTIFACTS_TOTAL,
        execution_mode="delivery_task",
        status="ready",
        risk_level="low",
    )
    PR_DRAFT_ARTIFACTS_TOTAL.labels(
        execution_mode="delivery_task",
        status="ready",
        risk_level="low",
    ).inc()
    after = _read(
        PR_DRAFT_ARTIFACTS_TOTAL,
        execution_mode="delivery_task",
        status="ready",
        risk_level="low",
    )
    assert after == before + 1
