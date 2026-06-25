"""Step 54.4 -- runtime / Kubernetes / GitOps threat model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"


def _model() -> dict:
    data = (
        yaml.safe_load((SEC / "runtime-gitops-threat-model.yaml").read_text(encoding="utf-8")) or {}
    )
    return data["runtimeGitopsThreatModel"]


def test_not_production_ready() -> None:
    assert _model()["productionReady"] is False


def test_required_scenarios_covered() -> None:
    scenarios = {t["scenario"] for t in _model()["threats"]}
    for required in (
        "kubernetes_manifest_drift",
        "argocd_sync_misuse",
        "helm_values_secret_leakage",
        "privilege_escalation",
        "serviceaccount_token_misuse",
        "production_placeholder_accidentally_deployed",
    ):
        assert required in scenarios


def test_static_baseline_caveat_references_step_55_and_56() -> None:
    caveat = " ".join(_model()["staticBaselineCaveat"]).lower()
    assert "step 55" in caveat
    assert "step 56" in caveat


def test_required_future_steps_include_cluster_smoke() -> None:
    assert "step_55_non_production_cluster_smoke" in _model()["requiredFutureSteps"]
