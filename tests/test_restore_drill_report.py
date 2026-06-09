"""Stage 36 -- RestoreDrillReport dataclass + isolated restore DB rules."""

from __future__ import annotations

import json

import pytest

from shared.sdk.backup import RestoreDrillReport, isolated_restore_db_name
from shared.sdk.backup.restore import (
    DEFAULT_RESTORE_DB_PREFIX,
    assert_isolated_restore_db,
)


def _make_report(**overrides):
    base = {
        "drill_id": "drill-20260609",
        "started_at": "2026-06-09T00:00:00Z",
        "finished_at": "2026-06-09T00:00:42Z",
        "backup_id": "bkp-1",
        "backup_artifact_path": "backups/x.dump.enc",
        "manifest_path": "backups/backup_manifest_x.json",
        "restore_db": "aiagents_restore_drill_20260609t000000z",
        "status": "passed",
    }
    base.update(overrides)
    return RestoreDrillReport(**base)


def test_isolated_restore_db_name_matches_prefix():
    name = isolated_restore_db_name(timestamp="20260609T000000Z")
    assert name.startswith(DEFAULT_RESTORE_DB_PREFIX)
    assert name == "aiagents_restore_drill_20260609t000000z"


def test_assert_isolated_restore_db_refuses_primary():
    with pytest.raises(ValueError):
        assert_isolated_restore_db("aiagents")
    with pytest.raises(ValueError):
        assert_isolated_restore_db("postgres")
    with pytest.raises(ValueError):
        assert_isolated_restore_db("template0")
    with pytest.raises(ValueError):
        assert_isolated_restore_db("")


def test_assert_isolated_restore_db_requires_prefix():
    with pytest.raises(ValueError):
        assert_isolated_restore_db("aiagents_restore")
    with pytest.raises(ValueError):
        assert_isolated_restore_db("my_drill_db")


def test_assert_isolated_restore_db_rejects_unsafe_identifiers():
    with pytest.raises(ValueError):
        # Prefix is right but contains an unsafe character.
        assert_isolated_restore_db("aiagents_restore_drill_'$1")
    with pytest.raises(ValueError):
        assert_isolated_restore_db("aiagents_restore_drill_-x")


def test_report_to_dict_serializes():
    r = _make_report()
    payload = json.loads(json.dumps(r.to_dict()))
    assert payload["restore_db"].startswith("aiagents_restore_drill_")
    assert payload["status"] == "passed"
    assert payload["production_executed"] is False
    assert payload["encrypted"] is False  # default; drill flips to True
    # All numeric duration fields exist.
    for key in (
        "backup_duration_seconds",
        "restore_duration_seconds",
        "total_drill_duration_seconds",
        "estimated_rto_seconds",
        "integrity_verify_duration_seconds",
    ):
        assert key in payload


def test_report_carries_audit_integrity_state():
    r = _make_report(
        audit_integrity_status="passed",
        audit_integrity_records_checked=12345,
        audit_integrity_mismatches=0,
    )
    payload = r.to_dict()
    assert payload["audit_integrity_status"] == "passed"
    assert payload["audit_integrity_records_checked"] == 12345
    assert payload["audit_integrity_mismatches"] == 0


def test_report_failure_carries_failure_reason():
    r = _make_report(status="failed", failure_reason="pg_restore_rc=1")
    payload = r.to_dict()
    assert payload["status"] == "failed"
    assert payload["failure_reason"] == "pg_restore_rc=1"
