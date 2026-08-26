"""Step AT-M3.2 -- PlanningStore against a real PostgreSQL.

Follows the existing store-test convention (tests/test_at_m2_team_store.py,
tests/test_at_m3_1_reasoning_store.py): skip when no database is reachable, so the suite stays
runnable on a workstation while still exercising the real asyncpg path wherever migration 038 has
been applied.

These are the assertions an in-memory fake cannot make honestly:

* that ``plan_revisions`` is append-only at the DATABASE layer, so a raw SQL caller cannot rewrite
  a revision either;
* that a cross-goal or non-existent predecessor is structurally unrepresentable rather than merely
  checked in Python;
* that ``uq_plan_revisions_one_successor`` genuinely permits one successor per predecessor under
  REAL concurrent writers, not just under Python's cooperative scheduling.

The last one is the load-bearing acceptance property for this slice, and it is asserted with
independent asyncpg connections racing the same predecessor.
"""

from __future__ import annotations

import asyncio
import uuid

import asyncpg
import pytest

from shared.sdk.agent_planning.models import (
    PlanLineageError,
    StalePlanRevisionError,
)
from shared.sdk.agent_planning.service import PlanningService
from shared.sdk.agent_planning.store import PlanningStore

_DB_SKIP = "no reachable PostgreSQL with migration 038 applied; skipping planning store test"


async def _store_or_skip() -> PlanningStore:
    store = PlanningStore()
    try:
        conn = await store._connect()
    except Exception:
        pytest.skip(_DB_SKIP)
    try:
        exists = await conn.fetchval("SELECT to_regclass('public.plan_revisions')")
        goals = await conn.fetchval("SELECT to_regclass('public.goals')")
    finally:
        await conn.close()
    if exists is None or goals is None:
        pytest.skip(_DB_SKIP)
    return store


async def _project(store: PlanningStore) -> str:
    conn = await store._connect()
    try:
        return str(
            await conn.fetchval(
                "INSERT INTO projects (title, summary) VALUES ($1,$2) RETURNING id",
                f"at-m3-2-store-test-{uuid.uuid4().hex[:8]}",
                "AT-M3.2 planning store test project",
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
                f"at-m3-2-planner-{uuid.uuid4().hex[:8]}",
            )
        )
    finally:
        await conn.close()


def _plan(objective: str = "Ship the inbox", extra_step: str | None = None) -> dict:
    steps = [
        {
            "step_key": "design",
            "title": "Design the inbox",
            "description": None,
            "required_capabilities": ["design_review"],
            "expected_outputs": ["design brief"],
            "depends_on": [],
            "constraints": [],
            "intended_owner_role": None,
        }
    ]
    if extra_step:
        steps.append(
            {
                "step_key": extra_step,
                "title": f"Step {extra_step}",
                "description": None,
                "required_capabilities": [],
                "expected_outputs": [],
                "depends_on": ["design"],
                "constraints": [],
                "intended_owner_role": None,
            }
        )
    return {
        "objective": objective,
        "steps": steps,
        "constraints": [],
        "acceptance_criteria": ["operator can read the inbox"],
    }


async def _goal_with_root(store: PlanningStore) -> tuple[str, str, str]:
    """(goal_id, principal_id, root_revision_id)."""
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal = await store.create_goal(
        {
            "project_id": project_id,
            "statement": "Deliver a clarification inbox",
            "acceptance_criteria": ["operator can read it"],
            "constraints": ["no production action"],
            "created_by": principal_id,
        }
    )
    root = await store.create_initial_revision(
        {"goal_id": str(goal["goal_id"]), "created_by": principal_id, "plan": _plan()}
    )
    return str(goal["goal_id"]), principal_id, str(root["plan_revision_id"])


# --- goal persistence and lineage ---------------------------------------------------------------


async def test_goal_persists_with_project_lineage():
    store = await _store_or_skip()
    project_id = await _project(store)
    principal_id = await _principal(store)
    goal = await store.create_goal(
        {
            "project_id": project_id,
            "statement": "Deliver a clarification inbox",
            "acceptance_criteria": ["operator can read it"],
            "constraints": ["no production action"],
            "created_by": principal_id,
        }
    )
    assert str(goal["project_id"]) == project_id
    assert goal["status"] == "draft"
    assert goal["acceptance_criteria"] == ["operator can read it"]

    read_back = await store.get_goal(goal["goal_id"])
    assert read_back is not None
    assert read_back["statement"] == "Deliver a clarification inbox"


