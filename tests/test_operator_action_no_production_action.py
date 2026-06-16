"""Stage 52 -- no production / deploy / github action is ever executable."""

from __future__ import annotations

import pytest

from shared.sdk.operator_actions.action_catalog import is_enabled
from shared.sdk.operator_actions.policy_gate import evaluate_action
from shared.sdk.operator_actions.rbac import role_can

PROD_ACTIONS = [
    "deployment.execute",
    "github.create_pr",
    "github.merge_pr",
    "backup.production_run",
    "backup.production_restore",
    "workflow.dispatch",
    "work_item.update_status",
    "policy.update",
    "budget.update",
    "incident.real_escalate",
]


@pytest.mark.parametrize("action", PROD_ACTIONS)
def test_no_role_can_execute(action) -> None:
    for role in ("viewer", "reviewer", "operator", "platform_admin"):
        assert role_can(role, action) is False
    assert is_enabled(action) is False


@pytest.mark.parametrize("action", PROD_ACTIONS)
async def test_policy_gate_blocks(action) -> None:
    d = await evaluate_action(action_type=action, role="platform_admin", policy_client=None)
    assert d.allowed is False
