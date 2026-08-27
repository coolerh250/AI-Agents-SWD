"""Step AT-M3.2-REMEDIATION-1 -- controlled lifecycle (D1) and project-safe numbering (D2).

Both defects AT-M3.2 Validation 1 raised, asserted against a real PostgreSQL because both are
database guarantees:

D1  the approved pipeline transitions the SAME revision draft -> accepted
    (planning-and-plan-revision-model.md section 4; "immutable once accepted" in
    source-of-truth-and-lineage-model.md). The first cut froze status from creation, which made
    that stage unreachable. Exactly one transition is authorized, and nothing else -- including a
    regression to draft -- may happen, even from raw SQL.

D2  revision_number is monotonic per PROJECT, so two Goals of one project share a sequence.
    Computing max()+1 without serialising made independent Goal lineages collide, and the
    collision was then misreported as "goal already has an initial revision". The project row is
    now locked for the numbering critical section.

Skips when no database is reachable, following the existing store-test convention.
"""

from __future__ import annotations

import asyncio
import uuid

import asyncpg
import pytest

from shared.sdk.agent_planning.models import (
    PlanLineageError,
    PlanRevisionLifecycleError,
    StalePlanRevisionError,
)
from shared.sdk.agent_planning.service import PlanningService
from shared.sdk.agent_planning.store import PlanningStore

_DB_SKIP = "no reachable PostgreSQL with migration 038 applied; skipping planning lifecycle test"


async def _store_or_skip() -> PlanningStore:
    store = PlanningStore()
    try:
        conn = await store._connect()
    except Exception:
        pytest.skip(_DB_SKIP)
    try:
        ok = await conn.fetchval("SELECT to_regclass('public.plan_revisions')")
        fn = await conn.fetchval("SELECT to_regproc('plan_revisions_enforce_lifecycle')")
    finally:
        await conn.close()
    if ok is None or fn is None:
        pytest.skip(_DB_SKIP)
    return store


def _plan(objective: str = "o") -> dict:
    return {"objective": objective, "steps": [], "constraints": [], "acceptance_criteria": []}


async def _project(store: PlanningStore, tag: str = "lifecycle") -> str:
    conn = await store._connect()
    try:
        return str(
            await conn.fetchval(
                "INSERT INTO projects (title) VALUES ($1) RETURNING id",
                f"at-m3-2-{tag}-{uuid.uuid4().hex[:8]}",
            )
        )
    finally:
        await conn.close()


async def _principal(store: PlanningStore) -> str:
    conn = await store._connect()
    try:
        return str(
            await conn.fetchval(
                """
                INSERT INTO actor_principals (principal_type, display_name)
                VALUES ('runtime_agent', $1) RETURNING principal_id
                """,
                f"at-m3-2-rm-{uuid.uuid4().hex[:8]}",
            )
        )
    finally:
        await conn.close()


async def _goal(store: PlanningStore, project_id: str, principal_id: str) -> str:
    goal = await store.create_goal(
        {"project_id": project_id, "statement": "G", "created_by": principal_id}
    )
    return str(goal["goal_id"])


async def _root(store: PlanningStore, goal_id: str, principal_id: str, **kw) -> dict:
    return await store.create_initial_revision(
        {"goal_id": goal_id, "created_by": principal_id, "plan": _plan(), **kw}
    )


# =================================================================================================
# D1 -- controlled lifecycle
# =================================================================================================


async def test_draft_transitions_to_accepted():
    """The stage the approved pipeline requires, on the SAME revision."""
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    root = await _root(store, goal_id, principal_id)
    assert root["status"] == "draft"

    accepted = await store.accept_revision(root["plan_revision_id"])
    assert accepted["status"] == "accepted"
    assert str(accepted["plan_revision_id"]) == str(root["plan_revision_id"])


async def test_acceptance_changes_nothing_but_status():
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    root = await _root(store, goal_id, principal_id)

    before = await store.get_revision(root["plan_revision_id"])
    after = await store.accept_revision(root["plan_revision_id"])
    for field in (
        "plan_revision_id",
        "project_id",
        "goal_id",
        "revision_number",
        "created_by",
        "reason",
        "supersedes_revision_id",
        "plan",
        "diff",
        "trace_ref",
        "created_at",
    ):
        assert before[field] == after[field], f"{field} changed during acceptance"
    assert before["status"] == "draft" and after["status"] == "accepted"


