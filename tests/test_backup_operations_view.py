"""Stage 36 -- structural tests for the /operations/backup endpoints + safety fields."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_operations() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py").read_text(
        encoding="utf-8"
    )


def test_backup_routes_registered():
    src = _read_operations()
    for path in (
        '@router.get("/backup/status")',
        '@router.get("/backup/reports")',
        '@router.get("/backup/reports/latest")',
    ):
        assert path in src, f"missing route: {path}"


def test_safety_carries_stage36_backup_fields():
    src = _read_operations()
    for field in (
        '"backup_encryption_enabled"',
        '"backup_encryption_production_ready"',
        '"backup_off_host_enabled"',
        '"backup_storage_mode"',
        '"latest_restore_drill_status"',
        '"backup_production_ready"',
        '"backup_gaps"',
        '"migration_down_scripts_complete"',
        '"dr_runbook_present"',
    ):
        assert field in src, f"missing safety field: {field}"


def test_summary_carries_backup_block():
    src = _read_operations()
    assert '"backup_summary"' in src
    # The compact summary helper has the right contract.
    assert "def _backup_compact_summary" in src
    assert '"latest_backup_at"' in src
    assert '"rto_seconds"' in src
    assert '"rpo_seconds"' in src


def test_status_endpoint_pins_production_executed_false():
    src = _read_operations()
    block_start = src.index("async def operations_backup_status")
    block_end = src.index("@router.get(", block_start + 1)
    block = src[block_start:block_end]
    assert '"production_executed": False' in block


def test_status_endpoint_returns_no_secret_keys():
    src = _read_operations()
    block_start = src.index("async def operations_backup_status")
    block_end = src.index("@router.get(", block_start + 1)
    block = src[block_start:block_end]
    for forbidden in ("BACKUP_ENCRYPTION_KEY", "BACKUP_STORAGE_SECRET_ACCESS_KEY"):
        # The endpoint must never reference these env vars by value.
        assert f'env.get("{forbidden}")' not in block
        assert f'os.environ["{forbidden}"]' not in block
