"""Step 61 -- non-production restore validation."""

from __future__ import annotations

from shared.sdk.backup_restore_dr import build_restore_validation_result


def test_production_target_blocked() -> None:
    r = build_restore_validation_result(
        restore_plan_id="p",
        target_environment="production",
        validation_types=["schema_validation"],
    )
    assert r.status == "blocked"


def test_passing_validation_never_touches_active_runtime() -> None:
    r = build_restore_validation_result(
        restore_plan_id="p",
        target_environment="nonprod",
        validation_types=["manifest_integrity_check", "redaction_validation"],
        checks=[{"name": "x", "passed": True}],
    )
    d = r.to_dict()
    assert d["status"] == "passed"
    assert d["active_database_overwritten"] is False
    assert d["active_redis_overwritten"] is False
    assert d["argocd_sync_performed"] is False
    assert d["kind_cluster_mutated"] is False
    assert d["production_executed"] is False


def test_failure_not_hidden() -> None:
    r = build_restore_validation_result(
        restore_plan_id="p",
        target_environment="nonprod",
        validation_types=["schema_validation"],
        checks=[{"name": "x", "passed": False}],
    )
    assert r.status == "failed"


def test_unknown_validation_type_blocked() -> None:
    r = build_restore_validation_result(
        restore_plan_id="p", target_environment="nonprod", validation_types=["delete_prod"]
    )
    assert r.status == "blocked"
