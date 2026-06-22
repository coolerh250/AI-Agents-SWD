"""Step 52.1 -- operator action authorization inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.operator_actions.action_catalog import DISABLED_ACTION_TYPES, ENABLED_ACTIONS

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "operator-action-authorization.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_inventory_matches_enabled_catalog() -> None:
    inv = {a["actionType"] for a in _d()["actions"]}
    assert inv == set(ENABLED_ACTIONS)


def test_all_actions_audited_and_csrf() -> None:
    for a in _d()["actions"]:
        assert a["auditRequired"] is True
        assert a["csrfRequired"] is True
        assert a["requiresReason"] is True
        assert a["productionEffect"] == "none"


def test_invariants() -> None:
    inv = _d()["invariants"]
    assert inv["acceptIsNotDeploy"] is True
    assert inv["verificationRerunAllowlistOnly"] is True
    assert inv["noArbitraryShell"] is True
    assert inv["noProductionAction"] is True


def test_disabled_actions_match_catalog() -> None:
    assert set(_d()["disabledActions"]["actionTypes"]) == set(DISABLED_ACTION_TYPES)
