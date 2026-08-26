"""Step AT-M3.1 -- ReasoningInvocationStore against a real PostgreSQL.

Follows the existing store-test convention (tests/test_at_m2_team_store.py): skip when no
database is reachable, so the suite stays runnable on a workstation while still exercising the
real asyncpg path wherever migration 037 has been applied.

AT-M3.1-REMEDIATION-1: these tests exercise the new atomic-ownership lifecycle
(try_begin_invocation / complete_invocation) and are the assertions the in-memory fake cannot make
with full confidence: that correlation_id is genuinely UNIQUE at the schema layer under REAL
concurrent writers (not just Python's cooperative scheduling), that the three-way
started/succeeded/failed CHECK constraint holds, and that a real ReasoningService backed by real
Postgres invokes the provider at most once per correlation_id even under a real concurrent race.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from shared.sdk.agent_reasoning.models import CritiqueArtifact, ReasoningRequest
from shared.sdk.agent_reasoning.service import ReasoningService
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


def _begin_data(*, project_id: str | None = None, correlation_id: str | None = None) -> dict:
    return {
        "project_id": project_id,
        "thread_id": None,
        "requested_by_principal_id": None,
        "reasoning_verb": "propose",
        "requested_provider_name": "mock",
        "provider_mode": "mock",
        "model_name": None,
        "round_number": 1,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "started_at": datetime.now(timezone.utc),
    }


def _terminal(*, status: str = "succeeded", **overrides) -> dict:
    data = {
        "status": status,
        "failure_category": None if status == "succeeded" else "malformed_output",
        "failure_reason": None if status == "succeeded" else "test failure",
        "latency_ms": 5,
        "audit_ref": None,
        "completed_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return data


# --- lifecycle: begin -> complete round trip -----------------------------------------------------


async def test_try_begin_invocation_inserts_a_started_row():
    store = await _store_or_skip()
    project = await _project(store)
    owned, row = await store.try_begin_invocation(_begin_data(project_id=project))
    assert owned is True
    assert row["status"] == "started"
    assert row["completed_at"] is None
    assert row["failure_category"] is None


async def test_complete_invocation_transitions_started_to_succeeded():
    store = await _store_or_skip()
    project = await _project(store)
    _owned, row = await store.try_begin_invocation(_begin_data(project_id=project))
    completed = await store.complete_invocation(
        row["invocation_id"], terminal=_terminal(status="succeeded")
    )
    assert completed["status"] == "succeeded"
    assert completed["completed_at"] is not None
    assert completed["failure_category"] is None


async def test_complete_invocation_transitions_started_to_failed():
    store = await _store_or_skip()
    project = await _project(store)
    _owned, row = await store.try_begin_invocation(_begin_data(project_id=project))
    completed = await store.complete_invocation(
        row["invocation_id"], terminal=_terminal(status="failed")
    )
    assert completed["status"] == "failed"
    assert completed["failure_category"] == "malformed_output"


async def test_a_second_complete_invocation_call_cannot_overwrite_a_terminal_row():
    """Guards against a duplicate/late completion attempt clobbering terminal truth."""
    store = await _store_or_skip()
    project = await _project(store)
    _owned, row = await store.try_begin_invocation(_begin_data(project_id=project))
    first = await store.complete_invocation(
        row["invocation_id"], terminal=_terminal(status="succeeded")
    )
    second = await store.complete_invocation(
        row["invocation_id"], terminal=_terminal(status="failed")
    )
    assert first["status"] == "succeeded"
    assert second["status"] == "succeeded", "the original terminal outcome must not be overwritten"
    assert second["completed_at"] == first["completed_at"]


# --- correlation_id ownership -----------------------------------------------------------------------


async def test_correlation_id_is_unique_and_a_second_claim_attempt_never_owns():
    store = await _store_or_skip()
    project = await _project(store)
    correlation_id = str(uuid.uuid4())
    first_owned, first_row = await store.try_begin_invocation(
        _begin_data(project_id=project, correlation_id=correlation_id)
    )
    second_owned, second_row = await store.try_begin_invocation(
        _begin_data(project_id=project, correlation_id=correlation_id)
    )
    assert first_owned is True
    assert second_owned is False
    assert second_row["invocation_id"] == first_row["invocation_id"]

    conn = await store._connect()
    try:
        count = await conn.fetchval(
            "SELECT count(*) FROM reasoning_invocations WHERE correlation_id=$1", correlation_id
        )
    finally:
        await conn.close()
    assert count == 1


async def test_ten_concurrent_claim_attempts_on_real_postgres_yield_exactly_one_owner():
    """The store-ownership half of Validation 1's proven race (10/10 provider invocations)."""
    store = await _store_or_skip()
    project = await _project(store)
    correlation_id = str(uuid.uuid4())
    results = await asyncio.gather(
        *[
            store.try_begin_invocation(
                _begin_data(project_id=project, correlation_id=correlation_id)
            )
            for _ in range(10)
        ]
    )
    owners = [owned for owned, _row in results if owned]
    assert len(owners) == 1, f"expected exactly one owner, got {len(owners)}"

    conn = await store._connect()
    try:
        count = await conn.fetchval(
            "SELECT count(*) FROM reasoning_invocations WHERE correlation_id=$1", correlation_id
        )
    finally:
        await conn.close()
    assert count == 1


