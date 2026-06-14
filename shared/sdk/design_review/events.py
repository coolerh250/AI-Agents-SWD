"""Stage 46 -- design review Redis stream + notification events.

All ``design_review.*`` notification events are operator-internal and on the
default real-delivery denylist (added in Stage 46).
"""

from __future__ import annotations

STREAM_DESIGN_REVIEW = "stream.design_review"
STREAM_DESIGN_REVIEW_EVENTS = "stream.design_review_events"

EVENT_DESIGN_REVIEW_STARTED = "design_review.started"
EVENT_DESIGN_REVIEW_COMPLETED = "design_review.completed"
EVENT_DESIGN_REVIEW_BLOCKED = "design_review.blocked"
EVENT_DESIGN_REVIEW_GATE_UPDATED = "design_review.gate_updated"
EVENT_DESIGN_REVIEW_FINDING_CREATED = "design_review.finding_created"
EVENT_DESIGN_REVIEW_GO_NO_GO_RECORDED = "design_review.go_no_go_recorded"

# Internal pipeline event published by the orchestrator router.
EVENT_PROJECT_DESIGN_REVIEW_REQUESTED = "project.design_review_requested"

DESIGN_REVIEW_NOTIFICATION_EVENTS: tuple[str, ...] = (
    EVENT_DESIGN_REVIEW_STARTED,
    EVENT_DESIGN_REVIEW_COMPLETED,
    EVENT_DESIGN_REVIEW_BLOCKED,
    EVENT_DESIGN_REVIEW_GATE_UPDATED,
    EVENT_DESIGN_REVIEW_FINDING_CREATED,
    EVENT_DESIGN_REVIEW_GO_NO_GO_RECORDED,
)

__all__ = [
    "STREAM_DESIGN_REVIEW",
    "STREAM_DESIGN_REVIEW_EVENTS",
    "EVENT_DESIGN_REVIEW_STARTED",
    "EVENT_DESIGN_REVIEW_COMPLETED",
    "EVENT_DESIGN_REVIEW_BLOCKED",
    "EVENT_DESIGN_REVIEW_GATE_UPDATED",
    "EVENT_DESIGN_REVIEW_FINDING_CREATED",
    "EVENT_DESIGN_REVIEW_GO_NO_GO_RECORDED",
    "EVENT_PROJECT_DESIGN_REVIEW_REQUESTED",
    "DESIGN_REVIEW_NOTIFICATION_EVENTS",
]
