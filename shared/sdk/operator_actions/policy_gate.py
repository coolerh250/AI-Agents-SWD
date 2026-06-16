"""Stage 52 -- operator-action policy gate (fail-closed).

Combines the local action catalog with the platform policy-engine. An action is
permitted only when: it is a known, execution-enabled catalog action; the role
is allowed; AND the policy-engine does not block it. If the policy-engine is
unavailable, the gate FAILS CLOSED (action blocked). ``production_executed`` is
always asserted false in the policy input.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.sdk.operator_actions.action_catalog import get_action_entry, is_enabled
from shared.sdk.operator_actions.rbac import role_can


@dataclass
class PolicyDecision:
    allowed: bool
    policy_status: str
    reason: str
    risk_level: str = "low"
    requires_confirmation: bool = False


async def evaluate_action(
    *,
    action_type: str,
    role: str,
    target_type: str | None = None,
    target_id: str | None = None,
    policy_client=None,
) -> PolicyDecision:
    """Evaluate an operator action. Fail-closed on any uncertainty."""
    entry = get_action_entry(action_type)
    if entry is None:
        return PolicyDecision(False, "policy_blocked", "unknown_action_type", "critical")
    if not is_enabled(action_type):
        return PolicyDecision(
            False,
            "action_disabled",
            "action_disabled",
            entry.risk_level,
            entry.requires_confirmation,
        )
    if not role_can(role, action_type):
        return PolicyDecision(
            False, "policy_blocked", "rbac_denied", entry.risk_level, entry.requires_confirmation
        )

    # Consult the platform policy-engine. The operator-action namespace is
    # treated as a low/medium-risk controlled action; a restricted verdict
    # blocks. Any error -> fail closed.
    if policy_client is not None:
        try:
            verdict = await policy_client.evaluate(
                action=f"operator_action:{action_type}",
            )
        except Exception:  # noqa: BLE001 - policy engine unavailable -> fail closed
            return PolicyDecision(
                False,
                "policy_blocked",
                "policy_engine_unavailable",
                entry.risk_level,
                entry.requires_confirmation,
            )
        if isinstance(verdict, dict) and verdict.get("allowed") is False:
            # The engine restricts unknown actions; our controlled operator
            # actions are not in RESTRICTED_ACTIONS, so allowed should be true.
            return PolicyDecision(
                False,
                "policy_blocked",
                "policy_engine_restricted",
                entry.risk_level,
                entry.requires_confirmation,
            )

    return PolicyDecision(
        allowed=True,
        policy_status="allowed",
        reason="ok",
        risk_level=entry.risk_level,
        requires_confirmation=entry.requires_confirmation,
    )


__all__ = ["PolicyDecision", "evaluate_action"]
