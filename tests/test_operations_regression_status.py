"""Stage 41 -- /operations/safety must carry verification environment fields."""

import json


from shared.sdk.verification import (
    DECISION_FULL_REGRESSION_PASSED,
    DECISION_VERIFICATION_ENVIRONMENT_CHECKED,
    DECISION_VERIFICATION_DEPENDENCY_READY,
)


# ---- Unit tests for _verification_environment_summary() --------------------

def _import_ops():
    import sys

    sys.path.insert(0, "apps/orchestrator/src")
    import importlib

    ops = importlib.import_module("operations")
    return ops


def test_verification_summary_no_file(tmp_path, monkeypatch):
    ops = _import_ops()
    monkeypatch.setattr(ops, "_REGRESSION_SUMMARY_PATH", tmp_path / "nonexistent.json")
    monkeypatch.chdir(tmp_path)
    result = ops._verification_environment_summary()
    assert result["verification_environment_ready"] is False
    assert result["latest_full_regression_status"] == "unknown"
    assert result["verification_host_dependency_caveat_closed"] is False
    assert result["verification_dependency_failures"] == []


def test_verification_summary_with_pass_report(tmp_path, monkeypatch):
    ops = _import_ops()
    summary = {
        "completed_at": "2026-06-13T12:00:00Z",
        "result_class": "pass",
        "environment_ready": True,
        "host_dependency_caveat_closed": True,
        "report_path": "source/regression-reports/regression_20260613_120000.json",
        "dependency_failures": [],
        "known_gaps": ["encryption_no_key"],
        "caveats": [],
        "summary": {"total": 21, "pass": 21, "fail": 0},
    }
    summary_file = tmp_path / "regression_latest_summary.json"
    summary_file.write_text(json.dumps(summary))
    monkeypatch.setattr(ops, "_REGRESSION_SUMMARY_PATH", summary_file)
    monkeypatch.chdir(tmp_path)

    result = ops._verification_environment_summary()
    assert result["verification_environment_ready"] is True
    assert result["latest_full_regression_status"] == "pass"
    assert result["verification_host_dependency_caveat_closed"] is True
    assert result["verification_known_gaps"] == ["encryption_no_key"]


def test_verification_summary_with_gaps_report(tmp_path, monkeypatch):
    ops = _import_ops()
    summary = {
        "completed_at": "2026-06-13T12:00:00Z",
        "result_class": "pass_with_documented_gaps",
        "environment_ready": True,
        "host_dependency_caveat_closed": True,
        "report_path": "source/regression-reports/regression_20260613.json",
        "dependency_failures": [],
        "known_gaps": ["encryption_no_key", "storage_not_off_host"],
        "caveats": [],
        "summary": {"total": 21, "pass": 20, "fail": 0},
    }
    summary_file = tmp_path / "regression_latest_summary.json"
    summary_file.write_text(json.dumps(summary))
    monkeypatch.setattr(ops, "_REGRESSION_SUMMARY_PATH", summary_file)
    monkeypatch.chdir(tmp_path)

    result = ops._verification_environment_summary()
    assert result["latest_full_regression_status"] == "pass_with_documented_gaps"
    assert "encryption_no_key" in result["verification_known_gaps"]


def test_verification_summary_corrupted_json(tmp_path, monkeypatch):
    ops = _import_ops()
    summary_file = tmp_path / "regression_latest_summary.json"
    summary_file.write_text("{not valid json")
    monkeypatch.setattr(ops, "_REGRESSION_SUMMARY_PATH", summary_file)
    monkeypatch.chdir(tmp_path)

    result = ops._verification_environment_summary()
    assert result["latest_full_regression_status"] == "error_reading_report"
    assert result["verification_environment_ready"] is False


# ---- Check audit/notification constants are defined ------------------------

def test_verification_audit_event_constants_defined():
    assert DECISION_VERIFICATION_ENVIRONMENT_CHECKED == "verification_environment_checked"
    assert DECISION_VERIFICATION_DEPENDENCY_READY == "verification_dependency_ready"
    assert DECISION_FULL_REGRESSION_PASSED == "full_regression_passed"


def test_verification_safety_fields_complete():
    required_fields = {
        "verification_environment_ready",
        "verification_runner_available",
        "latest_full_regression_status",
        "latest_full_regression_at",
        "latest_full_regression_report_path",
        "verification_dependency_failures",
        "verification_known_gaps",
        "verification_environment_caveats",
        "verification_host_dependency_caveat_closed",
    }
    ops = _import_ops()
    result = ops._verification_environment_summary()
    assert required_fields <= set(result.keys()), (
        f"Missing keys: {required_fields - set(result.keys())}"
    )
