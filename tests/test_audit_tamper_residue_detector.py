"""Stage 44 -- tamper residue detector script + operations summary."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

DETECTOR = Path("scripts/detect_audit_tamper_residue.sh")


def _import_ops():
    sys.path.insert(0, "apps/orchestrator/src")
    return importlib.import_module("operations")


def test_detector_script_exists_and_readonly():
    assert DETECTOR.is_file()
    text = DETECTOR.read_text(encoding="utf-8")
    # Read-only: it must never UPDATE/DELETE audit tables.
    assert "UPDATE audit_logs" not in text
    assert "DELETE FROM audit" not in text


def test_detector_has_pass_fail_markers():
    text = DETECTOR.read_text(encoding="utf-8")
    assert "AUDIT_TAMPER_RESIDUE_DETECTOR: PASS" in text
    assert "AUDIT_TAMPER_RESIDUE_DETECTOR: FAIL" in text


def test_detector_points_to_restore_exception_not_auto_fix():
    text = DETECTOR.read_text(encoding="utf-8")
    assert "controlled audit_log restore exception" in text
    assert "Do not manually update DB" in text


def test_detector_marker_is_tamper_simulation():
    text = DETECTOR.read_text(encoding="utf-8")
    assert "[TAMPER-SIMULATION]" in text


def test_operations_summary_no_residue(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_AUDIT_TAMPER_RESIDUE_LATEST", tmp_path / "none.json")
    monkeypatch.setattr(ops, "_AUDIT_VERIFICATION_LOCK_LATEST", tmp_path / "lock.json")
    monkeypatch.setattr(ops, "_REGRESSION_SUMMARY_PATH", tmp_path / "reg.json")
    out = ops._audit_serialization_summary()
    assert out["audit_tamper_residue_count"] is None
    assert out["audit_tamper_residue_detected"] is None


def test_operations_summary_residue_zero(tmp_path, monkeypatch):
    ops = _import_ops()
    p = tmp_path / "audit_tamper_residue_latest.json"
    p.write_text(json.dumps({"residue_count": 0, "residues": []}), encoding="utf-8")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"status": "released", "enabled": True}), encoding="utf-8")
    monkeypatch.setattr(ops, "_AUDIT_TAMPER_RESIDUE_LATEST", p)
    monkeypatch.setattr(ops, "_AUDIT_VERIFICATION_LOCK_LATEST", lock)
    monkeypatch.setattr(ops, "_REGRESSION_SUMMARY_PATH", tmp_path / "reg.json")
    out = ops._audit_serialization_summary()
    assert out["audit_tamper_residue_count"] == 0
    assert out["audit_tamper_residue_detected"] is False
    assert out["audit_tamper_simulation_isolated"] is True


def test_operations_summary_residue_present(tmp_path, monkeypatch):
    ops = _import_ops()
    p = tmp_path / "audit_tamper_residue_latest.json"
    p.write_text(
        json.dumps(
            {
                "residue_count": 1,
                "residues": [{"audit_log_id": "x", "decision_type": "d", "task_id": "smoke"}],
            }
        ),
        encoding="utf-8",
    )
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"status": "released", "enabled": True}), encoding="utf-8")
    monkeypatch.setattr(ops, "_AUDIT_TAMPER_RESIDUE_LATEST", p)
    monkeypatch.setattr(ops, "_AUDIT_VERIFICATION_LOCK_LATEST", lock)
    monkeypatch.setattr(ops, "_REGRESSION_SUMMARY_PATH", tmp_path / "reg.json")
    out = ops._audit_serialization_summary()
    assert out["audit_tamper_residue_count"] == 1
    assert out["audit_tamper_residue_detected"] is True
    assert out["audit_tamper_simulation_isolated"] is False
