"""Step AT-M3.6A -- read-only query projections over the canonical autonomous-runtime tables.

**Every statement in this module is a SELECT.** There is no INSERT, UPDATE, DELETE, no DDL, no
advisory lock, no ``FOR UPDATE``, no transaction that could take one, and no Redis client. That is
not a convention here, it is the slice's whole contract: an observability layer that can write is
an observability layer that will eventually be asked to fix something, and the fix becomes a second
authority over state the canonical tables already own.

WHAT THIS MODULE IS NOT
-----------------------
It is not a domain model. No Goal, WorkItem, TeamDecision, PlanRevision, ExecutionUnit, Assignment
or Dispatch is redefined, copied, cached or persisted here -- the queries below project the
canonical rows AT-M2, AT-M3.1-3.5 already own, and every cross-entity link travels as a real UUID.
Nothing joins on a title, a description, an agent display name or step prose.

POSTGRESQL IS THE ONLY SOURCE
-----------------------------
Redis is absent from this file on purpose. AT-M3.5 is explicit that stream delivery is
at-least-once and that ``plan_execution_dispatches`` is the exactly-once canonical boundary, so
"not in Redis" would not mean "not dispatched" and "a message exists" would not mean "a canonical
dispatch happened". The dispatch row and its ``published_at`` are the truth, and they are read
here.

SCOPE FAILS CLOSED
------------------
Every lookup resolves through canonical FK lineage rather than through a caller-supplied filter.
A unit is reached from its own ``plan_revision_id``; a dependency edge is accepted only when BOTH
endpoints belong to the revision being read; a Goal's audit evidence is probed with identifiers
read out of that Goal's own rows. An execution unit belonging to another Project therefore cannot
appear inside this Goal's view -- not because a filter excludes it, but because no join reaches it.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

# The AT-M3.5 cancellation vocabulary, imported rather than copied. These are the exact tuples
# `PlanDelegationStore._assert_lineage_not_cancelled` refuses new work on, so the read surface and
# the write surface cannot drift into two different answers to "is this lineage cancelled".
from shared.sdk.plan_delegation.store import (
    _CANCELLED_LIFECYCLE_STATES,
    _CANCELLED_STATUSES,
)

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

#: Bounds for every collection this module can return. No endpoint returns "every event ever":
#: audit_logs, team_messages and reasoning_invocations all grow without limit, and an unbounded
#: read of any of them is a production incident waiting for the first busy Goal.
MAX_PAGE = 500
DEFAULT_PAGE = 100


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def bounded(limit: Any, default: int = DEFAULT_PAGE) -> int:
    """The repository's existing limit convention, in one place."""
    try:
        requested = int(limit) if limit is not None else default
    except (TypeError, ValueError):
        requested = default
    return max(1, min(requested, MAX_PAGE))


def bounded_offset(offset: Any) -> int:
    try:
        return max(0, int(offset or 0))
    except (TypeError, ValueError):
        return 0


def _decode(row: asyncpg.Record | None, *fields: str) -> dict[str, Any] | None:
    """asyncpg hands JSONB back as text unless a codec is registered; decode the named columns."""
    if row is None:
        return None
    data = dict(row)
    for field in fields:
        value = data.get(field)
        if isinstance(value, str):
            try:
                data[field] = json.loads(value)
            except ValueError:  # pragma: no cover - a non-JSON JSONB column cannot occur
                data[field] = None
    return data


_UNIT_SELECT = """
    SELECT u.execution_unit_id, u.plan_execution_graph_id, u.plan_revision_id, u.step_key,
           u.project_id, u.goal_id, u.work_item_id, u.required_capabilities, u.expected_outputs,
           u.intended_owner_role, u.state, u.unavailable_reason, u.assigned_principal_id,
           u.assigned_role, u.assigned_agent_key, u.routing_decision_id, u.assigned_at,
           u.disposition, u.result_ref, u.completed_at, u.created_at, u.updated_at,
           w.title           AS work_item_title,
           w.work_item_key   AS work_item_key,
           w.status          AS work_item_status,
           w.lifecycle_state AS work_item_lifecycle_state,
           ap.display_name   AS assigned_principal_name,
           ap.principal_type AS assigned_principal_type,
           rd.requested_capability AS routing_requested_capability,
           rd.outcome              AS routing_outcome,
           rd.reason               AS routing_reason,
           rd.selected_role        AS routing_selected_role,
           rd.selected_stream      AS routing_selected_stream,
           rd.candidates_considered,
           rd.created_at           AS routing_decided_at,
           d.correlation_id, d.target_stream, d.published_at,
           d.created_at            AS dispatch_created_at,
           d.plan_revision_id      AS dispatch_plan_revision_id,
           d.step_key              AS dispatch_step_key,
           d.assigned_principal_id AS dispatch_principal_id,
           d.work_item_id          AS dispatch_work_item_id
    FROM plan_execution_units u
    JOIN project_work_items w ON w.id = u.work_item_id
    LEFT JOIN actor_principals ap ON ap.principal_id = u.assigned_principal_id
    LEFT JOIN agent_routing_decisions rd ON rd.routing_decision_id = u.routing_decision_id
    LEFT JOIN plan_execution_dispatches d ON d.execution_unit_id = u.execution_unit_id
"""


