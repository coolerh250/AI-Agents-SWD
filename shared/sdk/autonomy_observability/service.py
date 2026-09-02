"""Step AT-M3.6A -- assembly of the autonomous-runtime read models.

Reads canonical rows through :class:`AutonomyReadStore`, normalises them into the stable contract
shapes in ``contracts.py``, and asks ``models.py`` for the derived answers. It performs no write of
any kind: no INSERT, no UPDATE, no audit event, no Redis publish, no scheduler call, no
materialization, no reasoning retry. Two identical reads leave the database byte-identical, which
is the property ``tests/test_at_m3_6a_read_only_proof.py`` measures rather than assumes.

WHY ASSEMBLY LIVES HERE AND NOT IN THE ROUTER
The router's job is HTTP: a path, a status code, a response model. Putting the joins there would
make the lineage rules reachable only through a running FastAPI app, and the rule that matters most
in this slice -- that a superseded revision's graph is never presented as the current one -- has to
be testable directly.

PARTIAL STATE IS A RESULT, NOT A FAULT
A Goal with no discussion, a discussion with no decision, an accepted plan with no graph, a graph
with no assignment, a dispatch with no publish, a cancelled lineage: each is a legitimate position
for an autonomous team to be in. Every one of them returns 200 with the truth in it. The only 404
this module produces is for an identifier that does not resolve at all.
"""

from __future__ import annotations

from typing import Any

from shared.sdk.autonomy_observability import models
from shared.sdk.autonomy_observability.store import (
    DEFAULT_PAGE,
    MAX_PAGE,
    AutonomyReadStore,
    bounded,
    bounded_offset,
)


def _sid(value: Any) -> str | None:
    return str(value) if value is not None else None


class GoalNotFound(LookupError):
    """The identifier does not resolve to a Goal. Distinct from "the Goal has nothing yet"."""


class EntityNotFound(LookupError):
    """A revision, unit or discussion identifier that resolves to no canonical row."""


