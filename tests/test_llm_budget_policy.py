"""Stage 35 -- BudgetPolicyEvaluator (preflight + record_usage) tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from shared.sdk.llm_budget import (
    DECISION_ALLOWED,
    DECISION_BLOCKED,
    DECISION_WARNING,
    BudgetPolicyEvaluator,
    LLMBudgetPolicy,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeStore:
    """In-memory replacement for ``BudgetPolicyStore``."""

    def __init__(
        self,
        *,
        policy: LLMBudgetPolicy | None = None,
        daily_usage: float = 0.0,
        monthly_usage: float = 0.0,
        task_tokens: int = 0,
        task_cost: float = 0.0,
    ) -> None:
        self.policy = policy
        self.daily_usage = daily_usage
        self.monthly_usage = monthly_usage
        self.task_tokens = task_tokens
        self.task_cost = task_cost
        self.events: list[dict[str, Any]] = []

    async def get_active_policy(
        self, *, provider: str, task_id=None, workflow_id=None, user_id=None
    ):
        return self.policy

    async def get_daily_usage_usd(self, *, provider=None, day=None):
        return self.daily_usage

    async def get_monthly_usage_usd(self, *, provider=None, month=None):
        return self.monthly_usage

    async def get_task_usage(self, *, task_id):
        return {"tokens": self.task_tokens, "cost_usd": self.task_cost}

    async def record_budget_event(self, **kwargs):
        self.events.append(kwargs)
        return None


def _policy(**overrides) -> LLMBudgetPolicy:
    base = {
        "policy_id": str(uuid4()),
        "policy_name": "test",
        "scope_type": "global",
        "scope_id": None,
        "provider": "external_openai",
        "model_name": None,
        "max_tokens_per_task": None,
        "max_cost_per_task_usd": None,
        "max_cost_per_day_usd": None,
        "max_cost_per_month_usd": None,
        "enforcement_mode": "block",
        "status": "active",
        "created_by": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "metadata": {},
    }
    base.update(overrides)
    return LLMBudgetPolicy(**base)


def test_mock_provider_always_allowed():
    store = _FakeStore()
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    decision = _run(
        e.preflight(
            provider="mock",
            model_name="mock-deterministic",
            prompt_text="hello",
            task_id="T",
        )
    )
    assert decision.allowed is True
    assert decision.estimated_cost_usd == 0.0


def test_real_provider_no_policy_blocks():
    store = _FakeStore(policy=None)
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    decision = _run(
        e.preflight(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_text="hello world",
            task_id="T",
        )
    )
    assert decision.blocked is True
    assert decision.reason == "no_active_budget_policy"


def test_real_provider_allowed_under_policy():
    store = _FakeStore(policy=_policy(max_cost_per_day_usd=1.0))
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    decision = _run(
        e.preflight(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_text="hello",
            task_id="T",
        )
    )
    assert decision.allowed is True
    assert decision.policy_name == "test"
    assert decision.estimated_cost_usd > 0


def test_per_task_token_cap_blocks():
    store = _FakeStore(
        policy=_policy(max_tokens_per_task=10),
        task_tokens=8,
    )
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    # prompt of ~16 chars -> ~4 tokens prompt + 32 completion = 36 total > 10
    decision = _run(
        e.preflight(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_text="hello world test",
            task_id="T",
        )
    )
    assert decision.blocked is True
    assert decision.cap_breached == "token_per_task"


def test_per_task_cost_cap_blocks():
    store = _FakeStore(
        policy=_policy(max_cost_per_task_usd=0.000001),
    )
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    decision = _run(
        e.preflight(
            provider="external_openai",
            model_name="gpt-4-turbo",
            prompt_text="x" * 4000,
            task_id="T",
        )
    )
    assert decision.blocked is True
    assert decision.cap_breached == "cost_per_task"


def test_daily_cap_blocks_when_existing_usage_high():
    store = _FakeStore(
        policy=_policy(max_cost_per_day_usd=0.0001),
        daily_usage=0.0001,
    )
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    decision = _run(
        e.preflight(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_text="hello world",
            task_id="T",
        )
    )
    assert decision.blocked is True
    assert decision.cap_breached == "cost_per_day"


def test_monthly_cap_blocks_when_existing_usage_high():
    store = _FakeStore(
        policy=_policy(max_cost_per_month_usd=0.0001),
        monthly_usage=0.0001,
    )
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    decision = _run(
        e.preflight(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_text="hi",
            task_id="T",
        )
    )
    assert decision.blocked is True
    assert decision.cap_breached == "cost_per_month"


def test_warn_only_mode_returns_warning_not_block():
    store = _FakeStore(
        policy=_policy(
            max_cost_per_task_usd=0.000001,
            enforcement_mode="warn_only",
        ),
    )
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    decision = _run(
        e.preflight(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_text="x" * 200,
            task_id="T",
        )
    )
    assert decision.warning is True
    assert decision.blocked is False


def test_unknown_provider_blocks():
    store = _FakeStore(policy=_policy(provider="external_madeup"))
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    decision = _run(
        e.preflight(
            provider="external_madeup",
            model_name="x",
            prompt_text="hi",
            task_id="T",
        )
    )
    assert decision.blocked is True
    assert "unknown_provider" in (decision.reason or "")
    assert decision.cap_breached == "unknown_provider"


def test_preflight_records_one_event():
    store = _FakeStore(policy=_policy(max_cost_per_day_usd=1.0))
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    _run(
        e.preflight(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_text="hi",
            task_id="T",
        )
    )
    assert len(store.events) == 1
    assert store.events[0]["event_type"] == "preflight"
    assert store.events[0]["decision"] == DECISION_ALLOWED


def test_record_usage_mock_is_zero_cost():
    store = _FakeStore()
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    out = _run(
        e.record_usage(
            provider="mock",
            model_name="mock-deterministic",
            prompt_tokens=100,
            completion_tokens=50,
            task_id="T",
        )
    )
    assert out["recorded"] is True
    assert out["actual_cost_usd"] == 0.0
    assert out["exceeded"] is False


def test_record_usage_real_provider_writes_recorded_event():
    store = _FakeStore(policy=_policy(max_cost_per_day_usd=1.0))
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    out = _run(
        e.record_usage(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
            task_id="T",
            policy_id=store.policy.policy_id,
        )
    )
    assert out["recorded"] is True
    assert out["actual_cost_usd"] > 0
    # event_type=recorded_usage with decision=recorded
    assert any(
        ev["event_type"] == "recorded_usage" and ev["decision"] == "recorded" for ev in store.events
    )


def test_explain_decision_text():
    store = _FakeStore(policy=_policy(max_cost_per_day_usd=1.0))
    e = BudgetPolicyEvaluator(store=store)  # type: ignore[arg-type]
    allowed = _run(
        e.preflight(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_text="hi",
            task_id="T",
        )
    )
    assert "allowed" in e.explain_decision(allowed)
    store2 = _FakeStore(policy=None)
    e2 = BudgetPolicyEvaluator(store=store2)  # type: ignore[arg-type]
    blocked = _run(
        e2.preflight(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_text="hi",
            task_id="T",
        )
    )
    assert "blocked" in e2.explain_decision(blocked)
    # Each warning is also explainable.
    store3 = _FakeStore(
        policy=_policy(max_cost_per_task_usd=0.0000001, enforcement_mode="warn_only")
    )
    e3 = BudgetPolicyEvaluator(store=store3)  # type: ignore[arg-type]
    warning = _run(
        e3.preflight(
            provider="external_openai",
            model_name="gpt-4o-mini",
            prompt_text="x" * 500,
            task_id="T",
        )
    )
    assert warning.decision == DECISION_WARNING
    assert "warning" in e3.explain_decision(warning)
    # Avoid "unused import" pyflakes for the decision constants.
    assert DECISION_ALLOWED == "allowed"
    assert DECISION_BLOCKED == "blocked"
