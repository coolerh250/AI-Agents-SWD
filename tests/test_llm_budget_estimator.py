"""Stage 35 -- LLM cost estimator tests (pure)."""

from __future__ import annotations

import pytest

from shared.sdk.llm_budget import DEFAULT_PRICING, LLMCostEstimator, estimate_tokens


def test_estimate_tokens_simple():
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0
    # 8 chars -> ceil(8/4)=2 tokens
    assert estimate_tokens("12345678") == 2
    # 9 chars -> ceil(9/4)=3 tokens
    assert estimate_tokens("123456789") == 3


def test_mock_provider_zero_cost():
    e = LLMCostEstimator()
    out = e.estimate_cost(
        provider="mock",
        model_name="mock-deterministic",
        prompt_tokens=10_000,
        completion_tokens=10_000,
    )
    assert out["cost_usd"] == 0.0
    assert out["prompt_cost_usd"] == 0.0
    assert out["completion_cost_usd"] == 0.0
    assert out["model_known"] is True


def test_openai_known_model_pricing():
    e = LLMCostEstimator()
    out = e.estimate_cost(
        provider="external_openai",
        model_name="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=1000,
    )
    expected = 0.00015 + 0.0006
    assert abs(out["cost_usd"] - expected) < 1e-6
    assert out["fallback_used"] is False
    assert out["model_known"] is True


def test_anthropic_known_model_pricing():
    e = LLMCostEstimator()
    out = e.estimate_cost(
        provider="external_anthropic",
        model_name="claude-3-5-haiku",
        prompt_tokens=1000,
        completion_tokens=1000,
    )
    expected = 0.0008 + 0.004
    assert abs(out["cost_usd"] - expected) < 1e-6
    assert out["fallback_used"] is False


def test_unknown_model_uses_most_expensive_fallback():
    e = LLMCostEstimator()
    out = e.estimate_cost(
        provider="external_openai",
        model_name="totally-made-up-model",
        prompt_tokens=1000,
        completion_tokens=1000,
    )
    expected = 0.01 + 0.03  # gpt-4-turbo is the priciest in the OpenAI table
    assert abs(out["cost_usd"] - expected) < 1e-6
    assert out["fallback_used"] is True
    assert out["model_known"] is False
    assert out["model_name"] == "gpt-4-turbo"


def test_unknown_provider_raises():
    e = LLMCostEstimator()
    with pytest.raises(ValueError) as exc:
        e.estimate_cost(
            provider="external_madeup",
            model_name="x",
            prompt_tokens=10,
            completion_tokens=10,
        )
    assert "unknown_provider" in str(exc.value)


def test_supported_providers_lists_external_openai_and_anthropic():
    e = LLMCostEstimator()
    providers = e.supported_providers()
    assert "external_openai" in providers
    assert "external_anthropic" in providers
    assert "mock" in providers


def test_default_pricing_has_no_zero_external_entries():
    # An external pricing entry of $0 would silently bypass the
    # budget gate. Pin that this never happens.
    for provider in ("external_openai", "external_anthropic"):
        for model, entry in DEFAULT_PRICING[provider].items():
            assert entry["prompt"] > 0, f"prompt zero for {provider}/{model}"
            assert entry["completion"] > 0, f"completion zero for {provider}/{model}"
