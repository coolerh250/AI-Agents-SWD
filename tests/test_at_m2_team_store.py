"""Step AT-M2-TEAM-CORE -- TeamStore against a real PostgreSQL.

Follows the existing store-test convention (tests/test_agent_execution_store.py): skip when no
database is reachable, so the suite stays runnable on a workstation while still exercising the
real asyncpg path wherever migration 036 has been applied.

These are the assertions the in-memory fake cannot make: that the schema's CHECK constraints
actually reject an unaddressed message and an inconsistent routing row, that ON CONFLICT keeps
formation idempotent, and that JSONB round-trips as the store's callers expect.
"""

from __future__ import annotations

import uuid

import pytest

from shared.sdk.agent_team.capabilities import (
    FIX_DEFECTS,
    GENERATE_CODE,
    VERIFY_QUALITY,
    AgentCapabilityDeclaration,
)
from shared.sdk.agent_team.router import RoutingDecision
from shared.sdk.agent_team.store import TeamStore

_DB_SKIP = "no reachable PostgreSQL with migration 036 applied; skipping team store test"


async def _store_or_skip() -> TeamStore:
    store = TeamStore()
    try:
        conn = await store._connect()
    except Exception:
        pytest.skip(_DB_SKIP)
    try:
        exists = await conn.fetchval("SELECT to_regclass('public.actor_principals')")
    finally:
        await conn.close()
    if exists is None:
        pytest.skip(_DB_SKIP)
    return store


async def _project(store: TeamStore) -> str:
    """A scratch project row. Team tables are FK-bound to projects, as the contract requires."""
    conn = await store._connect()
    try:
        return str(
            await conn.fetchval(
                "INSERT INTO projects (title, summary) VALUES ($1,$2) RETURNING id",
                f"at-m2-store-test-{uuid.uuid4().hex[:8]}",
                "AT-M2 team store test project",
            )
        )
    finally:
        await conn.close()


def _declaration(key: str, role: str, caps: tuple[str, ...]) -> AgentCapabilityDeclaration:
    return AgentCapabilityDeclaration(
        agent_key=f"{key}-{uuid.uuid4().hex[:8]}",
        role=role,
        capabilities=caps,
        transport_stream=f"stream.{role}",
    )


async def test_registering_an_agent_is_idempotent_and_mints_one_principal():
    store = await _store_or_skip()
    declaration = _declaration("dev", "development", (GENERATE_CODE,))
    first = await store.register_agent(declaration)
    second = await store.register_agent(declaration)
    assert first["principal_id"] == second["principal_id"]
    assert first["agent_id"] == second["agent_id"]
    assert second["capabilities"] == (GENERATE_CODE,)


async def test_forming_a_team_twice_reactivates_rather_than_duplicating():
    store = await _store_or_skip()
    project = await _project(store)
    declaration = _declaration("qa", "qa", (VERIFY_QUALITY,))
    await store.register_agent(declaration)
    await store.add_member(project, declaration.agent_key)
    await store.set_membership_state(project, declaration.agent_key, "left")
    again = await store.add_member(project, declaration.agent_key)
    assert again["membership_state"] == "active"
    assert again["left_at"] is None
    assert len(await store.list_team(project)) == 1


async def test_leaving_preserves_the_row_so_past_work_stays_attributable():
    store = await _store_or_skip()
    project = await _project(store)
    declaration = _declaration("devops", "devops", (FIX_DEFECTS,))
    await store.register_agent(declaration)
    await store.add_member(project, declaration.agent_key)
    left = await store.set_membership_state(project, declaration.agent_key, "left")
    assert left["membership_state"] == "left"
    assert left["left_at"] is not None
    assert [m["agent_key"] for m in await store.list_team(project)] == [declaration.agent_key]


async def test_the_database_rejects_an_unaddressed_message():
    """chk_team_messages_addressed, enforced by the schema rather than only by the model."""
    import asyncpg

    store = await _store_or_skip()
    project = await _project(store)
    declaration = _declaration("req", "requirement", (GENERATE_CODE,))
    profile = await store.register_agent(declaration)
    thread = await store.open_thread(
        project_id=project, goal_ref="Build a todo API", thread_type="planning"
    )
    with pytest.raises(asyncpg.PostgresError):
        await store.post_message(
            {
                "thread_id": str(thread["thread_id"]),
                "project_id": project,
                "sender_principal_id": str(profile["principal_id"]),
                "message_type": "message",
                "summary": "who is this for?",
                "recipient_team": False,
            }
        )


