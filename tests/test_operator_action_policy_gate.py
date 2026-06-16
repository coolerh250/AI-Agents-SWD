"""Stage 52 -- policy gate: RBAC + policy-engine + fail-closed."""

from __future__ import annotations


from shared.sdk.operator_actions.policy_gate import evaluate_action


class _AllowClient:
    async def evaluate(self, action: str):
        return {"allowed": True, "approval_required": False, "risk_level": "low"}


class _BlockClient:
    async def evaluate(self, action: str):
        return {"allowed": False, "approval_required": True, "risk_level": "high"}


class _BoomClient:
    async def evaluate(self, action: str):
        raise RuntimeError("policy engine down")


async def test_allowed_action() -> None:
    d = await evaluate_action(
        action_type="delivery_package.accept", role="operator", policy_client=_AllowClient()
    )
    assert d.allowed is True
    assert d.requires_confirmation is True


async def test_rbac_denied() -> None:
    d = await evaluate_action(
        action_type="delivery_package.accept", role="reviewer", policy_client=_AllowClient()
    )
    assert d.allowed is False
    assert d.reason == "rbac_denied"


async def test_policy_engine_block() -> None:
    d = await evaluate_action(
        action_type="delivery_package.accept", role="operator", policy_client=_BlockClient()
    )
    assert d.allowed is False
    assert d.policy_status == "policy_blocked"


async def test_policy_engine_unavailable_fails_closed() -> None:
    d = await evaluate_action(
        action_type="delivery_package.accept", role="operator", policy_client=_BoomClient()
    )
    assert d.allowed is False
    assert d.reason == "policy_engine_unavailable"


async def test_no_policy_client_still_rbac_gated() -> None:
    d = await evaluate_action(
        action_type="operator_review.add_note", role="reviewer", policy_client=None
    )
    assert d.allowed is True
