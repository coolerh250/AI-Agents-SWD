"""Stage 51 -- restore drill is isolated-only; production restore blocked."""

from __future__ import annotations

import pytest

from shared.sdk.backup_dr.backup_runner import ProductionBackupBlocked
from shared.sdk.backup_dr.restore_drill import (
    assert_isolated_target,
    build_restore_drill_run,
    restore_drill_ok,
)


def test_build_drill_isolated_ok() -> None:
    d = build_restore_drill_run(
        restore_key="r1",
        target_database="aiagents_restore_drill_123",
        status="verified",
        schema_verified=True,
        row_count_verified=True,
        rto_seconds=4.2,
    )
    assert d.production_restore_performed is False
    assert restore_drill_ok(d) is True


@pytest.mark.parametrize("target", ["aiagents", "postgres", "production", "app_production"])
def test_production_restore_blocked(target) -> None:
    with pytest.raises(ProductionBackupBlocked):
        assert_isolated_target(target)
    with pytest.raises(ProductionBackupBlocked):
        build_restore_drill_run(restore_key="r", target_database=target)


def test_failed_drill_not_ok() -> None:
    d = build_restore_drill_run(
        restore_key="r2",
        target_database="aiagents_restore_drill_x",
        status="failed",
    )
    assert restore_drill_ok(d) is False