async def test_accepting_twice_is_a_no_op_not_an_error():
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    root = await _root(store, goal_id, principal_id)

    first = await store.accept_revision(root["plan_revision_id"])
    second = await store.accept_revision(root["plan_revision_id"])
    assert first == second


async def test_accepting_an_unknown_revision_returns_none():
    store = await _store_or_skip()
    assert await store.accept_revision(str(uuid.uuid4())) is None


@pytest.mark.parametrize("created_status", ["proposed", "rejected"])
async def test_no_transition_is_authorized_out_of_proposed_or_rejected(created_status):
    """The architecture names exactly one transition; the others are creation-time values only."""
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    root = await _root(store, goal_id, principal_id, status=created_status)
    with pytest.raises(PlanRevisionLifecycleError):
        await store.accept_revision(root["plan_revision_id"])


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        ("accepted", "draft"),
        ("accepted", "rejected"),
        ("accepted", "proposed"),
        ("draft", "rejected"),
        ("draft", "proposed"),
        ("proposed", "accepted"),
        ("rejected", "accepted"),
    ],
)
async def test_raw_sql_cannot_make_an_unauthorized_transition(from_status, to_status):
    """Direct SQL must not bypass the lifecycle -- the trigger is the authority, not the service."""
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    start = "draft" if from_status == "accepted" else from_status
    root = await _root(store, goal_id, principal_id, status=start)
    if from_status == "accepted":
        await store.accept_revision(root["plan_revision_id"])

    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                "UPDATE plan_revisions SET status=$2 WHERE plan_revision_id=$1",
                root["plan_revision_id"],
                to_status,
            )
    finally:
        await conn.close()


async def test_raw_sql_draft_to_accepted_is_the_one_permitted_status_write():
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    root = await _root(store, goal_id, principal_id)
    conn = await store._connect()
    try:
        await conn.execute(
            "UPDATE plan_revisions SET status='accepted' WHERE plan_revision_id=$1",
            root["plan_revision_id"],
        )
    finally:
        await conn.close()
    assert (await store.get_revision(root["plan_revision_id"]))["status"] == "accepted"


@pytest.mark.parametrize("accept_first", [False, True])
@pytest.mark.parametrize(
    "column,value",
    [
        ("plan", '{"objective":"rewritten","steps":[]}'),
        ("diff", '{"steps_added":["x"]}'),
        ("reason", "scope_correction"),
        ("revision_number", 99),
        ("trace_ref", "t2"),
    ],
)
async def test_plan_and_lineage_stay_immutable_before_and_after_acceptance(
    accept_first, column, value
):
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    root = await _root(store, goal_id, principal_id)
    if accept_first:
        await store.accept_revision(root["plan_revision_id"])

    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                f"UPDATE plan_revisions SET {column}=$2 WHERE plan_revision_id=$1",
                root["plan_revision_id"],
                value,
            )
    finally:
        await conn.close()


async def test_audit_ref_stays_write_once_after_the_lifecycle_change():
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    root = await _root(store, goal_id, principal_id)
    conn = await store._connect()
    try:
        await conn.execute(
            "UPDATE plan_revisions SET audit_ref='a1' WHERE plan_revision_id=$1",
            root["plan_revision_id"],
        )
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                "UPDATE plan_revisions SET audit_ref='a2' WHERE plan_revision_id=$1",
                root["plan_revision_id"],
            )
    finally:
        await conn.close()


async def test_supersession_stays_derived_after_acceptance():
    """Accepting a revision must not disturb the lineage-derived current-revision answer."""
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    root = await _root(store, goal_id, principal_id)
    await store.accept_revision(root["plan_revision_id"])

    successor = await store.create_successor_revision(
        {
            "goal_id": goal_id,
            "expected_current_revision_id": str(root["plan_revision_id"]),
            "created_by": principal_id,
            "plan": _plan("next"),
            "diff": {},
            "reason": "team_decision",
        }
    )
    assert await store.is_current(root["plan_revision_id"]) is False
    assert await store.is_current(successor["plan_revision_id"]) is True
    # The accepted predecessor keeps its own status; supersession is never written onto it.
    assert (await store.get_revision(root["plan_revision_id"]))["status"] == "accepted"
    current = await store.get_current_revision(goal_id)
    assert str(current["plan_revision_id"]) == str(successor["plan_revision_id"])


