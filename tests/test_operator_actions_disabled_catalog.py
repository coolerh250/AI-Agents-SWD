"""Stage 52 -- disabled catalog entries are never executable via policy gate."""

from __future__ import annotations

import pytest

from shared.sdk.operator_actions.policy_gate import evaluate_action


@pytest.mark.parametrize(
    "action_type",
    [
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
    ],
)
async def test_disabled_action_blocked(action_type) -> None:
    decision = await evaluate_action(
        action_type=action_type, role="platform_admin", policy_client=None
    )
    assert decision.allowed is False
    assert decision.policy_status in ("action_disabled", "policy_blocked")


async def test_unknown_action_blocked() -> None:
    decision = await evaluate_action(
        action_type="arbitrary.shell", role="platform_admin", policy_client=None
    )
    assert decision.allowed is False
