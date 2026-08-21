"""Step AT-M3.1 -- ReasoningInvocationStore against a real PostgreSQL.

Follows the existing store-test convention (tests/test_at_m2_team_store.py): skip when no
database is reachable, so the suite stays runnable on a workstation while still exercising the
real asyncpg path wherever migration 037 has been applied.

These are the assertions the in-memory fake cannot make: that ``correlation_id`` is genuinely
UNIQUE at the schema layer, that the status/failure-category CHECK constraint actually rejects an
inconsistent row, and that the ON CONFLICT DO NOTHING + re-fetch idempotency path round-trips
through real Postgres, not just a Python dict.
"""

from __future__ import annotations

import uuid

import pytest

from shared.sdk.agent_reasoning.store import ReasoningInvocationStore

_DB_SKIP = "no reachable PostgreSQL with migration 037 applied; skipping reasoning store test"


async def _store_or_skip() -> ReasoningInvocationStore:
    store = ReasoningInvocationStore()
    try:
        conn = await store._connect()
    except Exception:
        pytest.skip(_DB_SKIP)
    try:
        exists = await conn.fetchval("SELECT to_regclass('public.reasoning_invocations')")
    finally:
        await conn.close()
    if exists is None:
        pytest.skip(_DB_SKIP)
    return store


async def _project(store: ReasoningInvocationStore) -> str:
    conn = await store._connect()
    try:
        return str(
            await conn.fetchval(
                "INSERT INTO projects (title, summary) VALUES ($1,$2) RETURNING id",
                f"at-m3-1-store-test-{uuid.uuid4().hex[:8]}",
                "AT-M3.1 reasoning store test project",
            )
        )
    finally:
        await conn.close()


def _invocation(*, project_id: str | None = None, status: str = "succeeded", **overrides) -> dict:
    data = {
        "project_id": project_id,
        "thread_id": None,
        "requested_by_principal_id": None,
        "reasoning_verb": "propose",
        "requested_provider_name": "mock",
        "provider_mode": "mock",
        "model_name": None,
        "round_number": 1,
        "status": status,
        "failure_category": None if status == "succeeded" else "malformed_output",
        "failure_reason": None if status == "succeeded" else "test failure",
        "latency_ms": 5,
        "correlation_id": str(uuid.uuid4()),
        "audit_ref": None,
        "started_at": None,
        "completed_at": None,
    }
    data.update(overrides)
    return data


async def test_a_succeeded_invocation_round_trips():
    store = await _store_or_skip()
    project = await _project(store)
    recorded = await store.record_invocation(_invocation(project_id=project))
    assert recorded["status"] == "succeeded"
    assert recorded["provider_mode"] == "mock"
    fetched = await store.get_by_correlation_id(recorded["correlation_id"])
    assert fetched["invocation_id"] == recorded["invocation_id"]


async def test_correlation_id_is_unique_and_a_replay_returns_the_original_row():
    store = await _store_or_skip()
    project = await _project(store)
    data = _invocation(project_id=project)
    first = await store.record_invocation(data)
    # A second insert attempt with the SAME correlation_id but different content must resolve to
    # the first row, never create a second one and never overwrite the first.
    replay_attempt = dict(data)
    replay_attempt["reasoning_verb"] = "critique"
    second = await store.record_invocation(replay_attempt)
    assert second["invocation_id"] == first["invocation_id"]
    assert second["reasoning_verb"] == "propose", "the original row must not be overwritten"


async def test_the_database_rejects_a_failed_row_with_no_failure_category():
    """chk_reasoning_invocations_status_consistency, enforced by the schema, not only by Python."""
    import asyncpg

    store = await _store_or_skip()
    project = await _project(store)
    contradictory = _invocation(project_id=project, status="failed")
    contradictory["failure_category"] = None
    with pytest.raises(asyncpg.PostgresError):
        await store.record_invocation(contradictory)


async def test_the_database_rejects_an_unknown_reasoning_verb():
    import asyncpg

    store = await _store_or_skip()
    project = await _project(store)
    bad = _invocation(project_id=project)
    bad["reasoning_verb"] = "hallucinate"
    with pytest.raises(asyncpg.PostgresError):
        await store.record_invocation(bad)


async def test_the_database_rejects_a_live_provider_mode_this_slice_does_not_implement():
    """provider_mode is constrained to {'mock','disabled'} -- AT-M3.1 ships no live adapter."""
    import asyncpg

    store = await _store_or_skip()
    project = await _project(store)
    bad = _invocation(project_id=project)
    bad["provider_mode"] = "external_anthropic"
    with pytest.raises(asyncpg.PostgresError):
        await store.record_invocation(bad)


async def test_list_for_project_returns_only_that_projects_rows_newest_first():
    store = await _store_or_skip()
    project_a = await _project(store)
    project_b = await _project(store)
    first = await store.record_invocation(_invocation(project_id=project_a))
    second = await store.record_invocation(_invocation(project_id=project_a))
    await store.record_invocation(_invocation(project_id=project_b))
    rows = await store.list_for_project(project_a)
    assert [r["invocation_id"] for r in rows] == [second["invocation_id"], first["invocation_id"]]


async def test_project_thread_and_principal_are_all_nullable():
    """No forward reference to Goal/PlanRevision is invented; a call with none of these still
    persists (D14 / AT-M3.1 scope: this table names no Goal/PlanRevision column at all)."""
    store = await _store_or_skip()
    recorded = await store.record_invocation(_invocation(project_id=None))
    assert recorded["project_id"] is None
    assert recorded["thread_id"] is None
    assert recorded["requested_by_principal_id"] is None