class AutonomyObservabilityService:
    """The read surface's assembly layer. Every method is a query; none of them writes."""

    def __init__(self, store: AutonomyReadStore | None = None) -> None:
        self.store = store if store is not None else AutonomyReadStore()

    # --- normalisers ------------------------------------------------------------------------------

    @staticmethod
    def _goal_view(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "goal_id": str(row["goal_id"]),
            "project_id": str(row["project_id"]),
            "project_title": row["project_title"],
            "project_status": row["project_status"],
            "statement": row["statement"],
            "acceptance_criteria": list(row["acceptance_criteria"] or []),
            "constraints": list(row["constraints"] or []),
            "status": row["status"],
            "created_by": str(row["created_by"]),
            "created_at": row.get("created_at"),
        }

    @staticmethod
    def _lineage_view(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "primary_work_item_id": str(row["primary_work_item_id"]),
            "primary_work_item_title": row["primary_work_item_title"],
            "primary_work_item_key": row["primary_work_item_key"],
            "primary_work_item_status": row["primary_work_item_status"],
            "primary_work_item_lifecycle_state": row["primary_work_item_lifecycle_state"],
            "is_cancelled": bool(row["is_cancelled"]),
            "created_at": row.get("created_at"),
        }

    @staticmethod
    def _revision_view(row: dict[str, Any] | None, *, include_plan: bool) -> dict[str, Any] | None:
        """One PlanRevision. ``is_current`` is derived from lineage on every read, never stored."""
        if row is None:
            return None
        view = {
            "plan_revision_id": str(row["plan_revision_id"]),
            "goal_id": str(row["goal_id"]),
            "project_id": str(row["project_id"]),
            "revision_number": row["revision_number"],
            "status": row["status"],
            "reason": row["reason"],
            "created_by": _sid(row.get("created_by")),
            "supersedes_revision_id": _sid(row.get("supersedes_revision_id")),
            "superseded_by_revision_id": _sid(row.get("superseded_by_revision_id")),
            "trace_ref": row.get("trace_ref"),
            "created_at": row.get("created_at"),
            "is_current": (
                bool(row["is_current"])
                if row.get("is_current") is not None
                else row.get("superseded_by_revision_id") is None
            ),
            "is_accepted": row["status"] == "accepted",
            "plan_execution_graph_id": _sid(row.get("plan_execution_graph_id")),
            "is_materialized": row.get("plan_execution_graph_id") is not None,
            "materialized_at": row.get("materialized_at"),
            "step_count": row.get("step_count"),
        }
        if include_plan:
            # The accepted plan's own structured steps and dependency declarations, so a client
            # never has to parse plan prose to learn the shape of the work.
            view["plan"] = row.get("plan")
        return view

    @staticmethod
    def _discussion_view(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "discussion_id": str(row["discussion_id"]),
            "goal_id": str(row["goal_id"]),
            "project_id": str(row["project_id"]),
            "thread_id": str(row["thread_id"]),
            # The EXACT revision this discussion opened against. Immutable by trigger: a discussion
            # is permanently about the revision it deliberated, and is never rebound to a successor.
            "plan_revision_id": _sid(row.get("plan_revision_id")),
            "plan_revision_is_current": bool(row["plan_revision_is_current"]),
            "topic": row["topic"],
            "opened_by": str(row["opened_by"]),
            "required_capabilities": list(row["required_capabilities"] or []),
            "state": row["state"],
            "stop_reason": row.get("stop_reason"),
            "is_terminal": row["state"] != "open",
            "current_round": row["current_round"],
            "turns_taken": row["turns_taken"],
            "messages_posted": row["messages_posted"],
            "invocations_started": row["invocations_started"],
            "bounds": {
                "max_rounds": row["max_rounds"],
                "max_messages": row["max_messages"],
                "max_invocations": row["max_invocations"],
                "max_turns_per_participant": row["max_turns_per_participant"],
                "deadline_at": row.get("deadline_at"),
            },
            "deadline_expired": bool(row.get("deadline_expired")),
            "result_message_id": _sid(row.get("result_message_id")),
            "result_message_summary": row.get("result_message_summary"),
            "planning_decision_id": _sid(row.get("planning_decision_id")),
            "team_decision_id": _sid(row.get("team_decision_id")),
            "resulting_plan_revision_id": _sid(row.get("resulting_plan_revision_id")),
            "planning_outcome": row.get("planning_outcome"),
            "created_at": row.get("created_at"),
            "closed_at": row.get("closed_at"),
        }

    @staticmethod
    def _planning_decision_view(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "planning_decision_id": str(row["planning_decision_id"]),
            "goal_id": str(row["goal_id"]),
            "discussion_id": str(row["discussion_id"]),
            "outcome": row["outcome"],
            "result_message_id": str(row["result_message_id"]),
            "candidate_plan_message_id": str(row["candidate_plan_message_id"]),
            "candidate_message_summary": row.get("candidate_message_summary"),
            "candidate_message_type": row.get("candidate_message_type"),
            "predecessor_plan_revision_id": _sid(row.get("predecessor_plan_revision_id")),
            "resulting_plan_revision_id": _sid(row.get("resulting_plan_revision_id")),
            "resulting_revision_status": row.get("resulting_revision_status"),
            "resulting_revision_number": row.get("resulting_revision_number"),
            "resulting_revision_is_current": (
                None
                if row.get("resulting_revision_is_current") is None
                else bool(row["resulting_revision_is_current"])
            ),
            "team_decision": {
                "team_decision_id": str(row["team_decision_id"]),
                "thread_id": _sid(row.get("team_decision_thread_id")),
                "proposed_by": _sid(row.get("team_decision_proposed_by")),
                "options_considered": list(row.get("options_considered") or []),
                "selected_option": row.get("selected_option"),
                "rationale_summary": row.get("rationale_summary"),
                # Unresolved objections are reported, never suppressed.
                "dissent_summary": row.get("dissent_summary"),
                "created_at": row.get("team_decision_at"),
            },
            "created_at": row.get("created_at"),
        }

    @staticmethod
    def _unit_view(
        row: dict[str, Any],
        *,
        depends_on: list[dict[str, Any]],
        unlocks: list[dict[str, Any]],
        plan_is_current: bool,
    ) -> dict[str, Any]:
        """One execution unit, with everything a UI needs and nothing a UI must not have.

        The dispatch block never says "executing". It reports the canonical row, the isolated
        target stream, ``published_at``, and a ``dispatch_state`` that can only be
        ``NOT_DISPATCHED``, ``CANONICAL_DISPATCH_RECORDED_UNPUBLISHED`` or
        ``DISPATCHED_TO_CONTROL_STREAM``. ``execution_mode`` is stated on every terminal unit,
        because a completion recorded by AT-M3.5's internal seam is a control-plane simulation and
        is not evidence that an agent did anything.
        """
        dispatch_row = (
            {
                "correlation_id": str(row["correlation_id"]),
                "target_stream": row["target_stream"],
                "published_at": row.get("published_at"),
                "created_at": row.get("dispatch_created_at"),
                "plan_revision_id": _sid(row.get("dispatch_plan_revision_id")),
                "step_key": row.get("dispatch_step_key"),
                "assigned_principal_id": _sid(row.get("dispatch_principal_id")),
                "work_item_id": _sid(row.get("dispatch_work_item_id")),
            }
            if row.get("correlation_id")
            else None
        )
        state_view = {
            "execution_unit_id": str(row["execution_unit_id"]),
            "plan_execution_graph_id": str(row["plan_execution_graph_id"]),
            "plan_revision_id": str(row["plan_revision_id"]),
            "goal_id": str(row["goal_id"]),
            "project_id": str(row["project_id"]),
            "step_key": row["step_key"],
            "state": row["state"],
            "required_capabilities": list(row["required_capabilities"] or []),
            "expected_outputs": list(row["expected_outputs"] or []),
            "intended_owner_role": row.get("intended_owner_role"),
            "unavailable_reason": row.get("unavailable_reason"),
            "disposition": row.get("disposition"),
            "result_ref": row.get("result_ref"),
            "completed_at": row.get("completed_at"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            # The lineage carrier's identity stays at the top level with the other identifiers;
            # the nested block is its denormalised detail, not a second place to find its id.
            "work_item_id": str(row["work_item_id"]),
            "work_item": {
                "work_item_key": row.get("work_item_key"),
                "title": row.get("work_item_title"),
                "status": row.get("work_item_status"),
                "lifecycle_state": row.get("work_item_lifecycle_state"),
            },
            "assignment": {
                "assigned_principal_id": _sid(row.get("assigned_principal_id")),
                "assigned_principal_name": row.get("assigned_principal_name"),
                "assigned_principal_type": row.get("assigned_principal_type"),
                "assigned_role": row.get("assigned_role"),
                "assigned_agent_key": row.get("assigned_agent_key"),
                "assigned_at": row.get("assigned_at"),
            },
            # Deterministic routing evidence -- an eligible set, rejection reasons and the reason
            # the winner won. This is explainability of a rule, not model reasoning: no prompt, no
            # completion and no chain of thought exists in `agent_routing_decisions` to expose.
            "routing": {
                "routing_decision_id": _sid(row.get("routing_decision_id")),
                "requested_capability": row.get("routing_requested_capability"),
                "outcome": row.get("routing_outcome"),
                "reason": row.get("routing_reason"),
                "selected_role": row.get("routing_selected_role"),
                "selected_stream": row.get("routing_selected_stream"),
                "candidates_considered": list(row.get("candidates_considered") or []),
                "decided_at": row.get("routing_decided_at"),
                "preferred_role": row.get("intended_owner_role"),
                "preferred_role_is_a_filter": False,
            },
            "dispatch": dispatch_row,
            "dispatch_state": models.unit_dispatch_state({"dispatch": dispatch_row}),
            "dispatch_truth": models.DISPATCH_TRUTH_NOTE,
            "execution_mode": models.EXECUTION_MODE_INTERNAL,
            "depends_on": depends_on,
            "unlocks": unlocks,
            "plan_revision_is_current": plan_is_current,
            # Whether a scheduling pass has ever tried to give this unit an owner. Derived, and
            # surfaced at the top level so "materialized but never scheduled" is one field rather
            # than an inference a client has to make from a nested routing block.
            "has_routing_decision": row.get("routing_decision_id") is not None,
        }
        # The HumanApproval boundary is REPORTED, never touched. AT-M3.5 refers a production-effect
        # capability to it and creates no approval record, so the honest answer is "referred, and
        # no canonical approval row exists" rather than an invented approval state.
        state_view["human_approval"] = {
            "referred": row.get("unavailable_reason") == models.BLOCKER_REQUIRES_HUMAN_APPROVAL,
            "canonical_reason": row.get("unavailable_reason"),
            "approval_record": None,
            "note": (
                "AT-M3.5 refers a production-effect capability to the human approval boundary and "
                "creates no approval record; AT-M3.6A reads this boundary and never mutates it"
            ),
        }
        state_view["blockers"] = models.unit_blockers(
            {**row, "dispatch": dispatch_row, "depends_on": depends_on},
            plan_is_current=plan_is_current,
        )
        return state_view

    # --- topology ---------------------------------------------------------------------------------

    @staticmethod
    def _topology(edges: list[dict[str, Any]]) -> tuple[dict[str, list], dict[str, list]]:
        """``depends_on`` and its inverse ``unlocks``, keyed by execution_unit_id.

        Both directions come from ONE edge query. Topology is expressed with stable execution-unit
        and step identifiers so a frontend can lay out the DAG without parsing PlanContent text.
        """
        depends: dict[str, list] = {}
        unlocks: dict[str, list] = {}
        for edge in edges:
            child = str(edge["execution_unit_id"])
            parent = str(edge["depends_on_execution_unit_id"])
            depends.setdefault(child, []).append(
                {
                    "execution_unit_id": parent,
                    "step_key": edge["depends_on_step_key"],
                    "state": edge["depends_on_state"],
                    "dependency_type": edge["dependency_type"],
                    "depends_on_step_key": edge["depends_on_step_key"],
                }
            )
            unlocks.setdefault(parent, []).append(
                {
                    "execution_unit_id": child,
                    "step_key": edge["step_key"],
                    "dependency_type": edge["dependency_type"],
                }
            )
        return depends, unlocks

    async def _units_with_topology(
        self, plan_revision_id: str, *, plan_is_current: bool, limit: int, offset: int
    ) -> dict[str, Any]:
        page = await self.store.list_units(plan_revision_id, limit=limit, offset=offset)
        edges = await self.store.list_edges(plan_revision_id)
        depends, unlocks = self._topology(edges)
        units = [
            self._unit_view(
                row,
                depends_on=depends.get(str(row["execution_unit_id"]), []),
                unlocks=unlocks.get(str(row["execution_unit_id"]), []),
                plan_is_current=plan_is_current,
            )
            for row in page["rows"]
        ]
        return {"units": units, "total": page["total"], "edges": edges}

    # --- goal autonomy overview -------------------------------------------------------------------

    async def goal_overview(self, goal_id: str, *, turn_limit: int = 50) -> dict[str, Any]:
        """What this autonomous team is doing right now, and why.

        Entity-first: every block carries real identifiers a caller can follow to the deeper read,
        and the summary counts come after them rather than instead of them. That ordering is
        deliberate -- the historical failure this slice exists to correct is a product that showed
        aggregates while WorkItem identity, execution evidence and audit lineage stayed invisible.
        """
        async with self.store.session():
            return await self._goal_overview(goal_id, turn_limit=turn_limit)

    async def _goal_overview(self, goal_id: str, *, turn_limit: int) -> dict[str, Any]:
        """The overview's queries, running inside the connection its caller opened."""
        goal_row = await self.store.get_goal(goal_id)
        if goal_row is None:
            raise GoalNotFound(f"unknown goal {goal_id}")

        lineage_row = await self.store.get_execution_lineage(goal_id)
        members = await self.store.team_members(goal_row["project_id"])
        discussions = await self.store.list_discussions(goal_id, limit=DEFAULT_PAGE)
        decisions = await self.store.list_planning_decisions(goal_id)
        current_revision_row = await self.store.get_current_revision(goal_id)
        graphs = await self.store.list_graphs(goal_id)

        latest_discussion = self._discussion_view(
            discussions["rows"][0] if discussions["rows"] else None
        )
        participants: list[dict[str, Any]] = []
        turns: dict[str, Any] = {"total": 0, "rows": []}
        open_reasoning = 0
        if latest_discussion:
            participants = [
                {
                    "seat_index": p["seat_index"],
                    "principal_id": str(p["principal_id"]),
                    "display_name": p.get("display_name"),
                    "agent_key": p["agent_key"],
                    "functional_role": p["functional_role"],
                    "matched_capabilities": list(p["matched_capabilities"] or []),
                    "selection_reason": p["selection_reason"],
                    "turns_taken": p["turns_taken"],
                }
                for p in await self.store.discussion_participants(
                    latest_discussion["discussion_id"]
                )
            ]
            turns = await self.store.discussion_turns(
                latest_discussion["discussion_id"], limit=bounded(turn_limit)
            )
            open_reasoning = await self.store.open_reasoning_count(latest_discussion["thread_id"])

        current_revision = self._revision_view(current_revision_row, include_plan=True)
        current_graph = next(
            (
                g
                for g in graphs
                if current_revision
                and str(g["plan_revision_id"]) == current_revision["plan_revision_id"]
            ),
            None,
        )
        current_units: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        if current_graph is not None:
            assembled = await self._units_with_topology(
                str(current_graph["plan_revision_id"]),
                plan_is_current=True,
                limit=MAX_PAGE,
                offset=0,
            )
            current_units = assembled["units"]
            edges = assembled["edges"]

        snapshot = {
            "goal": goal_row,
            "lineage": lineage_row,
            "team_active_member_count": sum(
                1 for m in members if m["membership_state"] == "active"
            ),
            "discussion": (
                {**latest_discussion, "open_reasoning_count": open_reasoning}
                if latest_discussion
                else None
            ),
            "planning_decision": decisions[0] if decisions else None,
            "current_revision": current_revision,
            "current_graph": current_graph,
            "current_units": current_units,
        }

        historical = [
            {
                "plan_revision_id": str(g["plan_revision_id"]),
                "revision_number": g["revision_number"],
                "plan_execution_graph_id": str(g["plan_execution_graph_id"]),
                "step_count": g["step_count"],
                "materialized_at": g["created_at"],
                "is_current": bool(g["is_current"]),
                "state_counts": g["counts"].get("states", {}),
                "canonical_dispatch_rows": g["counts"].get("dispatch_rows", 0),
                "published_dispatch_rows": g["counts"].get("published_rows", 0),
                "execution_mode": models.EXECUTION_MODE_INTERNAL,
            }
            for g in graphs
            if not g["is_current"]
        ]

        return {
            "goal": self._goal_view(goal_row),
            "execution_lineage": self._lineage_view(lineage_row),
            "team": {
                "project_id": str(goal_row["project_id"]),
                "active_member_count": snapshot["team_active_member_count"],
                "members": [
                    {
                        "principal_id": str(m["agent_principal_id"]),
                        "display_name": m["display_name"],
                        "agent_key": m.get("agent_key"),
                        "functional_role": m["functional_role"],
                        "membership_state": m["membership_state"],
                        "profile_status": m.get("profile_status"),
                        "capabilities": list(m.get("capabilities") or []),
                        "joined_at": m.get("joined_at"),
                        "left_at": m.get("left_at"),
                    }
                    for m in members
                ],
            },
            "current_discussion": (
                None
                if latest_discussion is None
                else {
                    **latest_discussion,
                    "open_reasoning_invocations": open_reasoning,
                    "participants": participants,
                    "turn_count": turns["total"],
                    "turns_truncated": len(turns["rows"]) < turns["total"],
                    "turns": [
                        {
                            "round_index": t["round_index"],
                            "seat_index": t["seat_index"],
                            "speaker_principal_id": str(t["speaker_principal_id"]),
                            "speaker_display_name": t.get("speaker_display_name"),
                            "intent": t["intent"],
                            "reasoning_verb": t["reasoning_verb"],
                            "reasoning_invocation_id": _sid(t.get("reasoning_invocation_id")),
                            "status": t["status"],
                            "concern_count": t["concern_count"],
                            "message_id": _sid(t.get("message_id")),
                            "message_type": t.get("message_type"),
                            "message_summary": t.get("message_summary"),
                            "created_at": t.get("created_at"),
                        }
                        for t in turns["rows"]
                    ],
                }
            ),
            "discussion_count": discussions["total"],
            "current_planning_decision": self._planning_decision_view(
                decisions[0] if decisions else None
            ),
            "planning_decision_count": len(decisions),
            "current_plan_revision": current_revision,
            "plan_revision_count": await self.store.count_revisions(goal_id),
            "current_execution_graph": (
                None
                if current_graph is None
                else {
                    "plan_execution_graph_id": str(current_graph["plan_execution_graph_id"]),
                    "plan_revision_id": str(current_graph["plan_revision_id"]),
                    "revision_number": current_graph["revision_number"],
                    "step_count": current_graph["step_count"],
                    "materialized_by": str(current_graph["materialized_by"]),
                    "materialized_at": current_graph["created_at"],
                    "is_current": True,
                    "edge_count": len(edges),
                }
            ),
            "current_units": current_units,
            # Progress over the CURRENT graph only. A superseded revision's finished work is real
            # and stays visible under historical_execution_graphs; counting it here would make a
            # replanned Goal look further along than its current plan is.
            "progress": models.graph_progress(current_units),
            "autonomy_phase": models.autonomy_phase(snapshot),
            "blockers": models.goal_blockers(snapshot),
            "next_work": models.next_ready_work(current_units),
            "historical_execution_graphs": historical,
            "read_model": {
                "source_of_truth": "postgresql",
                "redis_consulted": False,
                "derived_fields": [
                    "autonomy_phase",
                    "blockers",
                    "progress",
                    "next_work",
                    "is_current",
                    "dispatch_state",
                ],
                "execution_mode": models.EXECUTION_MODE_INTERNAL,
                "note": (
                    "AT-M3.6A is read-only and stores nothing; every derived field above is "
                    "recomputed from canonical rows on each read"
                ),
            },
        }

    # --- plan revision history --------------------------------------------------------------------

    async def plan_revision_history(
        self, goal_id: str, *, limit: int = DEFAULT_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """Every revision this Goal has had, oldest first, with what each one dispatched.

        Revision N is not hidden because N+1 is current. Each entry says whether it was
        materialized, how its units ended, and how many canonical dispatches it authorized -- so
        "did the work the superseded plan dispatched ever finish" is answerable without guessing.
        """
        async with self.store.session():
            goal_row = await self.store.get_goal(goal_id)
            if goal_row is None:
                raise GoalNotFound(f"unknown goal {goal_id}")
            page = await self.store.list_revisions(goal_id, limit=limit, offset=offset)
            graphs = {str(g["plan_revision_id"]): g for g in await self.store.list_graphs(goal_id)}
        revisions = []
        for row in page["rows"]:
            view = self._revision_view(row, include_plan=False)
            assert view is not None
            graph = graphs.get(view["plan_revision_id"])
            view["execution"] = (
                None
                if graph is None
                else {
                    "plan_execution_graph_id": str(graph["plan_execution_graph_id"]),
                    "state_counts": graph["counts"].get("states", {}),
                    "unavailable": graph["counts"].get("unavailable", 0),
                    "canonical_dispatch_rows": graph["counts"].get("dispatch_rows", 0),
                    "published_dispatch_rows": graph["counts"].get("published_rows", 0),
                    "execution_mode": models.EXECUTION_MODE_INTERNAL,
                    "dispatch_truth": models.DISPATCH_TRUTH_NOTE,
                }
            )
            revisions.append(view)
        limit_used = bounded(limit)
        offset_used = bounded_offset(offset)
        return {
            "goal_id": str(goal_row["goal_id"]),
            "project_id": str(goal_row["project_id"]),
            "total": page["total"],
            "limit": limit_used,
            "offset": offset_used,
            "has_more": offset_used + len(revisions) < page["total"],
            "ordering": "revision_number ASC",
            "revisions": revisions,
        }

    # --- execution graph --------------------------------------------------------------------------

    async def execution_graph(
        self, plan_revision_id: str, *, limit: int = MAX_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """One PlanRevision's execution graph, entity-level and dependency-aware.

        A superseded revision's graph is returned in full and marked ``is_current: false``. It is
        never rebound to the current revision and its units are never re-labelled: work dispatched
        under revision N stays evidence about revision N, which is the whole point of the AT-M3.5
        stale-plan semantic.
        """
        async with self.store.session():
            graph = await self.store.get_graph(plan_revision_id)
            if graph is None:
                raise EntityNotFound(
                    f"plan revision {plan_revision_id} has no materialized execution graph"
                )
            plan_is_current = bool(graph["is_current"])
            assembled = await self._units_with_topology(
                str(graph["plan_revision_id"]),
                plan_is_current=plan_is_current,
                limit=limit,
                offset=offset,
            )
        limit_used = bounded(limit, MAX_PAGE)
        offset_used = bounded_offset(offset)
        return {
            "plan_execution_graph_id": str(graph["plan_execution_graph_id"]),
            "plan_revision_id": str(graph["plan_revision_id"]),
            "goal_id": str(graph["goal_id"]),
            "project_id": str(graph["project_id"]),
            "primary_work_item_id": _sid(graph.get("primary_work_item_id")),
            "revision_number": graph["revision_number"],
            "revision_status": graph["revision_status"],
            "revision_reason": graph["reason"],
            "supersedes_revision_id": _sid(graph.get("supersedes_revision_id")),
            "superseded_by_revision_id": _sid(graph.get("superseded_by_revision_id")),
            "is_current": plan_is_current,
            "lineage_status": "CURRENT" if plan_is_current else "HISTORICAL_SUPERSEDED",
            "step_count": graph["step_count"],
            "materialized_by": str(graph["materialized_by"]),
            "materialized_at": graph["created_at"],
            "total_units": assembled["total"],
            "limit": limit_used,
            "offset": offset_used,
            "has_more": offset_used + len(assembled["units"]) < assembled["total"],
            "ordering": "step_key ASC",
            "units": assembled["units"],
            "progress": models.graph_progress(assembled["units"]),
            "next_work": models.next_ready_work(assembled["units"]),
            "execution_mode": models.EXECUTION_MODE_INTERNAL,
            "dispatch_truth": models.DISPATCH_TRUTH_NOTE,
        }

    async def execution_unit(self, execution_unit_id: str) -> dict[str, Any]:
        """One execution unit with its full lineage, routing explanation and dispatch truth."""
        async with self.store.session():
            row = await self.store.get_unit(execution_unit_id)
            if row is None:
                raise EntityNotFound(f"unknown execution unit {execution_unit_id}")
            revision = await self.store.get_revision(row["plan_revision_id"])
            plan_is_current = bool(revision and revision["is_current"])
            edges = await self.store.list_edges(row["plan_revision_id"])
        depends, unlocks = self._topology(edges)
        unit_id = str(row["execution_unit_id"])
        view = self._unit_view(
            row,
            depends_on=depends.get(unit_id, []),
            unlocks=unlocks.get(unit_id, []),
            plan_is_current=plan_is_current,
        )
        view["lineage"] = {
            "goal_id": str(row["goal_id"]),
            "project_id": str(row["project_id"]),
            "plan_revision_id": str(row["plan_revision_id"]),
            "revision_number": revision["revision_number"] if revision else None,
            "revision_status": revision["status"] if revision else None,
            "plan_execution_graph_id": str(row["plan_execution_graph_id"]),
            "work_item_id": str(row["work_item_id"]),
            "lineage_status": "CURRENT" if plan_is_current else "HISTORICAL_SUPERSEDED",
        }
        return view

    # --- timeline ---------------------------------------------------------------------------------

    async def goal_timeline(
        self, goal_id: str, *, limit: int = DEFAULT_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """The Goal's audit evidence, correlated and bounded.

        EVIDENCE, NOT AUTHORITY. These rows say what was recorded at the time; the canonical tables
        say what is true now, and where they disagree the canonical tables win. Nothing here is
        synthesised from current state -- an event that was never written produces no entry, so a
        gap in the timeline is a real gap rather than a reconstruction.

        Cross-entity references are resolved against this Goal's OWN identifier sets and are
        reported only when they validate. An audit row naming a revision that belongs to another
        Goal contributes no ``plan_revision_id`` to its entry rather than being reported under this
        Goal's lineage.
        """
        async with self.store.session():
            goal_row = await self.store.get_goal(goal_id)
            if goal_row is None:
                raise GoalNotFound(f"unknown goal {goal_id}")
            page = await self.store.goal_audit_timeline(goal_id, limit=limit, offset=offset)
            revision_ids = await self.store.goal_revision_ids(goal_id)
            unit_ids = await self.store.goal_execution_unit_ids(goal_id)

        entries = []
        for row in page["rows"]:
            refs = row["artifact_refs"] or {}
            revision_ref = refs.get("plan_revision_id")
            unit_ref = refs.get("execution_unit_id")
            entries.append(
                {
                    "audit_id": str(row["id"]),
                    "occurred_at": row["created_at"],
                    "decision_type": row["decision_type"],
                    "agent": row["agent"],
                    "summary": row["summary"],
                    "result": row["result"],
                    "goal_id": str(goal_row["goal_id"]),
                    "plan_revision_id": (revision_ref if revision_ref in revision_ids else None),
                    "discussion_id": refs.get("discussion_id"),
                    "execution_unit_id": (unit_ref if unit_ref in unit_ids else None),
                    "step_key": refs.get("step_key"),
                    "correlation_id": refs.get("correlation_id"),
                    "reference_scope_verified": (
                        (revision_ref is None or revision_ref in revision_ids)
                        and (unit_ref is None or unit_ref in unit_ids)
                    ),
                }
            )
        limit_used = bounded(limit)
        offset_used = bounded_offset(offset)
        return {
            "goal_id": str(goal_row["goal_id"]),
            "project_id": str(goal_row["project_id"]),
            "total": page["total"],
            "limit": limit_used,
            "offset": offset_used,
            "has_more": offset_used + len(entries) < page["total"],
            "ordering": "created_at ASC, audit_id ASC",
            "authority": (
                "audit evidence, not canonical state; the runtime tables remain authoritative and "
                "no entry here is synthesised from current state"
            ),
            "entries": entries,
        }

    # --- reasoning --------------------------------------------------------------------------------

    async def discussion_reasoning(
        self, discussion_id: str, *, limit: int = DEFAULT_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """Safe operational metadata for the reasoning behind one discussion.

        Verb, provider name and mode, status, attempt, timing, sanitized failure reason and
        artifact TYPE. Never the artifact body, never a prompt, never a completion, never a
        scratchpad, and never a token trace: those either do not exist in the schema at all or are
        the business artifact's own surface (TeamMessage, candidate message, PlanRevision).
        """
        async with self.store.session():
            discussion = await self.store.get_discussion(discussion_id)
            if discussion is None:
                raise EntityNotFound(f"unknown discussion {discussion_id}")
            page = await self.store.list_reasoning_invocations(
                discussion["thread_id"], discussion["discussion_id"], limit=limit, offset=offset
            )
        limit_used = bounded(limit)
        offset_used = bounded_offset(offset)
        return {
            "discussion_id": str(discussion["discussion_id"]),
            "goal_id": str(discussion["goal_id"]),
            "project_id": str(discussion["project_id"]),
            "thread_id": str(discussion["thread_id"]),
            "plan_revision_id": _sid(discussion.get("plan_revision_id")),
            "total": page["total"],
            "limit": limit_used,
            "offset": offset_used,
            "has_more": offset_used + len(page["rows"]) < page["total"],
            "ordering": "created_at ASC, invocation_id ASC",
            "disclosure": (
                "operational metadata only: no prompt, no completion, no hidden reasoning, no "
                "scratchpad and no artifact body is exposed by this endpoint"
            ),
            "invocations": [
                {
                    "invocation_id": str(r["invocation_id"]),
                    "reasoning_verb": r["reasoning_verb"],
                    "provider_name": r["requested_provider_name"],
                    "provider_mode": r["provider_mode"],
                    "model_name": r.get("model_name"),
                    "status": r["status"],
                    "attempt": r.get("attempt"),
                    "round_number": r.get("round_number"),
                    "failure_category": r.get("failure_category"),
                    # The sanitized reason AT-M3.1 stores, passed through rather than re-derived.
                    "failure_reason": r.get("failure_reason"),
                    # The artifact's TYPE name from a closed CHECK. The object itself is the
                    # business artifact and is read through its own surface, not through here.
                    "artifact_type": r.get("artifact_type"),
                    "artifact_body_exposed": False,
                    "outcome_ref": r.get("outcome_ref"),
                    "input_tokens": r.get("input_tokens"),
                    "output_tokens": r.get("output_tokens"),
                    "estimated_cost_usd": (
                        float(r["estimated_cost_usd"])
                        if r.get("estimated_cost_usd") is not None
                        else None
                    ),
                    "latency_ms": r.get("latency_ms"),
                    "correlation_id": _sid(r.get("correlation_id")),
                    "requested_by_principal_id": _sid(r.get("requested_by_principal_id")),
                    "started_at": r.get("started_at"),
                    "completed_at": r.get("completed_at"),
                    # Replay context, where the turn ledger records one: which slot this attempt
                    # belonged to and which TeamMessage carried its result.
                    "turn": (
                        None
                        if r.get("round_index") is None
                        else {
                            "round_index": r["round_index"],
                            "seat_index": r["seat_index"],
                            "intent": r.get("intent"),
                            "status": r.get("turn_status"),
                            "message_id": _sid(r.get("message_id")),
                        }
                    ),
                }
                for r in page["rows"]
            ],
        }


__all__ = ["AutonomyObservabilityService", "EntityNotFound", "GoalNotFound"]
