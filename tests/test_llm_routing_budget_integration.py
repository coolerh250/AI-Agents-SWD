"""Stage 38 -- ModelRouter consults Stage 35 budget evaluator."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from shared.sdk.llm_routing import (
    AgentModelPolicy,
    DECISION_BUDGET_BLOCKED,
    DECISION_SELECTED,
    LLMModelEntry,
    MODEL_STATUS_ACTIVE,
    MODEL_TIER_DEVELOPMENT_QA,
    ModelRouter,
    build_capability_request,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeStore:
    def __init__(self):
        self.models: dict[str, LLMModelEntry] = {}
        self.policies: list[AgentModelPolicy] = []

    def add(self):
        self.models["external-real"] = LLMModelEntry(
            model_id=str(uuid4()),
            provider="external_openai",
            model_name="gpt-4o-mini",
            model_alias="external-real",
            model_tier=MODEL_TIER_DEVELOPMENT_QA,
            capabilities=["development_plan"],
            supported_schemas=["LLMDevelopmentPlan"],
            status=MODEL_STATUS_ACTIVE,
            plan_only_allowed=True,
            cost_per_1k_input_tokens=0.0,
            cost_per_1k_output_tokens=0.0,
        )
        self.policies.append(
            AgentModelPolicy(
                policy_id=str(uuid4()),
                agent_name="development-agent",
                capability="development_plan",
                preferred_model_alias="external-real",
                allowed_providers=["external_openai"],
                allowed_model_tiers=[MODEL_TIER_DEVELOPMENT_QA],
                fallback_model_aliases=[],
                allow_real_llm=True,
                max_cost_per_task_usd=10.0,
                max_tokens_per_task=100_000,
            )
        )

    async def get_active_policy(self, **kwargs):
        return self.policies[0] if self.policies else None

    async def get_model_by_alias(self, alias):
        return self.models.get(alias)

    async def record_decision(self, payload):
        class _Rec:
            routing_decision_id = str(uuid4())

        return _Rec()


class _FakeBudget:
    def __init__(self, allowed: bool, policy_id: str | None = None):
        self.allowed = allowed
        self.policy_id = policy_id

    async def preflight(self, **kwargs):
        class _Dec:
            def __init__(self, ok, policy_id):
                self.allowed = ok
                self.reason = None if ok else "budget_cap_exceeded"
                self.policy_id = policy_id

        return _Dec(self.allowed, self.policy_id)


def test_budget_evaluator_allow_lets_router_select():
    store = _FakeStore()
    store.add()
    router = ModelRouter(store=store, budget_evaluator=_FakeBudget(allowed=True))
    req = build_capability_request(
        agent_name="development-agent",
        capability="development_plan",
        requested_schema="LLMDevelopmentPlan",
        allow_real_llm_requested=True,
    )
    decision = _run(router.route(req))
    assert decision.decision == DECISION_SELECTED
    assert decision.real_llm_allowed is True


def test_budget_evaluator_block_returns_budget_blocked():
    store = _FakeStore()
    store.add()
    router = ModelRouter(store=store, budget_evaluator=_FakeBudget(allowed=False, policy_id="bp-1"))
    req = build_capability_request(
        agent_name="development-agent",
        capability="development_plan",
        requested_schema="LLMDevelopmentPlan",
        allow_real_llm_requested=True,
    )
    decision = _run(router.route(req))
    assert decision.decision == DECISION_BUDGET_BLOCKED


def test_budget_evaluator_not_called_for_mock_provider():
    """Mock provider routing must never trigger the Stage 35 evaluator."""

    class _CountedBudget:
        def __init__(self):
            self.calls = 0

        async def preflight(self, **kwargs):
            self.calls += 1

            class _Dec:
                allowed = True
                reason = None
                policy_id = None

            return _Dec()

    counted = _CountedBudget()
    # Fresh store using mock model.
    from tests.test_llm_model_router import _FakeStore as RouterFake

    store = RouterFake()
    store.add_policy()
    store.add_model()
    router = ModelRouter(store=store, budget_evaluator=counted)
    req = build_capability_request(agent_name="development-agent", capability="development_plan")
    _run(router.route(req))
    assert counted.calls == 0
