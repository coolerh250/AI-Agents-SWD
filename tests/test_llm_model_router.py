"""Stage 38 -- ModelRouter behaviour (fake store; no DB)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from shared.sdk.llm_routing import (
    AgentModelPolicy,
    DECISION_BLOCKED,
    DECISION_BUDGET_BLOCKED,
    DECISION_DIRECT_MODEL_REJECTED,
    DECISION_FALLBACK_SELECTED,
    DECISION_HUMAN_APPROVAL_REQUIRED,
    DECISION_MOCK_SELECTED,
    DECISION_POLICY_NOT_FOUND,
    DECISION_PROVIDER_UNAVAILABLE,
    LLMModelEntry,
    MODEL_STATUS_ACTIVE,
    MODEL_STATUS_INACTIVE,
    MODEL_TIER_DEVELOPMENT_QA,
    MODEL_TIER_DOCUMENTATION,
    ModelRouter,
    build_capability_request,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeStore:
    def __init__(self) -> None:
        self.models: dict[str, LLMModelEntry] = {}
        self.policies: list[AgentModelPolicy] = []
        self.persisted: list[dict[str, Any]] = []

    def add_model(self, **overrides) -> LLMModelEntry:
        base = {
            "model_id": str(uuid4()),
            "provider": "mock",
            "model_name": "mock-deterministic",
            "model_alias": "mock-default",
            "model_tier": MODEL_TIER_DOCUMENTATION,
            "capabilities": ["development_plan", "qa_review", "classification"],
            "supported_schemas": ["LLMDevelopmentPlan", "QAReviewReport"],
            "status": MODEL_STATUS_ACTIVE,
            "plan_only_allowed": True,
        }
        base.update(overrides)
        entry = LLMModelEntry(**base)
        self.models[entry.model_alias] = entry
        return entry

    def add_policy(self, **overrides) -> AgentModelPolicy:
        base = {
            "policy_id": str(uuid4()),
            "agent_name": "development-agent",
            "capability": "development_plan",
            "task_type": "default",
            "risk_level": "low",
            "preferred_model_alias": "mock-default",
            "allowed_model_tiers": [MODEL_TIER_DOCUMENTATION, MODEL_TIER_DEVELOPMENT_QA],
            "allowed_providers": ["mock", "external_openai"],
            "fallback_model_aliases": ["mock-lightweight"],
            "max_cost_per_task_usd": 0.05,
            "max_tokens_per_task": 8000,
            "requires_human_review": False,
            "allow_real_llm": False,
            "allow_patch_generation": False,
            "allow_workspace_write": False,
            "status": "active",
            "created_by": "test",
        }
        base.update(overrides)
        policy = AgentModelPolicy(**base)
        self.policies.append(policy)
        return policy

    async def get_active_policy(self, *, agent_name, capability, task_type, risk_level):
        for p in self.policies:
            if (
                p.agent_name == agent_name
                and p.capability == capability
                and p.status == "active"
                and p.task_type in (task_type, "default")
                and p.risk_level in (risk_level, "low")
            ):
                return p
        return None

    async def get_model_by_alias(self, alias):
        return self.models.get(alias)

    async def list_models(self, *, status=None, provider=None, limit=200):
        return list(self.models.values())

    async def list_policies(self, *, agent_name=None, status="active", limit=200):
        return list(self.policies)

    async def list_decisions(self, *, task_id=None, agent_name=None, decision=None, limit=100):
        return []

    async def record_decision(self, decision_dict):
        self.persisted.append(decision_dict)

        class _Rec:
            routing_decision_id = str(uuid4())

        return _Rec()


def test_router_selects_mock_when_policy_and_model_align():
    store = _FakeStore()
    store.add_policy()
    store.add_model()
    router = ModelRouter(store=store)
    req = build_capability_request(
        agent_name="development-agent",
        capability="development_plan",
        requested_schema="LLMDevelopmentPlan",
    )
    decision = _run(router.route(req))
    assert decision.decision == DECISION_MOCK_SELECTED
    assert decision.selected_model_alias == "mock-default"
    assert decision.real_llm_allowed is False
    assert decision.patch_generation_allowed is False
    assert decision.workspace_write_allowed is False


def test_router_blocks_when_no_policy():
    store = _FakeStore()
    store.add_model()
    router = ModelRouter(store=store)
    req = build_capability_request(agent_name="development-agent", capability="development_plan")
    decision = _run(router.route(req))
    assert decision.decision == DECISION_POLICY_NOT_FOUND


def test_router_blocks_inactive_model_falls_back_then_blocks():
    store = _FakeStore()
    store.add_policy(preferred_model_alias="inactive-real", fallback_model_aliases=[])
    store.add_model(
        provider="external_openai",
        model_name="gpt-4o-mini",
        model_alias="inactive-real",
        status=MODEL_STATUS_INACTIVE,
    )
    router = ModelRouter(store=store)
    req = build_capability_request(agent_name="development-agent", capability="development_plan")
    decision = _run(router.route(req))
    assert decision.decision in (DECISION_BLOCKED, DECISION_PROVIDER_UNAVAILABLE)


def test_router_uses_fallback_when_preferred_missing():
    store = _FakeStore()
    store.add_policy(preferred_model_alias="missing-alias")
    store.add_model()  # mock-default is the fallback
    store.add_model(model_alias="mock-lightweight")
    router = ModelRouter(store=store)
    req = build_capability_request(agent_name="development-agent", capability="development_plan")
    decision = _run(router.route(req))
    # preferred missing -> fallback alias mock-lightweight selected.
    assert decision.decision == DECISION_FALLBACK_SELECTED
    assert decision.fallback_used is True


def test_router_blocks_unsupported_schema():
    store = _FakeStore()
    store.add_policy()
    store.add_model(supported_schemas=["UnrelatedSchema"])
    store.add_model(model_alias="mock-lightweight", supported_schemas=["UnrelatedSchema"])
    router = ModelRouter(store=store)
    req = build_capability_request(
        agent_name="development-agent",
        capability="development_plan",
        requested_schema="LLMDevelopmentPlan",
    )
    decision = _run(router.route(req))
    # All candidates rejected -> blocked.
    assert decision.decision == DECISION_BLOCKED


def test_router_rejects_direct_model_selection_outside_policy():
    store = _FakeStore()
    store.add_policy(preferred_model_alias="mock-default", fallback_model_aliases=[])
    store.add_model()
    router = ModelRouter(store=store)
    req = build_capability_request(
        agent_name="development-agent",
        capability="development_plan",
        requested_model_alias="external-model-not-in-policy",
    )
    decision = _run(router.route(req))
    assert decision.decision == DECISION_DIRECT_MODEL_REJECTED
    assert decision.reason == "agent_direct_model_selection_rejected"


def test_router_blocks_patch_generation_hard_disabled():
    store = _FakeStore()
    store.add_policy(capability="code_patch_proposal")
    store.add_model()
    router = ModelRouter(store=store)
    req = build_capability_request(
        agent_name="development-agent",
        capability="code_patch_proposal",
        allow_patch_generation_requested=True,
    )
    decision = _run(router.route(req))
    assert decision.decision == DECISION_BLOCKED
    assert decision.reason == "patch_generation_hard_disabled"


def test_router_blocks_workspace_write_hard_disabled():
    store = _FakeStore()
    store.add_policy()
    store.add_model()
    router = ModelRouter(store=store)
    req = build_capability_request(
        agent_name="development-agent",
        capability="development_plan",
        allow_workspace_write_requested=True,
    )
    decision = _run(router.route(req))
    assert decision.decision == DECISION_BLOCKED
    assert decision.reason == "workspace_write_hard_disabled"


def test_router_critical_risk_requires_human_approval():
    store = _FakeStore()
    store.add_policy(risk_level="critical", allow_real_llm=False)
    store.add_model()
    router = ModelRouter(store=store)
    req = build_capability_request(
        agent_name="development-agent",
        capability="development_plan",
        risk_level="critical",
    )
    decision = _run(router.route(req))
    assert decision.decision == DECISION_HUMAN_APPROVAL_REQUIRED
    assert decision.requires_human_review is True


def test_router_blocks_when_policy_cost_cap_exceeded():
    store = _FakeStore()
    store.add_policy(max_cost_per_task_usd=0.000001)
    store.add_model(
        cost_per_1k_input_tokens=0.5,
        cost_per_1k_output_tokens=1.0,
        default_max_output_tokens=4096,
    )
    router = ModelRouter(store=store)
    req = build_capability_request(
        agent_name="development-agent",
        capability="development_plan",
        estimated_input_tokens=4000,
    )
    decision = _run(router.route(req))
    assert decision.decision == DECISION_BUDGET_BLOCKED


def test_router_persists_decision_when_asked():
    store = _FakeStore()
    store.add_policy()
    store.add_model()
    router = ModelRouter(store=store)
    req = build_capability_request(agent_name="development-agent", capability="development_plan")
    _run(router.route(req, persist=True))
    assert len(store.persisted) == 1
    assert store.persisted[0]["agent_name"] == "development-agent"
    # Patch + workspace are hard-False at the persist boundary.
    assert store.persisted[0]["patch_generation_allowed"] is False
    assert store.persisted[0]["workspace_write_allowed"] is False
