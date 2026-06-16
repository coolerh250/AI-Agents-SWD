"""Stage 52 -- RBAC for operator actions.

Backend-authoritative role checks. Frontend hide/disable is UX only and never a
security control. ``platform_admin`` deliberately has the SAME action set as
``operator`` -- the name grants no deploy / GitHub / production capability.
"""

from __future__ import annotations

from shared.sdk.operator_actions.action_catalog import get_action_entry

ROLE_RANK = {"viewer": 0, "reviewer": 1, "operator": 2, "platform_admin": 2}


def role_can(role: str, action_type: str) -> bool:
    """True iff ``role`` is permitted to perform ``action_type``.

    The action must be in the catalog AND execution-enabled AND the role must be
    in the action's allowed_roles. Disabled/unknown actions are never allowed.
    """
    entry = get_action_entry(action_type)
    if entry is None or not entry.execution_enabled:
        return False
    return role in entry.allowed_roles


def highest_role(roles: list[str]) -> str:
    """Return the most-privileged role from a set (viewer if empty/unknown)."""
    best = "viewer"
    best_rank = -1
    for r in roles:
        rank = ROLE_RANK.get(r, -1)
        if rank > best_rank:
            best_rank, best = rank, r
    return best if best_rank >= 0 else "viewer"


def allowed_actions_for_roles(roles: list[str]) -> list[str]:
    from shared.sdk.operator_actions.action_catalog import ENABLED_ACTIONS

    return [a for a in ENABLED_ACTIONS if any(role_can(r, a) for r in roles)]


__all__ = ["ROLE_RANK", "role_can", "highest_role", "allowed_actions_for_roles"]