async def test_goal_requires_a_real_project():
    store = await _store_or_skip()
    principal_id = await _principal(store)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await store.create_goal(
            {
                "project_id": str(uuid.uuid4()),
                "statement": "orphan goal",
                "created_by": principal_id,
            }
        )


# --- revision creation ---------------------------------------------------------------------------


async def test_initial_revision_is_root_and_current():
    store = await _store_or_skip()
    goal_id, _principal_id, root_id = await _goal_with_root(store)
    root = await store.get_revision(root_id)
    assert root["reason"] == "initial"
    assert root["supersedes_revision_id"] is None
    assert root["diff"] == {}
    current = await store.get_current_revision(goal_id)
    assert str(current["plan_revision_id"]) == root_id


async def test_a_goal_may_have_only_one_root_revision():
    store = await _store_or_skip()
    goal_id, principal_id, _root = await _goal_with_root(store)
    with pytest.raises(PlanLineageError):
        await store.create_initial_revision(
            {"goal_id": goal_id, "created_by": principal_id, "plan": _plan()}
        )


async def test_successor_appends_and_moves_current():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    successor = await store.create_successor_revision(
        {
            "goal_id": goal_id,
            "expected_current_revision_id": root_id,
            "created_by": principal_id,
            "plan": _plan(extra_step="build"),
            "diff": {"steps_added": ["build"]},
            "reason": "team_decision",
        }
    )
    assert str(successor["supersedes_revision_id"]) == root_id
    assert successor["revision_number"] > 1
    current = await store.get_current_revision(goal_id)
    assert str(current["plan_revision_id"]) == str(successor["plan_revision_id"])
    assert await store.is_current(root_id) is False
    assert await store.is_current(successor["plan_revision_id"]) is True


async def test_successor_creation_does_not_mutate_the_predecessor():
    """The strongest form of immutability: the predecessor row is byte-identical afterwards."""
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    before = await store.get_revision(root_id)
    await store.create_successor_revision(
        {
            "goal_id": goal_id,
            "expected_current_revision_id": root_id,
            "created_by": principal_id,
            "plan": _plan(objective="changed"),
            "diff": {"objective_changed": True},
            "reason": "goal_changed",
        }
    )
    after = await store.get_revision(root_id)
    assert before == after


# --- immutability, enforced by the database -------------------------------------------------------


@pytest.mark.parametrize(
    "column,value",
    [
        ("plan", '{"objective":"rewritten","steps":[]}'),
        ("status", "accepted"),
        ("reason", "scope_correction"),
        ("revision_number", 99),
    ],
)
async def test_raw_sql_cannot_update_a_revision(column, value):
    """A direct psql caller must not be able to rewrite history either."""
    store = await _store_or_skip()
    _goal_id, _principal_id, root_id = await _goal_with_root(store)
    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                f"UPDATE plan_revisions SET {column}=$2 WHERE plan_revision_id=$1",
                uuid.UUID(root_id),
                value,
            )
    finally:
        await conn.close()


async def test_raw_sql_cannot_repoint_supersession():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    successor = await store.create_successor_revision(
        {
            "goal_id": goal_id,
            "expected_current_revision_id": root_id,
            "created_by": principal_id,
            "plan": _plan(extra_step="build"),
            "diff": {},
            "reason": "team_decision",
        }
    )
    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                "UPDATE plan_revisions SET supersedes_revision_id=NULL WHERE plan_revision_id=$1",
                successor["plan_revision_id"],
            )
    finally:
        await conn.close()


# --- lineage integrity ------------------------------------------------------------------------------


async def test_cross_goal_predecessor_is_rejected():
    store = await _store_or_skip()
    _goal_a, principal_a, root_a = await _goal_with_root(store)
    goal_b, principal_b, _root_b = await _goal_with_root(store)
    with pytest.raises(PlanLineageError):
        await store.create_successor_revision(
            {
                "goal_id": goal_b,
                "expected_current_revision_id": root_a,
                "created_by": principal_b,
                "plan": _plan(),
                "diff": {},
                "reason": "team_decision",
            }
        )
    assert principal_a  # the other goal's principal is untouched


