"""Step 66C.1 -- Agent Workroom & Clarification RBAC.

Reuses the Step 66B TASK_ROLES vocabulary. No project/team scoping model exists
yet (documented gap carried over from 66A.3/66B) -- the only ownership scoping
enforced is Requester-to-own-task (checked by the caller in workroom_api.py,
same pattern as shared/sdk/tasks/rbac.py). All other roles are unscoped by
task ownership in this stage; this is a documented fallback, not overclaimed as
full project/team RBAC.

Step 66C.3 adds two more RBAC surfaces, both server-side and mandatory (no
frontend-only hiding): per-message visibility filtering (G1) and task-scoped
audit-evidence read access (G3). See docs/test/step66c3-message-visibility-evidence.md
and docs/test/step66c3-task-audit-evidence-endpoint-record.md for the enforced
matrix and the reasoning -- the matrix below is deliberately conservative
(fail-closed for any role/visibility combination not explicitly listed) rather
than an attempt to fully reproduce the illustrative table in the 66C.3 spec.
"""

from __future__ import annotations

from shared.sdk.tasks.rbac import TASK_ROLES

# Step 66C.3 (G1) -- which roles may see a message of a given `visibility`
# value. `task_participants` is unchanged from 66C.1/66C.2 (every role that can
# view the workroom at all sees these, still subject to the existing
# Requester-to-own-task scoping check in workroom_api.py). Any visibility value
# not present here is fail-closed (visible to nobody) rather than raising --
# an unrecognized value should never silently leak.
_VISIBILITY_ROLES: dict[str, frozenset[str]] = {
    "task_participants": TASK_ROLES,
    "operators": frozenset({"pm_engineering_lead", "platform_admin", "agent_operator"}),
    "audit_only": frozenset({"security_compliance_reviewer"}),
    "private_system": frozenset({"platform_admin", "agent_operator"}),
}

# Step 66C.3 (G3) -- roles allowed to read GET /tasks/{id}/audit-evidence.
# Requester and Reviewer/Approver are denied by default (conservative choice,
# documented in step66c3-task-audit-evidence-endpoint-record.md) -- audit
# evidence is a more sensitive surface than the workroom itself (it includes
# RBAC-denial reasons and body hashes across the whole task, not just messages
# the role already has visibility into).
_AUDIT_EVIDENCE_ROLES: frozenset[str] = frozenset(
    {"platform_admin", "agent_operator", "security_compliance_reviewer", "pm_engineering_lead"}
)

# View: all six roles (Requester further scoped to own task by the caller).
_VIEW_ROLES: frozenset[str] = TASK_ROLES

# Post a human workroom message: everyone except Security/Compliance Reviewer,
# which is view-only by default (matches ai-team-work-rbac-blueprint.md).
_POST_MESSAGE_ROLES: frozenset[str] = frozenset(
    {"requester", "pm_engineering_lead", "reviewer_approver", "platform_admin", "agent_operator"}
)

# Create a clarification request: PM/Eng Lead, Platform Admin, Agent Operator only.
# Requester defaults to NOT allowed (operator decision, spec 66C.1 section 7).
# Reviewer/Approver and Security/Compliance Reviewer are also excluded by default.
_CREATE_CLARIFICATION_ROLES: frozenset[str] = frozenset(
    {"pm_engineering_lead", "platform_admin", "agent_operator"}
)

# Answer a clarification: Requester (if task owner), PM/Eng Lead, Platform Admin.
_ANSWER_CLARIFICATION_ROLES: frozenset[str] = frozenset(
    {"requester", "pm_engineering_lead", "platform_admin"}
)


def can_view_workroom(role: str) -> bool:
    return role in _VIEW_ROLES


def can_post_message(role: str) -> bool:
    return role in _POST_MESSAGE_ROLES


def can_create_clarification(role: str) -> bool:
    return role in _CREATE_CLARIFICATION_ROLES


def can_answer_clarification(role: str) -> bool:
    return role in _ANSWER_CLARIFICATION_ROLES


def visible_message(role: str, visibility: str) -> bool:
    """Step 66C.3 (G1) -- true if `role` may see a message of this visibility."""
    allowed = _VISIBILITY_ROLES.get(visibility)
    return allowed is not None and role in allowed


def filter_messages_by_visibility(
    messages: list[dict[str, object]], role: str
) -> list[dict[str, object]]:
    """Step 66C.3 (G1) -- server-side visibility filter. Never bypassed by the
    frontend; the UI only ever renders what this function has already let
    through."""
    return [m for m in messages if visible_message(role, str(m["visibility"]))]


def can_view_audit_evidence(role: str) -> bool:
    """Step 66C.3 (G3) -- true if `role` may read GET /tasks/{id}/audit-evidence."""
    return role in _AUDIT_EVIDENCE_ROLES


__all__ = [
    "can_view_workroom",
    "can_post_message",
    "can_create_clarification",
    "can_answer_clarification",
    "visible_message",
    "filter_messages_by_visibility",
    "can_view_audit_evidence",
]
