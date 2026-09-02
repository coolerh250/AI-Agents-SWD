"""Step AT-M3.5 -- delegation event and audit vocabulary.

Names only. The dispatch command does not travel on a constant stream: its destination is derived
from the ``agent_key`` the AT-M2 router selected, so routing stays dynamic -- see
``models.delegation_stream_for``. What is fixed is the NAMESPACE it is derived within, and that
namespace is deliberately isolated from every live agent input stream.

``STREAM_PLAN_DELEGATION`` is that namespace root, and it also carries observation events (a graph
was materialized, a step could not be assigned) for anything watching the delegation layer. Nothing
consumes any of it; PostgreSQL remains the canonical state.

FORWARD CONTRACT FOR AT-M4, recorded here and deliberately not implemented here:

    AT-M3.5 has no execution consumer, by design. When AT-M4 introduces one, it MUST dedupe on the
    canonical dispatch identity -- ``correlation_id``, equivalently ``execution_unit_id`` -- BEFORE
    any execution effect. Redis Streams are at-least-once and concurrent schedulers may publish
    several copies of one canonical dispatch; every copy carries the same identity and the same
    envelope, and PostgreSQL holds exactly one dispatch row. A consumer that acted per message
    rather than per identity would execute one plan step more than once.

    That receiver is not built here, and no dedupe framework is introduced here. AT-M4 also owns the
    authenticated runtime-execution identity that agent-originated completion requires; until it
    exists, completion is an internal scheduler seam with no HTTP surface.
"""

from __future__ import annotations

#: The namespace root. Individual dispatch destinations are ``stream.plan_delegation.<agent_key>``.
STREAM_PLAN_DELEGATION = "stream.plan_delegation"

EVENT_GRAPH_MATERIALIZED = "plan_graph.materialized"
EVENT_UNIT_ASSIGNED = "plan_step.assigned"
EVENT_UNIT_UNASSIGNABLE = "plan_step.unassignable"
EVENT_UNIT_DISPATCHED = "plan_step.dispatched"
EVENT_UNIT_COMPLETED = "plan_step.completed"
EVENT_UNIT_READY = "plan_step.ready"

AUDIT_GRAPH_MATERIALIZED = "plan_graph_materialized"
AUDIT_UNIT_ASSIGNED = "plan_step_assigned"
AUDIT_UNIT_DISPATCHED = "plan_step_dispatched"
AUDIT_UNIT_RESULT = "plan_step_result_recorded"

__all__ = [
    "AUDIT_GRAPH_MATERIALIZED",
    "AUDIT_UNIT_ASSIGNED",
    "AUDIT_UNIT_DISPATCHED",
    "AUDIT_UNIT_RESULT",
    "EVENT_GRAPH_MATERIALIZED",
    "EVENT_UNIT_ASSIGNED",
    "EVENT_UNIT_COMPLETED",
    "EVENT_UNIT_DISPATCHED",
    "EVENT_UNIT_READY",
    "EVENT_UNIT_UNASSIGNABLE",
    "STREAM_PLAN_DELEGATION",
]
