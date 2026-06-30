"""Step 63A -- rollback / DR pilot readiness."""

from __future__ import annotations

from shared.sdk.controlled_rollout import loaders


def test_step61_pass_not_production_dr_ready() -> None:
    r = loaders.load("rollback_dr")
    assert r.get("step61_pass_is_production_dr_ready") is False


def test_no_restore_failover_execution() -> None:
    r = loaders.load("rollback_dr")
    assert r.get("executes_restore") is False
    assert r.get("executes_failover") is False


def test_rollback_dr_incomplete() -> None:
    assert loaders.rollback_dr_incomplete() is True
