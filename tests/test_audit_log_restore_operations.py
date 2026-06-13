"""Stage 43 -- operations endpoints read the restore report (read-only)."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path


def _import_ops():
    sys.path.insert(0, "apps/orchestrator/src")
    return importlib.import_module("operations")


def _run(coro):
    return asyncio.run(coro)


def _write_restore(tmp_path: Path, **over):
    report = {
        "restore_id": "audit_log_restore_20260613_140000",
        "created_at": "2026-06-13T14:00:00+00:00",
        "status": "completed",
        "restore_type": "test_tamper_residue",
        "affected_audit_log_id": "d714f03d-fa46-458b-9f3f-5f7418c923ff",
        "affected_sequence_number": 265288,
        "dry_run": False,
        "approved": True,
        "audit_logs_modified_count": 1,
        "audit_integrity_records_modified_count": 0,
        "before_contains_tamper_marker": True,
        "hash_match_after": True,
        "verifier_after_restore": {"status": "partial"},
        "precheck": {"ok": True, "before_contains_tamper_marker": True},
    }
    report.update(over)
    p = tmp_path / "audit_log_restore_latest.json"
    p.write_text(json.dumps(report), encoding="utf-8")
    return p


def test_restore_summary_no_file(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_LOG_RESTORE_LATEST", tmp_path / "nope.json")
    out = ops._audit_log_restore_summary()
    assert out["audit_log_restore_exception_available"] is False
    assert out["audit_log_restore_last_status"] is None
    assert out["audit_log_restore_integrity_restored"] is False


def test_restore_summary_completed(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_LOG_RESTORE_LATEST", _write_restore(tmp_path))
    out = ops._audit_log_restore_summary()
    assert out["audit_log_restore_exception_available"] is True
    assert out["audit_log_restore_last_status"] == "completed"
    assert out["audit_log_restore_last_audit_log_id"] == (
        "d714f03d-fa46-458b-9f3f-5f7418c923ff"
    )
    assert out["audit_log_restore_integrity_restored"] is True
    assert out["latest_log_restore_type"] == "test_tamper_residue"


def test_restore_summary_dry_run_not_restored(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(
        ops,
        "_AUDIT_LOG_RESTORE_LATEST",
        _write_restore(
            tmp_path, status="approval_required", approved=False, verifier_after_restore=None
        ),
    )
    out = ops._audit_log_restore_summary()
    assert out["audit_log_restore_last_status"] == "approval_required"
    assert out["audit_log_restore_integrity_restored"] is False


def test_log_restore_latest_endpoint(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_LOG_RESTORE_LATEST", _write_restore(tmp_path))
    body = _run(ops.operations_audit_log_restore_latest())
    assert body["available"] is True
    assert body["status"] == "completed"


def test_log_restore_latest_endpoint_missing(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_LOG_RESTORE_LATEST", tmp_path / "nope.json")
    body = _run(ops.operations_audit_log_restore_latest())
    assert body["available"] is False
    assert body["status"] == "unknown"


def test_log_restore_reports_endpoint(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_FORENSICS_DIR", str(tmp_path))
    (tmp_path / "audit_log_restore_20260613_140000.json").write_text(
        json.dumps(
            {
                "restore_id": "audit_log_restore_20260613_140000",
                "created_at": "2026-06-13T14:00:00+00:00",
                "status": "completed",
                "restore_type": "test_tamper_residue",
                "affected_audit_log_id": "d714f03d",
                "affected_sequence_number": 265288,
                "dry_run": False,
                "approved": True,
                "audit_logs_modified_count": 1,
                "audit_integrity_records_modified_count": 0,
            }
        ),
        encoding="utf-8",
    )
    body = _run(ops.operations_audit_log_restore_reports(limit=10))
    assert len(body["reports"]) == 1
    assert body["reports"][0]["audit_integrity_records_modified_count"] == 0
    assert body["reports"][0]["audit_logs_modified_count"] == 1