async def test_team_decision_fk_still_binds_an_accepted_revision():
    """The approved acceptance linkage: a TeamDecision names the revision it accepted."""
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    root = await _root(store, goal_id, principal_id)
    accepted = await store.accept_revision(root["plan_revision_id"])

    conn = await store._connect()
    try:
        thread_id = await conn.fetchval(
            """
            INSERT INTO conversation_threads (project_id, goal_ref, thread_type)
            VALUES ($1,$2,'planning') RETURNING thread_id
            """,
            uuid.UUID(project_id),
            f"goal:{goal_id}",
        )
        await conn.execute(
            """
            INSERT INTO team_decisions
              (project_id, thread_id, proposed_by, selected_option, rationale_summary,
               resulting_plan_revision_id)
            VALUES ($1,$2,$3,'accept-plan','the team accepted the plan',$4)
            """,
            uuid.UUID(project_id),
            thread_id,
            uuid.UUID(principal_id),
            accepted["plan_revision_id"],
        )
        bound = await conn.fetchval(
            "SELECT count(*) FROM team_decisions WHERE resulting_plan_revision_id=$1",
            accepted["plan_revision_id"],
        )
    finally:
        await conn.close()
    assert bound == 1


async def test_service_acceptance_audits_identifiers_only():
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    written: list[dict] = []

    class _Audit:
        def build_audit_event(self, **kwargs):
            return kwargs

        async def write_audit_event(self, event):
            written.append(event)
            return "audit-1"

    service = PlanningService(store=store, audit_client=_Audit())
    row = await service.create_initial_revision(
        goal_id=goal_id, created_by=principal_id, plan=_plan("SECRET-OBJECTIVE")
    )
    await service.accept_revision(str(row["plan_revision_id"]))

    event = written[-1]
    assert event["decision_type"] == "plan_revision_accepted"
    assert event["result"] == "accepted"
    assert "SECRET-OBJECTIVE" not in str(event)
    assert set(event["artifact_refs"]) == {
        "plan_revision_id",
        "goal_id",
        "revision_number",
        "status",
    }


# =================================================================================================
# D2 -- concurrency-safe per-project revision numbering
# =================================================================================================


async def test_concurrent_roots_across_goals_of_one_project_all_succeed():
    """D2's headline: 8 different Goals, one Project, 8 independent connections, 8 successes."""
    store = await _store_or_skip()
    project_id = await _project(store, "d2-roots")
    principal_id = await _principal(store)
    goal_ids = [await _goal(store, project_id, principal_id) for _ in range(8)]

    async def create(goal_id: str):
        try:
            row = await PlanningStore().create_initial_revision(
                {"goal_id": goal_id, "created_by": principal_id, "plan": _plan()}
            )
            return row["revision_number"]
        except Exception as exc:  # surfaced verbatim so a failure names itself
            return exc

    results = await asyncio.gather(*(create(g) for g in goal_ids))
    failures = [r for r in results if isinstance(r, Exception)]
    assert failures == [], f"independent goals collided: {failures}"
    numbers = sorted(results)
    assert len(set(numbers)) == 8, f"revision numbers were not unique: {numbers}"

    for goal_id in goal_ids:
        assert await store.get_current_revision(goal_id) is not None


async def test_concurrent_successors_across_goals_of_one_project_all_succeed():
    store = await _store_or_skip()
    project_id = await _project(store, "d2-succ")
    principal_id = await _principal(store)
    lineages = []
    for _ in range(8):
        goal_id = await _goal(store, project_id, principal_id)
        root = await _root(store, goal_id, principal_id)
        lineages.append((goal_id, str(root["plan_revision_id"])))

    async def successor(goal_id: str, root_id: str):
        try:
            row = await PlanningStore().create_successor_revision(
                {
                    "goal_id": goal_id,
                    "expected_current_revision_id": root_id,
                    "created_by": principal_id,
                    "plan": _plan("next"),
                    "diff": {},
                    "reason": "team_decision",
                }
            )
            return row["revision_number"]
        except Exception as exc:
            return exc

    results = await asyncio.gather(*(successor(g, r) for g, r in lineages))
    failures = [r for r in results if isinstance(r, Exception)]
    assert failures == [], f"independent lineages collided: {failures}"
    assert len(set(results)) == 8


