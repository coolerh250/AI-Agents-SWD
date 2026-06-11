"""Stage 38 -- LLM routing metrics are registered + incrementable."""

from __future__ import annotations


def test_routing_metrics_registered():
    from shared.sdk.observability import metrics

    for name in (
        "LLM_MODEL_ROUTING_REQUESTS_TOTAL",
        "LLM_MODEL_ROUTING_SELECTED_TOTAL",
        "LLM_MODEL_ROUTING_BLOCKED_TOTAL",
        "LLM_MODEL_ROUTING_FALLBACK_TOTAL",
        "LLM_MODEL_ROUTING_HUMAN_REVIEW_TOTAL",
        "LLM_MODEL_ROUTING_BUDGET_BLOCKED_TOTAL",
        "LLM_MODEL_POLICY_MISSING_TOTAL",
        "LLM_MODEL_DIRECT_SELECTION_REJECTED_TOTAL",
    ):
        assert hasattr(metrics, name), f"missing metric: {name}"


def test_routing_metrics_can_be_incremented():
    from shared.sdk.observability import metrics

    metrics.LLM_MODEL_ROUTING_REQUESTS_TOTAL.labels(
        agent_name="development-agent", capability="development_plan"
    ).inc()
    metrics.LLM_MODEL_ROUTING_SELECTED_TOTAL.labels(
        agent_name="development-agent",
        provider="mock",
        model_tier="tier_3_documentation_classification",
        decision="mock_selected",
    ).inc()
    metrics.LLM_MODEL_ROUTING_BLOCKED_TOTAL.labels(
        agent_name="development-agent", reason="policy_not_found"
    ).inc()
    metrics.LLM_MODEL_ROUTING_FALLBACK_TOTAL.labels(
        agent_name="qa-agent", model_tier="tier_2_development_qa"
    ).inc()
    metrics.LLM_MODEL_ROUTING_HUMAN_REVIEW_TOTAL.labels(
        agent_name="devops-agent", capability="delivery_risk_review"
    ).inc()
    metrics.LLM_MODEL_ROUTING_BUDGET_BLOCKED_TOTAL.labels(
        agent_name="development-agent", provider="external_openai"
    ).inc()
    metrics.LLM_MODEL_POLICY_MISSING_TOTAL.labels(
        agent_name="unknown-agent", capability="development_plan"
    ).inc()
    metrics.LLM_MODEL_DIRECT_SELECTION_REJECTED_TOTAL.labels(
        agent_name="development-agent", capability="development_plan"
    ).inc()


def test_routing_metric_labels_are_expected():
    from shared.sdk.observability import metrics

    assert metrics.LLM_MODEL_ROUTING_REQUESTS_TOTAL._labelnames == (
        "agent_name",
        "capability",
    )
    assert metrics.LLM_MODEL_ROUTING_SELECTED_TOTAL._labelnames == (
        "agent_name",
        "provider",
        "model_tier",
        "decision",
    )
    assert metrics.LLM_MODEL_ROUTING_BLOCKED_TOTAL._labelnames == (
        "agent_name",
        "reason",
    )
