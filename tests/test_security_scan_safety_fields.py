"""Step 54.2 -- local scan toolchain /operations/safety fields (SDK level)."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.security_findings import scan_safety_fields

ROOT = Path(__file__).resolve().parents[1]

EXPECT_FALSE = [
    "security_scan_external_upload_enabled",
    "security_scan_network_enabled",
    "security_scan_token_required",
    "security_scan_run_endpoint_enabled",
    "security_scan_reports_committed",
    "security_scan_production_gate_enabled",
    "security_scan_production_ready",
]


def _fields(runtime: Path | None) -> dict:
    return scan_safety_fields(ROOT, runtime)


def test_static_baseline_fields(tmp_path: Path) -> None:
    f = _fields(tmp_path)  # empty runtime dir
    assert f["security_local_scan_baseline_enabled"] is True
    assert f["security_scan_result_normalization_enabled"] is True
    assert f["security_local_secret_scan_configured"] is True
    assert f["security_local_sast_configured"] == "limited_custom_baseline"
    assert f["security_local_dependency_scan_configured"] == "limited_manifest_baseline"


def test_false_fields(tmp_path: Path) -> None:
    f = _fields(tmp_path)
    for k in EXPECT_FALSE:
        assert f[k] is False, k


def test_last_status_not_run_without_runtime(tmp_path: Path) -> None:
    f = _fields(tmp_path)
    for k in (
        "security_secret_scan_last_status",
        "security_sast_last_status",
        "security_dependency_scan_last_status",
    ):
        assert f[k] == "not_run"


def test_does_not_emit_production_executed_count(tmp_path: Path) -> None:
    assert "production_executed_true_count" not in _fields(tmp_path)
