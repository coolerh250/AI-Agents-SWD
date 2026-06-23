"""Step 54.2 -- scan status summary model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "security-scan-status-summary-model.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8")) or {}


def test_status_enum() -> None:
    assert {
        "not_configured",
        "tool_unavailable",
        "not_run",
        "completed_no_findings",
        "completed_with_findings",
        "failed",
    } <= set(_d()["statusEnum"])


def test_baseline_configuration() -> None:
    bc = _d()["baselineConfiguration"]
    assert bc["localScanBaselineEnabled"] is True
    assert bc["externalUploadEnabled"] is False
    assert bc["productionGateEnabled"] is False
    assert bc["productionReady"] is False
    assert bc["secretScanConfigured"] == "configured"
    assert bc["sastConfigured"] == "limited_custom_baseline"
    assert bc["dependencyScanConfigured"] == "limited_manifest_baseline"


def test_production_readiness_rule() -> None:
    rule = _d()["productionReadinessRule"]
    assert rule["anyNotConfigured"] == "not_ready"
    assert rule["anyToolUnavailable"] == "not_ready"
    assert rule["anyCritical"] == "fail"
    assert rule["productionGateEnabled"] is False