async def test_an_addressed_message_round_trips_with_its_jsonb():
    store = await _store_or_skip()
    project = await _project(store)
    sender = await store.register_agent(_declaration("req", "requirement", (GENERATE_CODE,)))
    recipient = await store.register_agent(_declaration("dev", "development", (GENERATE_CODE,)))
    thread = await store.open_thread(
        project_id=project, goal_ref="Build a todo API", thread_type="planning"
    )
    posted = await store.post_message(
        {
            "thread_id": str(thread["thread_id"]),
            "project_id": project,
            "sender_principal_id": str(sender["principal_id"]),
            "recipient_principal_id": str(recipient["principal_id"]),
            "message_type": "proposal",
            "summary": "Todo API needs create/list/delete endpoints",
            "content": {"endpoints": ["create", "list", "delete"]},
            "artifact_refs": {"requirement_spec": "spec-1"},
            "audit_ref": "audit-1",
        }
    )
    assert posted["content"] == {"endpoints": ["create", "list", "delete"]}
    assert posted["artifact_refs"] == {"requirement_spec": "spec-1"}
    listed = await store.list_messages(project, thread_id=str(thread["thread_id"]))
    assert [str(m["message_id"]) for m in listed] == [str(posted["message_id"])]


async def test_the_database_rejects_a_routing_row_that_contradicts_itself():
    """chk_routing_selected_consistency: 'no eligible agent' may never name one."""
    import asyncpg

    store = await _store_or_skip()
    project = await _project(store)
    profile = await store.register_agent(_declaration("qa", "qa", (VERIFY_QUALITY,)))
    contradictory = RoutingDecision(
        outcome="no_eligible_agent",
        requested_capability=VERIFY_QUALITY,
        reason="nobody is eligible, but a principal is named anyway",
        selected_principal_id=str(profile["principal_id"]),
    )
    with pytest.raises(asyncpg.PostgresError):
        await store.record_routing_decision(project_id=project, decision=contradictory)


async def test_a_routing_decision_persists_its_candidate_set():
    store = await _store_or_skip()
    project = await _project(store)
    profile = await store.register_agent(_declaration("qa", "qa", (VERIFY_QUALITY,)))
    decision = RoutingDecision(
        outcome="selected",
        requested_capability=VERIFY_QUALITY,
        reason="the only active team member declaring verify_quality",
        selected_principal_id=str(profile["principal_id"]),
        selected_role="qa",
        selected_stream="stream.qa",
        candidates_considered=(
            {"agent_key": "qa", "eligible": True, "rejected_because": None},
            {"agent_key": "dev", "eligible": False, "rejected_because": "capability_not_declared"},
        ),
    )
    record = await store.record_routing_decision(
        project_id=project, decision=decision, task_id="t-store-1"
    )
    assert record["outcome"] == "selected"
    assert len(record["candidates_considered"]) == 2
    history = await store.list_routing_decisions(project)
    assert [h["routing_decision_id"] for h in history] == [record["routing_decision_id"]]


async def test_routing_candidates_reflect_the_team_as_the_router_sees_it():
    store = await _store_or_skip()
    project = await _project(store)
    qa = _declaration("qa", "qa", (VERIFY_QUALITY,))
    dev = _declaration("dev", "development", (GENERATE_CODE,))
    for declaration in (qa, dev):
        await store.register_agent(declaration)
        await store.add_member(project, declaration.agent_key)
    candidates = {c.agent_key: c for c in await store.routing_candidates(project)}
    assert candidates[qa.agent_key].capabilities == frozenset({VERIFY_QUALITY})
    assert candidates[qa.agent_key].ineligibility(VERIFY_QUALITY) == ""
    assert candidates[dev.agent_key].ineligibility(VERIFY_QUALITY) == "capability_not_declared"

    await store.set_membership_state(project, qa.agent_key, "paused")
    paused = {c.agent_key: c for c in await store.routing_candidates(project)}
    assert paused[qa.agent_key].ineligibility(VERIFY_QUALITY) == "membership_state=paused"


async def test_a_handoff_transfers_ownership_only_once():
    store = await _store_or_skip()
    project = await _project(store)
    dev = await store.register_agent(_declaration("dev", "development", (GENERATE_CODE,)))
    qa = await store.register_agent(_declaration("qa", "qa", (VERIFY_QUALITY,)))
    offered = await store.offer_handoff(
        {
            "project_id": project,
            "from_principal_id": str(dev["principal_id"]),
            "to_principal_id": str(qa["principal_id"]),
            "reason": "implementation complete, verification needed",
            "context_refs": {"workspace": "ws-1"},
        }
    )
    assert offered["state"] == "offered"
    assert offered["context_refs"] == {"workspace": "ws-1"}
    accepted = await store.accept_handoff(str(offered["handoff_id"]))
    assert accepted["state"] == "accepted" and accepted["accepted_at"] is not None
    assert await store.accept_handoff(str(offered["handoff_id"])) is None