async def test_missing_predecessor_is_rejected():
    store = await _store_or_skip()
    goal_id, principal_id, _root = await _goal_with_root(store)
    with pytest.raises(PlanLineageError):
        await store.create_successor_revision(
            {
                "goal_id": goal_id,
                "expected_current_revision_id": str(uuid.uuid4()),
                "created_by": principal_id,
                "plan": _plan(),
                "diff": {},
                "reason": "team_decision",
            }
        )


async def test_duplicate_revision_number_is_rejected_by_the_database():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    root = await store.get_revision(root_id)
    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                """
                INSERT INTO plan_revisions
                  (project_id, goal_id, revision_number, created_by, reason, status, plan)
                VALUES ($1,$2,$3,$4,'initial','draft','{}'::jsonb)
                """,
                root["project_id"],
                root["goal_id"],
                root["revision_number"],
                uuid.UUID(principal_id),
            )
    finally:
        await conn.close()
    assert goal_id


async def test_self_supersession_is_rejected_by_the_database():
    store = await _store_or_skip()
    _goal_id, principal_id, root_id = await _goal_with_root(store)
    root = await store.get_revision(root_id)
    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                """
                INSERT INTO plan_revisions
                  (plan_revision_id, project_id, goal_id, revision_number, created_by, reason,
                   supersedes_revision_id, status, plan)
                VALUES ($1,$2,$3,$4,$5,'team_decision',$1,'draft','{}'::jsonb)
                """,
                uuid.UUID(root_id),
                root["project_id"],
                root["goal_id"],
                root["revision_number"] + 500,
                uuid.UUID(principal_id),
            )
    finally:
        await conn.close()


# --- stale-plan protection ---------------------------------------------------------------------


async def test_stale_expected_revision_fails_closed():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    await store.create_successor_revision(
        {
            "goal_id": goal_id,
            "expected_current_revision_id": root_id,
            "created_by": principal_id,
            "plan": _plan(extra_step="build"),
            "diff": {},
            "reason": "team_decision",
        }
    )
    # root is no longer current -- a second successor from it must be refused, not rebased.
    with pytest.raises(StalePlanRevisionError) as excinfo:
        await store.create_successor_revision(
            {
                "goal_id": goal_id,
                "expected_current_revision_id": root_id,
                "created_by": principal_id,
                "plan": _plan(objective="a third opinion"),
                "diff": {},
                "reason": "scope_correction",
            }
        )
    assert excinfo.value.expected_revision_id == root_id
    assert excinfo.value.actual_revision_id != root_id

    history = await store.list_revisions(goal_id)
    assert len(history) == 2, "the refused successor must not have been written"


async def test_concurrent_successors_yield_exactly_one_winner():
    """THE load-bearing acceptance property for AT-M3.2.

    Eight independent asyncpg connections race to derive a successor from the same current
    revision. Exactly one may become valid; every other caller must receive fail-closed staleness
    and must not have written a row.
    """
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    racers = 8

    async def attempt(index: int):
        # A fresh store per racer => a fresh connection, so this is real database concurrency and
        # not one connection's serialised statements.
        racer_store = PlanningStore()
        try:
            return await racer_store.create_successor_revision(
                {
                    "goal_id": goal_id,
                    "expected_current_revision_id": root_id,
                    "created_by": principal_id,
                    "plan": _plan(objective=f"racer {index}"),
                    "diff": {"objective_changed": True},
                    "reason": "team_decision",
                }
            )
        except StalePlanRevisionError as exc:
            return exc

    results = await asyncio.gather(*(attempt(i) for i in range(racers)))
    winners = [r for r in results if not isinstance(r, StalePlanRevisionError)]
    losers = [r for r in results if isinstance(r, StalePlanRevisionError)]

    assert len(winners) == 1, f"expected exactly one successor, got {len(winners)}"
    assert len(losers) == racers - 1

    history = await store.list_revisions(goal_id)
    assert len(history) == 2, f"exactly one successor row must exist, found {len(history) - 1}"
    assert str(history[1]["plan_revision_id"]) == str(winners[0]["plan_revision_id"])

    successors = [row for row in history if row["supersedes_revision_id"]]
    assert len(successors) == 1
    current = await store.get_current_revision(goal_id)
    assert str(current["plan_revision_id"]) == str(winners[0]["plan_revision_id"])


