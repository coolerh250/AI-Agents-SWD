"""Step 54.2 -- local scan baseline is never production-ready; baselines preserved."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.security_findings import readiness_view, scan_safety_fields, status_view

ROOT = Path(__file__).resolve().parents[1]


def test_status_and_safety_not_production_ready(tmp_path: Path) -> None:
    assert status_view(ROOT, tmp_path)["productionReady"] is False
    assert scan_safety_fields(ROOT, tmp_path)["security_scan_production_ready"] is False


def test_readiness_not_ready_without_runtime(tmp_path: Path) -> None:
    r = readiness_view(ROOT, tmp_path)
    assert r["productionReady"] is False
    assert r["productionGateEnabled"] is False
    assert r["blockers"]


def test_prior_stage_markers_artifacts_preserved() -> None:
    # Step 54.1 + 53 + 52 + 51 committed summaries remain present + non-production.
    sec = yaml.safe_load(
        (ROOT / "infra" / "security" / "security-foundation-summary.yaml").read_text("utf-8")
    )
    assert sec["securityFoundation"]["productionReady"] is False
    assert sec["securityFoundation"]["status"] == "modeled_not_enforced"
    for p in (
        "infra/kubernetes/runtime-baseline-summary.yaml",
        "infra/identity/identity-posture-summary.yaml",
        "infra/secrets/secret-foundation-summary.yaml",
    ):
        assert (ROOT / p).is_file()


def test_scan_status_model_production_gate_disabled() -> None:
    model = yaml.safe_load(
        (ROOT / "infra" / "security" / "security-scan-status-summary-model.yaml").read_text("utf-8")
    )
    assert model["baselineConfiguration"]["productionGateEnabled"] is False
    assert model["baselineConfiguration"]["productionReady"] is False
