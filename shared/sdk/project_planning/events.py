"""Stage 45 -- Redis stream + notification event constants for projects.

All ``project.*`` notification events live in a namespace that the
``DEFAULT_REAL_DELIVERY_DENYLIST`` blocks from real Discord delivery
(``project.*`` added there in Stage 45). These are operator-internal.
"""

from __future__ import annotations

# Redis streams for the project planning subsystem.
STREAM_PROJECT_PLANNING = "stream.project_planning"
STREAM_PROJECT_EVENTS = "stream.project_events"
STREAM_PROJECT_WORK_ITEMS = "stream.project_work_items"

# Notification event types (stream.notifications), project.* namespace.
EVENT_PROJECT_CREATED = "project.created"
EVENT_PROJECT_PLANNING_STARTED = "project.planning_started"
EVENT_PROJECT_PLANNING_COMPLETED = "project.planning_completed"
EVENT_PROJECT_PLANNING_FAILED = "project.planning_failed"
EVENT_PROJECT_GRAPH_VALIDATED = "project.graph_validated"
EVENT_PROJECT_WORK_ITEM_READY = "project.work_item_ready"
EVENT_PROJECT_WORK_ITEM_BLOCKED = "project.work_item_blocked"
EVENT_PROJECT_WORK_ITEM_COMPLETED = "project.work_item_completed"
EVENT_PROJECT_DELIVERY_READINESS_UPDATED = "project.delivery_readiness_updated"
EVENT_PROJECT_CLARIFICATION_REQUIRED = "project.clarification_required"

# Internal pipeline events (stream.project_planning / stream.project_events).
EVENT_REQUIREMENT_PROJECT_PLANNING_REQUESTED = "requirement.project_planning_requested"

PROJECT_NOTIFICATION_EVENTS: tuple[str, ...] = (
    EVENT_PROJECT_CREATED,
    EVENT_PROJECT_PLANNING_STARTED,
    EVENT_PROJECT_PLANNING_COMPLETED,
    EVENT_PROJECT_PLANNING_FAILED,
    EVENT_PROJECT_GRAPH_VALIDATED,
    EVENT_PROJECT_WORK_ITEM_READY,
    EVENT_PROJECT_WORK_ITEM_BLOCKED,
    EVENT_PROJECT_WORK_ITEM_COMPLETED,
    EVENT_PROJECT_DELIVERY_READINESS_UPDATED,
    EVENT_PROJECT_CLARIFICATION_REQUIRED,
)

__all__ = [
    "STREAM_PROJECT_PLANNING",
    "STREAM_PROJECT_EVENTS",
    "STREAM_PROJECT_WORK_ITEMS",
    "EVENT_PROJECT_CREATED",
    "EVENT_PROJECT_PLANNING_STARTED",
    "EVENT_PROJECT_PLANNING_COMPLETED",
    "EVENT_PROJECT_PLANNING_FAILED",
    "EVENT_PROJECT_GRAPH_VALIDATED",
    "EVENT_PROJECT_WORK_ITEM_READY",
    "EVENT_PROJECT_WORK_ITEM_BLOCKED",
    "EVENT_PROJECT_WORK_ITEM_COMPLETED",
    "EVENT_PROJECT_DELIVERY_READINESS_UPDATED",
    "EVENT_PROJECT_CLARIFICATION_REQUIRED",
    "EVENT_REQUIREMENT_PROJECT_PLANNING_REQUESTED",
    "PROJECT_NOTIFICATION_EVENTS",
]
