"""Stage 35 -- BudgetPolicyStore tests with stubbed asyncpg."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import asyncpg

from shared.sdk.llm_budget import BudgetPolicyStore


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeRow(dict):
    def __getitem__(self, key: str) -> Any:
        return dict.__getitem__(self, key)


def _make_policy_row(**overrides):
    base = {
        "policy_id": uuid4(),
        "policy_name": "p1",
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
    return _FakeRow(base)


def _make_event_row(**overrides):
    base = {
        "budget_event_id": uuid4(),
        "task_id": "T",
        "workflow_id": None,
        "policy_id": uuid4(),
        "provider": "external_openai",
        "model_name": "gpt-4o-mini",
        "event_type": "preflight",
        "estimated_prompt_tokens": 100,
        "estimated_completion_tokens": 50,
        "estimated_total_tokens": 150,
        "actual_prompt_tokens": None,
        "actual_completion_tokens": None,
        "actual_total_tokens": None,
        "estimated_cost_usd": 0.001,
        "actual_cost_usd": None,
        "budget_remaining_usd": None,
        "decision": "allowed",
        "reason": None,
        "created_at": datetime.now(timezone.utc),
        "metadata": {},
    }
    base.update(overrides)
    return _FakeRow(base)


class _Conn:
    def __init__(self, scripted):
        self._scripted = list(scripted)

    async def fetchrow(self, sql, *params):
        for i, (kind, value) in enumerate(self._scripted):
            if kind == "fetchrow":
                self._scripted.pop(i)
                return value
        return None

    async def fetch(self, sql, *params):
        for i, (kind, value) in enumerate(self._scripted):
            if kind == "fetch":
                self._scripted.pop(i)
                return value
        return []

    async def fetchval(self, sql, *params):
        for i, (kind, value) in enumerate(self._scripted):
            if kind == "fetchval":
                self._scripted.pop(i)
                return value
        return 0

    async def close(self):
        return None


def _patch(monkeypatch, scripted):
    conn = _Conn(scripted)

    async def _connect(*a, **k):
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)
    return conn


def test_create_policy_returns_dataclass(monkeypatch):
    _patch(monkeypatch, [("fetchrow", _make_policy_row())])
    store = BudgetPolicyStore(dsn="postgresql://x")
    p = _run(store.create_policy(policy_name="p", provider="external_openai"))
    assert p.policy_name == "p1"
    assert p.provider == "external_openai"
    assert p.enforcement_mode == "block"


def test_get_active_policy_returns_none_when_no_match(monkeypatch):
    _patch(monkeypatch, [("fetchrow", None)])
    store = BudgetPolicyStore(dsn="postgresql://x")
    out = _run(store.get_active_policy(provider="external_openai"))
    assert out is None


def test_get_active_policy_returns_match(monkeypatch):
    _patch(monkeypatch, [("fetchrow", _make_policy_row(policy_name="global-cap"))])
    store = BudgetPolicyStore(dsn="postgresql://x")
    out = _run(store.get_active_policy(provider="external_openai"))
    assert out is not None
    assert out.policy_name == "global-cap"


def test_list_policies_returns_rows(monkeypatch):
    _patch(monkeypatch, [("fetch", [_make_policy_row(), _make_policy_row()])])
    store = BudgetPolicyStore(dsn="postgresql://x")
    rows = _run(store.list_policies(provider="external_openai", limit=10))
    assert len(rows) == 2


def test_record_budget_event_returns_dataclass(monkeypatch):
    _patch(monkeypatch, [("fetchrow", _make_event_row())])
    store = BudgetPolicyStore(dsn="postgresql://x")
    event = _run(
        store.record_budget_event(
            task_id="T",
            workflow_id=None,
            policy_id=str(uuid4()),
            provider="external_openai",
            model_name="gpt-4o-mini",
            event_type="preflight",
            decision="allowed",
            estimated_cost_usd=0.001,
        )
    )
    assert event.task_id == "T"
    assert event.event_type == "preflight"
    assert event.decision == "allowed"


def test_get_daily_usage_returns_zero_when_empty(monkeypatch):
    _patch(monkeypatch, [("fetchval", 0)])
    store = BudgetPolicyStore(dsn="postgresql://x")
    out = _run(store.get_daily_usage_usd(provider="external_openai"))
    assert out == 0.0


def test_get_task_usage_returns_aggregates(monkeypatch):
    _patch(
        monkeypatch,
        [("fetchrow", _FakeRow({"tokens": 1234, "cost": 0.456}))],
    )
    store = BudgetPolicyStore(dsn="postgresql://x")
    out = _run(store.get_task_usage(task_id="T"))
    assert out["tokens"] == 1234
    assert out["cost_usd"] == 0.456


def test_get_usage_summary_collects_counts(monkeypatch):
    _patch(
        monkeypatch,
        [
            ("fetchval", 0.5),  # daily
            ("fetchval", 5.0),  # monthly
            (
                "fetchrow",
                _FakeRow({"allowed": 7, "blocked": 1, "warning": 0, "recorded": 3, "total": 11}),
            ),
        ],
    )
    store = BudgetPolicyStore(dsn="postgresql://x")
    out = _run(store.get_usage_summary(provider="external_openai"))
    assert out["daily_usage_usd"] == 0.5
    assert out["monthly_usage_usd"] == 5.0
    assert out["allowed_events"] == 7
    assert out["blocked_events"] == 1
    assert out["total_events"] == 11


def test_uuid_imports_unused():
    _ = UUID