class AutonomyReadStore:
    """SELECT-only projections over the canonical runtime.

    Follows the convention ``shared/sdk/agent_team/store.py`` set and every AT-M3 slice reused:
    ``DATABASE_URL`` from the environment, a connection per call by default, plain dict rows out.
    ``session()`` is the one addition -- an opt-in way for a composite read to hold one connection
    across its eighteen queries instead of opening eighteen.

    No pool and no cache. A cached answer would be a stored copy of derived state, which is exactly
    what this slice must not create.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self._shared: asyncpg.Connection | None = None

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=5)

    @asynccontextmanager
    async def session(self) -> AsyncIterator["AutonomyReadStore"]:
        """Hold ONE connection open across a composite read.

        A Goal overview asks this store roughly eighteen questions -- goal, lineage, roster,
        discussions, participants, turns, decisions, revisions, graphs, units, edges. Every AT-M3
        store connects per call, which is right for a command that issues two or three queries and
        wrong for one page view that issues eighteen: the connection handshakes would cost more
        than the queries.

        So the per-call default is unchanged and this is opt-in. Nothing about it makes the read
        transactional -- there is no BEGIN here and no isolation level is set. A composite read may
        still observe rows committed between two of its queries, which is the same guarantee
        eighteen separate connections gave, stated rather than accidentally improved.
        """
        conn = await self._connect()
        previous = self._shared
        self._shared = conn
        try:
            yield self
        finally:
            self._shared = previous
            await conn.close()

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[asyncpg.Connection]:
        """The shared connection when one is open, otherwise a private one closed on exit."""
        if self._shared is not None:
            yield self._shared
            return
        async with self._session() as conn:
            yield conn

    # --- goal / lineage --------------------------------------------------------------------------

    async def get_goal(self, goal_id: Any) -> dict[str, Any] | None:
        """The Goal and the Project it belongs to. The anchor every other read hangs off."""
        async with self._session() as conn:
            return _decode(
                await conn.fetchrow(
                    """
                    SELECT g.goal_id, g.project_id, g.statement, g.acceptance_criteria,
                           g.constraints, g.created_by, g.status, g.created_at,
                           p.title  AS project_title,
                           p.status AS project_status,
                           p.autonomy_level, p.risk_level
                    FROM goals g
                    JOIN projects p ON p.id = g.project_id
                    WHERE g.goal_id = $1
                    """,
                    _uuid(goal_id),
                ),
                "acceptance_criteria",
                "constraints",
            )

    async def get_execution_lineage(self, goal_id: Any) -> dict[str, Any] | None:
        """The Goal's single primary Work Item, and whether that lineage has been cancelled.

        ``is_cancelled`` is derived from the two vocabularies ``project_work_items`` genuinely
        carries -- the planner ``status`` and the delivery ``lifecycle_state`` -- using the exact
        tuples AT-M3.5 refuses new work on. There is no second cancellation model.
        """
        async with self._session() as conn:
            row = await conn.fetchrow(
                """
                SELECT l.goal_id, l.project_id, l.primary_work_item_id, l.created_at,
                       w.title, w.work_item_key, w.status, w.lifecycle_state, w.updated_at
                FROM goal_execution_lineage l
                JOIN project_work_items w ON w.id = l.primary_work_item_id
                WHERE l.goal_id = $1
                """,
                _uuid(goal_id),
            )
        if row is None:
            return None
        return {
            "goal_id": row["goal_id"],
            "project_id": row["project_id"],
            "primary_work_item_id": row["primary_work_item_id"],
            "primary_work_item_title": row["title"],
            "primary_work_item_key": row["work_item_key"],
            "primary_work_item_status": row["status"],
            "primary_work_item_lifecycle_state": row["lifecycle_state"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "is_cancelled": (
                row["status"] in _CANCELLED_STATUSES
                or row["lifecycle_state"] in _CANCELLED_LIFECYCLE_STATES
            ),
        }

    # --- team ------------------------------------------------------------------------------------

    async def team_members(self, project_id: Any, *, limit: int = MAX_PAGE) -> list[dict[str, Any]]:
        """The project's roster as it stands, including members who have left.

        Membership is historical by contract (``left_at``, never deleted), so a departed member is
        reported with its state rather than hidden -- a step assigned to someone who has since left
        must stay explicable.
        """
        async with self._session() as conn:
            rows = await conn.fetch(
                """
                SELECT m.membership_id, m.agent_principal_id, m.functional_role,
                       m.membership_state, m.joined_at, m.left_at,
                       pr.display_name, pr.principal_type,
                       ap.agent_key, ap.role AS profile_role, ap.capabilities,
                       ap.status AS profile_status, ap.transport_stream
                FROM project_team_memberships m
                JOIN actor_principals pr ON pr.principal_id = m.agent_principal_id
                LEFT JOIN agent_profiles ap ON ap.principal_id = m.agent_principal_id
                WHERE m.project_id = $1
                ORDER BY m.joined_at, m.membership_id
                LIMIT $2
                """,
                _uuid(project_id),
                bounded(limit),
            )
            return [_decode(row, "capabilities") for row in rows]  # type: ignore[misc]

    # --- plan revisions ---------------------------------------------------------------------------

    async def list_revisions(
        self, goal_id: Any, *, limit: int = DEFAULT_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """The Goal's PlanRevision history, oldest first, with currentness derived from lineage.

        ``is_current`` is not a column and never will be: the tip is the revision nothing
        supersedes, which is what ``PlanningStore`` computes on every write path. Revision N stays
        in this list when N+1 appears -- it stops being current, which is a fact about the lineage
        and not about N. Nothing is ever hidden because something newer exists.

        The ``plan`` body is deliberately NOT selected here. A history page is navigation; the plan
        of one revision is read through the revision detail, and pulling every JSONB plan for a
        long-lived Goal into a list response is the obvious way to make this endpoint slow.
        """
        async with self._session() as conn:
            total = await conn.fetchval(
                "SELECT count(*) FROM plan_revisions WHERE goal_id=$1", _uuid(goal_id)
            )
            rows = await conn.fetch(
                """
                SELECT r.plan_revision_id, r.project_id, r.goal_id, r.revision_number,
                       r.created_by, r.reason, r.supersedes_revision_id, r.status, r.trace_ref,
                       r.created_at,
                       NOT EXISTS (
                           SELECT 1 FROM plan_revisions s
                           WHERE s.supersedes_revision_id = r.plan_revision_id
                       ) AS is_current,
                       s2.plan_revision_id AS superseded_by_revision_id,
                       g.plan_execution_graph_id, g.step_count,
                       g.created_at AS materialized_at
                FROM plan_revisions r
                LEFT JOIN plan_revisions s2 ON s2.supersedes_revision_id = r.plan_revision_id
                LEFT JOIN plan_execution_graphs g ON g.plan_revision_id = r.plan_revision_id
                WHERE r.goal_id = $1
                ORDER BY r.revision_number ASC
                LIMIT $2 OFFSET $3
                """,
                _uuid(goal_id),
                bounded(limit),
                bounded_offset(offset),
            )
            return {"total": int(total or 0), "rows": [dict(row) for row in rows]}

    async def count_revisions(self, goal_id: Any) -> int:
        """How many revisions this Goal has had. A COUNT, not a page fetched to be measured."""
        async with self._session() as conn:
            return int(
                await conn.fetchval(
                    "SELECT count(*) FROM plan_revisions WHERE goal_id=$1", _uuid(goal_id)
                )
                or 0
            )

    async def get_revision(self, plan_revision_id: Any) -> dict[str, Any] | None:
        """One revision including its stored plan, its currentness and its graph if materialized."""
        async with self._session() as conn:
            return _decode(
                await conn.fetchrow(
                    """
                    SELECT r.plan_revision_id, r.project_id, r.goal_id, r.revision_number,
                           r.created_by, r.reason, r.supersedes_revision_id, r.status, r.plan,
                           r.trace_ref, r.created_at,
                           NOT EXISTS (
                               SELECT 1 FROM plan_revisions s
                               WHERE s.supersedes_revision_id = r.plan_revision_id
                           ) AS is_current,
                           s2.plan_revision_id AS superseded_by_revision_id,
                           g.plan_execution_graph_id, g.step_count,
                           g.created_at AS materialized_at, g.materialized_by
                    FROM plan_revisions r
                    LEFT JOIN plan_revisions s2 ON s2.supersedes_revision_id = r.plan_revision_id
                    LEFT JOIN plan_execution_graphs g ON g.plan_revision_id = r.plan_revision_id
                    WHERE r.plan_revision_id = $1
                    """,
                    _uuid(plan_revision_id),
                ),
                "plan",
            )

    async def get_current_revision(self, goal_id: Any) -> dict[str, Any] | None:
        """The chain tip: the one revision of this Goal that nothing supersedes."""
        async with self._session() as conn:
            return _decode(
                await conn.fetchrow(
                    """
                    SELECT r.plan_revision_id, r.project_id, r.goal_id, r.revision_number,
                           r.created_by, r.reason, r.supersedes_revision_id, r.status, r.plan,
                           r.trace_ref, r.created_at,
                           g.plan_execution_graph_id, g.step_count,
                           g.created_at AS materialized_at, g.materialized_by
                    FROM plan_revisions r
                    LEFT JOIN plan_execution_graphs g ON g.plan_revision_id = r.plan_revision_id
                    WHERE r.goal_id = $1
                      AND NOT EXISTS (
                          SELECT 1 FROM plan_revisions s
                          WHERE s.supersedes_revision_id = r.plan_revision_id
                      )
                    """,
                    _uuid(goal_id),
                ),
                "plan",
            )

    # --- discussion / decision --------------------------------------------------------------------

    async def list_discussions(
        self, goal_id: Any, *, limit: int = DEFAULT_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """Every discussion this Goal has had, newest first, each with its exact plan binding.

        ``plan_revision_is_current`` is the AT-M3.3 semantic, derived here the same way
        ``DeliberationService.plan_currency`` derives it: a discussion is permanently about the
        exact revision it opened against, and what moves is the world around it. A discussion bound
        to NO revision is current exactly while the Goal still has no plan.
        """
        async with self._session() as conn:
            total = await conn.fetchval(
                "SELECT count(*) FROM discussion_sessions WHERE goal_id=$1", _uuid(goal_id)
            )
            rows = await conn.fetch(
                """
                SELECT d.discussion_id, d.project_id, d.goal_id, d.plan_revision_id, d.thread_id,
                       d.opened_by, d.topic, d.required_capabilities, d.max_rounds, d.max_messages,
                       d.max_invocations, d.max_turns_per_participant, d.deadline_at,
                       d.current_round, d.turns_taken, d.messages_posted, d.invocations_started,
                       d.state, d.stop_reason, d.result_message_id, d.created_at, d.closed_at,
                       (d.deadline_at <= now()) AS deadline_expired,
                       CASE
                           WHEN d.plan_revision_id IS NULL THEN NOT EXISTS (
                               SELECT 1 FROM plan_revisions r WHERE r.goal_id = d.goal_id
                           )
                           ELSE NOT EXISTS (
                               SELECT 1 FROM plan_revisions s
                               WHERE s.supersedes_revision_id = d.plan_revision_id
                           )
                       END AS plan_revision_is_current,
                       m.summary AS result_message_summary,
                       pd.planning_decision_id, pd.team_decision_id,
                       pd.resulting_plan_revision_id, pd.outcome AS planning_outcome
                FROM discussion_sessions d
                LEFT JOIN team_messages m ON m.message_id = d.result_message_id
                LEFT JOIN planning_decisions pd ON pd.discussion_id = d.discussion_id
                WHERE d.goal_id = $1
                ORDER BY d.created_at DESC, d.discussion_id DESC
                LIMIT $2 OFFSET $3
                """,
                _uuid(goal_id),
                bounded(limit),
                bounded_offset(offset),
            )
            return {
                "total": int(total or 0),
                "rows": [_decode(row, "required_capabilities") for row in rows],
            }

    async def get_discussion(self, discussion_id: Any) -> dict[str, Any] | None:
        """One discussion, with the Goal and thread it is anchored to.

        The ``thread_id`` returned here is what scopes the reasoning read: an invocation is reached
        through the discussion's OWN thread rather than through a caller-supplied project filter,
        so another Goal's reasoning cannot be pulled into this discussion's view.
        """
        async with self._session() as conn:
            return _decode(
                await conn.fetchrow(
                    """
                    SELECT d.discussion_id, d.project_id, d.goal_id, d.plan_revision_id,
                           d.thread_id, d.topic, d.state, d.stop_reason, d.required_capabilities,
                           d.created_at, d.closed_at
                    FROM discussion_sessions d
                    WHERE d.discussion_id = $1
                    """,
                    _uuid(discussion_id),
                ),
                "required_capabilities",
            )

    async def discussion_participants(self, discussion_id: Any) -> list[dict[str, Any]]:
        """Seats in speaking order, with the capabilities each was selected for and the router's
        own reason -- carried through verbatim, never re-derived."""
        async with self._session() as conn:
            rows = await conn.fetch(
                """
                SELECT p.participant_id, p.principal_id, p.agent_key, p.functional_role,
                       p.matched_capabilities, p.selection_reason, p.seat_index, p.turns_taken,
                       pr.display_name
                FROM discussion_participants p
                JOIN actor_principals pr ON pr.principal_id = p.principal_id
                WHERE p.discussion_id = $1
                ORDER BY p.seat_index
                """,
                _uuid(discussion_id),
            )
            return [_decode(row, "matched_capabilities") for row in rows]  # type: ignore[misc]

    async def discussion_turns(
        self, discussion_id: Any, *, limit: int = DEFAULT_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """The turn ledger joined to the SUMMARY of the message each turn produced.

        ``team_messages.summary`` is a persisted, safety-screened collaboration artifact bounded to
        2000 characters by ``chk_team_messages_summary``. The message body, the reasoning artifact,
        the prompt and the completion are none of them selected here.
        """
        async with self._session() as conn:
            total = await conn.fetchval(
                "SELECT count(*) FROM discussion_turns WHERE discussion_id=$1",
                _uuid(discussion_id),
            )
            rows = await conn.fetch(
                """
                SELECT t.turn_id, t.round_index, t.seat_index, t.speaker_principal_id,
                       t.addressed_principal_id, t.addressed_team, t.intent, t.reasoning_verb,
                       t.reasoning_invocation_id, t.message_id, t.status, t.concern_count,
                       t.created_at, t.completed_at,
                       m.message_type, m.summary AS message_summary, m.created_at AS message_at,
                       pr.display_name AS speaker_display_name
                FROM discussion_turns t
                LEFT JOIN team_messages m ON m.message_id = t.message_id
                LEFT JOIN actor_principals pr ON pr.principal_id = t.speaker_principal_id
                WHERE t.discussion_id = $1
                ORDER BY t.round_index, t.seat_index
                LIMIT $2 OFFSET $3
                """,
                _uuid(discussion_id),
                bounded(limit),
                bounded_offset(offset),
            )
            return {"total": int(total or 0), "rows": [dict(row) for row in rows]}

    async def open_reasoning_count(self, thread_id: Any) -> int:
        """How many reasoning invocations on this discussion's thread are still 'started'."""
        if thread_id is None:
            return 0
        async with self._session() as conn:
            return int(
                await conn.fetchval(
                    "SELECT count(*) FROM reasoning_invocations "
                    "WHERE thread_id=$1 AND status='started'",
                    _uuid(thread_id),
                )
                or 0
            )

    async def list_reasoning_invocations(
        self, thread_id: Any, discussion_id: Any, *, limit: int = DEFAULT_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """Safe operational metadata for the reasoning behind one discussion.

        THE ARTIFACT BODY IS NOT SELECTED. ``reasoning_invocations.artifact`` is the durable
        recovery record AT-M3.4 added so a succeeded invocation can be replayed; reading it here
        would make this endpoint a second business surface for a decision that already has one.
        The business artifact is read through TeamMessage, the planning candidate and PlanRevision.
        ``artifact_type`` -- a type name from a closed CHECK -- is exposed; the object is not.

        No prompt, no completion, no scratchpad and no hidden reasoning exists in these columns to
        expose: AT-D03 R8 / INV-04 keeps them out of the schema entirely. ``failure_reason`` is the
        sanitized reason AT-M3.1 stores, and it is passed through rather than re-derived.
        """
        async with self._session() as conn:
            total = await conn.fetchval(
                "SELECT count(*) FROM reasoning_invocations WHERE thread_id=$1", _uuid(thread_id)
            )
            rows = await conn.fetch(
                """
                SELECT r.invocation_id, r.project_id, r.thread_id, r.requested_by_principal_id,
                       r.reasoning_verb, r.requested_provider_name, r.provider_mode, r.model_name,
                       r.round_number, r.status, r.attempt, r.artifact_type, r.failure_category,
                       r.failure_reason, r.outcome_ref, r.input_tokens, r.output_tokens,
                       r.estimated_cost_usd, r.latency_ms, r.correlation_id, r.started_at,
                       r.completed_at, r.created_at,
                       t.discussion_id, t.round_index, t.seat_index, t.intent,
                       t.status AS turn_status, t.message_id
                FROM reasoning_invocations r
                LEFT JOIN discussion_turns t
                       ON t.reasoning_invocation_id = r.invocation_id
                      AND t.discussion_id = $2
                WHERE r.thread_id = $1
                ORDER BY r.created_at ASC, r.invocation_id ASC
                LIMIT $3 OFFSET $4
                """,
                _uuid(thread_id),
                _uuid(discussion_id),
                bounded(limit),
                bounded_offset(offset),
            )
            return {"total": int(total or 0), "rows": [dict(row) for row in rows]}

    async def list_planning_decisions(
        self, goal_id: Any, *, limit: int = DEFAULT_PAGE
    ) -> list[dict[str, Any]]:
        """The formal decisions this Goal's team has recorded, newest first, with the TeamDecision
        each one produced and the candidate message the plan came from."""
        async with self._session() as conn:
            rows = await conn.fetch(
                """
                SELECT pd.planning_decision_id, pd.project_id, pd.goal_id, pd.discussion_id,
                       pd.result_message_id, pd.candidate_plan_message_id,
                       pd.predecessor_plan_revision_id, pd.team_decision_id,
                       pd.resulting_plan_revision_id, pd.outcome, pd.created_at,
                       td.thread_id       AS team_decision_thread_id,
                       td.proposed_by     AS team_decision_proposed_by,
                       td.options_considered, td.selected_option, td.rationale_summary,
                       td.dissent_summary, td.created_at AS team_decision_at,
                       cm.summary         AS candidate_message_summary,
                       cm.message_type    AS candidate_message_type,
                       cm.created_at      AS candidate_message_at,
                       r.status           AS resulting_revision_status,
                       r.revision_number  AS resulting_revision_number,
                       CASE WHEN pd.resulting_plan_revision_id IS NULL THEN NULL ELSE NOT EXISTS (
                           SELECT 1 FROM plan_revisions s
                           WHERE s.supersedes_revision_id = pd.resulting_plan_revision_id
                       ) END AS resulting_revision_is_current
                FROM planning_decisions pd
                LEFT JOIN team_decisions td ON td.decision_id = pd.team_decision_id
                LEFT JOIN team_messages cm ON cm.message_id = pd.candidate_plan_message_id
                LEFT JOIN plan_revisions r ON r.plan_revision_id = pd.resulting_plan_revision_id
                WHERE pd.goal_id = $1
                ORDER BY pd.created_at DESC, pd.planning_decision_id DESC
                LIMIT $2
                """,
                _uuid(goal_id),
                bounded(limit),
            )
            return [_decode(row, "options_considered") for row in rows]  # type: ignore[misc]

    # --- execution graph --------------------------------------------------------------------------

    async def list_graphs(self, goal_id: Any) -> list[dict[str, Any]]:
        """Every execution graph this Goal has ever materialized, with per-graph state counts.

        ONE query for the graphs and ONE for all of their counts -- never one count query per
        graph. Currentness is derived per graph from its revision's lineage, so a superseded
        revision's graph is reported as historical rather than being hidden or re-labelled.
        """
        async with self._session() as conn:
            graphs = await conn.fetch(
                """
                SELECT g.plan_execution_graph_id, g.project_id, g.goal_id, g.plan_revision_id,
                       g.step_count, g.materialized_by, g.created_at,
                       r.revision_number, r.status AS revision_status,
                       NOT EXISTS (
                           SELECT 1 FROM plan_revisions s
                           WHERE s.supersedes_revision_id = g.plan_revision_id
                       ) AS is_current
                FROM plan_execution_graphs g
                JOIN plan_revisions r ON r.plan_revision_id = g.plan_revision_id
                WHERE g.goal_id = $1
                ORDER BY r.revision_number ASC
                """,
                _uuid(goal_id),
            )
            counts = await conn.fetch(
                """
                SELECT u.plan_revision_id, u.state, count(*) AS n,
                       count(*) FILTER (WHERE u.unavailable_reason IS NOT NULL) AS unavailable,
                       count(d.execution_unit_id) AS dispatched_rows,
                       count(d.published_at)      AS published_rows
                FROM plan_execution_units u
                LEFT JOIN plan_execution_dispatches d
                       ON d.execution_unit_id = u.execution_unit_id
                WHERE u.goal_id = $1
                GROUP BY u.plan_revision_id, u.state
                """,
                _uuid(goal_id),
            )

        by_revision: dict[Any, dict[str, Any]] = {}
        for row in counts:
            bucket = by_revision.setdefault(
                row["plan_revision_id"],
                {"states": {}, "unavailable": 0, "dispatch_rows": 0, "published_rows": 0},
            )
            bucket["states"][row["state"]] = int(row["n"])
            bucket["unavailable"] += int(row["unavailable"] or 0)
            bucket["dispatch_rows"] += int(row["dispatched_rows"] or 0)
            bucket["published_rows"] += int(row["published_rows"] or 0)
        return [{**dict(g), "counts": by_revision.get(g["plan_revision_id"], {})} for g in graphs]

    async def get_graph(self, plan_revision_id: Any) -> dict[str, Any] | None:
        """One graph header, with the Goal's primary work item and the revision's currentness."""
        async with self._session() as conn:
            return _decode(
                await conn.fetchrow(
                    """
                    SELECT g.plan_execution_graph_id, g.project_id, g.goal_id, g.plan_revision_id,
                           g.step_count, g.materialized_by, g.audit_ref, g.created_at,
                           r.revision_number, r.status AS revision_status, r.reason,
                           r.supersedes_revision_id, r.created_by AS revision_created_by,
                           r.created_at AS revision_created_at,
                           NOT EXISTS (
                               SELECT 1 FROM plan_revisions s
                               WHERE s.supersedes_revision_id = g.plan_revision_id
                           ) AS is_current,
                           s2.plan_revision_id AS superseded_by_revision_id,
                           l.primary_work_item_id
                    FROM plan_execution_graphs g
                    JOIN plan_revisions r ON r.plan_revision_id = g.plan_revision_id
                    LEFT JOIN plan_revisions s2 ON s2.supersedes_revision_id = g.plan_revision_id
                    LEFT JOIN goal_execution_lineage l ON l.goal_id = g.goal_id
                    WHERE g.plan_revision_id = $1
                    """,
                    _uuid(plan_revision_id),
                )
            )

    async def list_units(
        self, plan_revision_id: Any, *, limit: int = MAX_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """The graph's execution units in step order, each with its routing evidence and dispatch.

        ONE query. The AT-M2 routing decision, the assigned principal, the work item and the
        canonical dispatch are LEFT JOINed rather than fetched per unit: a per-unit follow-up is
        the N+1 this endpoint exists to spare its callers, and a UI rendering a fifty-step plan
        would otherwise issue two hundred queries to draw one screen.

        Ordering is ``step_key``, which is backed by ``uq_peu_revision_step (plan_revision_id,
        step_key)`` -- deterministic, and index-ordered rather than sorted.
        """
        async with self._session() as conn:
            total = await conn.fetchval(
                "SELECT count(*) FROM plan_execution_units WHERE plan_revision_id=$1",
                _uuid(plan_revision_id),
            )
            rows = await conn.fetch(
                _UNIT_SELECT
                + """
                WHERE u.plan_revision_id = $1
                ORDER BY u.step_key
                LIMIT $2 OFFSET $3
                """,
                _uuid(plan_revision_id),
                bounded(limit, MAX_PAGE),
                bounded_offset(offset),
            )
            return {
                "total": int(total or 0),
                "rows": [
                    _decode(
                        row, "required_capabilities", "expected_outputs", "candidates_considered"
                    )
                    for row in rows
                ],
            }

    async def get_unit(self, execution_unit_id: Any) -> dict[str, Any] | None:
        """One execution unit with the same joined shape a graph read produces."""
        async with self._session() as conn:
            return _decode(
                await conn.fetchrow(
                    _UNIT_SELECT + " WHERE u.execution_unit_id = $1",
                    _uuid(execution_unit_id),
                ),
                "required_capabilities",
                "expected_outputs",
                "candidates_considered",
            )

    async def list_edges(self, plan_revision_id: Any) -> list[dict[str, Any]]:
        """The dependency DAG in EXECUTION-UNIT terms, not in plan prose.

        Both endpoints are required to belong to the revision being read. That is the fail-closed
        half: ``project_work_item_dependencies`` is a project-wide edge table, and without the
        second predicate an edge whose other end is a different revision's unit -- or another
        Goal's work item entirely -- could be reported as this graph's topology.

        Returned in both directions' raw form; ``unlocks`` is inverted from this same set in
        memory rather than by a second query.
        """
        async with self._session() as conn:
            rows = await conn.fetch(
                """
                SELECT child.execution_unit_id  AS execution_unit_id,
                       child.step_key           AS step_key,
                       parent.execution_unit_id AS depends_on_execution_unit_id,
                       parent.step_key          AS depends_on_step_key,
                       parent.state             AS depends_on_state,
                       d.dependency_type
                FROM project_work_item_dependencies d
                JOIN plan_execution_units child  ON child.work_item_id = d.work_item_id
                JOIN plan_execution_units parent ON parent.work_item_id = d.depends_on_work_item_id
                WHERE child.plan_revision_id = $1
                  AND parent.plan_revision_id = $1
                ORDER BY child.step_key, parent.step_key
                """,
                _uuid(plan_revision_id),
            )
            return [dict(row) for row in rows]

    # --- audit evidence ---------------------------------------------------------------------------

    async def goal_audit_timeline(
        self, goal_id: Any, *, limit: int = DEFAULT_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """The Goal's correlated operational timeline, built from audit events that EXIST.

        THE SCOPE IS DERIVED FROM CANONICAL LINEAGE, NOT FROM THE CALLER. AT-M3 slices do not all
        stamp ``goal_id`` into ``artifact_refs`` -- the delegation events carry
        ``plan_revision_id`` and ``execution_unit_id`` instead -- so a goal_id-only filter would
        silently drop assignment and dispatch evidence. The probe set is therefore assembled from
        this Goal's OWN rows: its goal id, the revision ids of ``plan_revisions WHERE goal_id=$1``
        and the discussion ids of ``discussion_sessions WHERE goal_id=$1``. Another Project's audit
        row cannot match, because no identifier from another Project is ever in the probe set.

        Nothing is synthesised. If an audit event was never written, no entry appears -- current
        state is never back-projected into evidence it does not have.

        ORDERING is ``created_at ASC, id ASC``. ``id`` is the audit row's UUID primary key and is
        the stable secondary key for the tie: two events written in the same transaction share a
        timestamp, and without it a page boundary could show one row twice or skip it.
        """
        goal = _uuid(goal_id)
        async with self._session() as conn:
            revisions = await conn.fetch(
                "SELECT plan_revision_id FROM plan_revisions WHERE goal_id=$1", goal
            )
            discussions = await conn.fetch(
                "SELECT discussion_id, thread_id FROM discussion_sessions WHERE goal_id=$1", goal
            )
            probes = [json.dumps({"goal_id": str(goal)})]
            probes += [json.dumps({"plan_revision_id": str(r[0])}) for r in revisions]
            probes += [json.dumps({"discussion_id": str(d[0])}) for d in discussions]
            probes += [json.dumps({"thread_id": str(d[1])}) for d in discussions]

            total = await conn.fetchval(
                """
                SELECT count(*) FROM audit_logs a
                WHERE a.artifact_refs @> ANY ($1::jsonb[])
                """,
                probes,
            )
            rows = await conn.fetch(
                """
                SELECT a.id, a.created_at, a.agent, a.decision_type, a.summary, a.result,
                       a.artifact_refs, a.task_id
                FROM audit_logs a
                WHERE a.artifact_refs @> ANY ($1::jsonb[])
                ORDER BY a.created_at ASC, a.id ASC
                LIMIT $2 OFFSET $3
                """,
                probes,
                bounded(limit),
                bounded_offset(offset),
            )
            return {
                "total": int(total or 0),
                "probe_count": len(probes),
                "rows": [_decode(row, "artifact_refs") for row in rows],
            }

    async def goal_revision_ids(self, goal_id: Any) -> set[str]:
        """This Goal's revision ids, for validating cross-entity references in audit evidence."""
        async with self._session() as conn:
            rows = await conn.fetch(
                "SELECT plan_revision_id FROM plan_revisions WHERE goal_id=$1", _uuid(goal_id)
            )
            return {str(row[0]) for row in rows}

    async def goal_execution_unit_ids(self, goal_id: Any) -> set[str]:
        async with self._session() as conn:
            rows = await conn.fetch(
                "SELECT execution_unit_id FROM plan_execution_units WHERE goal_id=$1",
                _uuid(goal_id),
            )
            return {str(row[0]) for row in rows}


__all__ = [
    "DEFAULT_PAGE",
    "DEFAULT_DATABASE_URL",
    "MAX_PAGE",
    "AutonomyReadStore",
    "bounded",
    "bounded_offset",
]