async def test_concurrent_successors_leave_the_predecessor_untouched():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    before = await store.get_revision(root_id)

    async def attempt(index: int):
        try:
            return await PlanningStore().create_successor_revision(
                {
                    "goal_id": goal_id,
                    "expected_current_revision_id": root_id,
                    "created_by": principal_id,
                    "plan": _plan(objective=f"racer {index}"),
                    "diff": {},
                    "reason": "team_decision",
                }
            )
        except StalePlanRevisionError as exc:
            return exc

    await asyncio.gather(*(attempt(i) for i in range(4)))
    assert await store.get_revision(root_id) == before


# --- history, current resolution and diff ---------------------------------------------------------


async def test_history_is_append_only_and_ordered():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    current = root_id
    for index, reason in enumerate(["team_decision", "goal_changed", "debug_plan_invalid"]):
        row = await store.create_successor_revision(
            {
                "goal_id": goal_id,
                "expected_current_revision_id": current,
                "created_by": principal_id,
                "plan": _plan(objective=f"revision {index + 2}"),
                "diff": {"objective_changed": True},
                "reason": reason,
            }
        )
        current = str(row["plan_revision_id"])

    history = await store.list_revisions(goal_id)
    assert len(history) == 4
    numbers = [row["revision_number"] for row in history]
    assert numbers == sorted(numbers), "history must be ordered by revision number"
    assert len(set(numbers)) == 4, "revision numbers must be unique within the lineage"
    assert history[0]["reason"] == "initial"
    assert [row["reason"] for row in history[1:]] == [
        "team_decision",
        "goal_changed",
        "debug_plan_invalid",
    ]
    assert str((await store.get_current_revision(goal_id))["plan_revision_id"]) == current


async def test_service_computes_the_diff_server_side():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    service = PlanningService(store=store)
    row = await service.create_successor_revision(
        goal_id=goal_id,
        expected_current_revision_id=root_id,
        created_by=principal_id,
        plan=_plan(extra_step="build"),
        reason="team_decision",
        rationale="the team split design from build",
    )
    diff = row["diff"]
    assert diff["steps_added"] == ["build"]
    assert diff["dependencies_added"] == ["design->build"]
    assert diff["rationale"] == "the team split design from build"

    fetched = await service.get_diff(str(row["plan_revision_id"]))
    assert fetched["diff"] == diff
    assert fetched["supersedes_revision_id"] == root_id


async def test_root_revision_diff_is_empty_not_missing():
    store = await _store_or_skip()
    _goal_id, _principal_id, root_id = await _goal_with_root(store)
    fetched = await PlanningService(store=store).get_diff(root_id)
    assert fetched is not None
    assert fetched["diff"] == {}
    assert fetched["supersedes_revision_id"] is None


async def test_service_rejects_a_caller_supplied_initial_reason_for_a_successor():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    with pytest.raises(PlanLineageError):
        await PlanningService(store=store).create_successor_revision(
            goal_id=goal_id,
            expected_current_revision_id=root_id,
            created_by=principal_id,
            plan=_plan(),
            reason="initial",
        )


# --- TeamDecision FK (AT-D14 pre-cleared) ---------------------------------------------------------


