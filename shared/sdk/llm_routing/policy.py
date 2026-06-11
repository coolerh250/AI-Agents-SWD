"""Stage 38 -- default agent model policies.

Default-deny: when the router cannot find an active policy for
(agent, task_type, capability, risk_level), it returns
``DECISION_POLICY_NOT_FOUND``. The seed below covers the five
pipeline agents (intake / requirement / development / qa / devops)
across the capability vocabulary defined in :mod:`registry`.

Every seeded policy:
* refuses real LLM (``allow_real_llm=False``) unless explicitly
  activated by an operator.
* refuses patch generation (``allow_patch_generation=False``).
* refuses workspace write (``allow_workspace_write=False``).
* requires human review on high / critical risk.

These flags are independent of the model registry; the router
intersects both.
"""

from __future__ import annotations

from typing import Any

from .models import (
    AGENT_DEFAULT_TASK_TYPE,
    MODEL_TIER_DEVELOPMENT_QA,
    MODEL_TIER_DOCUMENTATION,
    MODEL_TIER_LIGHTWEIGHT,
)
from .registry import (
    CAPABILITY_CLARIFICATION_QUESTION,
    CAPABILITY_CLASSIFICATION,
    CAPABILITY_DELIVERY_RISK_REVIEW,
    CAPABILITY_DEVELOPMENT_PLAN,
    CAPABILITY_DOCUMENTATION,
    CAPABILITY_QA_REVIEW,
    CAPABILITY_REQUIREMENT_ANALYSIS,
    CAPABILITY_ROLLBACK_PLAN,
    CAPABILITY_SUMMARIZATION,
    CAPABILITY_TEST_PLAN,
)


def _policy(
    *,
    agent_name: str,
    capability: str,
    risk_level: str = "low",
    task_type: str = AGENT_DEFAULT_TASK_TYPE,
    preferred_model_alias: str | None = "mock-default",
    allowed_tiers: list[str] | None = None,
    allowed_providers: list[str] | None = None,
    fallback_aliases: list[str] | None = None,
    max_cost: float | None = 0.05,
    max_tokens: int | None = 8000,
    requires_human_review: bool = False,
    allow_real_llm: bool = False,
    allow_patch_generation: bool = False,
    allow_workspace_write: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "agent_name": agent_name,
        "task_type": task_type,
        "capability": capability,
        "risk_level": risk_level,
        "preferred_model_alias": preferred_model_alias,
        "allowed_model_tiers": list(allowed_tiers or [MODEL_TIER_DOCUMENTATION]),
        "allowed_providers": list(allowed_providers or ["mock"]),
        "fallback_model_aliases": list(fallback_aliases or ["mock-lightweight"]),
        "max_cost_per_task_usd": max_cost,
        "max_tokens_per_task": max_tokens,
        "requires_human_review": bool(requires_human_review),
        "allow_real_llm": bool(allow_real_llm),
        "allow_patch_generation": bool(allow_patch_generation),
        "allow_workspace_write": bool(allow_workspace_write),
        "status": "active",
        "created_by": "system",
        "metadata": {"notes": notes} if notes else {},
    }


