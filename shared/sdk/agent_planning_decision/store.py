"""Step AT-M3.4 -- asyncpg store for the formal planning decision.

Persistence only, following the store convention the rest of ``shared/sdk`` uses. One method here
carries the whole milestone's weight, and it is the only interesting thing in the file.

**Finalization is ONE transaction.** The successor PlanRevision, the TeamDecision that selects it,
the draft -> accepted transition and the ledger row are written together or not at all. That single
choice removes every partial canonical state this slice could otherwise reach:

* a draft revision with no decision -- impossible, the insert rolled back;
* a decision naming a revision that was never accepted -- impossible, same;
* an accepted revision with no decision -- impossible, same;
* two decisions claiming the same selection -- impossible, ``uq_planning_decisions_discussion``.

No reconciliation daemon, no repair registry and no compensating workflow exists here, because a
transaction is the boundary and none of them is needed once it is.

**The CAS is reused, not copied.** ``PlanningStore.create_successor_revision`` takes ``FOR UPDATE``
on the predecessor and re-checks currency inside that lock; this module passes it the transaction's
connection so that protection runs where it can actually protect, instead of a second copy of the
rule living here. A second implementation of a stale-protection rule is a rule that eventually
disagrees with itself.

**Exactly once, in three layers, none of them a Python lock:**

``uq_planning_decisions_discussion``   one formal decision per discussion, forever
``uq_plan_revisions_one_successor``    (AT-M3.2) one successor per predecessor, forever
``uq_plan_revisions_one_root_per_goal``(AT-M3.2) one root per planless Goal
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import asyncpg

from shared.sdk.agent_planning.models import StalePlanRevisionError
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_planning_decision.models import (
    PLAN_ACCEPTED,
    REVISION_REASON,
    PlanningDecisionStateError,
)
from shared.sdk.agent_team.store import TeamStore

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_DECISION_COLUMNS = """
    planning_decision_id, project_id, goal_id, discussion_id, result_message_id,
    predecessor_plan_revision_id, team_decision_id, resulting_plan_revision_id, outcome,
    idempotency_key, audit_ref, created_at
