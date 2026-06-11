"""Stage 38 -- model registry seed + validation."""

from __future__ import annotations

from shared.sdk.llm_routing import (
    LLMModelEntry,
    MODEL_STATUS_ACTIVE,
    MODEL_STATUS_INACTIVE,
    default_models,
    validate_model_entry,
)


def test_default_seed_contains_mock_active():
    seed = default_models()
    aliases = {e["model_alias"] for e in seed}
    assert "mock-default" in aliases
    assert "mock-lightweight" in aliases
    by_alias = {e["model_alias"]: e for e in seed}
    assert by_alias["mock-default"]["status"] == MODEL_STATUS_ACTIVE
    assert by_alias["mock-default"]["plan_only_allowed"] is True


def test_real_providers_seeded_inactive():
    seed = {e["model_alias"]: e for e in default_models()}
    assert seed["openai-plan-only"]["status"] == MODEL_STATUS_INACTIVE
    assert seed["anthropic-plan-only"]["status"] == MODEL_STATUS_INACTIVE


def test_no_seed_entry_allows_patch_or_workspace_or_production():
    for entry in default_models():
        assert entry["patch_generation_allowed"] is False
        assert entry["workspace_write_allowed"] is False
        assert entry["production_use_allowed"] is False


def test_validate_blocks_patch_generation_flag():
    bad = dict(default_models()[0])
    bad["patch_generation_allowed"] = True
    problems = validate_model_entry(bad)
    assert "hard_safety:patch_generation_must_be_false" in problems


def test_validate_blocks_workspace_write_flag():
    bad = dict(default_models()[0])
    bad["workspace_write_allowed"] = True
    problems = validate_model_entry(bad)
    assert "hard_safety:workspace_write_must_be_false" in problems


def test_validate_blocks_production_use_flag():
    bad = dict(default_models()[0])
    bad["production_use_allowed"] = True
    problems = validate_model_entry(bad)
    assert "hard_safety:production_use_must_be_false" in problems


def test_validate_requires_basic_fields():
    bad = {"provider": "", "model_name": "", "model_alias": "", "model_tier": ""}
    problems = validate_model_entry(bad)
    assert "missing:provider" in problems
    assert "missing:model_alias" in problems


def test_llmmodelentry_to_safe_dict_carries_no_secret():
    entry = LLMModelEntry(
        model_id="00000000-0000-0000-0000-000000000001",
        provider="mock",
        model_name="mock-deterministic",
        model_alias="mock-default",
    )
    payload = entry.to_safe_dict()
    for forbidden in ("api_key", "openai_api_key", "anthropic_api_key", "token"):
        assert forbidden not in payload