DEFAULT_AGENT_POLICY_SEED: tuple[dict[str, Any], ...] = (
    # intake-agent: classification / summarization (low cost, low risk).
    _policy(
        agent_name="intake-agent",
        capability=CAPABILITY_CLASSIFICATION,
        allowed_tiers=[MODEL_TIER_LIGHTWEIGHT, MODEL_TIER_DOCUMENTATION],
        preferred_model_alias="mock-lightweight",
        fallback_aliases=["mock-default"],
        max_cost=0.01,
        max_tokens=2000,
        notes="default-deny shape; mock-only by default",
    ),
    _policy(
        agent_name="intake-agent",
        capability=CAPABILITY_SUMMARIZATION,
        allowed_tiers=[MODEL_TIER_LIGHTWEIGHT, MODEL_TIER_DOCUMENTATION],
        preferred_model_alias="mock-lightweight",
        fallback_aliases=["mock-default"],
        max_cost=0.02,
        max_tokens=3000,
    ),
    # requirement-agent: requirement_analysis + clarification.
    _policy(
        agent_name="requirement-agent",
        capability=CAPABILITY_REQUIREMENT_ANALYSIS,
        allowed_tiers=[MODEL_TIER_DOCUMENTATION, MODEL_TIER_DEVELOPMENT_QA],
        preferred_model_alias="mock-default",
        fallback_aliases=["mock-lightweight"],
        max_cost=0.05,
        max_tokens=5000,
    ),
    _policy(
        agent_name="requirement-agent",
        capability=CAPABILITY_CLARIFICATION_QUESTION,
        allowed_tiers=[MODEL_TIER_DOCUMENTATION, MODEL_TIER_DEVELOPMENT_QA],
        preferred_model_alias="mock-default",
        fallback_aliases=["mock-lightweight"],
        max_cost=0.03,
        max_tokens=2000,
    ),
    # development-agent: development_plan only. Real LLM still disabled
    # by default; an operator may flip allow_real_llm=true plus
    # activate the openai-plan-only entry to switch to real plan-only.
    _policy(
        agent_name="development-agent",
        capability=CAPABILITY_DEVELOPMENT_PLAN,
        risk_level="medium",
        allowed_tiers=[MODEL_TIER_DEVELOPMENT_QA, MODEL_TIER_DOCUMENTATION],
        preferred_model_alias="mock-default",
        fallback_aliases=["mock-lightweight"],
        max_cost=0.10,
        max_tokens=8000,
        requires_human_review=True,
        notes="patch_generation hard-off; workspace_write hard-off",
    ),
    # qa-agent: qa_review + test_plan advisory; never executes.
    _policy(
        agent_name="qa-agent",
        capability=CAPABILITY_QA_REVIEW,
        risk_level="medium",
        # tier_2 is the canonical home; tier_3 is the mock fallback
        # because the default seed's mock-default is tier_3.
        allowed_tiers=[MODEL_TIER_DEVELOPMENT_QA, MODEL_TIER_DOCUMENTATION],
        preferred_model_alias="mock-default",
        fallback_aliases=["mock-lightweight"],
        max_cost=0.05,
        max_tokens=5000,
        requires_human_review=True,
        notes="advisory only; cannot approve / reject",
    ),
    _policy(
        agent_name="qa-agent",
        capability=CAPABILITY_TEST_PLAN,
        risk_level="medium",
        allowed_tiers=[MODEL_TIER_DEVELOPMENT_QA, MODEL_TIER_DOCUMENTATION],
        preferred_model_alias="mock-default",
        fallback_aliases=["mock-lightweight"],
        max_cost=0.05,
        max_tokens=5000,
        requires_human_review=True,
    ),
    # devops-agent: delivery risk / rollback advisory. Always
    # requires human review.
    _policy(
        agent_name="devops-agent",
        capability=CAPABILITY_DELIVERY_RISK_REVIEW,
        risk_level="high",
        allowed_tiers=[MODEL_TIER_DEVELOPMENT_QA, MODEL_TIER_DOCUMENTATION],
        preferred_model_alias="mock-default",
        fallback_aliases=["mock-lightweight"],
        max_cost=0.10,
        max_tokens=5000,
        requires_human_review=True,
    ),
    _policy(
        agent_name="devops-agent",
        capability=CAPABILITY_ROLLBACK_PLAN,
        risk_level="high",
        allowed_tiers=[MODEL_TIER_DEVELOPMENT_QA, MODEL_TIER_DOCUMENTATION],
        preferred_model_alias="mock-default",
        fallback_aliases=["mock-lightweight"],
        max_cost=0.10,
        max_tokens=5000,
        requires_human_review=True,
    ),
    # Shared docs capability available to all agents -- low risk,
    # no real LLM, mock by default.
    _policy(
        agent_name="documentation-agent",
        capability=CAPABILITY_DOCUMENTATION,
        allowed_tiers=[MODEL_TIER_DOCUMENTATION, MODEL_TIER_LIGHTWEIGHT],
        preferred_model_alias="mock-default",
        fallback_aliases=["mock-lightweight"],
        max_cost=0.05,
        max_tokens=5000,
    ),
)


def default_agent_policies() -> tuple[dict[str, Any], ...]:
    return tuple(
        dict(
            p,
            allowed_model_tiers=list(p["allowed_model_tiers"]),
            allowed_providers=list(p["allowed_providers"]),
            fallback_model_aliases=list(p["fallback_model_aliases"]),
            metadata=dict(p["metadata"]),
        )
        for p in DEFAULT_AGENT_POLICY_SEED
    )
