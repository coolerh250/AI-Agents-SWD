"""Step 54.4 -- nothing in the integrated layer claims production readiness."""

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.generate_release_risk_summary import build_release_risk_summary
from scripts.generate_security_evidence_package import build_evidence_package
from scripts.generate_security_readiness_report import build_security_readiness_report
from shared.sdk.security_integrated import integrated_safety_fields, step54_status_view

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"

MODEL_FILES = [
    ("threat-model-baseline.yaml", "threatModel"),
    ("agent-threat-model.yaml", "agentThreatModel"),
    ("supply-chain-threat-model.yaml", "supplyChainThreatModel"),
    ("runtime-gitops-threat-model.yaml", "runtimeGitopsThreatModel"),
    ("release-risk-summary-model.yaml", "releaseRiskSummaryModel"),
    ("security-evidence-package-schema.yaml", "securityEvidencePackageSchema"),
]


def test_all_models_production_ready_false() -> None:
    for name, key in MODEL_FILES:
        data = yaml.safe_load((SEC / name).read_text(encoding="utf-8")) or {}
        assert data[key]["productionReady"] is False, name


def test_generators_production_ready_false() -> None:
    assert build_evidence_package()["productionReady"] is False
    risk = build_release_risk_summary()
    assert risk["productionReady"] is False
    assert risk["status"] not in ("production_ready", "production_approved")
    assert build_security_readiness_report()["productionReady"] is False


def test_safety_and_status_not_production_ready() -> None:
    f = integrated_safety_fields(ROOT)
    assert f["security_step54_production_ready"] is False
    assert f["security_release_gate_enabled"] is False
    assert step54_status_view()["productionReady"] is False
