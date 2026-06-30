"""Step 61 -- restore plan model."""

from __future__ import annotations

import pytest

from shared.sdk.backup_restore_dr import build_restore_plan
from shared.sdk.backup_restore_dr.models import FORBIDDEN_RESTORE_TYPES


@pytest.mark.parametrize("rt", list(FORBIDDEN_RESTORE_TYPES))
def test_forbidden_restore_types_blocked(rt: str) -> None:
    p = build_restore_plan(target="pg", restore_type=rt, target_environment="nonprod")
    assert p.status == "blocked"
    assert "forbidden_restore_type" in (p.blocked_reason or "")
    assert p.to_dict()["production_restore"] is False


@pytest.mark.parametrize("env", ["production", "prod"])
def test_production_target_blocked(env: str) -> None:
    p = build_restore_plan(target="pg", restore_type="validate_backup", target_environment=env)
    assert p.status == "blocked"
    assert p.blocked_reason == "production_environment_forbidden"


def test_nonproduction_plan_never_executes() -> None:
    p = build_restore_plan(
        target="pg", restore_type="dry_run_restore", target_environment="nonprod"
    )
    d = p.to_dict()
    assert p.status == "planned"
    assert d["restore_executed"] is False
    assert d["production_restore"] is False
    assert d["validation_required"] is True
    assert d["rollback_plan_required"] is True


def test_unknown_restore_type_blocked() -> None:
    p = build_restore_plan(
        target="pg", restore_type="wipe_everything", target_environment="nonprod"
    )
    assert p.status == "blocked"
