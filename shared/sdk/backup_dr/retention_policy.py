"""Stage 51 -- backup retention policy + dry-run cleanup.

Builds a retention policy and computes a DRY-RUN cleanup report. Deletion is
NEVER performed: ``delete_enabled`` stays false and ``actual_delete_count`` is
always 0. The dry-run only reports which artifacts a future enabled run *would*
delete.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from shared.sdk.backup_dr.models import BackupRetentionPolicy


def build_retention_policy(
    *,
    policy_key: str = "backup-dr-default-retention",
    keep_last: int = 7,
    keep_daily: int = 7,
    keep_weekly: int = 4,
    keep_monthly: int = 3,
) -> BackupRetentionPolicy:
    return BackupRetentionPolicy(
        policy_key=policy_key,
        keep_last=keep_last,
        keep_daily=keep_daily,
        keep_weekly=keep_weekly,
        keep_monthly=keep_monthly,
        delete_enabled=False,
        dry_run_only=True,
        metadata={"dry_run_only": True},
    )


def compute_retention_dry_run(
    policy: BackupRetentionPolicy,
    backups: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute a dry-run retention report.

    ``backups`` is a list of dicts (most-recent first or with ``created_at``).
    Candidates beyond ``keep_last`` are reported as delete-candidates, but
    nothing is deleted (delete_enabled is false).
    """
    items = list(backups or [])
    # Sort newest-first when created_at is present.
    items.sort(key=lambda b: str(b.get("created_at") or ""), reverse=True)
    keep = max(0, int(policy.keep_last))
    candidates = items[keep:]
    candidate_keys = [
        str(b.get("backup_key") or b.get("id") or i) for i, b in enumerate(candidates)
    ]

    return {
        "policy_key": policy.policy_key,
        "status": "completed",
        "total_backups": len(items),
        "keep_last": keep,
        "candidate_delete_count": len(candidates),
        "actual_delete_count": 0,
        "delete_enabled": False,
        "dry_run_only": True,
        "candidate_keys": candidate_keys,
    }


def retention_configured(policy: BackupRetentionPolicy) -> bool:
    return policy.dry_run_only and not policy.delete_enabled


__all__ = [
    "build_retention_policy",
    "compute_retention_dry_run",
    "retention_configured",
]
