"""Step 55.1 -- non-production cluster bootstrap plan + values override."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "infra" / "kubernetes" / "nonproduction-cluster-bootstrap-plan.yaml"
LOCAL_VALUES = (
    ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "values-nonprod-smoke-local.yaml"
)


def _plan() -> dict:
    return (yaml.safe_load(PLAN.read_text(encoding="utf-8")) or {})[
        "nonProductionClusterBootstrapPlan"
    ]


def test_kind_option_non_production_namespace() -> None:
    plan = _plan()
    assert plan["clusterOption"] == "kind"
    assert plan["namespace"].startswith("aiagents-smoke")
    assert "prod" not in plan["namespace"].lower()
    assert "prod" not in plan["expectedContext"].lower()


def test_no_push_no_login_secret_not_committed() -> None:
    plan = _plan()
    assert plan["imageHandling"]["pushPerformed"] is False
    assert plan["imageHandling"]["registryLoginPerformed"] is False
    assert plan["inClusterSecret"]["committed"] is False


def test_forbidden_actions_and_invariants() -> None:
    plan = _plan()
    forb = plan["forbidden"]
    for key in ("productionCluster", "publicIngress", "loadBalancer", "registryLogin",
                "imagePush", "argocdSync", "productionSecret"):
        assert forb[key] is True
    inv = plan["safetyInvariants"]
    assert inv["productionExecuted"] is False
    assert inv["kubernetesProductionDeployPerformed"] is False
    assert inv["argocdSyncPerformed"] is False


def test_local_values_are_smoke_only_non_production() -> None:
    v = yaml.safe_load(LOCAL_VALUES.read_text(encoding="utf-8")) or {}
    assert v["global"]["production"] is False
    assert v["global"]["realDeployEnabled"] is False
    # Scoped subset: the deployed app components carry a local smoke-only image tag.
    for comp in ("orchestrator", "policy-engine", "approval-engine", "audit-service"):
        assert v["components"][comp]["image"]["tag"] == "smoke-local"
    # vault disabled in the local smoke; postgres/redis enabled in-cluster.
    assert v["components"]["vault"]["enabled"] is False
    assert v["components"]["postgres"]["enabled"] is True
    assert v["components"]["redis"]["enabled"] is True
