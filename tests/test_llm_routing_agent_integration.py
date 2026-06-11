"""Stage 38 -- per-agent default routing decisions for the pipeline agents."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from shared.sdk.llm_routing import (
    AgentModelPolicy,
    DECISION_MOCK_SELECTED,
    LLMModelEntry,
    MODEL_TIER_DOCUMENTATION,
    MODEL_TIER_LIGHTWEIGHT,
    ModelRouter,
    build_capability_request,
    default_agent_policies,
    default_models,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _SeededStore:
    def __init__(self) -> None:
        self.models: dict[str, LLMModelEntry] = {}
        for entry in default_models():
            self.models[entry["model_alias"]] = LLMModelEntry(
                model_id=str(uuid4()),
                provider=entry["provider"],
                model_name=entry["model_name"],
                model_alias=entry["model_alias"],
                model_tier=entry["model_tier"],
                capabilities=list(entry["capabilities"]),
                supported_schemas=list(entry["supported_schemas"]),
                status=entry["status"],
                plan_only_allowed=entry["plan_only_allowed"],
                requires_human_review=entry["requires_human_review"],
                cost_per_1k_input_tokens=entry["cost_per_1k_input_tokens"],
                cost_per_1k_output_tokens=entry["cost_per_1k_output_tokens"],
            )
        self.policies: list[AgentModelPolicy] = []
        for entry in default_agent_policies():
            self.policies.append(
                AgentModelPolicy(
                    policy_id=str(uuid4()),
                    agent_name=entry["agent_name"],
                    capability=entry["capability"],
                    task_type=entry.get("task_type", "default"),
                    risk_level=entry.get("risk_level", "low"),
                    preferred_model_alias=entry.get("preferred_model_alias"),
                    allowed_model_tiers=list(entry.get("allowed_model_tiers", [])),
                    allowed_providers=list(entry.get("allowed_providers", [])),
                    fallback_model_aliases=list(entry.get("fallback_model_aliases", [])),
                    max_cost_per_task_usd=entry.get("max_cost_per_task_usd"),
                    max_tokens_per_task=entry.get("max_tokens_per_task"),
                    requires_human_review=bool(entry.get("requires_human_review", False)),
                    allow_real_llm=bool(entry.get("allow_real_llm", False)),
                    allow_patch_generation=False,
                    allow_workspace_write=False,
                    status="active",
                    created_by="test",
                )
            )

    async def get_active_policy(self, *, agent_name, capability, task_type, risk_level):
        for p in self.policies:
            if p.agent_name == agent_name and p.capability == capability:
                return p
        return None

    async def get_model_by_alias(self, alias):
        return self.models.get(alias)

    async def record_decision(self, payload):
        class _Rec:
            routing_decision_id = str(uuid4())

        return _Rec()


def _route(agent: str, capability: str, **kwargs):
    store = _SeededStore()
    router = ModelRouter(store=store)
    req = build_capability_request(agent_name=agent, capability=capability, **kwargs)
    return _run(router.route(req))


def test_intake_agent_classification_selects_lightweight_mock():
    decision = _route("intake-agent", "classification")
    assert decision.decision == DECISION_MOCK_SELECTED
    assert decision.selected_model_tier in (
        MODEL_TIER_LIGHTWEIGHT,
        MODEL_TIER_DOCUMENTATION,
    )


def test_requirement_agent_selects_mock_default():
    decision = _route("requirement-agent", "requirement_analysis")
    assert decision.decision == DECISION_MOCK_SELECTED
    assert decision.selected_provider == "mock"


def test_development_agent_selects_mock_for_plan():
    decision = _route(
        "development-agent",
        "development_plan",
        requested_schema="LLMDevelopmentPlan",
    )
    assert decision.decision == DECISION_MOCK_SELECTED
    assert decision.requires_human_review is True


def test_qa_agent_selects_mock_for_qa_review():
    decision = _route("qa-agent", "qa_review", requested_schema="QAReviewReport")
    assert decision.decision == DECISION_MOCK_SELECTED
    assert decision.requires_human_review is True


def test_devops_agent_delivery_risk_requires_human_review():
    decision = _route("devops-agent", "delivery_risk_review")
    assert decision.decision == DECISION_MOCK_SELECTED
    assert decision.requires_human_review is True


def test_documentation_capability_selects_mock():
    decision = _route("documentation-agent", "documentation")
    assert decision.decision == DECISION_MOCK_SELECTED


def test_unknown_agent_returns_policy_not_found():
    decision = _route("unknown-agent", "development_plan")
    assert decision.decision == "policy_not_found"
