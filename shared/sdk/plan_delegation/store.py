"""Step AT-M3.5 -- asyncpg store for the plan execution graph, its assignments and its dispatches.

Follows the existing store convention (connect per call, ``DATABASE_URL`` from the environment,
plain dict rows) set by ``shared/sdk/agent_team/store.py`` and reused by every AT-M3 slice.

Four properties are enforced by PostgreSQL rather than by application memory, because a second
worker, a restarted process or a raw SQL caller would not share that memory:

* **One graph per accepted PlanRevision.** ``uq_peg_plan_revision``. Eight concurrent
  materializations resolve to one; each loser's WHOLE transaction rolls back, so a partial graph
  is not a state this store can leave behind, and it then replays the winner's graph.
* **One canonical assignment per unit.** Every assignment writes under ``FOR UPDATE`` on the unit
  and is guarded by ``WHERE state='ready'``, so a lost race is a no-op replay rather than a second
  routing decision row.
* **One canonical dispatch per unit.** ``plan_execution_dispatches`` has ``execution_unit_id`` as
  its PRIMARY KEY. Redis may deliver a command twice; a second canonical dispatch is not
  representable.
* **Stale-plan protection is AT-M3.2's compare-and-swap, reused, not copied.** Every write path
  that creates NEW work calls ``PlanningStore.confirm_current_revision`` on this transaction's own
  connection: it takes ``FOR UPDATE`` on the revision and re-checks for a successor inside that
  lock. A revision that stops being current between an application pre-read and the commit is
  therefore caught by the database, not by a check someone could forget to write.

LOCK ORDER, everywhere in this module: **project row -> plan revision -> primary work item ->
execution unit**, and dependent units in ``execution_unit_id`` order. ``PlanningStore`` documents
project-then-predecessor for its own writes, and this module extends the same chain rather than
approaching it from the other end.

WHY THIS STORE VALIDATES. It is otherwise persistence-only, but the plan it materializes is read
out of a JSONB column written by code that may be years older than this module, and an unexecutable
plan must stop the materialization inside the transaction rather than after it. The plan is
therefore re-parsed through ``PlanContent`` and re-checked for cycles HERE, on the row, and is
never accepted from the caller -- the same refusal AT-M3.4 made when it removed the caller-supplied
plan from its finalize command.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from shared.sdk.agent_planning.models import PlanContent, parse_plan
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_team.models import assert_content_is_safe
from shared.sdk.agent_team.router import RoutingDecision
from shared.sdk.agent_team.store import TeamStore
from shared.sdk.plan_delegation.models import (
    DISPOSITION_SUCCEEDED,
    UNIT_ASSIGNED,
    UNIT_BLOCKED,
    UNIT_COMPLETED,
    UNIT_DISPATCHED,
    UNIT_FAILED,
    UNIT_READY,
    DispatchLineageError,
    ExecutionLineageCancelledError,
    ExecutionUnitStateError,
    PlanRevisionNotDispatchableError,
    unavailable_reason_for,
    validate_plan_graph,
    work_item_status_for,
)

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

#: The constraint that decides the materialization race. Named explicitly: mapping every unique
#: violation to one meaning is how AT-M3.2 came to report a numbering collision as a duplicate
#: root, and that lesson applies here unchanged.
_GRAPH_PER_REVISION = "uq_peg_plan_revision"
_UNIT_PER_STEP = "uq_peu_revision_step"

#: Work-item statuses that mean the Goal's autonomous execution lineage has been stopped. Both
#: vocabularies are consulted because ``project_work_items`` genuinely carries two: the planner
#: ``status`` (017) and the delivery ``lifecycle_state`` (Step 57). Either saying "cancelled" is
#: enough to refuse new work; requiring both to agree would let one of them be bypassed.
_CANCELLED_STATUSES = ("cancelled",)
_CANCELLED_LIFECYCLE_STATES = ("cancelled", "archived")

_GRAPH_COLUMNS = """
    plan_execution_graph_id, project_id, goal_id, plan_revision_id, step_count, materialized_by,
    audit_ref, created_at
"""

_UNIT_COLUMNS = """
    execution_unit_id, plan_execution_graph_id, plan_revision_id, step_key, project_id, goal_id,
    work_item_id, required_capabilities, expected_outputs, intended_owner_role, state,
    unavailable_reason, assigned_principal_id, assigned_role, assigned_agent_key, assigned_stream,
    routing_decision_id, assigned_at, disposition, result_ref, completed_at, created_at, updated_at
"""

_DISPATCH_COLUMNS = """
    execution_unit_id, plan_revision_id, step_key, project_id, work_item_id,
    assigned_principal_id, routing_decision_id, target_stream, correlation_id, published_at,
    audit_ref, created_at
