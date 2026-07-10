"""Step 66C.1 -- Agent Workroom & Clarification RBAC.

Reuses the Step 66B TASK_ROLES vocabulary. No project/team scoping model exists
yet (documented gap carried over from 66A.3/66B) -- the only ownership scoping
enforced is Requester-to-own-task (checked by the caller in workroom_api.py,
same pattern as shared/sdk/tasks/rbac.py). All other roles are unscoped by
task ownership in this stage; this is a documented fallback, not overclaimed as
full project/team RBAC.
"""

from __future__ import annotations

from shared.sdk.tasks.rbac import TASK_ROLES

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


__all__ = [
    "can_view_workroom",
    "can_post_message",
    "can_create_clarification",
    "can_answer_clarification",
]
