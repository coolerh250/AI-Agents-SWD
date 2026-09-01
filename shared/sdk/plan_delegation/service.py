"""Step AT-M3.5 -- plan-driven delegation runtime.

Three commands, and deliberately only three:

``materialize_accepted_plan``   an accepted, current PlanRevision becomes a durable execution graph
``schedule_ready_work``          ready steps acquire owners and become dispatched commands
``record_step_result``           a dispatched step reports back, and unlocks what it was blocking

There is no ``set_ready``, no ``assign_principal``, no ``mark_dispatched`` and no
``rebind_revision``. Every one of those would let a caller reach past the invariants the store
enforces -- readiness is derived from dependencies, ownership is decided by the AT-M2 router from
the live team, and a dispatch is bound to the revision that authorized it. A command that could
override any of them would make the guarantee a convention.

WHAT THIS LAYER DOES NOT DO, and cannot: it runs no code, no shell, no test, no Git operation, no
GitHub call, no deployment and no external request. ``dispatch`` here means "agent X, this plan
step is now yours" -- a structured work assignment on an internal stream. Performing the work is
AT-M4, and nothing in this module could be given that capability without new imports, a new
migration and a new decision.

TRANSPORT IS AT-LEAST-ONCE; CANONICAL STATE IS EXACTLY-ONCE. The dispatch row commits first and is
published afterwards, because a Redis ``XADD`` cannot join a PostgreSQL transaction. A crash
between the two leaves a canonical dispatch with ``published_at`` NULL, and the next schedule pass
re-publishes THAT SAME dispatch -- same row, same correlation id -- rather than minting a second
one. A consumer may therefore see one command twice and must dedupe on ``correlation_id``; it can
never see two different commands for one step.

Audit and events degrade gracefully, matching ``TeamService`` and ``PlanningService``: a missing
audit sink must not stop work being delegated, and must not silently turn a recorded dispatch into
an unrecorded one -- the durable row is written first, and the announcement follows.
"""

from __future__ import annotations

import contextlib
from typing import Any

from shared.sdk.agent_planning.models import PlanStep
from shared.sdk.agent_team.store import TeamStore
from shared.sdk.plan_delegation import events as delegation_events
from shared.sdk.plan_delegation.models import (
    UNIT_ASSIGNED,
    UNIT_DISPATCHED,
    UNIT_READY,
    build_dispatch_envelope,
    resolve_step_assignment,
)
from shared.sdk.plan_delegation.store import PlanDelegationStore


