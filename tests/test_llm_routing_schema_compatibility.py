"""Stage 38 -- schema compatibility checks."""

from __future__ import annotations

from shared.sdk.llm_routing import LLMModelEntry, schema_supported


def test_no_schema_is_treated_as_no_constraint():
    entry = LLMModelEntry(
        model_id="x",
        provider="mock",
        model_name="mock-deterministic",
        model_alias="mock-default",
        supported_schemas=["LLMDevelopmentPlan"],
    )
    assert schema_supported(entry, None) is True
    assert schema_supported(entry, "") is True


def test_schema_match_returns_true():
    entry = LLMModelEntry(
        model_id="x",
        provider="mock",
        model_name="mock-deterministic",
        model_alias="mock-default",
        supported_schemas=["LLMDevelopmentPlan", "QAReviewReport"],
    )
    assert schema_supported(entry, "LLMDevelopmentPlan") is True
    assert schema_supported(entry, "QAReviewReport") is True


def test_schema_miss_returns_false():
    entry = LLMModelEntry(
        model_id="x",
        provider="mock",
        model_name="mock-deterministic",
        model_alias="mock-default",
        supported_schemas=["LLMDevelopmentPlan"],
    )
    assert schema_supported(entry, "OtherSchema") is False


def test_empty_supported_schemas_means_any_explicit_schema_fails():
    entry = LLMModelEntry(
        model_id="x",
        provider="mock",
        model_name="mock-deterministic",
        model_alias="mock-default",
    )
    assert schema_supported(entry, None) is True
    assert schema_supported(entry, "LLMDevelopmentPlan") is False