async def test_team_decisions_resulting_plan_revision_has_a_real_fk():
    store = await _store_or_skip()
    conn = await store._connect()
    try:
        column_type = await conn.fetchval("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name='team_decisions' AND column_name='resulting_plan_revision_id'
            """)
        fk = await conn.fetchval("""
            SELECT count(*) FROM information_schema.table_constraints
            WHERE table_name='team_decisions' AND constraint_type='FOREIGN KEY'
              AND constraint_name='fk_team_decisions_resulting_plan_revision'
            """)
    finally:
        await conn.close()
    assert column_type == "uuid"
    assert fk == 1


async def test_team_decision_cannot_name_a_nonexistent_plan_revision():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    root = await store.get_revision(root_id)
    conn = await store._connect()
    try:
        thread_id = await conn.fetchval(
            """
            INSERT INTO conversation_threads (project_id, goal_ref, thread_type)
            VALUES ($1,$2,'planning') RETURNING thread_id
            """,
            root["project_id"],
            f"goal:{goal_id}",
        )
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await conn.execute(
                """
                INSERT INTO team_decisions
                  (project_id, thread_id, proposed_by, selected_option, rationale_summary,
                   resulting_plan_revision_id)
                VALUES ($1,$2,$3,'option-a','because',$4)
                """,
                root["project_id"],
                thread_id,
                uuid.UUID(principal_id),
                uuid.uuid4(),
            )
        # The real revision is accepted.
        await conn.execute(
            """
            INSERT INTO team_decisions
              (project_id, thread_id, proposed_by, selected_option, rationale_summary,
               resulting_plan_revision_id)
            VALUES ($1,$2,$3,'option-a','because',$4)
            """,
            root["project_id"],
            thread_id,
            uuid.UUID(principal_id),
            uuid.UUID(root_id),
        )
    finally:
        await conn.close()


# --- audit / storage prohibition ------------------------------------------------------------------


async def test_store_refuses_a_plan_carrying_forbidden_keys():
    """A direct store caller bypasses the Pydantic models entirely; the screen still applies."""
    store = await _store_or_skip()
    goal_id, principal_id, _root = await _goal_with_root(store)
    with pytest.raises(ValueError):
        await store.create_successor_revision(
            {
                "goal_id": goal_id,
                "expected_current_revision_id": _root,
                "created_by": principal_id,
                "plan": {"objective": "x", "chain_of_thought": "secret deliberation"},
                "diff": {},
                "reason": "team_decision",
            }
        )


async def test_no_plan_revision_column_holds_reasoning_or_credentials():
    store = await _store_or_skip()
    conn = await store._connect()
    try:
        columns = [row["column_name"] for row in await conn.fetch("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name IN ('plan_revisions','goals')
                """)]
    finally:
        await conn.close()
    forbidden = ("chain_of_thought", "scratchpad", "prompt", "secret", "credential", "api_key")
    leaks = [c for c in columns if any(marker in c for marker in forbidden)]
    assert leaks == []


async def test_audit_events_carry_identifiers_not_plan_content():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)

    written: list[dict] = []

    class _AuditClient:
        def build_audit_event(self, **kwargs):
            return kwargs

        async def write_audit_event(self, event):
            written.append(event)
            return f"audit-{len(written)}"

    service = PlanningService(store=store, audit_client=_AuditClient())
    await service.create_successor_revision(
        goal_id=goal_id,
        expected_current_revision_id=root_id,
        created_by=principal_id,
        plan=_plan(objective="a brand new objective"),
        reason="goal_changed",
        rationale="requester amended the goal",
    )
    assert written, "an audit event should have been recorded"
    event = written[-1]
    blob = str(event)
    assert "a brand new objective" not in blob
    assert "requester amended the goal" not in blob
    assert event["decision_type"] == "plan_revision_superseded"
    assert set(event["artifact_refs"]) == {
        "plan_revision_id",
        "goal_id",
        "revision_number",
        "reason",
        "supersedes_revision_id",
        "created_by",
    }


async def test_stale_rejection_is_audited_as_rejected():
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)
    written: list[dict] = []

    class _AuditClient:
        def build_audit_event(self, **kwargs):
            return kwargs

        async def write_audit_event(self, event):
            written.append(event)
            return "audit-1"

    service = PlanningService(store=store, audit_client=_AuditClient())
    await service.create_successor_revision(
        goal_id=goal_id,
        expected_current_revision_id=root_id,
        created_by=principal_id,
        plan=_plan(objective="first"),
        reason="team_decision",
    )
    with pytest.raises(StalePlanRevisionError):
        await service.create_successor_revision(
            goal_id=goal_id,
            expected_current_revision_id=root_id,
            created_by=principal_id,
            plan=_plan(objective="second"),
            reason="team_decision",
        )
    assert written[-1]["decision_type"] == "plan_revision_stale_rejected"
    assert written[-1]["result"] == "rejected_stale"


async def test_audit_failure_does_not_lose_the_revision():
    """A missing or failing audit sink must never turn a recorded plan into an unrecorded one."""
    store = await _store_or_skip()
    goal_id, principal_id, root_id = await _goal_with_root(store)

    class _BrokenAudit:
        def build_audit_event(self, **kwargs):
            raise RuntimeError("audit sink down")

        async def write_audit_event(self, event):  # pragma: no cover - never reached
            raise RuntimeError("audit sink down")

    service = PlanningService(store=store, audit_client=_BrokenAudit())
    row = await service.create_successor_revision(
        goal_id=goal_id,
        expected_current_revision_id=root_id,
        created_by=principal_id,
        plan=_plan(objective="survives a broken audit sink"),
        reason="team_decision",
    )
    assert await store.get_revision(row["plan_revision_id"]) is not None