async def test_ten_concurrent_service_invoke_calls_on_real_postgres_call_the_provider_once():
    """End-to-end reproduction of Validation 1's most severe finding (artifact/evidence
    misattribution under concurrency) against REAL Postgres, now closed: at most one provider
    invocation per correlation_id, and no losing caller ever receives an artifact."""
    store = await _store_or_skip()
    project = await _project(store)
    service = ReasoningService(store=store, audit_client=None)
    call_count = {"n": 0}

    class _CountingProvider:
        name = "mock"
        mode = "mock"

        def propose(self, request):
            call_count["n"] += 1
            from shared.sdk.agent_reasoning.mock_provider import MockReasoningProvider

            return MockReasoningProvider().propose(request)

        def critique(self, request) -> CritiqueArtifact:
            raise NotImplementedError

        def summarize_decision(self, request):
            raise NotImplementedError

    correlation_id = str(uuid.uuid4())
    request = ReasoningRequest(
        verb="propose",
        context={"goal_statement": "g"},
        project_id=project,
        correlation_id=correlation_id,
    )
    results = await asyncio.gather(
        *[service.invoke(request, provider=_CountingProvider()) for _ in range(10)]
    )

    assert call_count["n"] == 1, f"provider invoked {call_count['n']} times, expected exactly 1"
    fresh = [r for r in results if r.disposition == "fresh"]
    others = [r for r in results if r.disposition != "fresh"]
    assert len(fresh) == 1
    assert len(others) == 9
    assert all(r.artifact is None for r in others), "no losing caller may receive an artifact"
    winning_id = fresh[0].invocation["invocation_id"]
    assert all(r.invocation["invocation_id"] == winning_id for r in others)


# --- schema constraints ----------------------------------------------------------------------------


async def test_the_database_rejects_a_failed_row_with_no_failure_category():
    """chk_reasoning_invocations_status_consistency, enforced by the schema, not only by Python."""
    import asyncpg

    store = await _store_or_skip()
    project = await _project(store)
    _owned, row = await store.try_begin_invocation(_begin_data(project_id=project))
    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                "UPDATE reasoning_invocations SET status='failed', completed_at=now() "
                "WHERE invocation_id=$1",
                row["invocation_id"],
            )
    finally:
        await conn.close()


async def test_the_database_rejects_an_unknown_reasoning_verb():
    import asyncpg

    store = await _store_or_skip()
    project = await _project(store)
    bad = _begin_data(project_id=project)
    bad["reasoning_verb"] = "hallucinate"
    with pytest.raises(asyncpg.PostgresError):
        await store.try_begin_invocation(bad)


