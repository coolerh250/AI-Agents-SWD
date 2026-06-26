"""Step 56 -- non-production ArgoCD never claims production readiness."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.argocd_sync import posture

ROOT = Path(__file__).resolve().parents[1]
GITOPS = ROOT / "infra" / "gitops"


def test_committed_descriptors_production_ready_false() -> None:
    for rel, key in (
        ("nonproduction-argocd-manual-sync-summary.yaml", "nonProductionArgocdManualSyncSummary"),
        ("nonproduction-argocd-manual-sync-plan.yaml", "nonProductionArgocdManualSyncPlan"),
        ("nonproduction-argocd-install-boundary.yaml", "nonProductionArgocdInstallBoundary"),
    ):
        data = (yaml.safe_load((GITOPS / rel).read_text(encoding="utf-8")) or {})[key]
        assert data["productionReady"] is False


def test_posture_views_production_not_ready() -> None:
    for view in (
        posture.preflight_view(ROOT),
        posture.install_view(ROOT),
        posture.application_view(ROOT),
        posture.readiness_view(ROOT),
    ):
        assert view["productionReady"] is False


def test_no_production_gitops_ready_claim() -> None:
    blob = "\n".join(p.read_text(encoding="utf-8") for p in GITOPS.rglob("*.yaml")).lower()
    assert "production gitops ready" not in blob
    assert "production argocd ready" not in blob
    assert "auto-sync ready" not in blob
