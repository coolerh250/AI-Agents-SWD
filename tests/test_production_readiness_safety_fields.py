"""Step 62 -- production readiness safety fields."""

from __future__ import annotations

from shared.sdk.production_readiness import production_readiness_safety_fields


def test_enabled_flags() -> None:
    sf = production_readiness_safety_fields()
    assert sf["production_readiness_gate_enabled"] is True
    assert sf["production_readiness_gate_report_generated"] is True
    assert sf["production_readiness_operator_review_enabled"] is True


def test_dangerous_toggles_false() -> None:
    sf = production_readiness_safety_fields()
    for k in (
        "production_readiness_gate_production_ready",
        "production_readiness_gate_production_approved",
        "production_readiness_gate_allows_production_action",
        "production_readiness_gate_allows_deploy",
        "production_readiness_gate_allows_sync",
        "production_readiness_gate_allows_merge",
        "production_readiness_gate_allows_image_push",
        "production_readiness_gate_allows_restore",
        "production_readiness_gate_allows_failover",
        "production_readiness_operator_review_is_approval",
        "production_rollout_execution_enabled",
    ):
        assert sf[k] is False, k


def test_executed_counts_zero() -> None:
    sf = production_readiness_safety_fields()
    for k in (
        "production_deployment_executed_count",
        "production_sync_executed_count",
        "production_restore_executed_count",
        "production_failover_executed_count",
    ):
        assert sf[k] == 0, k


def test_counts_present() -> None:
    sf = production_readiness_safety_fields()
    assert sf["production_readiness_missing_prerequisite_count"] == 12
    assert sf["production_readiness_blocker_count"] >= 5