async def test_the_database_rejects_a_live_provider_mode_this_slice_does_not_implement():
    """provider_mode is constrained to {'mock','disabled'} -- AT-M3.1 ships no live adapter."""
    import asyncpg

    store = await _store_or_skip()
    project = await _project(store)
    bad = _begin_data(project_id=project)
    bad["provider_mode"] = "external_anthropic"
    with pytest.raises(asyncpg.PostgresError):
        await store.try_begin_invocation(bad)


async def test_the_database_rejects_an_unrecognised_status():
    import asyncpg

    store = await _store_or_skip()
    project = await _project(store)
    _owned, row = await store.try_begin_invocation(_begin_data(project_id=project))
    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                "UPDATE reasoning_invocations SET status='queued' WHERE invocation_id=$1",
                row["invocation_id"],
            )
    finally:
        await conn.close()


# --- failure_reason safety at the store layer -------------------------------------------------------


async def test_the_store_sanitizes_an_unsafe_failure_reason_on_real_postgres():
    store = await _store_or_skip()
    project = await _project(store)
    _owned, row = await store.try_begin_invocation(_begin_data(project_id=project))
    completed = await store.complete_invocation(
        row["invocation_id"],
        terminal=_terminal(
            status="failed",
            failure_reason="chain_of_thought: leaked reasoning; api_key=sk-ant-abcdef123456",
        ),
    )
    assert "chain_of_thought" not in completed["failure_reason"]
    assert "sk-ant-abcdef123456" not in completed["failure_reason"]


# --- read-only helpers, other AT-M2 tables untouched --------------------------------------------------


async def test_list_for_project_returns_only_that_projects_rows_newest_first():
    store = await _store_or_skip()
    project_a = await _project(store)
    project_b = await _project(store)
    _o1, first = await store.try_begin_invocation(_begin_data(project_id=project_a))
    await store.complete_invocation(first["invocation_id"], terminal=_terminal())
    _o2, second = await store.try_begin_invocation(_begin_data(project_id=project_a))
    await store.complete_invocation(second["invocation_id"], terminal=_terminal())
    _o3, other = await store.try_begin_invocation(_begin_data(project_id=project_b))
    await store.complete_invocation(other["invocation_id"], terminal=_terminal())
    rows = await store.list_for_project(project_a)
    assert [r["invocation_id"] for r in rows] == [second["invocation_id"], first["invocation_id"]]


async def test_project_thread_and_principal_are_all_nullable():
    """No forward reference to Goal/PlanRevision is invented; a call with none of these still
    persists (D14 / AT-M3.1 scope: this table names no Goal/PlanRevision column at all)."""
    store = await _store_or_skip()
    _owned, row = await store.try_begin_invocation(_begin_data(project_id=None))
    assert row["project_id"] is None
    assert row["thread_id"] is None
    assert row["requested_by_principal_id"] is None


async def test_migration_037_alters_no_at_m2_table():
    """Migration 037 itself still adds nothing to any AT-M2 table.

    This assertion originally read "resulting_plan_revision_id stays FK-less", with the FK
    expected to arrive when M3.2 pre-cleared it under AT-D14 -- which migration 038 has now done.
    The property 037 actually owns is narrower and unchanged: reasoning_invocations names no
    column on an AT-M2 table, and 037 introduced no constraint on one. The FK's own existence is
    asserted by tests/test_at_m3_2_planning_store.py, which is the slice that authorized it.
    """
    store = await _store_or_skip()
    conn = await store._connect()
    try:
        rows = await conn.fetch("""
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
            WHERE tc.table_name='team_decisions' AND tc.constraint_type='FOREIGN KEY'
              AND ccu.table_name='reasoning_invocations'
            """)
    finally:
        await conn.close()
    assert [row["constraint_name"] for row in rows] == []
