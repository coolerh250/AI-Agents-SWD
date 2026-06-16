"""Stage 52 -- the static operator-action catalog.

Defines exactly which actions Admin Console v1 permits and which are explicitly
DISABLED. The catalog is the single source of truth for allowed roles, risk
level, confirmation requirement, and execution-enabled state. High-risk actions
(deploy, GitHub write, PR, workflow mutation, production backup, policy/budget
edits, arbitrary shell) appear only as DISABLED entries -- they can be listed in
the UI as future capability but never executed.
"""

from __future__ import annotations

from shared.sdk.operator_actions.models import ActionPolicyEntry

# --- enabled, controlled actions -------------------------------------------
ENABLED_ACTIONS: dict[str, ActionPolicyEntry] = {
    "operator_review.add_note": ActionPolicyEntry(
        action_type="operator_review.add_note",
        allowed_roles=["reviewer", "operator", "platform_admin"],
        risk_level="low",
        requires_reason=True,
        requires_confirmation=False,
        requires_approval_engine=False,
        execution_enabled=True,
    ),
    "delivery_package.request_changes": ActionPolicyEntry(
        action_type="delivery_package.request_changes",
        allowed_roles=["reviewer", "operator", "platform_admin"],
        risk_level="low",
        requires_reason=True,
        requires_confirmation=True,
        requires_approval_engine=False,
        execution_enabled=True,
    ),
    "delivery_package.accept": ActionPolicyEntry(
        action_type="delivery_package.accept",
        allowed_roles=["operator", "platform_admin"],
        risk_level="medium",
        requires_reason=True,
        requires_confirmation=True,
        requires_approval_engine=False,
        execution_enabled=True,
    ),
    "delivery_package.reject": ActionPolicyEntry(
        action_type="delivery_package.reject",
        allowed_roles=["operator", "platform_admin"],
        risk_level="medium",
        requires_reason=True,
        requires_confirmation=True,
        requires_approval_engine=False,
        execution_enabled=True,
    ),
    "verification.rerun": ActionPolicyEntry(
        action_type="verification.rerun",
        allowed_roles=["operator", "platform_admin"],
        risk_level="medium",
        requires_reason=True,
        requires_confirmation=True,
        requires_approval_engine=False,
        execution_enabled=True,
    ),
}

# --- explicitly disabled (future capability, never executable) -------------
DISABLED_ACTION_TYPES: tuple[str, ...] = (
    "workflow.pause",
    "workflow.resume",
    "workflow.dispatch",
    "work_item.update_status",
    "project.cancel",
    "github.create_pr",
    "github.merge_pr",
    "deployment.execute",
    "backup.production_run",
    "backup.production_restore",
    "policy.update",
    "model_policy.update",
    "budget.update",
    "incident.real_escalate",
)

DISABLED_ACTIONS: dict[str, ActionPolicyEntry] = {
    action_type: ActionPolicyEntry(
        action_type=action_type,
        allowed_roles=[],
        risk_level="critical",
        requires_reason=True,
        requires_confirmation=True,
        requires_approval_engine=True,
        execution_enabled=False,
    )
    for action_type in DISABLED_ACTION_TYPES
}


def get_action_entry(action_type: str) -> ActionPolicyEntry | None:
    return ENABLED_ACTIONS.get(action_type) or DISABLED_ACTIONS.get(action_type)


def is_enabled(action_type: str) -> bool:
    entry = ENABLED_ACTIONS.get(action_type)
    return bool(entry and entry.execution_enabled)


def is_known(action_type: str) -> bool:
    return action_type in ENABLED_ACTIONS or action_type in DISABLED_ACTIONS


def catalog_view() -> dict:
    """UI-safe catalog: enabled + disabled entries with no secrets."""
    return {
        "enabled": [e.model_dump() for e in ENABLED_ACTIONS.values()],
        "disabled": [e.model_dump() for e in DISABLED_ACTIONS.values()],
    }


__all__ = [
    "ENABLED_ACTIONS",
    "DISABLED_ACTIONS",
    "DISABLED_ACTION_TYPES",
    "get_action_entry",
    "is_enabled",
    "is_known",
    "catalog_view",
]
