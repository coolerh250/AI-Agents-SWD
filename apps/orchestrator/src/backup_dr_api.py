"""Stage 51 -- Backup / DR readiness read-only operations API.

Ten read-only GET endpoints exposing the backup / DR readiness baseline
(encryption config, latest backup, manifest, off-host transfer, restore drill,
schedule, retention, migration rollback catalog, readiness evaluation, gap
closure report). All reads are resilient: a failing store degrades to a safe
default. Responses carry statuses / ids / labels / counts only -- never a raw
key, secret, DB password, or chain-of-thought.

An optional controlled POST (``/operations/backup-dr/run-verification``) is
scaffolded but DISABLED by default (``ENABLE_BACKUP_DR_RUN_VERIFICATION=false``)
-- it returns ``action_disabled`` and performs no backup / restore / cloud
write / schedule enablement.
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from shared.sdk.backup_dr import BackupDrStore

router = APIRouter(prefix="/operations/backup-dr", tags=["backup-dr"])


def _store() -> BackupDrStore:
    return BackupDrStore()


def _flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


async def _safe(coro, default):
    try:
        return await coro
    except Exception:
        return default


@router.get("/encryption")
async def encryption() -> dict:
    data = await _safe(_store().get_latest_encryption_config(), None)
    return {"encryption": data, "raw_key_persisted": False}


@router.get("/latest-backup")
async def latest_backup() -> dict:
    data = await _safe(_store().get_latest_backup_run(), None)
    return {"backup": data}


@router.get("/manifests/latest")
async def latest_manifest() -> dict:
    data = await _safe(_store().get_latest_manifest(), None)
    return {"manifest": data}


@router.get("/offhost/latest")
async def latest_offhost() -> dict:
    data = await _safe(_store().get_latest_transfer(), None)
    return {"offhost_transfer": data}


@router.get("/restore-drill/latest")
async def latest_restore_drill() -> dict:
    data = await _safe(_store().get_latest_restore_drill(), None)
    return {"restore_drill": data}


@router.get("/schedule")
async def schedule() -> dict:
    data = await _safe(_store().get_latest_schedule(), None)
    return {"schedule": data, "production_schedule_enabled": False}


@router.get("/retention")
async def retention() -> dict:
    data = await _safe(_store().get_latest_retention(), None)
    return {"retention": data, "delete_enabled": False}


@router.get("/migration-rollback-catalog")
async def migration_rollback_catalog() -> dict:
    entries = await _safe(_store().get_migration_catalog(), [])
    unknown = sum(1 for e in entries if e.get("reversibility") == "unknown")
    return {
        "entries": entries,
        "total": len(entries),
        "unknown_count": unknown,
        "complete": bool(entries) and unknown == 0,
    }


@router.get("/readiness/latest")
async def readiness_latest() -> dict:
    data = await _safe(_store().get_latest_readiness(), None)
    if data is None:
        return {
            "readiness": None,
            "status": "passed_with_gaps",
            "remaining_gaps": [
                "encryption_no_key",
                "storage_not_off_host",
                "schedule_dry_run_only",
                "migration_down_gaps",
            ],
        }
    return {
        "readiness": {k: v for k, v in data.items() if k != "metadata"},
        "status": data.get("status"),
        "remaining_gaps": data.get("remaining_gaps", []),
        "limitations": data.get("limitations", []),
    }


@router.get("/report/latest")
async def report_latest() -> dict:
    data = await _safe(_store().get_latest_report(), None)
    return {"report": data}


@router.post("/run-verification")
async def run_verification() -> dict:
    """Controlled, DISABLED-by-default. Never runs a backup / restore here."""
    if not _flag("ENABLE_BACKUP_DR_RUN_VERIFICATION", False):
        return {
            "status": "action_disabled",
            "reason": "policy_blocked",
            "production_executed": False,
            "real_cloud_write_performed": False,
            "hint": "drive scripts/verify_backup_dr_gap_closure.sh instead",
        }
    # Even when the flag is on, this endpoint does NOT perform a real backup /
    # restore -- it only reports the latest persisted readiness evaluation.
    data = await _safe(_store().get_latest_readiness(), None)
    return {"status": "reported", "readiness": data, "production_executed": False}


__all__ = ["router"]
