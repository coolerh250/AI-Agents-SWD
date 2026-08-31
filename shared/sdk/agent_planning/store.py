"""Step AT-M3.2 -- asyncpg store for Goal and immutable PlanRevision.

Persistence only. Follows the existing store convention (connect per call, ``DATABASE_URL`` from
the environment, plain dict rows) set by ``shared/sdk/agent_team/store.py`` and reused by
``shared/sdk/agent_reasoning/store.py``.

Two things here are deliberately NOT solved in application memory, because a second process, a
second worker or a raw SQL caller would not share that memory:

* **Supersession is derived from lineage**, by asking whether any row names this one. There is no
  status column to keep in sync and no UPDATE on the predecessor -- creating a successor writes
  exactly one row and touches nothing else.
* **Stale-plan protection is a database guarantee.** ``create_successor_revision`` takes
  ``FOR UPDATE`` on the predecessor so concurrent callers serialise, and re-checks currency inside
  that lock. Even if a caller bypassed this store entirely, the partial unique index
  ``uq_plan_revisions_one_successor`` still permits at most one successor per predecessor; a
  losing writer gets a unique violation, which is translated here into
  ``StalePlanRevisionError``. Two layers, both in PostgreSQL.
* **Per-project revision numbers are allocated under the project row's own lock.** The contract
  numbers revisions per PROJECT, so two different Goals of one project share a sequence. Computing
  ``max(revision_number) + 1`` without serialising made independent Goal lineages collide -- AT-M3.2
  Validation 1's D2. Every allocation now takes ``SELECT ... FROM projects ... FOR UPDATE`` first,
  so the critical section is exactly the numbering and nothing else, and unrelated projects never
  serialise against each other.

LOCK ORDER, everywhere in this module: **project row, then predecessor revision.** Both write paths
take it in that order, which is what stops two callers deadlocking by approaching the same pair
from opposite ends.

A unique violation is never mapped to a single domain meaning. Each constraint means something
different, and reporting the wrong one sends the next reader somewhere else entirely -- reporting
a numbering collision as "this goal already has an initial revision" was the second half of D2.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from shared.sdk.agent_planning.models import (
    PlanLineageError,
    PlanRevisionAllocationError,
    PlanRevisionLifecycleError,
    StalePlanRevisionError,
)
from shared.sdk.agent_team.models import assert_content_is_safe

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_GOAL_COLUMNS = """
    goal_id, project_id, statement, acceptance_criteria, constraints, created_by, status,
    audit_ref, created_at
"""

_REVISION_COLUMNS = """
    plan_revision_id, project_id, goal_id, revision_number, created_by, reason,
    supersedes_revision_id, status, plan, diff, trace_ref, audit_ref, created_at
