"""Stage 42 -- operations endpoints read forensic/repair reports (read-only)."""

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


def _write_forensic(tmp_path: Path, **over):
    report = {
        "report_id": "audit_forensic_20260613_120000",
        "created_at": "2026-06-13T12:00:00+00:00",
        "first_failed_sequence": 265288,
        "failed_records_count": 1,
        "root_cause_classification": "test_tamper_not_restored",
        "repair_allowed": True,
        "repair_risk": "low",
        "production_executed": False,
    }
    report.update(over)
    p = tmp_path / "audit_forensic_latest.json"
    p.write_text(json.dumps(report), encoding="utf-8")
    return p


def _write_repair(tmp_path: Path, **over):
    report = {
        "repair_id": "audit_repair_20260613_130000",
        "status": "approval_required",
        "root_cause": "test_tamper_not_restored",
        "dry_run": True,
        "approved": False,
        "audit_logs_modified": False,
        "changed_records_count": 0,
        "verification_after_repair": None,
    }
    report.update(over)
    p = tmp_path / "audit_repair_latest.json"
    p.write_text(json.dumps(report), encoding="utf-8")
    return p


def test_forensic_summary_no_file(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_FORENSIC_LATEST", tmp_path / "nope.json")
    monkeypatch.setattr(ops, "_AUDIT_REPAIR_LATEST", tmp_path / "nope2.json")
    out = ops._audit_forensic_summary()
    assert out["audit_chain_forensics_available"] is False
    assert out["audit_chain_first_failed_sequence"] is None
    assert out["audit_chain_repair_allowed"] is None
    assert out["audit_chain_integrity_restored"] is False


def test_forensic_summary_with_reports(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_FORENSIC_LATEST", _write_forensic(tmp_path))
    monkeypatch.setattr(ops, "_AUDIT_REPAIR_LATEST", _write_repair(tmp_path))
    out = ops._audit_forensic_summary()
    assert out["audit_chain_forensics_available"] is True
    assert out["audit_chain_first_failed_sequence"] == 265288
    assert out["latest_forensic_root_cause"] == "test_tamper_not_restored"
    assert out["audit_chain_root_cause_classified"] is True
    assert out["audit_chain_repair_required"] is True
    assert out["audit_chain_repair_allowed"] is True
    assert out["audit_chain_repair_last_status"] == "approval_required"
    assert out["audit_chain_integrity_restored"] is False


def test_integrity_restored_true_after_completed_repair(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_FORENSIC_LATEST", _write_forensic(tmp_path))
    monkeypatch.setattr(
        ops,
        "_AUDIT_REPAIR_LATEST",
        _write_repair(
            tmp_path,
            status="completed",
            approved=True,
            dry_run=False,
            verification_after_repair={"passed": True},
        ),
    )
    out = ops._audit_forensic_summary()
    assert out["audit_chain_integrity_restored"] is True


def test_forensics_latest_endpoint(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_FORENSIC_LATEST", _write_forensic(tmp_path))
    body = _run(ops.operations_audit_forensics_latest())
    assert body["available"] is True
    assert body["root_cause_classification"] == "test_tamper_not_restored"


def test_forensics_latest_endpoint_missing(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_FORENSIC_LATEST", tmp_path / "nope.json")
    body = _run(ops.operations_audit_forensics_latest())
    assert body["available"] is False
    assert body["status"] == "unknown"


def test_repair_latest_endpoint(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_REPAIR_LATEST", _write_repair(tmp_path))
    body = _run(ops.operations_audit_repair_latest())
    assert body["available"] is True
    assert body["status"] == "approval_required"


def test_reports_listing_endpoints(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_FORENSICS_DIR", str(tmp_path))
    # write a couple of historical reports
    (tmp_path / "audit_forensic_20260613_120000.json").write_text(
        json.dumps(
            {
                "report_id": "audit_forensic_20260613_120000",
                "created_at": "2026-06-13T12:00:00+00:00",
                "root_cause_classification": "test_tamper_not_restored",
                "first_failed_sequence": 265288,
                "failed_records_count": 1,
                "repair_allowed": True,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "audit_repair_20260613_130000.json").write_text(
        json.dumps(
            {
                "repair_id": "audit_repair_20260613_130000",
                "started_at": "2026-06-13T13:00:00+00:00",
                "status": "approval_required",
                "root_cause": "test_tamper_not_restored",
                "dry_run": True,
                "approved": False,
                "audit_logs_modified": False,
                "changed_records_count": 0,
            }
        ),
        encoding="utf-8",
    )
    f = _run(ops.operations_audit_forensics_reports(limit=10))
    r = _run(ops.operations_audit_repair_reports(limit=10))
    assert len(f["reports"]) == 1
    assert f["reports"][0]["report_id"] == "audit_forensic_20260613_120000"
    assert len(r["reports"]) == 1
    assert r["reports"][0]["audit_logs_modified"] is False
