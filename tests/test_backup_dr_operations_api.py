"""Stage 51 -- backup / DR read-only operations API."""

from __future__ import annotations

import backup_dr_api
import pytest


class _FakeStore:
    async def get_latest_encryption_config(self):
        return {
            "key_source": "key_file",
            "key_id": "abc",
            "status": "configured",
            "raw_key_persisted": False,
        }

    async def get_latest_backup_run(self):
        return {
            "backup_key": "b",
            "environment": "test",
            "encrypted": True,
            "production_executed": False,
        }

    async def get_latest_manifest(self):
        return {"encryption_key_id": "abc", "manifest_json": {}}

    async def get_latest_transfer(self):
        return {
            "status": "verified",
            "readback_verified": True,
            "real_cloud_write_performed": False,
        }

    async def get_latest_restore_drill(self):
        return {"status": "verified", "production_restore_performed": False, "rto_seconds": 3.0}

    async def get_latest_schedule(self):
        return {
            "schedule_type": "cron_spec",
            "dry_run_validated": True,
            "production_schedule_enabled": False,
        }

    async def get_latest_retention(self):
        return {"policy_key": "p", "delete_enabled": False, "actual_delete_count": 0}

    async def get_migration_catalog(self):
        return [{"migration_file": "001.sql", "reversibility": "forward_only"}]

    async def get_latest_readiness(self):
        return {
            "status": "passed_with_non_production_limitations",
            "remaining_gaps": [],
            "limitations": ["x"],
            "metadata": {},
        }

    async def get_latest_report(self):
        return {"readiness": {"status": "passed_with_non_production_limitations"}}


@pytest.fixture(autouse=True)
def _wire(monkeypatch):
    monkeypatch.setattr(backup_dr_api, "_store", lambda: _FakeStore())


async def test_readiness_latest_closed() -> None:
    d = await backup_dr_api.readiness_latest()
    assert d["status"] == "passed_with_non_production_limitations"
    assert d["remaining_gaps"] == []


async def test_encryption_no_raw_key() -> None:
    d = await backup_dr_api.encryption()
    assert d["raw_key_persisted"] is False
    assert "raw_key" not in str(d).lower().replace("raw_key_persisted", "")


async def test_offhost_and_restore() -> None:
    off = await backup_dr_api.latest_offhost()
    assert off["offhost_transfer"]["real_cloud_write_performed"] is False
    rd = await backup_dr_api.latest_restore_drill()
    assert rd["restore_drill"]["production_restore_performed"] is False


async def test_migration_catalog_endpoint() -> None:
    d = await backup_dr_api.migration_rollback_catalog()
    assert d["unknown_count"] == 0
    assert d["complete"] is True


async def test_run_verification_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_BACKUP_DR_RUN_VERIFICATION", raising=False)
    d = await backup_dr_api.run_verification()
    assert d["status"] == "action_disabled"
    assert d["production_executed"] is False


async def test_readiness_default_when_no_data(monkeypatch) -> None:
    class _Empty:
        async def get_latest_readiness(self):
            return None

    monkeypatch.setattr(backup_dr_api, "_store", lambda: _Empty())
    d = await backup_dr_api.readiness_latest()
    assert d["status"] == "passed_with_gaps"
    assert "encryption_no_key" in d["remaining_gaps"]
