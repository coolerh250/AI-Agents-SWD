"""Stage 38 -- default model registry seed.

The default registry is deliberately conservative: only the
``mock`` and ``mock-deterministic`` family is ``status=active`` and
``plan_only_allowed=true``. Real external models
(``external_openai`` / ``external_anthropic``) are seeded as
``status=inactive`` so the router refuses to use them unless an
operator explicitly activates them.

No entry has ``patch_generation_allowed=true`` or
``workspace_write_allowed=true`` or ``production_use_allowed=true``.
The hard safety rails persist even if an operator flips a registry
flag -- the router consults Stage 30 + Stage 35 guards on top.
"""

from __future__ import annotations

from typing import Any

from .models import (
    LLMModelEntry,
    MODEL_STATUS_ACTIVE,
    MODEL_STATUS_INACTIVE,
    MODEL_TIER_DEVELOPMENT_QA,
    MODEL_TIER_DOCUMENTATION,
    MODEL_TIER_LIGHTWEIGHT,
)

# Standard capability vocabulary referenced by the agent policies.
CAPABILITY_CLASSIFICATION = "classification"
CAPABILITY_SUMMARIZATION = "summarization"
CAPABILITY_REQUIREMENT_ANALYSIS = "requirement_analysis"
CAPABILITY_CLARIFICATION_QUESTION = "clarification_question"
CAPABILITY_DEVELOPMENT_PLAN = "development_plan"
CAPABILITY_TEST_PLAN = "test_plan"
CAPABILITY_QA_REVIEW = "qa_review"
CAPABILITY_POLICY_REVIEW = "policy_review"
CAPABILITY_DOCUMENTATION = "documentation"
CAPABILITY_DELIVERY_RISK_REVIEW = "delivery_risk_review"
CAPABILITY_ROLLBACK_PLAN = "rollback_plan"
CAPABILITY_CODE_PATCH_PROPOSAL = "code_patch_proposal"
CAPABILITY_EMBEDDING = "embedding"

ALL_CAPABILITIES: tuple[str, ...] = (
    CAPABILITY_CLASSIFICATION,
    CAPABILITY_SUMMARIZATION,
    CAPABILITY_REQUIREMENT_ANALYSIS,
    CAPABILITY_CLARIFICATION_QUESTION,
    CAPABILITY_DEVELOPMENT_PLAN,
    CAPABILITY_TEST_PLAN,
    CAPABILITY_QA_REVIEW,
    CAPABILITY_POLICY_REVIEW,
    CAPABILITY_DOCUMENTATION,
    CAPABILITY_DELIVERY_RISK_REVIEW,
    CAPABILITY_ROLLBACK_PLAN,
    CAPABILITY_CODE_PATCH_PROPOSAL,
    CAPABILITY_EMBEDDING,
)

# Schema names referenced by the Stage 30 prompt contract + tests.
SCHEMA_DEVELOPMENT_PLAN = "LLMDevelopmentPlan"
SCHEMA_PATCH_PROPOSAL = "LLMPatchProposal"
SCHEMA_TEST_PLAN = "LLMTestPlan"
SCHEMA_REQUIREMENT_ANALYSIS = "RequirementAnalysis"
SCHEMA_CLASSIFICATION = "ClassificationResult"
SCHEMA_QA_REVIEW = "QAReviewReport"
SCHEMA_DOCUMENTATION = "DocumentationDraft"
SCHEMA_DELIVERY_RISK = "DeliveryRiskReport"


def _entry(
    *,
    provider: str,
    model_name: str,
    model_alias: str,
    model_tier: str,
    capabilities: list[str],
    supported_schemas: list[str],
    status: str,
    plan_only_allowed: bool,
    cost_input: float = 0.0,
    cost_output: float = 0.0,
    risk_level: str = "low",
    requires_human_review: bool = True,
    max_context_tokens: int | None = None,
    default_max_output_tokens: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "model_name": model_name,
        "model_alias": model_alias,
        "model_tier": model_tier,
        "capabilities": list(capabilities),
        "supported_schemas": list(supported_schemas),
        "max_context_tokens": max_context_tokens,
        "default_max_output_tokens": default_max_output_tokens,
        "cost_per_1k_input_tokens": cost_input,
        "cost_per_1k_output_tokens": cost_output,
        "latency_class": "fast" if model_tier == MODEL_TIER_LIGHTWEIGHT else "standard",
        "risk_level": risk_level,
        "status": status,
        "plan_only_allowed": bool(plan_only_allowed),
        # Hard-off. Stage 38 NEVER ships a model entry that flips
        # these to true. The router still consults Stage 30 + 35
        # guards on top of the registry.
        "patch_generation_allowed": False,
        "workspace_write_allowed": False,
        "production_use_allowed": False,
        "requires_human_review": bool(requires_human_review),
        "metadata": dict(metadata or {}),
    }


