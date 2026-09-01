"""Step AT-M3.5 -- delegation event and audit vocabulary.

Names only. The dispatch command itself does not travel on a delegation stream: it is published to
the SELECTED AGENT'S OWN ``transport_stream``, which is what makes routing dynamic -- the
destination is a property of who the router chose, never a constant in this file.

``STREAM_PLAN_DELEGATION`` carries observation events (a graph was materialized, a unit became
ready, a step could not be assigned) for anything watching the delegation layer. Nothing consumes
it to decide anything; PostgreSQL remains the canonical state.
"""

from __future__ import annotations

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
