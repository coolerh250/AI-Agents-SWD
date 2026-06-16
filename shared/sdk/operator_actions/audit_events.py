"""Stage 52 -- operator-action audit decision_type constants + safe refs."""

from __future__ import annotations

DECISION_OPERATOR_SESSION_CREATED = "operator_session_created"
DECISION_OPERATOR_SESSION_REVOKED = "operator_session_revoked"
DECISION_OPERATOR_ACTION_REQUESTED = "operator_action_requested"
DECISION_OPERATOR_ACTION_POLICY_BLOCKED = "operator_action_policy_blocked"
DECISION_OPERATOR_ACTION_CONFIRMED = "operator_action_confirmed"
DECISION_OPERATOR_ACTION_COMPLETED = "operator_action_completed"
DECISION_OPERATOR_ACTION_FAILED = "operator_action_failed"
DECISION_OPERATOR_REVIEW_NOTE_ADDED = "operator_review_note_added"
DECISION_DELIVERY_PACKAGE_OPERATOR_ACCEPTED = "delivery_package_operator_accepted"
DECISION_DELIVERY_PACKAGE_OPERATOR_REJECTED = "delivery_package_operator_rejected"
DECISION_DELIVERY_PACKAGE_CHANGES_REQUESTED = "delivery_package_changes_requested"
DECISION_VERIFICATION_RERUN_STARTED = "verification_rerun_started"
DECISION_VERIFICATION_RERUN_COMPLETED = "verification_rerun_completed"
DECISION_VERIFICATION_RERUN_FAILED = "verification_rerun_failed"

OPERATOR_ACTION_DECISION_TYPES: tuple[str, ...] = (
    DECISION_OPERATOR_SESSION_CREATED,
    DECISION_OPERATOR_SESSION_REVOKED,
    DECISION_OPERATOR_ACTION_REQUESTED,
    DECISION_OPERATOR_ACTION_POLICY_BLOCKED,
    DECISION_OPERATOR_ACTION_CONFIRMED,
    DECISION_OPERATOR_ACTION_COMPLETED,
    DECISION_OPERATOR_ACTION_FAILED,
    DECISION_OPERATOR_REVIEW_NOTE_ADDED,
    DECISION_DELIVERY_PACKAGE_OPERATOR_ACCEPTED,
    DECISION_DELIVERY_PACKAGE_OPERATOR_REJECTED,
    DECISION_DELIVERY_PACKAGE_CHANGES_REQUESTED,
    DECISION_VERIFICATION_RERUN_STARTED,
    DECISION_VERIFICATION_RERUN_COMPLETED,
    DECISION_VERIFICATION_RERUN_FAILED,
)


def safe_operator_action_refs(
    *,
    action_key: str | None = None,
    action_type: str | None = None,
    identity_key: str | None = None,
    role: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    policy_status: str | None = None,
    status: str | None = None,
    verification_key: str | None = None,
    result_marker: str | None = None,
) -> dict:
    """Audit ``artifact_refs`` carrying only opaque ids / labels / statuses --
    never a raw token, secret, reason text dump, or chain-of-thought."""
    refs: dict = {
        "controlled_only": True,
        "production_executed": False,
        "github_write_performed": False,
        "pr_created": False,
        "deployment_performed": False,
        "external_delivery_performed": False,
    }
    for key, value in (
        ("action_key", action_key),
        ("action_type", action_type),
        ("identity_key", identity_key),
        ("role", role),
        ("target_type", target_type),
        ("target_id", target_id),
        ("policy_status", policy_status),
        ("status", status),
        ("verification_key", verification_key),
        ("result_marker", result_marker),
    ):
        if value is not None:
            refs[key] = value
    return refs


__all__ = [
    "DECISION_OPERATOR_SESSION_CREATED",
    "DECISION_OPERATOR_SESSION_REVOKED",
    "DECISION_OPERATOR_ACTION_REQUESTED",
    "DECISION_OPERATOR_ACTION_POLICY_BLOCKED",
    "DECISION_OPERATOR_ACTION_CONFIRMED",
    "DECISION_OPERATOR_ACTION_COMPLETED",
    "DECISION_OPERATOR_ACTION_FAILED",
    "DECISION_OPERATOR_REVIEW_NOTE_ADDED",
    "DECISION_DELIVERY_PACKAGE_OPERATOR_ACCEPTED",
    "DECISION_DELIVERY_PACKAGE_OPERATOR_REJECTED",
    "DECISION_DELIVERY_PACKAGE_CHANGES_REQUESTED",
    "DECISION_VERIFICATION_RERUN_STARTED",
    "DECISION_VERIFICATION_RERUN_COMPLETED",
    "DECISION_VERIFICATION_RERUN_FAILED",
    "OPERATOR_ACTION_DECISION_TYPES",
    "safe_operator_action_refs",
]
