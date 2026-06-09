"""Stage 35 -- LLM cost governance Prometheus counters."""

from __future__ import annotations

from shared.sdk.observability import metrics as m


def test_stage35_counters_exist():
    assert hasattr(m, "LLM_BUDGET_PREFLIGHT_TOTAL")
    assert hasattr(m, "LLM_BUDGET_ALLOWED_TOTAL")
    assert hasattr(m, "LLM_BUDGET_BLOCKED_TOTAL")
    assert hasattr(m, "LLM_REAL_PLAN_CALLS_TOTAL")
    assert hasattr(m, "LLM_REAL_PLAN_BLOCKED_TOTAL")
    assert hasattr(m, "LLM_COST_USD_TOTAL")
    assert hasattr(m, "LLM_TOKENS_TOTAL")


def test_counter_labels():
    assert m.LLM_BUDGET_PREFLIGHT_TOTAL._labelnames == (
        "provider",
        "decision",
        "reason",
    )
    assert m.LLM_BUDGET_ALLOWED_TOTAL._labelnames == ("provider", "model")
    assert m.LLM_BUDGET_BLOCKED_TOTAL._labelnames == ("provider", "reason")
    assert m.LLM_REAL_PLAN_CALLS_TOTAL._labelnames == (
        "provider",
        "model",
        "result",
    )
    assert m.LLM_REAL_PLAN_BLOCKED_TOTAL._labelnames == ("provider", "reason")
    assert m.LLM_COST_USD_TOTAL._labelnames == ("provider", "model")
    assert m.LLM_TOKENS_TOTAL._labelnames == ("provider", "model", "kind")


def test_counters_increment_without_error():
    m.LLM_BUDGET_PREFLIGHT_TOTAL.labels(
        provider="external_openai", decision="allowed", reason="none"
    ).inc()
    m.LLM_BUDGET_ALLOWED_TOTAL.labels(provider="external_openai", model="gpt-4o-mini").inc()
    m.LLM_BUDGET_BLOCKED_TOTAL.labels(provider="external_openai", reason="cost_per_task").inc()
    m.LLM_REAL_PLAN_CALLS_TOTAL.labels(
        provider="external_openai", model="gpt-4o-mini", result="success"
    ).inc()
    m.LLM_REAL_PLAN_BLOCKED_TOTAL.labels(provider="external_openai", reason="budget").inc()
    m.LLM_COST_USD_TOTAL.labels(provider="mock", model="mock-deterministic").inc(0.0)
    m.LLM_TOKENS_TOTAL.labels(provider="external_openai", model="gpt-4o-mini", kind="total").inc(
        123
    )
