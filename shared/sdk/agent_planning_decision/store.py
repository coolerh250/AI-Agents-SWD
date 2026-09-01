"""Step AT-M3.4 -- asyncpg store for the formal planning decision.

Persistence only, following the store convention the rest of ``shared/sdk`` uses. One method here
carries the whole milestone's weight, and it is the only interesting thing in the file.

**Finalization is ONE transaction.** The PlanRevision write (when the outcome calls for one), the
TeamDecision, the draft -> accepted transition and the ledger row are written together or not at
all. That single choice removes every partial canonical state this slice could otherwise reach:

* a draft revision with no decision -- impossible, the insert rolled back;
* a decision naming a revision that was never accepted -- impossible, same;
* an accepted revision with no decision -- impossible, same;
* two decisions claiming the same selection -- impossible, ``UNIQUE (discussion_id)``;
* two decisions accepting the same revision -- impossible, ``UNIQUE (resulting_plan_revision_id)``.

No reconciliation daemon, no repair registry and no compensating workflow exists here, because a
transaction is the boundary and none of them is needed once it is.

**The discussion row is the serialization point.** Every transaction below opens by locking the
``discussion_sessions`` row it is consuming, then re-reads the ledger inside that lock. Workers
racing one discussion therefore queue rather than collide, and every loser sees the winner's
committed row instead of a constraint violation it has to interpret. It is the same "serialize on
the row you are changing" pattern ``PlanningStore._lock_project`` already uses for revision
numbering -- one row lock, not a registry.

**The CAS is reused, not copied.** ``PlanningStore.create_successor_revision`` takes ``FOR UPDATE``
on the predecessor and re-checks currency inside that lock, and ``confirm_current_revision`` does
the same thing without writing, for the outcomes that change no plan. Both run on this
transaction's connection, so the protection runs where it can actually protect instead of a second
copy of the rule living here. A second implementation of a stale-protection rule is a rule that
eventually disagrees with itself.

**Exactly once, in four layers, none of them a Python lock:**

``UNIQUE (discussion_id)``              one formal decision per discussion, forever
``UNIQUE (resulting_plan_revision_id)`` one decision per accepted revision, forever
``uq_plan_revisions_one_successor``     (AT-M3.2) one successor per predecessor, forever
``uq_plan_revisions_one_root_per_goal`` (AT-M3.2) one root per planless Goal
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
    CASE_ACCEPT_DRAFT,
    CASE_CHANGED,
    CASE_INITIAL,
    CASE_NO_CHANGE,
    OUTCOME_FOR_CASE,
    REVISION_REASON,
    PlanningDecisionStateError,
)
from shared.sdk.agent_team.store import TeamStore

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_DECISION_COLUMNS = """
    planning_decision_id, project_id, goal_id, discussion_id, result_message_id,
    candidate_plan_message_id, predecessor_plan_revision_id, team_decision_id,
    resulting_plan_revision_id, outcome, idempotency_key, audit_ref, created_at
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


