"""Stage 51 -- retention dry-run never deletes."""

from __future__ import annotations

from shared.sdk.backup_dr.retention_policy import (
    build_retention_policy,
    compute_retention_dry_run,
    retention_configured,
)


def test_policy_dry_run_only() -> None:
    p = build_retention_policy()
    assert p.delete_enabled is False
    assert p.dry_run_only is True
    assert retention_configured(p) is True


def test_dry_run_reports_candidates_no_delete() -> None:
    p = build_retention_policy(keep_last=3)
    backups = [{"backup_key": f"b{i}", "created_at": f"2026-06-{i:02d}"} for i in range(1, 11)]
    report = compute_retention_dry_run(p, backups)
    assert report["actual_delete_count"] == 0
    assert report["delete_enabled"] is False
    assert report["candidate_delete_count"] == 7
    assert report["total_backups"] == 10


def test_dry_run_empty() -> None:
    report = compute_retention_dry_run(build_retention_policy(), [])
    assert report["candidate_delete_count"] == 0
    assert report["actual_delete_count"] == 0
