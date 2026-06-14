"""Stage 45 -- map a work item's work_type to a suggested agent role.

Deterministic, table-driven. Existing agents (requirement-agent,
development-agent, qa-agent, devops-agent) are used where they fit;
future roles (planner-agent, architecture-capability,
security-capability, delivery-capability) are returned as *suggestions*
only. A future/unknown role MUST NOT cause a dispatch failure -- the
caller keeps the work item at ``status=pending`` /
``dispatch_policy=planning_only`` so nothing is auto-dispatched to a
non-existent agent.
"""

from __future__ import annotations

# Existing, runnable agents in this repo.
EXISTING_AGENT_ROLES = frozenset(
    {
        "requirement-agent",
        "development-agent",
        "qa-agent",
        "devops-agent",
    }
)

# Future roles -- reserved, not yet runnable. Never dispatched this stage.
FUTURE_AGENT_ROLES = frozenset(
    {
        "planner-agent",
        "architecture-capability",
        "backend-agent",
        "frontend-agent",
        "security-capability",
        "delivery-capability",
    }
)

# work_type -> suggested agent role. Future roles are intentionally
# mapped for some types so the graph is forward-compatible; the caller
# treats them as planning-only.
_WORK_TYPE_TO_ROLE = {
    "requirement": "requirement-agent",
    "architecture": "architecture-capability",
    "backend": "development-agent",
    "frontend": "development-agent",
    "database": "development-agent",
    "integration": "development-agent",
    "qa": "qa-agent",
    "security": "security-capability",
    "devops": "devops-agent",
    "documentation": "development-agent",
    "release": "delivery-capability",
}

_DEFAULT_ROLE = "development-agent"


def assign_agent_role(work_type: str | None) -> str:
    """Return the suggested agent role for a work_type."""
    if not work_type:
        return _DEFAULT_ROLE
    return _WORK_TYPE_TO_ROLE.get(work_type.lower().strip(), _DEFAULT_ROLE)


def is_runnable_role(role: str | None) -> bool:
    """True only for agents that actually exist and can be dispatched."""
    return bool(role) and role in EXISTING_AGENT_ROLES


def is_future_role(role: str | None) -> bool:
    return bool(role) and role in FUTURE_AGENT_ROLES


def resolve_dispatch_policy(
    work_type: str | None,
    risk_level: str,
    *,
    default_policy: str = "planning_only",
) -> str:
    """Decide a safe dispatch policy for a work item.

    * high / production risk -> ``approval_required`` (never auto-run).
    * a runnable role at low/medium risk -> the caller's default
      (still ``planning_only`` this stage; flips only when
      ``ENABLE_PROJECT_WORK_ITEM_DISPATCH`` is turned on later).
    * a future/unknown role -> ``planning_only`` always.
    """
    role = assign_agent_role(work_type)
    if risk_level in ("high", "production"):
        return "approval_required"
    if not is_runnable_role(role):
        return "planning_only"
    return default_policy


__all__ = [
    "EXISTING_AGENT_ROLES",
    "FUTURE_AGENT_ROLES",
    "assign_agent_role",
    "is_runnable_role",
    "is_future_role",
    "resolve_dispatch_policy",
]
