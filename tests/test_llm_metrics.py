"""Stage 30 — LLM metrics counters."""

from __future__ import annotations

from shared.sdk.observability import metrics as M


def test_llm_metrics_defined() -> None:
    """Every Stage 30 metric must exist on the metrics module."""
    for name in (
        "LLM_INTERACTIONS_TOTAL",
        "LLM_PROPOSALS_TOTAL",
        "LLM_POLICY_BLOCKS_TOTAL",
        "LLM_REAL_CALLS_TOTAL",
        "LLM_REAL_CALLS_BLOCKED_TOTAL",
        "LLM_TOKEN_USAGE_TOTAL",
        "LLM_ESTIMATED_COST_TOTAL",
    ):
        assert hasattr(M, name), name


def test_llm_interactions_total_accepts_labels() -> None:
    counter = M.LLM_INTERACTIONS_TOTAL.labels(
        provider="mock",
        model="mock-deterministic",
        interaction_type="development_plan",
        status="ok",
    )
    counter.inc()


def test_llm_proposals_total_accepts_labels() -> None:
    M.LLM_PROPOSALS_TOTAL.labels(
        provider="mock", proposal_type="patch_proposal", status="policy_passed"
    ).inc()


def test_llm_policy_blocks_total_accepts_rule_label() -> None:
    M.LLM_POLICY_BLOCKS_TOTAL.labels(rule="path_blocked").inc()


def test_llm_real_calls_labels_total() -> None:
    M.LLM_REAL_CALLS_TOTAL.labels(provider="external_openai_placeholder", result="skipped").inc()
    M.LLM_REAL_CALLS_BLOCKED_TOTAL.labels(
        provider="external_openai_placeholder", reason="network_call_disabled"
    ).inc()


def test_metrics_endpoint_text_includes_llm_counters() -> None:
    body, _ct = M.metrics_response()
    text = body.decode("utf-8")
    # The /metrics text exposition format names match the variable
    # names lowercased + sufffixed. Spot-check one.
    assert "llm_interactions_total" in text
    assert "llm_proposals_total" in text
    assert "llm_policy_blocks_total" in text
