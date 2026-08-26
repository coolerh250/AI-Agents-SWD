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
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

from shared.sdk.agent_planning.models import (
    PlanLineageError,
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

#: Raised by uq_plan_revisions_one_successor when a second caller derives from the same
#: predecessor, and by uq_plan_revisions_one_root_per_goal for a duplicate root.
_UNIQUE_VIOLATION = "23505"


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

    async def create_initial_revision(self, data: dict[str, Any]) -> dict[str, Any]:
        """The root revision for a goal. ``reason`` is always 'initial' (DB-enforced).

        ``uq_plan_revisions_one_root_per_goal`` makes a second root impossible, so calling this
        twice for one goal raises rather than forking the lineage into an unresolvable pair of
        tips.
        """
        conn = await self._connect()
        try:
            async with conn.transaction():
                goal = await conn.fetchrow(
                    "SELECT goal_id, project_id FROM goals WHERE goal_id=$1",
                    _uuid_or_none(data["goal_id"]),
                )
                if goal is None:
                    raise PlanLineageError(f"unknown goal {data['goal_id']}")
                number = await self._next_revision_number(conn, goal["project_id"])
                try:
                    row = await conn.fetchrow(
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
                    raise PlanLineageError(
                        f"goal {data['goal_id']} already has an initial revision"
                    ) from exc
            return _json_row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

    async def create_successor_revision(self, data: dict[str, Any]) -> dict[str, Any]:
        """Append revision N+1, superseding ``data["expected_current_revision_id"]``.

        Fail-closed in every direction: an unknown predecessor, a predecessor belonging to a
        different goal, or a predecessor that is no longer current all raise rather than write.
        The predecessor row itself is never modified -- supersession is a fact the successor's own
        row asserts.
        """
        expected = _uuid_or_none(data["expected_current_revision_id"])
        goal_id = _uuid_or_none(data["goal_id"])

        conn = await self._connect()
        try:
            async with conn.transaction():
                # Lock the predecessor first. Two concurrent successors for the same predecessor
                # serialise here rather than racing to the unique index.
                predecessor = await conn.fetchrow(
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
                successor_id = await conn.fetchval(
                    "SELECT plan_revision_id FROM plan_revisions WHERE supersedes_revision_id=$1",
                    expected,
                )
                if successor_id is not None:
                    raise StalePlanRevisionError(
                        expected=expected,
                        actual=await self._current_revision_id(conn, goal_id),
                        goal_id=goal_id,
                    )

                number = await self._next_revision_number(conn, predecessor["project_id"])
                try:
                    row = await conn.fetchrow(
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
                    # The last line of defence, and the one that holds for a caller that never
                    # took the lock above: uq_plan_revisions_one_successor rejected a second
                    # successor for this predecessor. Reported as staleness, which is what it is.
                    if "one_successor" in str(exc):
                        raise StalePlanRevisionError(
                            expected=expected, actual=None, goal_id=goal_id
                        ) from exc
                    raise
            return _json_row(row)  # type: ignore[return-value]
        finally:
            await conn.close()

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

    async def _next_revision_number(self, conn: asyncpg.Connection, project_id: Any) -> int:
        """Monotonic per PROJECT (architecture contract section 3), not per goal.

        A collision between two goals of the same project racing for the same number is caught by
        ``uq_plan_revisions_project_number`` and surfaces as a unique violation rather than a
        silently reused number.
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
