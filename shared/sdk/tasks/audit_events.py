"""Step 66B.1 -- task API audit decision_type constants + safe refs."""

from __future__ import annotations

DECISION_TASK_CREATED = "task_created"
DECISION_TASK_SUBMITTED = "task_submitted"
DECISION_TASK_REJECTED_BY_POLICY = "task_rejected_by_policy"
# Step 66B.3 -- emitted on every RBAC denial (403): role lacks the capability, or a
# Requester targets another actor's task. Hardens the audit evidence surface so
# denied attempts are traceable, not just successful actions.
DECISION_TASK_RBAC_DENIED = "task_rbac_denied"

TASK_DECISION_TYPES: tuple[str, ...] = (
    DECISION_TASK_CREATED,
    DECISION_TASK_SUBMITTED,
    DECISION_TASK_REJECTED_BY_POLICY,
    DECISION_TASK_RBAC_DENIED,
)


def safe_task_refs(
    *,
    task_id: str | None = None,
    correlation_id: str | None = None,
    actor: str | None = None,
    role: str | None = None,
    action: str | None = None,
    production_effect: bool | None = None,
    environment: str | None = None,
    status: str | None = None,
) -> dict:
    """Audit ``artifact_refs`` carrying only opaque ids / labels / statuses --
    never a raw token, secret, or payload dump."""
    refs: dict = {
        "production_executed": False,
        "workflow_dispatched": False,
        "external_write_performed": False,
        "github_write_performed": False,
        "discord_send_performed": False,
        "llm_call_performed": False,
    }
    for key, value in (
        ("task_id", task_id),
        ("correlation_id", correlation_id),
        ("actor", actor),
        ("role", role),
        ("action", action),
        ("production_effect", production_effect),
        ("environment", environment),
        ("status", status),
    ):
        if value is not None:
            refs[key] = value
    return refs


__all__ = [
    "DECISION_TASK_CREATED",
    "DECISION_TASK_SUBMITTED",
    "DECISION_TASK_REJECTED_BY_POLICY",
    "DECISION_TASK_RBAC_DENIED",
    "TASK_DECISION_TYPES",
    "safe_task_refs",
]
