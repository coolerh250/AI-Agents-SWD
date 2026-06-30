"""Step 61 -- DR operation model + readiness."""

from __future__ import annotations

import pytest

from shared.sdk.backup_restore_dr import build_dr_operation, evaluate_readiness
from shared.sdk.backup_restore_dr.models import (
    DR_OPERATION_TYPES,
    FORBIDDEN_DR_OPERATION_TYPES,
)


@pytest.mark.parametrize("op", list(FORBIDDEN_DR_OPERATION_TYPES))
def test_forbidden_operation_blocked(op: str) -> None:
    o = build_dr_operation(operation_type=op, target_environment="nonprod")
    assert o.status == "blocked"
    d = o.to_dict()
    assert d["production_restore"] is False
    assert d["production_failover"] is False
    assert d["production_executed"] is False


@pytest.mark.parametrize("op", list(DR_OPERATION_TYPES))
def test_allowed_operation_recorded(op: str) -> None:
    o = build_dr_operation(operation_type=op, target_environment="nonprod")
    assert o.status == "recorded"


def test_production_target_blocked() -> None:
    o = build_dr_operation(operation_type="backup_inventory", target_environment="production")
    assert o.status == "blocked"


def test_readiness_never_production_ready() -> None:
    r = evaluate_readiness(target_environment="nonprod", evidence={})
    assert r.decision == "blocked_by_missing_evidence"
    d = r.to_dict()
    assert d["production_ready"] is False
    assert d["production_restore_ready"] is False
    full = {
        "backup_inventory": 1,
        "backup_target_classification": 1,
        "restore_plan": 1,
        "restore_validation_result": 1,
    }
    r2 = evaluate_readiness(target_environment="nonprod", evidence=full)
    assert r2.decision == "ready_for_operator_review"
    assert r2.to_dict()["production_ready"] is False