async def test_same_predecessor_race_still_yields_exactly_one_successor():
    """The D2 fix must not weaken the one-successor-per-predecessor invariant."""
    store = await _store_or_skip()
    project_id = await _project(store, "d2-race")
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    root = await _root(store, goal_id, principal_id)
    root_id = str(root["plan_revision_id"])
    before = await store.get_revision(root_id)

    async def attempt(index: int):
        try:
            return await PlanningStore().create_successor_revision(
                {
                    "goal_id": goal_id,
                    "expected_current_revision_id": root_id,
                    "created_by": principal_id,
                    "plan": _plan(f"racer-{index}"),
                    "diff": {},
                    "reason": "team_decision",
                }
            )
        except StalePlanRevisionError as exc:
            return exc

    results = await asyncio.gather(*(attempt(i) for i in range(8)))
    winners = [r for r in results if not isinstance(r, Exception)]
    losers = [r for r in results if isinstance(r, StalePlanRevisionError)]
    assert len(winners) == 1
    assert len(losers) == 7

    history = await store.list_revisions(goal_id)
    assert len(history) == 2
    assert len([r for r in history if r["supersedes_revision_id"]]) == 1
    assert await store.get_revision(root_id) == before


async def test_separate_projects_do_not_serialize_against_each_other():
    """The lock is per project row, so unrelated projects never contend."""
    store = await _store_or_skip()
    principal_id = await _principal(store)
    goals = []
    for index in range(8):
        project_id = await _project(store, f"d2-iso{index}")
        goals.append(await _goal(store, project_id, principal_id))

    async def create(goal_id: str):
        try:
            row = await PlanningStore().create_initial_revision(
                {"goal_id": goal_id, "created_by": principal_id, "plan": _plan()}
            )
            return row["revision_number"]
        except Exception as exc:
            return exc

    results = await asyncio.gather(*(create(g) for g in goals))
    assert [r for r in results if isinstance(r, Exception)] == []
    # Each project has its own sequence, so every one of them starts at 1.
    assert set(results) == {1}


async def test_duplicate_root_is_reported_as_a_duplicate_root():
    """The misdiagnosis half of D2: this message must only appear when it is true."""
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)
    await _root(store, goal_id, principal_id)

    with pytest.raises(PlanLineageError) as excinfo:
        await store.create_initial_revision(
            {"goal_id": goal_id, "created_by": principal_id, "plan": _plan()}
        )
    assert "already has an initial revision" in str(excinfo.value)


async def test_concurrent_roots_never_report_a_false_duplicate_root():
    store = await _store_or_skip()
    project_id = await _project(store, "d2-nofalse")
    principal_id = await _principal(store)
    goal_ids = [await _goal(store, project_id, principal_id) for _ in range(8)]

    async def create(goal_id: str):
        try:
            await PlanningStore().create_initial_revision(
                {"goal_id": goal_id, "created_by": principal_id, "plan": _plan()}
            )
            return None
        except Exception as exc:
            return str(exc)

    messages = [m for m in await asyncio.gather(*(create(g) for g in goal_ids)) if m]
    assert messages == [], f"a goal with no revision was told it already had one: {messages}"


async def test_rollback_releases_the_project_lock():
    """A failed allocation must not leave the project row locked for the next caller."""
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal_id = await _goal(store, project_id, principal_id)

    with pytest.raises(ValueError):
        await store.create_initial_revision(
            {
                "goal_id": goal_id,
                "created_by": principal_id,
                "plan": {"objective": "o", "chain_of_thought": "leak"},
            }
        )
    # The next allocation on the same project must proceed without blocking.
    row = await asyncio.wait_for(
        store.create_initial_revision(
            {"goal_id": goal_id, "created_by": principal_id, "plan": _plan()}
        ),
        timeout=10,
    )
    assert row["revision_number"] == 1
