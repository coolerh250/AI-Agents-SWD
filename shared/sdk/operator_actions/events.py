"""Stage 52 -- operator-action notification event constants.

All ``operator_action.*`` / ``operator_review.*`` / ``verification_rerun.*``
events are operator-internal and DEFAULT-DENIED for real external delivery (see
shared.sdk.notifications.real_delivery_policy).
"""

from __future__ import annotations

STREAM_OPERATOR_ACTIONS = "stream.operator_actions"

EVENT_ACTION_REQUESTED = "operator_action.requested"
EVENT_ACTION_POLICY_BLOCKED = "operator_action.policy_blocked"
EVENT_ACTION_COMPLETED = "operator_action.completed"
EVENT_ACTION_FAILED = "operator_action.failed"
EVENT_REVIEW_ACCEPTED = "operator_review.accepted"
EVENT_REVIEW_REJECTED = "operator_review.rejected"
EVENT_REVIEW_CHANGES_REQUESTED = "operator_review.changes_requested"
EVENT_RERUN_STARTED = "verification_rerun.started"
EVENT_RERUN_COMPLETED = "verification_rerun.completed"
EVENT_RERUN_FAILED = "verification_rerun.failed"

OPERATOR_ACTION_EVENTS: tuple[str, ...] = (
    EVENT_ACTION_REQUESTED,
    EVENT_ACTION_POLICY_BLOCKED,
    EVENT_ACTION_COMPLETED,
    EVENT_ACTION_FAILED,
    EVENT_REVIEW_ACCEPTED,
    EVENT_REVIEW_REJECTED,
    EVENT_REVIEW_CHANGES_REQUESTED,
    EVENT_RERUN_STARTED,
    EVENT_RERUN_COMPLETED,
    EVENT_RERUN_FAILED,
)

OPERATOR_ACTION_DENY_PATTERNS: tuple[str, ...] = (
    "operator_action.*",
    "operator_review.*",
    "verification_rerun.*",
)


__all__ = [
    "STREAM_OPERATOR_ACTIONS",
    "EVENT_ACTION_REQUESTED",
    "EVENT_ACTION_POLICY_BLOCKED",
    "EVENT_ACTION_COMPLETED",
    "EVENT_ACTION_FAILED",
    "EVENT_REVIEW_ACCEPTED",
    "EVENT_REVIEW_REJECTED",
    "EVENT_REVIEW_CHANGES_REQUESTED",
    "EVENT_RERUN_STARTED",
    "EVENT_RERUN_COMPLETED",
    "EVENT_RERUN_FAILED",
    "OPERATOR_ACTION_EVENTS",
    "OPERATOR_ACTION_DENY_PATTERNS",
]
