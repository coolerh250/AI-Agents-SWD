"""Stage 44 -- operations safety serialization fields + endpoints."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys


def _import_ops():
    sys.path.insert(0, "apps/orchestrator/src")
    return importlib.import_module("operations")


def _run(coro):
    return asyncio.run(coro)


def _setup(tmp_path, monkeypatch, *, residue_count=0, serialized=True, lock_status="released"):
    ops = _import_ops()
    residue = tmp_path / "audit_tamper_residue_latest.json"
    residue.write_text(json.dumps({"residue_count": residue_count, "residues": []}), "utf-8")
    lock = tmp_path / "audit_verification_lock_latest.json"
    lock.write_text(json.dumps({"status": lock_status, "enabled": True}), "utf-8")
    reg = tmp_path / "regression_latest_summary.json"
    reg.write_text(
        json.dumps(
            {
                "result_class": "pass_with_documented_gaps",
                "audit_lock_used": True,
                "audit_touching_scripts_serialized": serialized,
            }
        ),
        "utf-8",
    )
    monkeypatch.setattr(ops, "_AUDIT_TAMPER_RESIDUE_LATEST", residue)
    monkeypatch.setattr(ops, "_AUDIT_VERIFICATION_LOCK_LATEST", lock)
    monkeypatch.setattr(ops, "_REGRESSION_SUMMARY_PATH", reg)
    return ops


def test_serialization_summary_healthy(tmp_path, monkeypatch):
    ops = _setup(tmp_path, monkeypatch)
    out = ops._audit_serialization_summary()
    assert out["audit_verification_lock_enabled"] is True
    assert out["audit_verification_lock_last_status"] == "released"
    assert out["audit_touching_regression_serialized"] is True
    assert out["audit_tamper_residue_detected"] is False
    assert out["audit_tamper_residue_count"] == 0
    assert out["audit_tamper_simulation_isolated"] is True
    assert out["latest_full_regression_audit_lock_used"] is True
    assert out["latest_full_regression_audit_touching_serialized"] is True


def test_serialization_summary_unknown_when_absent(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_TAMPER_RESIDUE_LATEST", tmp_path / "a.json")
    monkeypatch.setattr(ops, "_AUDIT_VERIFICATION_LOCK_LATEST", tmp_path / "b.json")
    monkeypatch.setattr(ops, "_REGRESSION_SUMMARY_PATH", tmp_path / "c.json")
    out = ops._audit_serialization_summary()
    assert out["audit_verification_lock_enabled"] is False
    assert out["audit_touching_regression_serialized"] is None
    assert out["audit_tamper_residue_count"] is None


def test_residue_present_breaks_isolation(tmp_path, monkeypatch):
    ops = _setup(tmp_path, monkeypatch, residue_count=2)
    out = ops._audit_serialization_summary()
    assert out["audit_tamper_residue_detected"] is True
    assert out["audit_tamper_residue_count"] == 2
    assert out["audit_tamper_simulation_isolated"] is False


def test_tamper_residue_endpoint(tmp_path, monkeypatch):
    ops = _setup(tmp_path, monkeypatch, residue_count=0)
    body = _run(ops.operations_audit_tamper_residue())
    assert body["available"] is True
    assert body["residue_count"] == 0


def test_verification_lock_endpoint(tmp_path, monkeypatch):
    ops = _setup(tmp_path, monkeypatch)
    body = _run(ops.operations_audit_verification_lock_latest())
    assert body["available"] is True
    assert body["status"] == "released"


def test_endpoints_unknown_when_absent(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_TAMPER_RESIDUE_LATEST", tmp_path / "none.json")
    monkeypatch.setattr(ops, "_AUDIT_VERIFICATION_LOCK_LATEST", tmp_path / "none2.json")
    r = _run(ops.operations_audit_tamper_residue())
    lk = _run(ops.operations_audit_verification_lock_latest())
    assert r["available"] is False and r["status"] == "unknown"
    assert lk["available"] is False and lk["status"] == "unknown"