class PlanDelegationService:
    def __init__(
        self,
        store: Any | None = None,
        team_store: Any | None = None,
        event_bus: Any | None = None,
        audit_client: Any | None = None,
    ) -> None:
        self.store = store if store is not None else PlanDelegationStore()
        self.team_store = team_store if team_store is not None else TeamStore()
        self.event_bus = event_bus
        self.audit_client = audit_client

    # --- side channels ---------------------------------------------------------------------------

    async def _publish(self, stream: str, payload: dict[str, Any]) -> bool:
        if self.event_bus is None:
            return False
        try:
            await self.event_bus.publish_event(stream, payload)
            return True
        except Exception:
            # The canonical dispatch is already durable and unpublished; the next schedule pass
            # re-publishes it. Swallowing here is what keeps a broker outage from rolling back
            # work that PostgreSQL has already committed.
            return False

    async def _observe(self, event: str, payload: dict[str, Any]) -> None:
        """Best-effort observation event. Nothing consumes it to decide anything."""
        if self.event_bus is None:
            return
        with contextlib.suppress(Exception):
            await self.event_bus.publish_event(
                delegation_events.STREAM_PLAN_DELEGATION, {"event": event, **payload}
            )

    async def _audit(
        self, decision_type: str, summary: str, result: str, refs: dict[str, Any]
    ) -> str | None:
        """Best-effort. Identifiers, state, reason and capabilities only -- never plan content."""
        if self.audit_client is None:
            return None
        try:
            event = self.audit_client.build_audit_event(
                agent="plan-delegation-runtime",
                decision_type=decision_type,
                summary=summary,
                result=result,
                artifact_refs=refs,
            )
            return await self.audit_client.write_audit_event(event)
        except Exception:
            return None

    # --- materialize ------------------------------------------------------------------------------

    async def materialize_accepted_plan(
        self, *, goal_id: str, plan_revision_id: str, materialized_by: str
    ) -> dict[str, Any]:
        """Build the durable execution graph for one accepted, current PlanRevision.

        Idempotent by construction: the graph's uniqueness on ``plan_revision_id`` is what makes a
        repeated call -- or eight simultaneous ones -- return the same canonical graph instead of a
        second one. The plan is read from the revision row; this command takes no plan and no step
        list from its caller.
        """
        result = await self.store.materialize(
            goal_id=goal_id,
            plan_revision_id=plan_revision_id,
            materialized_by=materialized_by,
        )
        graph = result["graph"]
        if result["created"]:
            await self._audit(
                delegation_events.AUDIT_GRAPH_MATERIALIZED,
                f"plan revision {plan_revision_id} materialized "
                f"{graph['step_count']} execution unit(s)",
                "materialized",
                {
                    "goal_id": str(goal_id),
                    "project_id": str(graph["project_id"]),
                    "plan_revision_id": str(plan_revision_id),
                    "plan_execution_graph_id": str(graph["plan_execution_graph_id"]),
                    "primary_work_item_id": str(result["primary_work_item_id"]),
                    "step_count": graph["step_count"],
                },
            )
            await self._observe(
                delegation_events.EVENT_GRAPH_MATERIALIZED,
                {
                    "goal_id": str(goal_id),
                    "project_id": str(graph["project_id"]),
                    "plan_revision_id": str(plan_revision_id),
                    "step_count": graph["step_count"],
                },
            )
        return result

    # --- schedule ----------------------------------------------------------------------------------

    async def schedule_ready_work(
        self, *, plan_revision_id: str, trace_id: str = ""
    ) -> dict[str, Any]:
        """Assign, dispatch and publish every step of this graph that is due, once each.

        A single pass over the units the graph still owes something to, in step-key order so two
        schedulers walk them identically. Each unit passes through at most three boundaries --
        assignment, canonical dispatch, transport publish -- and each is independently idempotent,
        so a restart mid-pass resumes rather than repeats.

        A stale or cancelled lineage aborts the WHOLE pass rather than skipping a unit: both are
        facts about the graph, not about one step, and continuing would dispatch the rest of a plan
        that is no longer authoritative.
        """
        units = await self.store.list_schedulable_units(plan_revision_id)
        if not units:
            return {"plan_revision_id": str(plan_revision_id), "results": []}

        plan = await self.store.get_revision_plan(plan_revision_id)
        if plan is None:  # pragma: no cover - a graph cannot outlive its revision (FK cascade)
            raise LookupError(f"plan revision {plan_revision_id} no longer exists")
        steps = {step.step_key: step for step in plan.steps}

        # The team as it is right now. Read once per pass so every unit in one pass is routed
        # against the same roster, which is what makes the pass reproducible.
        candidates = await self.team_store.routing_candidates(str(units[0]["project_id"]))

        results = []
        for unit in units:
            results.append(
                await self._advance_unit(
                    unit=unit,
                    step=steps[unit["step_key"]],
                    candidates=candidates,
                    trace_id=trace_id,
                )
            )
        return {"plan_revision_id": str(plan_revision_id), "results": results}

    async def _advance_unit(
        self,
        *,
        unit: dict[str, Any],
        step: PlanStep,
        candidates: list[Any],
        trace_id: str,
    ) -> dict[str, Any]:
        unit_id = str(unit["execution_unit_id"])

        if unit["state"] == UNIT_READY:
            decision = resolve_step_assignment(
                required_capabilities=tuple(unit["required_capabilities"]),
                candidates=candidates,
                project_id=str(unit["project_id"]),
                intended_owner_role=unit["intended_owner_role"],
                work_item_id=str(unit["work_item_id"]),
            )
            audit_ref = await self._audit(
                delegation_events.AUDIT_UNIT_ASSIGNED,
                f"routing step {unit['step_key']!r} of plan revision "
                f"{unit['plan_revision_id']}: {decision.outcome}",
                decision.outcome,
                {
                    "project_id": str(unit["project_id"]),
                    "plan_revision_id": str(unit["plan_revision_id"]),
                    "step_key": unit["step_key"],
                    "execution_unit_id": unit_id,
                    "required_capabilities": list(unit["required_capabilities"]),
                    "selected_role": decision.selected_role,
                    "reason": decision.reason,
                },
            )
            applied = await self.store.apply_assignment(
                execution_unit_id=unit_id, decision=decision, audit_ref=audit_ref
            )
            unit = applied["unit"]
            if applied["outcome"] == "unassignable":
                await self._observe(
                    delegation_events.EVENT_UNIT_UNASSIGNABLE,
                    {
                        "project_id": str(unit["project_id"]),
                        "plan_revision_id": str(unit["plan_revision_id"]),
                        "step_key": unit["step_key"],
                        "execution_unit_id": unit_id,
                        "reason": unit["unavailable_reason"],
                    },
                )
                return {
                    "execution_unit_id": unit_id,
                    "step_key": unit["step_key"],
                    "outcome": "unassignable",
                    "reason": unit["unavailable_reason"],
                    "routing_reason": decision.reason,
                    "published": False,
                }
            if applied["outcome"] == "assigned":
                await self._observe(
                    delegation_events.EVENT_UNIT_ASSIGNED,
                    {
                        "project_id": str(unit["project_id"]),
                        "plan_revision_id": str(unit["plan_revision_id"]),
                        "step_key": unit["step_key"],
                        "execution_unit_id": unit_id,
                        "assigned_role": unit["assigned_role"],
                    },
                )

        if unit["state"] == UNIT_ASSIGNED:
            dispatched = await self.store.create_dispatch(execution_unit_id=unit_id)
            unit = dispatched["unit"]
            dispatch = dispatched["dispatch"]
            outcome = dispatched["outcome"]
        elif unit["state"] == UNIT_DISPATCHED:
            dispatch = await self.store.get_dispatch(unit_id)
            outcome = "replay"
        else:
            # Another worker moved it past dispatch entirely, or it is no longer schedulable.
            return {
                "execution_unit_id": unit_id,
                "step_key": unit["step_key"],
                "outcome": "unchanged",
                "reason": unit["state"],
                "published": False,
            }

        published = False
        if dispatch is not None and dispatch["published_at"] is None:
            published = await self._publish_dispatch(
                unit=unit, step=step, dispatch=dispatch, trace_id=trace_id
            )

        return {
            "execution_unit_id": unit_id,
            "step_key": unit["step_key"],
            "outcome": "dispatched" if outcome == "dispatched" else "replay",
            "assigned_principal_id": (
                str(unit["assigned_principal_id"]) if unit["assigned_principal_id"] else None
            ),
            "assigned_role": unit["assigned_role"],
            "target_stream": dispatch["target_stream"] if dispatch else None,
            "correlation_id": str(dispatch["correlation_id"]) if dispatch else None,
            "published": published,
        }

    async def _publish_dispatch(
        self,
        *,
        unit: dict[str, Any],
        step: PlanStep,
        dispatch: dict[str, Any],
        trace_id: str,
    ) -> bool:
        """Put the canonical dispatch on the SELECTED agent's own stream.

        The destination comes from the routing decision, never from a constant: change the team and
        the same plan step goes somewhere else. ``published_at`` is stamped only after the broker
        accepted it, so an unpublished dispatch stays visible to the next pass.
        """
        lineage = await self.store.get_execution_lineage(unit["goal_id"])
        if lineage is None:  # pragma: no cover - a unit cannot outlive its Goal's lineage row
            raise LookupError(f"goal {unit['goal_id']} has no execution lineage")
        envelope = build_dispatch_envelope(
            project_id=str(unit["project_id"]),
            goal_id=str(unit["goal_id"]),
            primary_work_item_id=str(lineage["primary_work_item_id"]),
            work_item_id=str(unit["work_item_id"]),
            execution_unit_id=str(unit["execution_unit_id"]),
            plan_revision_id=str(unit["plan_revision_id"]),
            step=step,
            assigned_principal_id=str(unit["assigned_principal_id"]),
            assigned_role=unit["assigned_role"],
            correlation_id=str(dispatch["correlation_id"]),
            trace_id=trace_id,
        )
        if not await self._publish(dispatch["target_stream"], envelope):
            return False
        await self.store.mark_dispatch_published(unit["execution_unit_id"])
        await self._audit(
            delegation_events.AUDIT_UNIT_DISPATCHED,
            f"step {unit['step_key']!r} of plan revision {unit['plan_revision_id']} dispatched to "
            f"principal {unit['assigned_principal_id']}",
            "dispatched",
            {
                "project_id": str(unit["project_id"]),
                "plan_revision_id": str(unit["plan_revision_id"]),
                "step_key": unit["step_key"],
                "execution_unit_id": str(unit["execution_unit_id"]),
                "assigned_principal_id": str(unit["assigned_principal_id"]),
                "target_stream": dispatch["target_stream"],
                "correlation_id": str(dispatch["correlation_id"]),
            },
        )
        return True

    # --- completion --------------------------------------------------------------------------------

    async def record_step_result(
        self,
        *,
        execution_unit_id: str,
        reported_by: str,
        correlation_id: str,
        disposition: str,
        result_ref: str | None = None,
    ) -> dict[str, Any]:
        """Apply a dispatched step's terminal result and unlock whatever it was blocking.

        The caller must present the dispatch's own correlation id and the principal it was issued
        to. This is the internal completion seam AT-M4 will fill with a real Run result; until then
        it is the only way a unit reaches a terminal state, and it is not a way for an arbitrary
        caller to assert one.
        """
        applied = await self.store.record_result(
            execution_unit_id=execution_unit_id,
            reported_by=reported_by,
            correlation_id=correlation_id,
            disposition=disposition,
            result_ref=result_ref,
        )
        unit = applied["unit"]
        if applied["outcome"] == "recorded":
            await self._audit(
                delegation_events.AUDIT_UNIT_RESULT,
                f"step {unit['step_key']!r} of plan revision {unit['plan_revision_id']} "
                f"reported {disposition}",
                disposition,
                {
                    "project_id": str(unit["project_id"]),
                    "plan_revision_id": str(unit["plan_revision_id"]),
                    "step_key": unit["step_key"],
                    "execution_unit_id": str(unit["execution_unit_id"]),
                    "reported_by": str(reported_by),
                    "unblocked_step_keys": [u["step_key"] for u in applied["unblocked"]],
                },
            )
            await self._observe(
                delegation_events.EVENT_UNIT_COMPLETED,
                {
                    "project_id": str(unit["project_id"]),
                    "plan_revision_id": str(unit["plan_revision_id"]),
                    "step_key": unit["step_key"],
                    "state": unit["state"],
                    "unblocked_step_keys": [u["step_key"] for u in applied["unblocked"]],
                },
            )
        return applied

    # --- reads --------------------------------------------------------------------------------------

    async def get_graph(self, plan_revision_id: str) -> dict[str, Any] | None:
        return await self.store.get_graph(plan_revision_id)

    async def get_unit(self, execution_unit_id: str) -> dict[str, Any] | None:
        return await self.store.get_unit(execution_unit_id)


__all__ = ["PlanDelegationService"]
