"""Step 66B.1 -- task API RBAC foundation.

Six-role vocabulary from the Step 66A.3 RBAC blueprint (ai-team-work-rbac-blueprint.md).
Scoped to the three 66B.1 capabilities only (create / view / submit); the full
capability matrix (approve, retry/replay, manage settings, etc.) is deferred to the
stages that implement those actions.
"""

from __future__ import annotations

TASK_ROLES: frozenset[str] = frozenset(
    {
        "requester",
        "pm_engineering_lead",
        "reviewer_approver",
        "platform_admin",
        "agent_operator",
        "security_compliance_reviewer",
    }
)

# Matches the "Create task" row of ai-team-work-rbac-blueprint.md: Requester + PM/Eng
# Lead + Platform Admin allowed; Reviewer / Agent Operator / Sec-Compliance denied.
_CREATE_ROLES: frozenset[str] = frozenset({"requester", "pm_engineering_lead", "platform_admin"})

# Matches the "View task / workroom" row: all six roles can view; Requester is
# additionally scoped to own tasks only (enforced by the caller, not here).
_VIEW_ROLES: frozenset[str] = TASK_ROLES

# Submit shares the create capability set (submitting is part of the assignment flow).
_SUBMIT_ROLES: frozenset[str] = _CREATE_ROLES


def can_create(role: str) -> bool:
    return role in _CREATE_ROLES


def can_view(role: str) -> bool:
    return role in _VIEW_ROLES


def can_submit(role: str) -> bool:
    return role in _SUBMIT_ROLES


__all__ = ["TASK_ROLES", "can_create", "can_view", "can_submit"]
