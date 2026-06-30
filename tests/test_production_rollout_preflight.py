"""Step 62 -- production rollout preflight."""

from __future__ import annotations

from shared.sdk.production_readiness import preflight


def test_rollout_execution_disabled() -> None:
    assert preflight.rollout_execution_enabled() is False


def test_rollout_not_started() -> None:
    assert preflight.rollout_status() in ("not_started", "blocked", "planning_only")


def test_no_check_claims_production_ready() -> None:
    for c in preflight.load_checks():
        assert c.get("status") not in ("production_ready", "ready_production", "approved")
