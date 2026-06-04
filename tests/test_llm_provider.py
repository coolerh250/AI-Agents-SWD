"""Stage 30 — LLM provider abstraction tests."""

from __future__ import annotations


import pytest

from shared.sdk.llm import (
    ALLOWED_PROVIDERS,
    DEFAULT_PROVIDER,
    DisabledLLMProvider,
    ExternalLLMProviderGuard,
    MockLLMProvider,
    get_provider,
    real_llm_guard,
)
from shared.sdk.llm.provider import LLMProviderError


def test_default_provider_is_mock() -> None:
    assert DEFAULT_PROVIDER == "mock"
    assert "mock" in ALLOWED_PROVIDERS
    assert "disabled" in ALLOWED_PROVIDERS


def test_mock_provider_deterministic_development_plan() -> None:
    p = MockLLMProvider()
    a = p.generate_development_plan(task_id="t-x", description="please add /healthz API")
    b = p.generate_development_plan(task_id="t-x", description="please add /healthz API")
    assert a.task_id == b.task_id
    assert a.summary == b.summary
    assert a.files_to_consider == b.files_to_consider
    assert a.requires_human_review is True
    assert b.requires_human_review is True


def test_mock_provider_deterministic_patch_proposal() -> None:
    p = MockLLMProvider()
    a = p.generate_patch_proposal(task_id="t-x", description="please add /healthz API")
    b = p.generate_patch_proposal(task_id="t-x", description="please add /healthz API")
    assert a.patch_id == b.patch_id
    assert len(a.changes) == len(b.changes)
    for ca, cb in zip(a.changes, b.changes):
        assert ca.file_path == cb.file_path
        assert ca.change_type == cb.change_type
    assert a.requires_human_review is True


def test_disabled_provider_refuses_all_calls() -> None:
    p = DisabledLLMProvider()
    with pytest.raises(LLMProviderError):
        p.generate_development_plan(task_id="t-y")
    with pytest.raises(LLMProviderError):
        p.generate_patch_proposal(task_id="t-y")
    with pytest.raises(LLMProviderError):
        p.generate_test_plan(task_id="t-y")


def test_external_openai_guard_blocks_by_default() -> None:
    g = ExternalLLMProviderGuard("openai")
    # Even though we don't set allow_real=True, the guard must
    # gracefully return a non-network mock-shaped response with
    # requires_human_review=True.
    plan = g.generate_development_plan(task_id="t-y", description="please add api")
    assert plan.requires_human_review is True
    assert plan.confidence <= 0.4
    assert any("real_call_skipped" in a for a in plan.assumptions)


def test_external_anthropic_guard_skips_real_call() -> None:
    g = ExternalLLMProviderGuard("anthropic")
    proposal = g.generate_patch_proposal(task_id="t-z", description="please add api")
    assert proposal.requires_human_review is True
    assert "real_call_skipped" in proposal.safety_notes


def test_get_provider_factory_mock() -> None:
    assert get_provider("mock").name == "mock"


def test_get_provider_factory_disabled() -> None:
    assert get_provider("disabled").name == "disabled"


def test_get_provider_factory_external_placeholder() -> None:
    p = get_provider("external_openai_placeholder")
    assert p.name == "external_openai_placeholder"


def test_get_provider_unknown_falls_back_to_disabled() -> None:
    p = get_provider("does-not-exist-xyz")
    assert p.name == "disabled"


def test_real_llm_guard_blocks_when_allow_real_false() -> None:
    allowed, reason = real_llm_guard(provider_name="mock", allow_real=False, env={})
    assert allowed is False
    assert reason == "allow_real_false"


def test_real_llm_guard_blocks_when_run_real_false() -> None:
    allowed, reason = real_llm_guard(
        provider_name="external_openai_placeholder",
        allow_real=True,
        env={"RUN_REAL_LLM_TEST": "false"},
    )
    assert allowed is False
    assert reason == "run_real_llm_test_false"


def test_real_llm_guard_blocks_when_network_disabled() -> None:
    allowed, reason = real_llm_guard(
        provider_name="external_openai_placeholder",
        allow_real=True,
        env={"RUN_REAL_LLM_TEST": "true"},
    )
    assert allowed is False
    assert reason == "network_call_disabled"


def test_real_llm_guard_blocks_when_api_key_missing() -> None:
    allowed, reason = real_llm_guard(
        provider_name="external_openai_placeholder",
        allow_real=True,
        env={
            "RUN_REAL_LLM_TEST": "true",
            "ENABLE_REAL_LLM_NETWORK_CALL": "true",
        },
    )
    assert allowed is False
    assert reason == "api_key_missing"


def test_real_llm_guard_passes_when_all_set() -> None:
    allowed, reason = real_llm_guard(
        provider_name="external_openai_placeholder",
        allow_real=True,
        env={
            "RUN_REAL_LLM_TEST": "true",
            "ENABLE_REAL_LLM_NETWORK_CALL": "true",
            "OPENAI_API_KEY": "stub-not-real",
        },
    )
    # Guard returns True only when all three rails align; the
    # provider itself still refuses to dial the network in Stage 30.
    assert allowed is True


def test_mock_provider_policy_trip_outputs_violating_change() -> None:
    """When the description carries the trip-word, the mock emits a
    proposal whose changes will be refused by the safety policy."""
    p = MockLLMProvider()
    prop = p.generate_patch_proposal(task_id="trip", description="please denied path")
    assert prop.changes
    # The trip-target lives under infra/* which the denylist refuses.
    assert "infra/" in prop.changes[0].file_path


def test_real_llm_test_skipped_default_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env vars set ⇒ default skipped path."""
    for key in (
        "RUN_REAL_LLM_TEST",
        "ENABLE_REAL_LLM_NETWORK_CALL",
        "LLM_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    allowed, reason = real_llm_guard(provider_name="mock", allow_real=True)
    assert allowed is False
    assert reason == "run_real_llm_test_false"


def test_provider_never_leaks_api_key_in_response() -> None:
    """The mock provider must never echo an API key value, even when
    a key-shaped string sneaks into the description."""
    p = MockLLMProvider()
    descr = "please add API key OPENAI_API_KEY=sk-" + ("A" * 40)
    plan = p.generate_development_plan(task_id="leak", description=descr)
    flat = " ".join([plan.summary, plan.test_strategy, *plan.assumptions, *plan.questions])
    assert "sk-" + ("A" * 40) not in flat