"""


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _decode(row: asyncpg.Record | None, *fields: str) -> dict[str, Any] | None:
    """asyncpg returns JSONB as text unless a codec is registered; decode the named columns."""
    if row is None:
        return None
    data = dict(row)
    for field in fields:
        value = data.get(field)
        if isinstance(value, str):
            data[field] = json.loads(value)
    return data


def _unit_row(row: asyncpg.Record | None) -> dict[str, Any] | None:
    return _decode(row, "required_capabilities", "expected_outputs")


def _safe_list(values: Any, field: str) -> str:
    """Serialise a step's declared contract after re-screening it for forbidden key names.

    Defence in depth, for the same reason ``PlanningStore._safe_json`` does it: a caller going
    through the service cannot smuggle a key past the closed Pydantic models, and a direct store
    caller never touches those models at all.
    """
    payload = list(values or ())
    assert_content_is_safe(payload, field=field)
    return json.dumps(payload)


class PlanDelegationStore:
    def __init__(
        self,
        database_url: str | None = None,
        *,
        planning_store: Any | None = None,
        team_store: Any | None = None,
    ) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        # Composition, not inheritance: the currency CAS and the routing evidence stay owned by the
        # modules that define them, and this store borrows them on its own connection.
        self.planning_store = planning_store or PlanningStore(self.database_url)
        self.team_store = team_store or TeamStore(self.database_url)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    @asynccontextmanager
    async def _session(self, conn: asyncpg.Connection | None) -> AsyncIterator[asyncpg.Connection]:
        if conn is not None:
            yield conn
            return
        own = await self._connect()
        try:
            yield own
        finally:
            await own.close()

    # --- materialization -------------------------------------------------------------------------

    async def materialize(
        self,
        *,
        goal_id: Any,
        plan_revision_id: Any,
        materialized_by: Any,
        conn: asyncpg.Connection | None = None,
    ) -> dict[str, Any]:
        """Turn one accepted, current PlanRevision into a durable execution graph, once.

        The plan is read from the revision row, never taken from the caller. Everything -- the
        Goal's execution root, the graph, one child work item and one unit per step, and every
        dependency edge -- is written in ONE transaction, so an invalid plan or a lost race leaves
        nothing behind.

        Returns the canonical graph either way. ``created`` says whether THIS call built it; a
        loser of the eight-way race gets ``created=False`` and the same graph the winner wrote.
        """
        goal = _uuid(goal_id)
        revision = _uuid(plan_revision_id)

        async with self._session(conn) as connection:
            try:
                async with connection.transaction():
                    return await self._materialize_locked(
                        connection,
                        goal_id=goal,
                        plan_revision_id=revision,
                        materialized_by=_uuid(materialized_by),
                    )
            except asyncpg.UniqueViolationError as exc:
                if (exc.constraint_name or "") not in (_GRAPH_PER_REVISION, _UNIT_PER_STEP):
                    raise
            # The transaction above rolled back in full. The winner's graph is committed and
            # complete, so replaying it is a read, not a repair.
            graph = await self._read_graph(connection, revision)
            if graph is None:  # pragma: no cover - only reachable if the winner also rolled back
                raise RuntimeError(
                    f"materialization of plan revision {plan_revision_id} lost its race to a "
                    "graph that then disappeared"
                )
            graph["created"] = False
            return graph

    async def _materialize_locked(
        self,
        connection: asyncpg.Connection,
        *,
        goal_id: uuid.UUID,
        plan_revision_id: uuid.UUID,
        materialized_by: uuid.UUID,
    ) -> dict[str, Any]:
        goal = await connection.fetchrow(
            "SELECT goal_id, project_id, statement FROM goals WHERE goal_id=$1", goal_id
        )
        if goal is None:
            raise PlanRevisionNotDispatchableError(f"unknown goal {goal_id}")
        project_id = goal["project_id"]

        # Lock order starts here: project, then revision. Materializations of one project queue
        # behind each other for the length of one graph build; different projects never contend.
        await connection.fetchval("SELECT id FROM projects WHERE id=$1 FOR UPDATE", project_id)

        revision = await self._confirm_dispatchable_revision(connection, goal_id, plan_revision_id)
        plan = self._plan_from_revision(revision)

        lineage = await self._ensure_execution_lineage(
            connection, goal_id=goal_id, project_id=project_id, statement=goal["statement"]
        )

        graph_row = await connection.fetchrow(
            f"""
            INSERT INTO plan_execution_graphs
              (project_id, goal_id, plan_revision_id, step_count, materialized_by)
            VALUES ($1,$2,$3,$4,$5)
            RETURNING {_GRAPH_COLUMNS}
            """,
            project_id,
            goal_id,
            plan_revision_id,
            len(plan.steps),
            materialized_by,
        )
        graph_id = graph_row["plan_execution_graph_id"]

        work_item_by_step: dict[str, uuid.UUID] = {}
        units: list[dict[str, Any]] = []
        for step in plan.steps:
            state = UNIT_READY if not step.depends_on else UNIT_BLOCKED
            work_item_id = await connection.fetchval(
                """
                INSERT INTO project_work_items
                  (project_id, parent_work_item_id, work_item_key, title, description, status,
                   metadata)
                VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb)
                RETURNING id
                """,
                project_id,
                lineage["primary_work_item_id"],
                f"R{revision['revision_number']}-{step.step_key}",
                step.title,
                step.description,
                work_item_status_for(state),
                json.dumps(
                    {
                        "source": "at_m3_5_plan_delegation",
                        "plan_revision_id": str(plan_revision_id),
                        "step_key": step.step_key,
                    }
                ),
            )
            work_item_by_step[step.step_key] = work_item_id
            unit = await connection.fetchrow(
                f"""
                INSERT INTO plan_execution_units
                  (plan_execution_graph_id, plan_revision_id, step_key, project_id, goal_id,
                   work_item_id, required_capabilities, expected_outputs, intended_owner_role,
                   state)
                VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9,$10)
                RETURNING {_UNIT_COLUMNS}
                """,
                graph_id,
                plan_revision_id,
                step.step_key,
                project_id,
                goal_id,
                work_item_id,
                _safe_list(step.required_capabilities, "required_capabilities"),
                _safe_list(step.expected_outputs, "expected_outputs"),
                step.intended_owner_role,
                state,
            )
            units.append(_unit_row(unit))  # type: ignore[arg-type]

        for step in plan.steps:
            for parent in step.depends_on:
                await connection.execute(
                    """
                    INSERT INTO project_work_item_dependencies
                      (project_id, work_item_id, depends_on_work_item_id, dependency_type)
                    VALUES ($1,$2,$3,'blocks')
                    ON CONFLICT ON CONSTRAINT uq_project_dep_pair DO NOTHING
                    """,
                    project_id,
                    work_item_by_step[step.step_key],
                    work_item_by_step[parent],
                )

        return {
            "graph": dict(graph_row),
            "primary_work_item_id": lineage["primary_work_item_id"],
            "units": units,
            "created": True,
        }

    async def _ensure_execution_lineage(
        self,
        connection: asyncpg.Connection,
        *,
        goal_id: uuid.UUID,
        project_id: uuid.UUID,
        statement: str,
    ) -> dict[str, Any]:
        """The Goal's single primary Work Item -- created once, then reused by every revision.

        Safe as a check-then-insert because the caller holds the project row lock for the whole
        transaction, and ``goal_execution_lineage``'s PRIMARY KEY is the second layer for anyone
        who does not.
        """
        existing = await connection.fetchrow(
            "SELECT goal_id, project_id, primary_work_item_id FROM goal_execution_lineage "
            "WHERE goal_id=$1",
            goal_id,
        )
        if existing is not None:
            return dict(existing)

        primary_work_item_id = await connection.fetchval(
            """
            INSERT INTO project_work_items
              (project_id, work_item_key, title, description, status, metadata)
            VALUES ($1,$2,$3,$4,'in_progress',$5::jsonb)
            RETURNING id
            """,
            project_id,
            f"GOAL-{str(goal_id)[:8]}",
            f"Goal execution lineage: {statement[:240]}",
            "The single autonomous execution root for this Goal. Plan steps materialize as its "
            "children; it is never dispatched itself.",
            json.dumps({"source": "at_m3_5_plan_delegation", "goal_id": str(goal_id)}),
        )
        row = await connection.fetchrow(
            """
            INSERT INTO goal_execution_lineage (goal_id, project_id, primary_work_item_id)
            VALUES ($1,$2,$3)
            RETURNING goal_id, project_id, primary_work_item_id
            """,
            goal_id,
            project_id,
            primary_work_item_id,
        )
        return dict(row)

    # --- lineage gates ----------------------------------------------------------------------------

    async def _confirm_dispatchable_revision(
        self,
        connection: asyncpg.Connection,
        goal_id: uuid.UUID,
        plan_revision_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Hold the revision still and prove it may authorize NEW work, or raise.

        ``confirm_current_revision`` is AT-M3.2's own read-only compare-and-swap: it locks the
        revision and re-checks for a successor inside that lock, raising ``StalePlanRevisionError``
        when one exists and ``PlanLineageError`` when the revision belongs to a different Goal.
        Both propagate unchanged -- renaming them here would suggest this slice has a second
        stale-plan mechanism, and it does not.

        The status check is this slice's own: only an ACCEPTED revision may create or advance an
        execution graph. A draft is a plan the team has not adopted.
        """
        revision = await self.planning_store.confirm_current_revision(
            goal_id, plan_revision_id, conn=connection
        )
        if revision["status"] != "accepted":
            raise PlanRevisionNotDispatchableError(
                f"plan revision {plan_revision_id} is '{revision['status']}'; only an accepted "
                "revision may create or advance an execution graph"
            )
        return revision

    def _plan_from_revision(self, revision: dict[str, Any]) -> PlanContent:
        """Re-parse and re-validate the stored plan. Fails closed on historical rows."""
        plan = parse_plan(revision["plan"])
        validate_plan_graph(plan)
        return plan

    async def _assert_lineage_not_cancelled(
        self, connection: asyncpg.Connection, goal_id: Any
    ) -> None:
        """Refuse new work when the Goal's primary Work Item has been cancelled.

        The existing work-item cancel semantics stay authoritative: this slice reads them and
        stops, it does not define a second cancellation model for plan graphs. The primary work
        item is locked, so a cancellation committing concurrently is either visible here or waits
        behind this transaction.
        """
        row = await connection.fetchrow(
            """
            SELECT w.id, w.status, w.lifecycle_state
            FROM goal_execution_lineage g
            JOIN project_work_items w ON w.id = g.primary_work_item_id
            WHERE g.goal_id = $1
            FOR UPDATE OF w
            """,
            _uuid(goal_id),
        )
        if row is None:
            raise PlanRevisionNotDispatchableError(
                f"goal {goal_id} has no execution lineage; materialize its plan first"
            )
        if row["status"] in _CANCELLED_STATUSES or (
            row["lifecycle_state"] in _CANCELLED_LIFECYCLE_STATES
        ):
            raise ExecutionLineageCancelledError(
                f"the primary work item for goal {goal_id} is "
                f"status={row['status']}/lifecycle_state={row['lifecycle_state']}; no new plan "
                "step may be assigned or dispatched"
            )

    # --- assignment --------------------------------------------------------------------------------

    async def apply_assignment(
        self,
        *,
        execution_unit_id: Any,
        decision: RoutingDecision,
        audit_ref: str | None = None,
        conn: asyncpg.Connection | None = None,
    ) -> dict[str, Any]:
        """Record one routing decision against one ready unit, exactly once.

        ``outcome`` is ``assigned`` when a principal took it, ``unassignable`` when the routing
        decision honestly says nobody on this team can, and ``replay`` when another worker already
        decided -- in which case NO routing decision row is written, so eight racing schedulers
        leave one piece of evidence rather than eight.
        """
        unit_id = _uuid(execution_unit_id)
        async with self._session(conn) as connection:
            async with connection.transaction():
                unit = await self._require_unit(connection, unit_id)
                await self._confirm_dispatchable_revision(
                    connection, unit["goal_id"], unit["plan_revision_id"]
                )
                await self._assert_lineage_not_cancelled(connection, unit["goal_id"])

                locked = _unit_row(
                    await connection.fetchrow(
                        f"SELECT {_UNIT_COLUMNS} FROM plan_execution_units "
                        "WHERE execution_unit_id=$1 FOR UPDATE",
                        unit_id,
                    )
                )
                assert locked is not None
                if locked["state"] != UNIT_READY:
                    return {"outcome": "replay", "unit": locked, "routing_decision": None}

                record = await self.team_store.record_routing_decision(
                    project_id=locked["project_id"],
                    decision=decision,
                    work_item_id=locked["work_item_id"],
                    audit_ref=audit_ref,
                    conn=connection,
                )
                routing_decision_id = record["routing_decision_id"]

                if not decision.selected:
                    updated = _unit_row(
                        await connection.fetchrow(
                            f"""
                            UPDATE plan_execution_units
                            SET unavailable_reason=$2, routing_decision_id=$3, updated_at=now()
                            WHERE execution_unit_id=$1 AND state='{UNIT_READY}'
                            RETURNING {_UNIT_COLUMNS}
                            """,
                            unit_id,
                            unavailable_reason_for(decision),
                            routing_decision_id,
                        )
                    )
                    return {
                        "outcome": "unassignable",
                        "unit": updated,
                        "routing_decision": record,
                    }

                updated = _unit_row(
                    await connection.fetchrow(
                        f"""
                        UPDATE plan_execution_units
                        SET state='{UNIT_ASSIGNED}',
                            assigned_principal_id=$2,
                            assigned_role=$3,
                            assigned_agent_key=$4,
                            assigned_stream=$5,
                            routing_decision_id=$6,
                            unavailable_reason=NULL,
                            assigned_at=now(),
                            updated_at=now()
                        WHERE execution_unit_id=$1 AND state='{UNIT_READY}'
                        RETURNING {_UNIT_COLUMNS}
                        """,
                        unit_id,
                        _uuid(decision.selected_principal_id),
                        decision.selected_role,
                        decision.selected_agent_key,
                        decision.selected_stream,
                        routing_decision_id,
                    )
                )
                assert updated is not None
                await self._mirror_work_item(
                    connection,
                    work_item_id=updated["work_item_id"],
                    state=UNIT_ASSIGNED,
                    assigned_agent_key=decision.selected_agent_key,
                    assigned_role=decision.selected_role,
                )
                return {"outcome": "assigned", "unit": updated, "routing_decision": record}

    # --- dispatch ----------------------------------------------------------------------------------

    async def create_dispatch(
        self,
        *,
        execution_unit_id: Any,
        audit_ref: str | None = None,
        conn: asyncpg.Connection | None = None,
    ) -> dict[str, Any]:
        """Create the ONE canonical dispatch for an assigned unit.

        ``outcome`` is ``dispatched`` when this call created it and ``replay`` when it already
        existed. The canonical dispatch is the committed row; publishing it to a stream is a
        separate, at-least-once step the caller performs afterwards.
        """
        unit_id = _uuid(execution_unit_id)
        async with self._session(conn) as connection:
            async with connection.transaction():
                unit = await self._require_unit(connection, unit_id)
                await self._confirm_dispatchable_revision(
                    connection, unit["goal_id"], unit["plan_revision_id"]
                )
                await self._assert_lineage_not_cancelled(connection, unit["goal_id"])

                locked = _unit_row(
                    await connection.fetchrow(
                        f"SELECT {_UNIT_COLUMNS} FROM plan_execution_units "
                        "WHERE execution_unit_id=$1 FOR UPDATE",
                        unit_id,
                    )
                )
                assert locked is not None
                if locked["state"] == UNIT_DISPATCHED:
                    existing = await self._read_dispatch(connection, unit_id)
                    return {"outcome": "replay", "unit": locked, "dispatch": existing}
                if locked["state"] != UNIT_ASSIGNED:
                    raise ExecutionUnitStateError(
                        f"execution unit {execution_unit_id} is '{locked['state']}'; only an "
                        "assigned unit may be dispatched"
                    )

                dispatch = dict(
                    await connection.fetchrow(
                        f"""
                        INSERT INTO plan_execution_dispatches
                          (execution_unit_id, plan_revision_id, step_key, project_id, work_item_id,
                           assigned_principal_id, routing_decision_id, target_stream, audit_ref)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                        RETURNING {_DISPATCH_COLUMNS}
                        """,
                        unit_id,
                        locked["plan_revision_id"],
                        locked["step_key"],
                        locked["project_id"],
                        locked["work_item_id"],
                        locked["assigned_principal_id"],
                        locked["routing_decision_id"],
                        locked["assigned_stream"],
                        audit_ref,
                    )
                )
                updated = _unit_row(
                    await connection.fetchrow(
                        f"""
                        UPDATE plan_execution_units SET state='{UNIT_DISPATCHED}', updated_at=now()
                        WHERE execution_unit_id=$1 AND state='{UNIT_ASSIGNED}'
                        RETURNING {_UNIT_COLUMNS}
                        """,
                        unit_id,
                    )
                )
                assert updated is not None
                await self._mirror_work_item(
                    connection, work_item_id=updated["work_item_id"], state=UNIT_DISPATCHED
                )
                await self._record_work_item_event(
                    connection,
                    unit=updated,
                    event_type="plan_step.dispatched",
                    from_state=UNIT_ASSIGNED,
                    to_state=UNIT_DISPATCHED,
                    reason="capability-routed plan step dispatched to its assigned principal",
                    correlation_id=str(dispatch["correlation_id"]),
                )
                return {"outcome": "dispatched", "unit": updated, "dispatch": dispatch}

    async def mark_dispatch_published(
        self, execution_unit_id: Any, *, conn: asyncpg.Connection | None = None
    ) -> bool:
        """Record that the transport actually carried this canonical dispatch. Write-once."""
        async with self._session(conn) as connection:
            row = await connection.fetchval(
                """
                UPDATE plan_execution_dispatches SET published_at=now()
                WHERE execution_unit_id=$1 AND published_at IS NULL
                RETURNING execution_unit_id
                """,
                _uuid(execution_unit_id),
            )
            return row is not None

    # --- completion --------------------------------------------------------------------------------

    async def record_result(
        self,
        *,
        execution_unit_id: Any,
        reported_by: Any,
        correlation_id: Any,
        disposition: str,
        result_ref: str | None = None,
        conn: asyncpg.Connection | None = None,
    ) -> dict[str, Any]:
        """Apply one terminal result to a dispatched unit and unlock what it was blocking.

        The result must come through the unit's OWN canonical dispatch: the correlation id and the
        reporting principal are both checked against the dispatch row. A caller that never received
        the dispatch cannot produce that pair, which is what keeps an arbitrary external assertion
        from advancing the graph.

        Deliberately does NOT check plan currency or lineage cancellation. Work already handed to a
        principal is allowed to finish and be recorded truthfully even after a successor revision
        appears -- planning-and-plan-revision-model.md section 7 carries in-flight work forward and
        never destroys its history. What supersession stops is NEW dispatch, and that is enforced
        where new dispatch happens.
        """
        unit_id = _uuid(execution_unit_id)
        if disposition not in ("succeeded", "failed"):
            raise ValueError(f"unknown disposition {disposition!r}")

        async with self._session(conn) as connection:
            async with connection.transaction():
                locked = _unit_row(
                    await connection.fetchrow(
                        f"SELECT {_UNIT_COLUMNS} FROM plan_execution_units "
                        "WHERE execution_unit_id=$1 FOR UPDATE",
                        unit_id,
                    )
                )
                if locked is None:
                    raise ExecutionUnitStateError(f"unknown execution unit {execution_unit_id}")

                dispatch = await self._read_dispatch(connection, unit_id)
                if dispatch is None:
                    raise DispatchLineageError(
                        f"execution unit {execution_unit_id} has no canonical dispatch; a result "
                        "cannot be reported for work that was never handed over"
                    )
                if str(dispatch["correlation_id"]) != str(correlation_id):
                    raise DispatchLineageError(
                        f"the correlation id reported for execution unit {execution_unit_id} does "
                        "not belong to its canonical dispatch"
                    )
                if str(dispatch["assigned_principal_id"]) != str(reported_by):
                    raise DispatchLineageError(
                        f"execution unit {execution_unit_id} was dispatched to principal "
                        f"{dispatch['assigned_principal_id']}; a result from another principal is "
                        "not a result for this unit"
                    )

                terminal = UNIT_COMPLETED if disposition == DISPOSITION_SUCCEEDED else UNIT_FAILED
                if locked["state"] in (UNIT_COMPLETED, UNIT_FAILED):
                    if locked["state"] != terminal:
                        raise ExecutionUnitStateError(
                            f"execution unit {execution_unit_id} already terminalized as "
                            f"'{locked['state']}' and may not be re-reported as '{terminal}'"
                        )
                    return {"outcome": "replay", "unit": locked, "unblocked": []}
                if locked["state"] != UNIT_DISPATCHED:
                    raise ExecutionUnitStateError(
                        f"execution unit {execution_unit_id} is '{locked['state']}'; only a "
                        "dispatched unit may report a result"
                    )

                updated = _unit_row(
                    await connection.fetchrow(
                        f"""
                        UPDATE plan_execution_units
                        SET state=$2, disposition=$3, result_ref=$4, completed_at=now(),
                            updated_at=now()
                        WHERE execution_unit_id=$1 AND state='{UNIT_DISPATCHED}'
                        RETURNING {_UNIT_COLUMNS}
                        """,
                        unit_id,
                        terminal,
                        disposition,
                        result_ref,
                    )
                )
                assert updated is not None
                await self._mirror_work_item(
                    connection, work_item_id=updated["work_item_id"], state=terminal
                )
                await self._record_work_item_event(
                    connection,
                    unit=updated,
                    event_type="plan_step.result_recorded",
                    from_state=UNIT_DISPATCHED,
                    to_state=terminal,
                    reason=disposition,
                    correlation_id=str(dispatch["correlation_id"]),
                )

                unblocked: list[dict[str, Any]] = []
                if terminal == UNIT_COMPLETED:
                    unblocked = await self._unblock_dependents(connection, updated["work_item_id"])
                return {"outcome": "recorded", "unit": updated, "unblocked": unblocked}

    async def _unblock_dependents(
        self, connection: asyncpg.Connection, completed_work_item_id: Any
    ) -> list[dict[str, Any]]:
        """Promote every blocked dependent whose dependencies are NOW all complete.

        Locked in ``execution_unit_id`` order so two upstream completions racing to promote the
        same fan-in dependent cannot deadlock, and guarded by ``WHERE state='blocked'`` so the
        promotion happens exactly once however many upstreams finish at the same moment. The loser
        of the race re-reads the dependency count inside the lock, sees the winner's commit, and
        finds nothing left to do.
        """
        candidates = await connection.fetch(
            f"""
            SELECT u.execution_unit_id
            FROM plan_execution_units u
            JOIN project_work_item_dependencies d ON d.work_item_id = u.work_item_id
            WHERE d.depends_on_work_item_id = $1 AND u.state = '{UNIT_BLOCKED}'
            ORDER BY u.execution_unit_id
            FOR UPDATE OF u
            """,
            completed_work_item_id,
        )

        promoted: list[dict[str, Any]] = []
        for candidate in candidates:
            unit_id = candidate["execution_unit_id"]
            # A dependency whose target has no execution unit counts as UNSATISFIED. Failing
            # closed here is the difference between "nothing is blocking this" and "we could not
            # see what is blocking this".
            outstanding = await connection.fetchval(
                f"""
                SELECT count(*)
                FROM project_work_item_dependencies d
                LEFT JOIN plan_execution_units p ON p.work_item_id = d.depends_on_work_item_id
                WHERE d.work_item_id = (
                        SELECT work_item_id FROM plan_execution_units WHERE execution_unit_id=$1
                      )
                  AND (p.execution_unit_id IS NULL OR p.state <> '{UNIT_COMPLETED}')
                """,
                unit_id,
            )
            if int(outstanding or 0) > 0:
                continue
            row = _unit_row(
                await connection.fetchrow(
                    f"""
                    UPDATE plan_execution_units SET state='{UNIT_READY}', updated_at=now()
                    WHERE execution_unit_id=$1 AND state='{UNIT_BLOCKED}'
                    RETURNING {_UNIT_COLUMNS}
                    """,
                    unit_id,
                )
            )
            if row is None:
                continue
            await self._mirror_work_item(
                connection, work_item_id=row["work_item_id"], state=UNIT_READY
            )
            promoted.append(row)
        return promoted

    # --- work item mirroring -------------------------------------------------------------------------

    async def _mirror_work_item(
        self,
        connection: asyncpg.Connection,
        *,
        work_item_id: Any,
        state: str,
        assigned_agent_key: str | None = None,
        assigned_role: str | None = None,
    ) -> None:
        """Keep the execution-lineage row truthful about the unit it carries.

        One writer, in the same transaction as the unit's own transition, so the two cannot drift.
        The unit remains canonical; this is the projection every existing reader of
        ``project_work_items`` already understands.
        """
        await connection.execute(
            """
            UPDATE project_work_items
            SET status=$2,
                assigned_agent=COALESCE($3, assigned_agent),
                assigned_agent_role=COALESCE($4, assigned_agent_role),
                completed_at=CASE WHEN $2='completed' THEN now() ELSE completed_at END,
                updated_at=now()
            WHERE id=$1
            """,
            work_item_id,
            work_item_status_for(state),
            assigned_agent_key,
            assigned_role,
        )

    async def _record_work_item_event(
        self,
        connection: asyncpg.Connection,
        *,
        unit: dict[str, Any],
        event_type: str,
        from_state: str,
        to_state: str,
        reason: str,
        correlation_id: str | None,
    ) -> None:
        """Append the transition to the EXISTING work-item event log.

        Identifiers, states and a short reason only -- never plan text, never a result body.
        """
        await connection.execute(
            """
            INSERT INTO work_item_events
              (project_id, work_item_id, event_type, from_state, to_state, actor, role, reason,
               correlation_id, metadata)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb)
            """,
            unit["project_id"],
            unit["work_item_id"],
            event_type,
            from_state,
            to_state,
            str(unit["assigned_principal_id"]) if unit["assigned_principal_id"] else None,
            unit["assigned_role"],
            reason,
            correlation_id,
            json.dumps(
                {
                    "plan_revision_id": str(unit["plan_revision_id"]),
                    "step_key": unit["step_key"],
                    "execution_unit_id": str(unit["execution_unit_id"]),
                }
            ),
        )

    # --- reads ----------------------------------------------------------------------------------------

    async def _require_unit(
        self, connection: asyncpg.Connection, execution_unit_id: uuid.UUID
    ) -> dict[str, Any]:
        unit = _unit_row(
            await connection.fetchrow(
                f"SELECT {_UNIT_COLUMNS} FROM plan_execution_units WHERE execution_unit_id=$1",
                execution_unit_id,
            )
        )
        if unit is None:
            raise ExecutionUnitStateError(f"unknown execution unit {execution_unit_id}")
        return unit

    async def _read_dispatch(
        self, connection: asyncpg.Connection, execution_unit_id: uuid.UUID
    ) -> dict[str, Any] | None:
        row = await connection.fetchrow(
            f"SELECT {_DISPATCH_COLUMNS} FROM plan_execution_dispatches WHERE execution_unit_id=$1",
            execution_unit_id,
        )
        return dict(row) if row is not None else None

    async def _read_graph(
        self, connection: asyncpg.Connection, plan_revision_id: uuid.UUID
    ) -> dict[str, Any] | None:
        graph = await connection.fetchrow(
            f"SELECT {_GRAPH_COLUMNS} FROM plan_execution_graphs WHERE plan_revision_id=$1",
            plan_revision_id,
        )
        if graph is None:
            return None
        units = await connection.fetch(
            f"SELECT {_UNIT_COLUMNS} FROM plan_execution_units WHERE plan_revision_id=$1 "
            "ORDER BY step_key",
            plan_revision_id,
        )
        primary = await connection.fetchval(
            "SELECT primary_work_item_id FROM goal_execution_lineage WHERE goal_id=$1",
            graph["goal_id"],
        )
        return {
            "graph": dict(graph),
            "primary_work_item_id": primary,
            "units": [_unit_row(row) for row in units],
        }

    async def get_graph(self, plan_revision_id: Any) -> dict[str, Any] | None:
        """The whole graph: units in step order, dependency edges and dispatch records."""
        revision = _uuid(plan_revision_id)
        conn = await self._connect()
        try:
            graph = await self._read_graph(conn, revision)
            if graph is None:
                return None
            graph["dependencies"] = await self.list_dependencies(revision, conn=conn)
            dispatches = await conn.fetch(
                f"""
                SELECT {_DISPATCH_COLUMNS} FROM plan_execution_dispatches
                WHERE plan_revision_id=$1 ORDER BY created_at
                """,
                revision,
            )
            graph["dispatches"] = [dict(row) for row in dispatches]
            graph["is_current"] = await self.planning_store.is_current(revision)
            return graph
        finally:
            await conn.close()

    async def list_dependencies(
        self, plan_revision_id: Any, *, conn: asyncpg.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Dependency edges expressed in PLAN terms -- step key to step key."""
        async with self._session(conn) as connection:
            rows = await connection.fetch(
                """
                SELECT child.step_key AS step_key, parent.step_key AS depends_on_step_key,
                       d.dependency_type
                FROM project_work_item_dependencies d
                JOIN plan_execution_units child ON child.work_item_id = d.work_item_id
                JOIN plan_execution_units parent
                     ON parent.work_item_id = d.depends_on_work_item_id
                WHERE child.plan_revision_id = $1
                ORDER BY child.step_key, parent.step_key
                """,
                _uuid(plan_revision_id),
            )
            return [dict(row) for row in rows]

    async def get_unit(self, execution_unit_id: Any) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            unit = _unit_row(
                await conn.fetchrow(
                    f"SELECT {_UNIT_COLUMNS} FROM plan_execution_units WHERE execution_unit_id=$1",
                    _uuid(execution_unit_id),
                )
            )
            if unit is None:
                return None
            unit["dispatch"] = await self._read_dispatch(conn, _uuid(execution_unit_id))
            return unit
        finally:
            await conn.close()

    async def list_schedulable_units(self, plan_revision_id: Any) -> list[dict[str, Any]]:
        """Units a schedule pass may still act on, in deterministic step order.

        ``ready`` needs an owner, ``assigned`` needs a dispatch, and ``dispatched`` with no
        ``published_at`` needs its canonical dispatch re-published -- the crash window between the
        committed row and the stream that could not join its transaction.
        """
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"""
                SELECT {_UNIT_COLUMNS}
                FROM plan_execution_units u
                WHERE u.plan_revision_id=$1
                  AND (
                      u.state IN ('{UNIT_READY}', '{UNIT_ASSIGNED}')
                      OR (u.state = '{UNIT_DISPATCHED}' AND EXISTS (
                            SELECT 1 FROM plan_execution_dispatches d
                            WHERE d.execution_unit_id = u.execution_unit_id
                              AND d.published_at IS NULL))
                  )
                ORDER BY u.step_key
                """,
                _uuid(plan_revision_id),
            )
            return [_unit_row(row) for row in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def get_dispatch(self, execution_unit_id: Any) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            return await self._read_dispatch(conn, _uuid(execution_unit_id))
        finally:
            await conn.close()

    async def get_execution_lineage(self, goal_id: Any) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT goal_id, project_id, primary_work_item_id, created_at "
                "FROM goal_execution_lineage WHERE goal_id=$1",
                _uuid(goal_id),
            )
            return dict(row) if row is not None else None
        finally:
            await conn.close()

    async def get_revision_plan(self, plan_revision_id: Any) -> PlanContent | None:
        """The parsed plan a graph was materialized from, for envelope construction."""
        revision = await self.planning_store.get_revision(plan_revision_id)
        if revision is None:
            return None
        return parse_plan(revision["plan"])


__all__ = ["DEFAULT_DATABASE_URL", "PlanDelegationStore"]
