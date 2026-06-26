"""Step 56 -- non-production ArgoCD manual-sync plan."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "infra" / "gitops" / "nonproduction-argocd-manual-sync-plan.yaml"


def _plan() -> dict:
    return (yaml.safe_load(PLAN.read_text(encoding="utf-8")) or {})[
        "nonProductionArgocdManualSyncPlan"
    ]


def test_manual_only_non_production() -> None:
    plan = _plan()
    assert plan["productionReady"] is False
    assert plan["destinationNamespace"] == "aiagents-smoke-dev"
    assert plan["argocdNamespace"] == "argocd-nonprod"
    sp = plan["syncPolicy"]
    assert sp["manualOnly"] is True
    assert sp["automated"] is False
    assert sp["prune"] is False
    assert sp["selfHeal"] is False


def test_forbidden_actions_and_invariants() -> None:
    plan = _plan()
    forb = plan["forbidden"]
    for key in (
        "productionCluster",
        "productionNamespace",
        "autoSync",
        "prune",
        "selfHeal",
        "publicIngress",
        "loadBalancer",
        "githubWrite",
        "imagePush",
        "registryLogin",
    ):
        assert forb[key] is True
    inv = plan["safetyInvariants"]
    assert inv["argocdProductionSyncPerformed"] is False
    assert inv["kubernetesProductionDeployPerformed"] is False
    assert inv["productionExecuted"] is False


def test_source_is_explicit_no_credential() -> None:
    src = _plan()["source"]
    assert "*" not in src["repoURL"]
    assert src["externalRepoCredentialUsed"] is False
    assert "charts/ai-agents-platform" in src["path"]