"""

_LEDGER_UNIQUE = {
    "planning_decisions_discussion_id_key",
    "planning_decisions_idempotency_key_key",
    "planning_decisions_team_decision_id_key",
    "planning_decisions_resulting_plan_revision_id_key",
}


class LedgerRaceLost(RuntimeError):
    """Another worker finalized this same discussion first.

    Not a fault: it is the expected outcome for every worker but one when several finalize the same
    converged discussion, and the caller's correct response is to read the canonical decision, not
    to retry the write.
    """


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _row(record: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(record) if record is not None else None


class PlanningDecisionStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.planning = PlanningStore(self.database_url)
        self.team = TeamStore(self.database_url)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # --- the one write ---------------------------------------------------------------------------

    async def finalize(
        self,
        *,
        project_id: Any,
        goal_id: Any,
        discussion_id: Any,
        thread_id: Any,
        result_message_id: Any,
        predecessor_plan_revision_id: Any,
        decided_by: Any,
        plan: dict[str, Any],
        diff: dict[str, Any],
        evidence: Any,
        idempotency_key: str,
        audit_ref: str | None = None,
    ) -> dict[str, Any]:
        """Write the whole decision, atomically. Raises rather than half-succeeding.

        Order inside the transaction is fixed by the foreign keys and by the lock order AT-M3.2
        established (project row, then predecessor):

        1. create the revision as ``draft`` -- never directly as ``accepted``. Creating it accepted
           would bypass the very acceptance stage the TeamDecision is supposed to be the chooser
           for, which is the AT-M3.2 backlog concern this milestone closes on the autonomous path.
        2. record the TeamDecision, naming the revision it selected.
        3. transition that same revision draft -> accepted, through AT-M3.2's own guarded lifecycle.
        4. insert the ledger row, whose UNIQUE discussion_id is the exactly-once anchor.

        ``StalePlanRevisionError`` from step 1 aborts everything: no decision, no revision, no
        ledger row, and the predecessor untouched. That is the fail-closed path for both the stale
        race and two discussions contending for one predecessor.
        """
        conn = await self._connect()
        try:
            async with conn.transaction():
                if predecessor_plan_revision_id is None:
                    revision = await self.planning.create_initial_revision(
                        {
                            "goal_id": goal_id,
                            "created_by": decided_by,
                            "reason": "initial",
                            "status": "draft",
                            "plan": plan,
                            "trace_ref": str(result_message_id),
                        },
                        conn=conn,
                    )
                else:
                    revision = await self.planning.create_successor_revision(
                        {
                            "goal_id": goal_id,
                            "expected_current_revision_id": predecessor_plan_revision_id,
                            "created_by": decided_by,
                            "reason": REVISION_REASON,
                            "status": "draft",
                            "plan": plan,
                            "diff": diff,
                            "trace_ref": str(result_message_id),
                        },
                        conn=conn,
                    )

                decision = await self.team.record_decision(
                    {
                        "project_id": project_id,
                        "thread_id": thread_id,
                        "proposed_by": decided_by,
                        "options_considered": list(evidence.options_considered),
                        "selected_option": evidence.selected_option,
                        "rationale_summary": evidence.rationale_summary,
                        "dissent_summary": evidence.dissent_summary,
                        "resulting_plan_revision_id": revision["plan_revision_id"],
                        "audit_ref": audit_ref,
                    },
                    conn=conn,
                )

                accepted = await self.planning.accept_revision(
                    revision["plan_revision_id"], conn=conn
                )
                if accepted is None or accepted["status"] != "accepted":
                    # Unreachable through this path -- the revision was created draft microseconds
                    # ago inside this same transaction. Raising rather than continuing means that
                    # if it ever does happen, nothing is recorded at all.
                    raise PlanningDecisionStateError(
                        f"revision {revision['plan_revision_id']} did not accept; "
                        "no planning decision was recorded"
                    )

                try:
                    ledger = await conn.fetchrow(
                        f"""
                        INSERT INTO planning_decisions
                          (project_id, goal_id, discussion_id, result_message_id,
                           predecessor_plan_revision_id, team_decision_id,
                           resulting_plan_revision_id, outcome, idempotency_key, audit_ref)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                        RETURNING {_DECISION_COLUMNS}
                        """,
                        _uuid_or_none(project_id),
                        _uuid_or_none(goal_id),
                        _uuid_or_none(discussion_id),
                        _uuid_or_none(result_message_id),
                        _uuid_or_none(predecessor_plan_revision_id),
                        _uuid_or_none(decision["decision_id"]),
                        _uuid_or_none(revision["plan_revision_id"]),
                        PLAN_ACCEPTED,
                        idempotency_key,
                        audit_ref,
                    )
                except asyncpg.UniqueViolationError as exc:
                    # Someone else finalized this exact discussion while we held the predecessor
                    # lock. Their work is canonical and ours rolls back whole.
                    if (exc.constraint_name or "") in _LEDGER_UNIQUE:
                        raise LedgerRaceLost(str(discussion_id)) from exc
                    raise

            return {
                "planning_decision": _row(ledger),
                "team_decision": decision,
                "plan_revision": accepted,
            }
        finally:
            await conn.close()

    # --- reads -------------------------------------------------------------------------------------

    async def get_by_discussion(self, discussion_id: Any) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            return _row(
                await conn.fetchrow(
                    f"SELECT {_DECISION_COLUMNS} FROM planning_decisions WHERE discussion_id=$1",
                    _uuid_or_none(discussion_id),
                )
            )
        finally:
            await conn.close()

    async def get(self, planning_decision_id: Any) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            return _row(
                await conn.fetchrow(
                    f"""
                    SELECT {_DECISION_COLUMNS} FROM planning_decisions
                    WHERE planning_decision_id=$1
                    """,
                    _uuid_or_none(planning_decision_id),
                )
            )
        finally:
            await conn.close()

    async def list_for_goal(self, goal_id: Any, limit: int = 100) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"""
                SELECT {_DECISION_COLUMNS} FROM planning_decisions
                WHERE goal_id=$1 ORDER BY created_at LIMIT $2
                """,
                _uuid_or_none(goal_id),
                limit,
            )
            return [dict(row) for row in rows]
        finally:
            await conn.close()

    async def get_team_decision(self, decision_id: Any) -> dict[str, Any] | None:
        """Read the AT-M2 TeamDecision this planning decision points at."""
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                """
                SELECT decision_id, project_id, thread_id, proposed_by, options_considered,
                       selected_option, rationale_summary, dissent_summary,
                       resulting_plan_revision_id, audit_ref, created_at
                FROM team_decisions WHERE decision_id=$1
                """,
                _uuid_or_none(decision_id),
            )
            if row is None:
                return None
            record = dict(row)
            value = record.get("options_considered")
            if isinstance(value, str):
                record["options_considered"] = json.loads(value)
            return record
        finally:
            await conn.close()


__all__ = [
    "DEFAULT_DATABASE_URL",
    "LedgerRaceLost",
    "PlanningDecisionStore",
    "StalePlanRevisionError",
]
