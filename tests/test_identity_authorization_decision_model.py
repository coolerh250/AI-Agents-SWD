"""Step 52.3 -- identity authorization decision model + separations."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "identity-authorization-decision-model.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_decision_chain_stages() -> None:
    stages = [s["stage"] for s in _d()["decisionChain"]]
    for required in (
        "authentication",
        "role_mapping",
        "rbac",
        "policy_engine",
        "confirmation",
        "idempotency",
        "audit",
        "final_authorization",
    ):
        assert required in stages


def test_separations() -> None:
    sep = _d()["separations"]
    assert sep["roleMappingIsNotRbac"] is True
    assert sep["rbacIsNotPolicyApproval"] is True
    assert sep["confirmationIsNotPermission"] is True
    assert sep["humanAcceptanceIsNotDeploymentApproval"] is True
    assert sep["platformAdminIsNotInfrastructureAdmin"] is True


def test_production_actions_future_gated() -> None:
    pa = _d()["productionActions"]
    assert pa["requireFutureProductionApprovalGate"] is True
    assert pa["currentlyExecutable"] is False
