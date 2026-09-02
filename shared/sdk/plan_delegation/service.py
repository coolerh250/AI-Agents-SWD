"""Step AT-M3.5 -- plan-driven delegation runtime.

Two PUBLIC commands, and deliberately only two:

``materialize_accepted_plan``   an accepted, current PlanRevision becomes a durable execution graph
``schedule_ready_work``          ready steps acquire owners and become dispatched commands

plus one INTERNAL seam, reachable from the scheduler and from tests but from no HTTP route:

``record_internal_result``       a dispatched step's mock result, applied to the graph

There is no ``set_ready``, no ``assign_principal``, no ``mark_dispatched`` and no
``rebind_revision``. Every one of those would let a caller reach past the invariants the store
enforces -- readiness is derived from dependencies, ownership is decided by the AT-M2 router from
the live team, and a dispatch is bound to the revision that authorized it. A command that could
override any of them would make the guarantee a convention.

Completion is internal for the same reason, arrived at the hard way. It was public, guarded by a
caller-supplied ``reported_by`` and ``correlation_id`` checked against the dispatch row -- and both
values are published by the read surface, so the guard was a lookup rather than an authorization.
AT-M4 owns the authenticated runtime-execution identity a real completion ingress needs; until it
exists there is no honest public completion, so there is none. What remains takes no identity at
all and reads every attributed value from the canonical dispatch.

WHAT THIS LAYER DOES NOT DO, and cannot: it runs no code, no shell, no test, no Git operation, no
GitHub call, no deployment and no external request. ``dispatch`` here means "agent X, this plan
step is now yours" -- a structured work assignment staged on an ISOLATED internal stream that
nothing consumes. Performing the work is AT-M4, and nothing in this module could be given that
capability without new imports, a new migration and a new decision.

TRANSPORT IS AT-LEAST-ONCE; CANONICAL STATE IS EXACTLY-ONCE. The dispatch row commits first and is
published afterwards, because a Redis ``XADD`` cannot join a PostgreSQL transaction. A crash
between the two leaves a canonical dispatch with ``published_at`` NULL, and the next schedule pass
re-publishes THAT SAME dispatch -- same row, same correlation id -- rather than minting a second
one. A consumer may therefore see one command twice and must dedupe on ``correlation_id``; it can
never see two different commands for one step. The AUDIT record follows the durable state rather
than the wire: only the worker whose compare-and-swap actually stamps ``published_at`` claims a
dispatch success, so one canonical dispatch produces one success event however many copies of it
reached the broker.

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
        """Stage the canonical dispatch on the selected agent's ISOLATED delegation stream.

        The destination is still a function of who the router chose -- change the team and the same
        plan step goes somewhere else -- but it is derived from the winner's ``agent_key`` rather
        than being the winner's own live ``transport_stream``. Those streams have real consumers,
        and a ``plan_step.dispatched`` envelope landing on one would reach ``StreamAgent.handle()``:
        AT-M4 execution started by a stream name. See ``DELEGATION_STREAM_PREFIX``.

        ``published_at`` is stamped only after the broker accepted the message, so an unpublished
        dispatch stays visible to the next pass.

        **The audit event follows the stamp, not the publish.** Several workers may put a copy of
        the same canonical dispatch on the wire -- that is the at-least-once transport working -- and
        each successful ``XADD`` is a delivery ATTEMPT, not a second dispatch. Only the worker whose
        compare-and-swap actually moves ``published_at`` from NULL to a timestamp emits the canonical
        dispatch-success event, so the audit chain records one success per durable dispatch rather
        than one per network call. Auditing every publish would make the record say the team handed
        the step over three times when it handed it over once.
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
        # Write-once: exactly one contender wins this, however many published a copy.
        if not await self.store.mark_dispatch_published(unit["execution_unit_id"]):
            return True
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

    async def record_internal_result(
        self,
        *,
        execution_unit_id: str,
        disposition: str,
        evidence_ref: str | None = None,
    ) -> dict[str, Any]:
        """INTERNAL scheduler seam: apply a mock result and unlock whatever it was blocking.

        Not reachable over HTTP, and deliberately so. AT-M4 is not authorized, so no authenticated
        runtime-agent identity exists yet; a public completion mutation would therefore have had to
        authenticate on identifiers -- ``reported_by`` and ``correlation_id`` -- that the read
        surface hands out. Identifiers are not credentials, and a check against a value the caller
        can look up is not a check. The route is gone and the inputs are gone with it.

        What remains is this: the caller says WHICH unit finished and HOW, and every identity the
        record is attributed to -- assigned principal, correlation id, plan revision, step -- is read
        from that unit's own canonical dispatch row. Impersonation is unrepresentable rather than
        detected.

        ``evidence_ref`` is a REFERENCE to a result, never a result body.

        AT-M4 owns the authenticated agent/runtime completion boundary. When it exists, it
        establishes which unit is being answered and then calls this; it does not replace it. This
        remediation deliberately implements no part of that boundary -- no mTLS, no JWT, no API key,
        no signed callback, no bearer token.
        """
        applied = await self.store.record_result(
            execution_unit_id=execution_unit_id,
            disposition=disposition,
            result_ref=evidence_ref,
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
                    # Read from the canonical dispatch, never from the caller.
                    "assigned_principal_id": (
                        str(unit["assigned_principal_id"])
                        if unit["assigned_principal_id"]
                        else None
                    ),
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
