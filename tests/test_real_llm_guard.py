"""Stage 35 -- real-LLM plan-only guard tests."""

from __future__ import annotations

from shared.sdk.llm import real_llm_plan_only_guard


def _env(**kv):
    return dict(kv)


def test_guard_blocks_when_interaction_type_not_plan():
    allowed, reason = real_llm_plan_only_guard(
        provider_name="external_openai",
        allow_real=True,
        interaction_type="patch_proposal",
        env=_env(
            RUN_REAL_LLM_TEST="true",
            ENABLE_REAL_LLM_NETWORK_CALL="true",
            OPENAI_API_KEY="x",
        ),
    )
    assert allowed is False
    assert reason == "interaction_type_not_plan"


def test_guard_blocks_when_allow_real_false():
    allowed, reason = real_llm_plan_only_guard(
        provider_name="external_openai",
        allow_real=False,
        interaction_type="development_plan",
        env=_env(),
    )
    assert allowed is False
    assert reason == "allow_real_false"


def test_guard_blocks_when_provider_not_real():
    allowed, reason = real_llm_plan_only_guard(
        provider_name="mock",
        allow_real=True,
        interaction_type="development_plan",
        env=_env(),
    )
    assert allowed is False
    assert reason == "provider_not_real_plan_only"


def test_guard_blocks_when_run_real_llm_test_false():
    allowed, reason = real_llm_plan_only_guard(
        provider_name="external_openai",
        allow_real=True,
        interaction_type="development_plan",
        env=_env(),
    )
    assert allowed is False
    assert reason == "run_real_llm_test_false"


def test_guard_blocks_when_network_call_disabled():
    allowed, reason = real_llm_plan_only_guard(
        provider_name="external_openai",
        allow_real=True,
        interaction_type="development_plan",
        env=_env(RUN_REAL_LLM_TEST="true"),
    )
    assert allowed is False
    assert reason == "network_call_disabled"


def test_guard_blocks_when_api_key_missing():
    allowed, reason = real_llm_plan_only_guard(
        provider_name="external_openai",
        allow_real=True,
        interaction_type="development_plan",
        env=_env(
            RUN_REAL_LLM_TEST="true",
            ENABLE_REAL_LLM_NETWORK_CALL="true",
        ),
    )
    assert allowed is False
    assert reason == "api_key_missing"


def test_guard_passes_when_all_env_present_openai():
    allowed, reason = real_llm_plan_only_guard(
        provider_name="external_openai",
        allow_real=True,
        interaction_type="development_plan",
        env=_env(
            RUN_REAL_LLM_TEST="true",
            ENABLE_REAL_LLM_NETWORK_CALL="true",
            OPENAI_API_KEY="sk-test",
        ),
    )
    assert allowed is True
    assert reason == "ok"


def test_guard_passes_when_all_env_present_anthropic():
    allowed, reason = real_llm_plan_only_guard(
        provider_name="external_anthropic",
        allow_real=True,
        interaction_type="development_plan",
        env=_env(
            RUN_REAL_LLM_TEST="true",
            ENABLE_REAL_LLM_NETWORK_CALL="true",
            ANTHROPIC_API_KEY="sk-ant-x",
        ),
    )
    assert allowed is True
    assert reason == "ok"


def test_guard_does_not_echo_key_value():
    allowed, reason = real_llm_plan_only_guard(
        provider_name="external_openai",
        allow_real=True,
        interaction_type="development_plan",
        env=_env(
            RUN_REAL_LLM_TEST="true",
            ENABLE_REAL_LLM_NETWORK_CALL="true",
            OPENAI_API_KEY="sk-DOLPHINS-SECRET-VALUE",
        ),
    )
    assert allowed is True
    # The reason string should never carry the key value.
    assert "DOLPHINS" not in reason
