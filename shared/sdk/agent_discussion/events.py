"""Stage 46 -- agent discussion Redis stream + notification events.

All ``discussion.*`` notification events are operator-internal and on the
default real-delivery denylist (added in Stage 46).
"""

from __future__ import annotations

STREAM_AGENT_DISCUSSIONS = "stream.agent_discussions"

EVENT_DISCUSSION_SESSION_STARTED = "discussion.session_started"
EVENT_DISCUSSION_CONTRIBUTION_ADDED = "discussion.contribution_added"
EVENT_DISCUSSION_SESSION_COMPLETED = "discussion.session_completed"

DISCUSSION_NOTIFICATION_EVENTS: tuple[str, ...] = (
    EVENT_DISCUSSION_SESSION_STARTED,
    EVENT_DISCUSSION_CONTRIBUTION_ADDED,
    EVENT_DISCUSSION_SESSION_COMPLETED,
)

__all__ = [
    "STREAM_AGENT_DISCUSSIONS",
    "EVENT_DISCUSSION_SESSION_STARTED",
    "EVENT_DISCUSSION_CONTRIBUTION_ADDED",
    "EVENT_DISCUSSION_SESSION_COMPLETED",
    "DISCUSSION_NOTIFICATION_EVENTS",
]
