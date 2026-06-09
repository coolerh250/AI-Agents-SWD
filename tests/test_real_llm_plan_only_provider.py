"""Stage 35 -- RealLLMPlanOnlyProvider tests.

The provider's wire path is exercised lightly: the goal is to pin the
hard guarantees (no patch, no test plan, guard-blocked path returns a
deterministic skipped plan, response parsing copes with both JSON and
free text). The real wire call is exercised by the manual verifier.
"""

from __future__ import annotations

import pytest

from shared.sdk.llm import (
    LLMProviderError,
    RealLLMPlanOnlyProvider,
)
from shared.sdk.llm.plan_only_provider import _parse_openai_plan, _parse_anthropic_plan


def test_provider_init_rejects_unknown_vendor():
    with pytest.raises(LLMProviderError):
        RealLLMPlanOnlyProvider(vendor="not-a-vendor")  # type: ignore[arg-type]


def test_provider_default_model_for_openai():
    p = RealLLMPlanOnlyProvider(vendor="openai", env={})
    assert p.name == "external_openai"
    assert p.model_name == "gpt-4o-mini"


def test_provider_default_model_for_anthropic():
    p = RealLLMPlanOnlyProvider(vendor="anthropic", env={})
    assert p.name == "external_anthropic"
    assert p.model_name == "claude-3-5-haiku"


def test_provider_refuses_generate_patch_proposal():
    p = RealLLMPlanOnlyProvider(vendor="openai", env={})
    with pytest.raises(LLMProviderError) as exc:
        p.generate_patch_proposal()
    assert "plan_only_provider_refuses_patch" in str(exc.value)


def test_provider_refuses_generate_test_plan():
    p = RealLLMPlanOnlyProvider(vendor="openai", env={})
    with pytest.raises(LLMProviderError) as exc:
        p.generate_test_plan()
    assert "plan_only_provider_refuses_test_plan" in str(exc.value)


def test_guard_blocked_returns_skipped_plan():
    p = RealLLMPlanOnlyProvider(vendor="openai", env={})
    # Default env has no real-LLM opt-in -> guard refuses.
    plan = p.generate_development_plan(
        task_id="T-1",
        prompt_contract={"interaction_type": "development_plan"},
        allow_real=True,
        env={},
    )
    assert plan.task_id == "T-1"
    assert "real_llm_test_skipped" in (plan.summary or "")
    assert plan.requires_human_review is True
    assert plan.confidence == 0.0


def test_guard_blocked_when_wrong_interaction_type():
    p = RealLLMPlanOnlyProvider(vendor="openai", env={})
    plan = p.generate_development_plan(
        task_id="T-2",
        prompt_contract={"interaction_type": "patch_proposal"},
        allow_real=True,
        env={
            "RUN_REAL_LLM_TEST": "true",
            "ENABLE_REAL_LLM_NETWORK_CALL": "true",
            "OPENAI_API_KEY": "sk-x",
        },
    )
    assert "interaction_type_not_plan" in (plan.summary or "")


def test_parse_openai_plan_json_response():
    plan = _parse_openai_plan(
        task_id="T-3",
        response_json={
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"summary":"do thing","files_to_consider":'
                            '["docs/a.md"],"proposed_steps":["s1"],'
                            '"assumptions":[],"questions":[],"risks":[],'
                            '"test_strategy":"unit","confidence":0.6}'
                        )
                    }
                }
            ]
        },
    )
    assert plan.summary.startswith("do thing")
    assert plan.files_to_consider == ["docs/a.md"]
    assert plan.proposed_steps == ["s1"]
    assert plan.test_strategy.startswith("unit")
    # requires_human_review remains True (forced by the dataclass).
    assert plan.requires_human_review is True


def test_parse_anthropic_plan_extracts_text_blocks():
    plan = _parse_anthropic_plan(
        task_id="T-4",
        response_json={
            "content": [
                {"type": "text", "text": '{"summary":"ok"}'},
            ]
        },
    )
    assert plan.summary == "ok"


def test_parse_plan_fallback_for_free_text():
    plan = _parse_openai_plan(
        task_id="T-5",
        response_json={"choices": [{"message": {"content": "not json text"}}]},
    )
    assert plan.summary == "not json text"
    assert "best_effort_parse" in plan.assumptions


def test_parse_plan_redacts_secret_in_response():
    plan = _parse_openai_plan(
        task_id="T-6",
        response_json={
            "choices": [
                {
                    "message": {
                        "content": ('{"summary":"please ssh with sk-FAKEFAKE0123456789abcdef"}')
                    }
                }
            ]
        },
    )
    # The redactor scrubs the token-shaped string from the preview.
    assert "sk-FAKEFAKE0123456789abcdef" not in plan.summary
