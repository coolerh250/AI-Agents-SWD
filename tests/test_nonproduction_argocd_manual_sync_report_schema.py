"""Step 56 -- non-production ArgoCD manual-sync summary + report schema."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "infra" / "gitops" / "nonproduction-argocd-manual-sync-summary.yaml"
GENERATOR = ROOT / "scripts" / "run_nonproduction_argocd_manual_sync_report.py"


def _s() -> dict:
    return (yaml.safe_load(SUMMARY.read_text(encoding="utf-8")) or {})[
        "nonProductionArgocdManualSyncSummary"
    ]


def test_summary_records_manual_sync_non_production() -> None:
    s = _s()
    assert s["productionReady"] is False
    assert s["manualSyncPerformed"] is True
    assert s["manualSyncSucceeded"] is True
    assert s["autoSyncEnabled"] is False
    assert s["pruneEnabled"] is False
    assert s["selfHealEnabled"] is False
    assert s["destinationNamespace"] == "aiagents-smoke-dev"


def test_summary_safety_invariants_false() -> None:
    s = _s()
    for flag in (
        "productionNamespaceTouched",
        "publicIngressEnabled",
        "loadBalancerEnabled",
        "argocdProductionSyncPerformed",
        "kubernetesProductionDeployPerformed",
        "externalRepoCredentialUsed",
        "productionExecuted",
        "argocdServerExposed",
    ):
        assert s[flag] is False, flag


def test_report_generator_is_read_only_redacted() -> None:
    src = GENERATOR.read_text(encoding="utf-8")
    assert 'MARKER = "NONPROD_ARGOCD_SYNC_REPORT_RUN"' in src
    assert '"productionExecuted": False' in src
    assert '"argocdProductionSyncPerformed": False' in src
    # No write/sync/apply against the cluster from the report generator.
    assert "patch" not in src.lower()
    assert "apply" not in src.lower()
