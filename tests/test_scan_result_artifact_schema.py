"""Step 54.2 -- scan result artifact schema + ScanResult invariants."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.security_findings import ScanResult

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "scan-result-artifact-schema.yaml"


def test_schema_file_and_status_enum() -> None:
    d = yaml.safe_load(F.read_text(encoding="utf-8")) or {}
    assert "scanResult" in d
    assert set(d["statusEnum"]) == {
        "passed",
        "completed_with_findings",
        "tool_unavailable",
        "config_error",
        "failed",
    }
    assert "tool_unavailable_is_not_passed" in d["invariants"]


def test_scanresult_never_production_ready() -> None:
    r = ScanResult(scan_type="secret", scanner="x", status="passed", production_ready=True)
    assert r.production_ready is False


def test_tool_unavailable_is_distinct_status() -> None:
    r = ScanResult(scan_type="sast", scanner="bandit", status="tool_unavailable")
    assert r.status == "tool_unavailable"
    assert r.status != "passed"