#: Deterministic seed loaded by the migration / runtime smoke. Only
#: the mock family is active; real providers are seeded inactive.
DEFAULT_MODEL_SEED: tuple[dict[str, Any], ...] = (
    _entry(
        provider="mock",
        model_name="mock-deterministic",
        model_alias="mock-default",
        model_tier=MODEL_TIER_DOCUMENTATION,
        capabilities=list(ALL_CAPABILITIES),
        supported_schemas=[
            SCHEMA_DEVELOPMENT_PLAN,
            SCHEMA_PATCH_PROPOSAL,
            SCHEMA_TEST_PLAN,
            SCHEMA_REQUIREMENT_ANALYSIS,
            SCHEMA_CLASSIFICATION,
            SCHEMA_QA_REVIEW,
            SCHEMA_DOCUMENTATION,
            SCHEMA_DELIVERY_RISK,
        ],
        status=MODEL_STATUS_ACTIVE,
        plan_only_allowed=True,
        requires_human_review=False,
        max_context_tokens=8192,
        default_max_output_tokens=1024,
        metadata={"note": "deterministic in-process generator; zero cost"},
    ),
    _entry(
        provider="mock",
        model_name="mock-lightweight",
        model_alias="mock-lightweight",
        model_tier=MODEL_TIER_LIGHTWEIGHT,
        capabilities=[
            CAPABILITY_CLASSIFICATION,
            CAPABILITY_SUMMARIZATION,
            CAPABILITY_EMBEDDING,
        ],
        supported_schemas=[SCHEMA_CLASSIFICATION],
        status=MODEL_STATUS_ACTIVE,
        plan_only_allowed=True,
        requires_human_review=False,
        max_context_tokens=4096,
        default_max_output_tokens=512,
        metadata={"note": "intake-agent / lightweight classification fallback"},
    ),
    _entry(
        provider="external_openai",
        model_name="gpt-4o-mini",
        model_alias="openai-plan-only",
        model_tier=MODEL_TIER_DEVELOPMENT_QA,
        capabilities=[
            CAPABILITY_DEVELOPMENT_PLAN,
            CAPABILITY_REQUIREMENT_ANALYSIS,
            CAPABILITY_QA_REVIEW,
            CAPABILITY_DOCUMENTATION,
        ],
        supported_schemas=[
            SCHEMA_DEVELOPMENT_PLAN,
            SCHEMA_REQUIREMENT_ANALYSIS,
            SCHEMA_QA_REVIEW,
        ],
        status=MODEL_STATUS_INACTIVE,
        plan_only_allowed=True,
        requires_human_review=True,
        cost_input=0.00015,
        cost_output=0.0006,
        risk_level="medium",
        max_context_tokens=128_000,
        default_max_output_tokens=2048,
        metadata={"note": "Stage 35 plan-only pilot; inactive by default"},
    ),
    _entry(
        provider="external_anthropic",
        model_name="claude-3-5-haiku",
        model_alias="anthropic-plan-only",
        model_tier=MODEL_TIER_DEVELOPMENT_QA,
        capabilities=[
            CAPABILITY_DEVELOPMENT_PLAN,
            CAPABILITY_REQUIREMENT_ANALYSIS,
            CAPABILITY_QA_REVIEW,
            CAPABILITY_DOCUMENTATION,
        ],
        supported_schemas=[
            SCHEMA_DEVELOPMENT_PLAN,
            SCHEMA_REQUIREMENT_ANALYSIS,
            SCHEMA_QA_REVIEW,
        ],
        status=MODEL_STATUS_INACTIVE,
        plan_only_allowed=True,
        requires_human_review=True,
        cost_input=0.0008,
        cost_output=0.004,
        risk_level="medium",
        max_context_tokens=200_000,
        default_max_output_tokens=2048,
        metadata={"note": "Stage 35 plan-only pilot; inactive by default"},
    ),
)


def default_models() -> tuple[dict[str, Any], ...]:
    """Return the default seed; copy so callers cannot mutate the constant."""

    return tuple(
        dict(
            m,
            capabilities=list(m["capabilities"]),
            supported_schemas=list(m["supported_schemas"]),
            metadata=dict(m["metadata"]),
        )
        for m in DEFAULT_MODEL_SEED
    )


def validate_model_entry(entry: dict[str, Any] | LLMModelEntry) -> list[str]:
    """Return human-readable validation problems (empty when valid)."""

    if isinstance(entry, LLMModelEntry):
        data = entry.to_safe_dict()
    else:
        data = dict(entry)
    problems: list[str] = []
    for required in ("provider", "model_name", "model_alias", "model_tier"):
        if not data.get(required):
            problems.append(f"missing:{required}")
    if data.get("patch_generation_allowed") is True:
        problems.append("hard_safety:patch_generation_must_be_false")
    if data.get("workspace_write_allowed") is True:
        problems.append("hard_safety:workspace_write_must_be_false")
    if data.get("production_use_allowed") is True:
        problems.append("hard_safety:production_use_must_be_false")
    return problems
