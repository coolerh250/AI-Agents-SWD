"""Step 56 -- non-production ArgoCD safety fields (from the committed summary)."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.argocd_sync import nonprod_argocd_safety_fields

ROOT = Path(__file__).resolve().parents[1]


def test_safety_fields_non_production() -> None:
    f = nonprod_argocd_safety_fields(ROOT)
    assert f["nonprod_argocd_enabled"] is True
    assert f["nonprod_argocd_namespace"] == "argocd-nonprod"
    assert f["nonprod_argocd_installed"] is True
    assert f["nonprod_argocd_project_created"] is True
    assert f["nonprod_argocd_application_created"] is True
    assert f["nonprod_argocd_manual_sync_performed"] is True
    assert f["nonprod_argocd_manual_sync_succeeded"] is True
    assert f["nonprod_argocd_destination_namespace"] == "aiagents-smoke-dev"


def test_safety_fields_dangerous_toggles_off() -> None:
    f = nonprod_argocd_safety_fields(ROOT)
    for key in (
        "nonprod_argocd_auto_sync_enabled",
        "nonprod_argocd_prune_enabled",
        "nonprod_argocd_self_heal_enabled",
        "nonprod_argocd_production_namespace_touched",
        "nonprod_argocd_public_ingress_enabled",
        "nonprod_argocd_loadbalancer_enabled",
        "argocd_production_sync_performed",
    ):
        assert f[key] is False, key