"""

#: Every unique constraint on plan_revisions, and the domain fact each one actually reports.
#: Mapping them all to one meaning is how a numbering collision came to be reported as a
#: duplicate root (AT-M3.2 Validation 1, D2).
_ROOT_PER_GOAL = "uq_plan_revisions_one_root_per_goal"
_ONE_SUCCESSOR = "uq_plan_revisions_one_successor"
_PROJECT_NUMBER = "uq_plan_revisions_project_number"


def _safe_json(payload: Any, field: str) -> str:
    """Serialise a plan/diff payload after re-screening it for forbidden key names.

    Defence-in-depth, and not decorative: the Pydantic models are closed (``extra="forbid"``), so
    a caller going through ``PlanningService`` cannot smuggle an extra key -- but a direct store
    caller never touches those models at all. This mirrors ``ReasoningInvocationStore`` applying
    ``sanitize_failure_reason`` at the store layer as well as the service layer, for exactly the
    same reason.

    Screens key NAMES, which is the established mechanism in this domain
    (``TeamStore.post_message``). It is not a value-level secret scanner and does not claim to be.
    """
    assert_content_is_safe(payload, field=field)
    return json.dumps(payload)


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _json_row(row: asyncpg.Record | None) -> dict[str, Any] | None:
    """asyncpg returns JSONB as text unless a codec is registered; decode the two JSON columns."""
    if row is None:
        return None
    data = dict(row)
    for field in ("plan", "diff", "acceptance_criteria", "constraints"):
        value = data.get(field)
        if isinstance(value, str):
            data[field] = json.loads(value)
    return data


class PlanningStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    @asynccontextmanager
    async def _session(self, conn: asyncpg.Connection | None) -> AsyncIterator[asyncpg.Connection]:
        """Run on the caller's connection when one is given, otherwise on our own.

        Composability, not convenience. AT-M3.4 has to write a successor revision, a TeamDecision
        and the draft -> accepted transition in ONE transaction, and it has to use THIS module's
        compare-and-swap while doing it. Letting a caller pass its connection in is what makes that
        reuse possible; the alternative is a second copy of the stale-protection rule living in the
        caller, and a rule with two implementations is a rule that eventually disagrees with itself.

        Every write below keeps its own ``conn.transaction()``. On our own connection that is the
        transaction; on a caller's it is a savepoint inside theirs, so a fail-closed raise still
        undoes exactly this method's writes and still propagates to abort the caller's.
        """
        if conn is not None:
            yield conn
            return
        own = await self._connect()
        try:
            yield own
        finally:
            await own.close()

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # --- goals ---------------------------------------------------------------------------------

    async def create_goal(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"""
                INSERT INTO goals
                  (project_id, statement, acceptance_criteria, constraints, created_by, status,
                   audit_ref)
                VALUES ($1,$2,$3::jsonb,$4::jsonb,$5,$6,$7)
                RETURNING {_GOAL_COLUMNS}
                """,
                _uuid_or_none(data["project_id"]),
                data["statement"],
                json.dumps(list(data.get("acceptance_criteria", ()))),
                json.dumps(list(data.get("constraints", ()))),
                _uuid_or_none(data["created_by"]),
                data.get("status", "draft"),
                data.get("audit_ref"),
            )
            return _json_row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def get_goal(self, goal_id: Any) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            return _json_row(
                await conn.fetchrow(
                    f"SELECT {_GOAL_COLUMNS} FROM goals WHERE goal_id=$1", _uuid_or_none(goal_id)
                )
            )
        finally:
            await conn.close()

    async def list_goals_for_project(
        self, project_id: Any, limit: int = 100
    ) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"""
                SELECT {_GOAL_COLUMNS} FROM goals
                WHERE project_id=$1 ORDER BY created_at DESC LIMIT $2
                """,
                _uuid_or_none(project_id),
                limit,
            )
            return [_json_row(row) for row in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    # --- plan revisions ------------------------------------------------------------------------

    async def create_initial_revision(
        self, data: dict[str, Any], *, conn: asyncpg.Connection | None = None
    ) -> dict[str, Any]:
        """The root revision for a goal. ``reason`` is always 'initial' (DB-enforced).

        ``uq_plan_revisions_one_root_per_goal`` makes a second root impossible, so calling this
        twice for one goal raises rather than forking the lineage into an unresolvable pair of
        tips. The project row is locked before the number is computed, so two Goals of the SAME
        project creating their roots concurrently both succeed with distinct numbers instead of
        colliding.
        """
        async with self._session(conn) as connection:
            async with connection.transaction():
                goal = await connection.fetchrow(
                    "SELECT goal_id, project_id FROM goals WHERE goal_id=$1",
                    _uuid_or_none(data["goal_id"]),
                )
                if goal is None:
                    raise PlanLineageError(f"unknown goal {data['goal_id']}")
                await self._lock_project(connection, goal["project_id"])
                number = await self._next_revision_number(connection, goal["project_id"])
                try:
                    row = await connection.fetchrow(
                        f"""
                        INSERT INTO plan_revisions
                          (project_id, goal_id, revision_number, created_by, reason,
                           supersedes_revision_id, status, plan, diff, trace_ref, audit_ref)
                        VALUES ($1,$2,$3,$4,'initial',NULL,$5,$6::jsonb,'{{}}'::jsonb,$7,$8)
                        RETURNING {_REVISION_COLUMNS}
                        """,
                        goal["project_id"],
                        goal["goal_id"],
                        number,
                        _uuid_or_none(data["created_by"]),
                        data.get("status", "draft"),
                        _safe_json(data["plan"], "plan"),
                        data.get("trace_ref"),
                        data.get("audit_ref"),
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise self._unique_violation_meaning(
                        exc, goal_id=data["goal_id"], number=number
                    ) from exc
            return _json_row(row)  # type: ignore[return-value]

    async def create_successor_revision(
        self, data: dict[str, Any], *, conn: asyncpg.Connection | None = None
    ) -> dict[str, Any]:
        """Append revision N+1, superseding ``data["expected_current_revision_id"]``.

        Fail-closed in every direction: an unknown predecessor, a predecessor belonging to a
        different goal, or a predecessor that is no longer current all raise rather than write.
        The predecessor row itself is never modified -- supersession is a fact the successor's own
        row asserts.

        Locks in the module's fixed order: project row first (for the per-project number), then
        the predecessor (for currency). Independent lineages of the same project contend only for
        the numbering, so they all succeed; contenders for the SAME predecessor still resolve to
        exactly one winner.
        """
        expected = _uuid_or_none(data["expected_current_revision_id"])
        goal_id = _uuid_or_none(data["goal_id"])

        async with self._session(conn) as connection:
            async with connection.transaction():
                # Identify the owning project before taking any lock, so the lock order below is
                # always project-then-predecessor. This read decides nothing; every check that
                # matters happens after both locks are held.
                project_id = await connection.fetchval(
                    "SELECT project_id FROM goals WHERE goal_id=$1", goal_id
                )
                if project_id is None:
                    raise PlanLineageError(f"unknown goal {data['goal_id']}")
                await self._lock_project(connection, project_id)

                predecessor = await connection.fetchrow(
                    """
                    SELECT plan_revision_id, project_id, goal_id, revision_number
                    FROM plan_revisions WHERE plan_revision_id=$1 FOR UPDATE
                    """,
                    expected,
                )
                if predecessor is None:
                    raise PlanLineageError(f"unknown predecessor revision {expected}")
                if predecessor["goal_id"] != goal_id:
                    raise PlanLineageError(
                        f"predecessor revision {expected} belongs to goal "
                        f"{predecessor['goal_id']}, not {goal_id}"
                    )

                # Currency, re-read inside the lock. The winner of a race commits its successor
                # before the loser's SELECT runs, so the loser sees it here.
                successor_id = await connection.fetchval(
                    "SELECT plan_revision_id FROM plan_revisions WHERE supersedes_revision_id=$1",
                    expected,
                )
                if successor_id is not None:
                    raise StalePlanRevisionError(
                        expected=expected,
                        actual=await self._current_revision_id(connection, goal_id),
                        goal_id=goal_id,
                    )

                number = await self._next_revision_number(connection, predecessor["project_id"])
                try:
                    row = await connection.fetchrow(
                        f"""
                        INSERT INTO plan_revisions
                          (project_id, goal_id, revision_number, created_by, reason,
                           supersedes_revision_id, status, plan, diff, trace_ref, audit_ref)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10,$11)
                        RETURNING {_REVISION_COLUMNS}
                        """,
                        predecessor["project_id"],
                        goal_id,
                        number,
                        _uuid_or_none(data["created_by"]),
                        data["reason"],
                        expected,
                        data.get("status", "draft"),
                        _safe_json(data["plan"], "plan"),
                        _safe_json(data.get("diff", {}), "diff"),
                        data.get("trace_ref"),
                        data.get("audit_ref"),
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise self._unique_violation_meaning(
                        exc, goal_id=goal_id, expected=expected, number=number
                    ) from exc
            return _json_row(row)  # type: ignore[return-value]

    # --- lifecycle ------------------------------------------------------------------------------

    async def accept_revision(
        self, plan_revision_id: Any, *, conn: asyncpg.Connection | None = None
    ) -> dict[str, Any] | None:
        """Transition a revision from 'draft' to 'accepted' -- the pipeline's acceptance stage.

        The ONLY write this store ever makes to an existing revision, and the only status
        transition the approved architecture names. Guarded by ``WHERE status='draft'`` here and
        by the lifecycle trigger in the database, so neither a lost race nor a direct SQL caller
        can move a revision anywhere else.

        Already ``accepted`` is a no-op that returns the row: acceptance is a conclusion, and
        recording the same conclusion twice is not an error. ``proposed``/``rejected`` raise --
        the architecture authorizes no transition out of them. An unknown id returns ``None``.
        """
        async with self._session(conn) as connection:
            row = await connection.fetchrow(
                f"""
                UPDATE plan_revisions SET status='accepted'
                WHERE plan_revision_id=$1 AND status='draft'
                RETURNING {_REVISION_COLUMNS}
                """,
                _uuid_or_none(plan_revision_id),
            )
            if row is not None:
                return _json_row(row)

            current = await connection.fetchrow(
                f"SELECT {_REVISION_COLUMNS} FROM plan_revisions WHERE plan_revision_id=$1",
                _uuid_or_none(plan_revision_id),
            )
            if current is None:
                return None
            if current["status"] == "accepted":
                return _json_row(current)
            raise PlanRevisionLifecycleError(
                f"revision {plan_revision_id} is '{current['status']}'; the only authorized "
                "lifecycle transition is draft -> accepted"
            )

    # --- derived lineage reads -----------------------------------------------------------------

    async def get_current_revision(self, goal_id: Any) -> dict[str, Any] | None:
        """The chain tip: the one revision of this goal that nothing supersedes.

        Exactly one row by construction -- one root per goal, at most one successor per revision.
        """
        conn = await self._connect()
        try:
            return _json_row(await self._current_revision(conn, _uuid_or_none(goal_id)))
        finally:
            await conn.close()

    async def get_revision(self, plan_revision_id: Any) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            return _json_row(
                await conn.fetchrow(
                    f"SELECT {_REVISION_COLUMNS} FROM plan_revisions WHERE plan_revision_id=$1",
                    _uuid_or_none(plan_revision_id),
                )
            )
        finally:
            await conn.close()

    async def list_revisions(self, goal_id: Any, limit: int = 200) -> list[dict[str, Any]]:
        """Full history, oldest first. Nothing is ever removed from it by a replan."""
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"""
                SELECT {_REVISION_COLUMNS} FROM plan_revisions
                WHERE goal_id=$1 ORDER BY revision_number ASC LIMIT $2
                """,
                _uuid_or_none(goal_id),
                limit,
            )
            return [_json_row(row) for row in rows]  # type: ignore[misc]
        finally:
            await conn.close()

    async def is_current(self, plan_revision_id: Any) -> bool:
        conn = await self._connect()
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM plan_revisions WHERE supersedes_revision_id=$1",
                _uuid_or_none(plan_revision_id),
            )
            present = await conn.fetchval(
                "SELECT 1 FROM plan_revisions WHERE plan_revision_id=$1",
                _uuid_or_none(plan_revision_id),
            )
            return bool(present) and not exists
        finally:
            await conn.close()

    # --- internals -----------------------------------------------------------------------------

    async def _lock_project(self, conn: asyncpg.Connection, project_id: Any) -> None:
        """Serialize per-project revision numbering on the project row itself.

        The numbering rule is per PROJECT, so the project row is the natural and smallest
        serialization point: two Goals of one project queue behind each other for the length of
        one ``max()`` and one INSERT, and two different projects never contend at all. Held for
        the rest of the transaction and released by commit or rollback, like any row lock.
        """
        await conn.fetchval("SELECT id FROM projects WHERE id=$1 FOR UPDATE", project_id)

    def _unique_violation_meaning(
        self,
        exc: asyncpg.UniqueViolationError,
        *,
        goal_id: Any,
        expected: Any = None,
        number: int | None = None,
    ) -> Exception:
        """The domain fact a specific unique constraint reports -- never a blanket meaning."""
        name = exc.constraint_name or ""
        if name == _ROOT_PER_GOAL:
            return PlanLineageError(f"goal {goal_id} already has an initial revision")
        if name == _ONE_SUCCESSOR:
            return StalePlanRevisionError(expected=expected, actual=None, goal_id=goal_id)
        if name == _PROJECT_NUMBER:
            return PlanRevisionAllocationError(
                f"revision number {number} was already taken for this project while its row was "
                "locked; the per-project allocator's serialization point did not hold"
            )
        return exc

    async def _next_revision_number(self, conn: asyncpg.Connection, project_id: Any) -> int:
        """Monotonic per PROJECT (architecture contract section 3), not per goal.

        Callers MUST hold ``_lock_project`` for this project first. Without it two goals of the
        same project read the same ``max()`` and one of them loses to
        ``uq_plan_revisions_project_number`` -- which is the defect this lock exists to remove,
        not a race the constraint is expected to absorb.
        """
        current = await conn.fetchval(
            "SELECT max(revision_number) FROM plan_revisions WHERE project_id=$1", project_id
        )
        return int(current or 0) + 1

    async def _current_revision(
        self, conn: asyncpg.Connection, goal_id: Any
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            f"""
            SELECT {_REVISION_COLUMNS} FROM plan_revisions r
            WHERE r.goal_id=$1
              AND NOT EXISTS (
                  SELECT 1 FROM plan_revisions s
                  WHERE s.supersedes_revision_id = r.plan_revision_id
              )
            """,
            goal_id,
        )

    async def _current_revision_id(self, conn: asyncpg.Connection, goal_id: Any) -> Any:
        row = await self._current_revision(conn, goal_id)
        return row["plan_revision_id"] if row else None


__all__ = ["DEFAULT_DATABASE_URL", "PlanningStore"]