class RevisionAlreadyDecided(RuntimeError):
    """A DIFFERENT discussion's decision already claimed the revision this one wanted to accept.

    Reachable only in the accept-the-current-draft case, where two discussions bound to the same
    unaccepted revision both conclude it should stand. One of them is right and first; the other is
    a genuine conflict, not a replay, because its own discussion has no decision to return.
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
        case: str,
        project_id: Any,
        goal_id: Any,
        discussion_id: Any,
        thread_id: Any,
        result_message_id: Any,
        candidate_plan_message_id: Any,
        predecessor_plan_revision_id: Any,
        planner_principal_id: Any,
        plan: dict[str, Any],
        diff: dict[str, Any],
        evidence: Any,
        idempotency_key: str,
        audit_ref: str | None = None,
    ) -> dict[str, Any]:
        """Write the whole decision, atomically. Raises rather than half-succeeding.

        Order inside the transaction is fixed: the discussion row first (the thing being consumed),
        then whatever AT-M3.2's own lock order requires (project row, then predecessor), then the
        decision, then the ledger.

        1. lock the discussion and re-read the ledger, so a worker that lost a race learns it here
           rather than through a constraint violation it has to decode.
        2. reach the revision the outcome calls for -- created as ``draft`` for the two cases that
           need a new one, and never directly as ``accepted``. Creating it accepted would bypass
           the very acceptance stage the TeamDecision is supposed to be the chooser for.
        3. record the TeamDecision, naming the revision it selected -- or naming none, for a
           decision that changed nothing.
        4. accept the revision, when there is one, through AT-M3.2's own guarded lifecycle.
        5. insert the ledger row, whose UNIQUE discussion_id is the exactly-once anchor.

        ``StalePlanRevisionError`` from step 2 aborts everything: no decision, no revision, no
        ledger row, and the predecessor untouched. That is the fail-closed path for the stale race,
        for two discussions contending for one predecessor, and -- new in this remediation -- for a
        no-change decision whose plan stopped being current while it was being made.
        """
        conn = await self._connect()
        try:
            async with conn.transaction():
                await conn.fetchval(
                    "SELECT discussion_id FROM discussion_sessions WHERE discussion_id=$1 "
                    "FOR UPDATE",
                    _uuid_or_none(discussion_id),
                )
                settled = await conn.fetchrow(
                    f"SELECT {_DECISION_COLUMNS} FROM planning_decisions WHERE discussion_id=$1",
                    _uuid_or_none(discussion_id),
                )
                if settled is not None:
                    raise LedgerRaceLost(str(discussion_id))

                revision = await self._revision_for(
                    conn,
                    case=case,
                    goal_id=goal_id,
                    predecessor_plan_revision_id=predecessor_plan_revision_id,
                    planner_principal_id=planner_principal_id,
                    plan=plan,
                    diff=diff,
                    result_message_id=result_message_id,
                )

                decision = await self.team.record_decision(
                    {
                        "project_id": project_id,
                        "thread_id": thread_id,
                        "proposed_by": planner_principal_id,
                        "options_considered": list(evidence.options_considered),
                        "selected_option": evidence.selected_option,
                        "rationale_summary": evidence.rationale_summary,
                        "dissent_summary": evidence.dissent_summary,
                        "resulting_plan_revision_id": (
                            revision["plan_revision_id"] if revision else None
                        ),
                        "audit_ref": audit_ref,
                    },
                    conn=conn,
                )

                accepted = revision
                if revision is not None:
                    accepted = await self.planning.accept_revision(
                        revision["plan_revision_id"], conn=conn
                    )
                    if accepted is None or accepted["status"] != "accepted":
                        # Unreachable through this path -- the revision is draft and locked inside
                        # this same transaction. Raising rather than continuing means that if it
                        # ever does happen, nothing is recorded at all.
                        raise PlanningDecisionStateError(
                            f"revision {revision['plan_revision_id']} did not accept; "
                            "no planning decision was recorded"
                        )

                try:
                    ledger = await conn.fetchrow(
                        f"""
                        INSERT INTO planning_decisions
                          (project_id, goal_id, discussion_id, result_message_id,
                           candidate_plan_message_id, predecessor_plan_revision_id,
                           team_decision_id, resulting_plan_revision_id, outcome,
                           idempotency_key, audit_ref)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                        RETURNING {_DECISION_COLUMNS}
                        """,
                        _uuid_or_none(project_id),
                        _uuid_or_none(goal_id),
                        _uuid_or_none(discussion_id),
                        _uuid_or_none(result_message_id),
                        _uuid_or_none(candidate_plan_message_id),
                        _uuid_or_none(predecessor_plan_revision_id),
                        _uuid_or_none(decision["decision_id"]),
                        _uuid_or_none(accepted["plan_revision_id"]) if accepted else None,
                        OUTCOME_FOR_CASE[case],
                        idempotency_key,
                        audit_ref,
                    )
                except asyncpg.UniqueViolationError as exc:
                    name = exc.constraint_name or ""
                    if name == "planning_decisions_resulting_plan_revision_id_key":
                        # Another DISCUSSION's decision already accepted this revision. Ours rolls
                        # back whole, and this is a conflict rather than a replay: there is no
                        # decision of our own to return.
                        raise RevisionAlreadyDecided(
                            f"revision {accepted['plan_revision_id'] if accepted else None} was "
                            "already accepted by another planning decision"
                        ) from exc
                    if name in _LEDGER_UNIQUE:
                        raise LedgerRaceLost(str(discussion_id)) from exc
                    raise

            return {
                "planning_decision": _row(ledger),
                "team_decision": decision,
                "plan_revision": accepted,
            }
        finally:
            await conn.close()

    async def _revision_for(
        self,
        conn: asyncpg.Connection,
        *,
        case: str,
        goal_id: Any,
        predecessor_plan_revision_id: Any,
        planner_principal_id: Any,
        plan: dict[str, Any],
        diff: dict[str, Any],
        result_message_id: Any,
    ) -> dict[str, Any] | None:
        """The revision this outcome acts on: created, confirmed, or none at all.

        Four cases, and the interesting thing about the last two is what they do NOT write. A
        decision that changes nothing must not mint a superseding revision holding an identical
        plan -- that permanently consumes the predecessor's one successor slot for a decision that
        changed nothing, which is the defect this remediation removes.
        """
        if case == CASE_INITIAL:
            return await self.planning.create_initial_revision(
                {
                    "goal_id": goal_id,
                    "created_by": planner_principal_id,
                    "reason": "initial",
                    "status": "draft",
                    "plan": plan,
                    "trace_ref": str(result_message_id),
                },
                conn=conn,
            )

        if case == CASE_CHANGED:
            return await self.planning.create_successor_revision(
                {
                    "goal_id": goal_id,
                    "expected_current_revision_id": predecessor_plan_revision_id,
                    "created_by": planner_principal_id,
                    "reason": REVISION_REASON,
                    "status": "draft",
                    "plan": plan,
                    "diff": diff,
                    "trace_ref": str(result_message_id),
                },
                conn=conn,
            )

        # Both remaining cases write nothing to plan_revisions, and both still have a currency
        # claim to defend, so both take the same lock the writing path takes.
        current = await self.planning.confirm_current_revision(
            goal_id, predecessor_plan_revision_id, conn=conn
        )

        if case == CASE_ACCEPT_DRAFT:
            if current["status"] != "draft":
                # It became accepted between the read and this lock -- by another discussion's
                # decision. Fail closed rather than record a second acceptance of one revision.
                raise PlanningDecisionStateError(
                    f"revision {current['plan_revision_id']} is '{current['status']}', not "
                    "'draft'; it was accepted while this decision was being made"
                )
            return current

        if case == CASE_NO_CHANGE:
            return None

        raise PlanningDecisionStateError(f"unknown planning case {case!r}")

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

    async def get_message(self, message_id: Any) -> dict[str, Any] | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM team_messages WHERE message_id=$1", _uuid_or_none(message_id)
            )
            if row is None:
                return None
            record = dict(row)
            for key in ("content", "artifact_refs"):
                if isinstance(record.get(key), str):
                    record[key] = json.loads(record[key])
            return record
        finally:
            await conn.close()


__all__ = [
    "DEFAULT_DATABASE_URL",
    "LedgerRaceLost",
    "PlanningDecisionStore",
    "RevisionAlreadyDecided",
    "StalePlanRevisionError",
]
