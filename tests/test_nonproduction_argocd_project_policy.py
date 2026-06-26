"""Step 56 -- non-production ArgoCD project policy + AppProject manifest."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "infra" / "gitops" / "nonproduction-argocd-project-policy.yaml"
MANIFEST = ROOT / "infra" / "gitops" / "nonproduction" / "aiagents-nonprod-project.yaml"


def test_policy_restricted() -> None:
    p = (yaml.safe_load(POLICY.read_text(encoding="utf-8")) or {})[
        "nonProductionArgocdProjectPolicy"
    ]["project"]
    assert p["productionAllowed"] is False
    assert p["wildcardDestinationAllowed"] is False
    assert p["clusterWideResourcesAllowed"] is False
    assert p["destinations"] == [
        {"namespace": "aiagents-smoke-dev", "server": "https://kubernetes.default.svc"}
    ]
    assert p["syncPolicy"] == {"automated": False, "prune": False, "selfHeal": False}


def test_manifest_matches_policy() -> None:
    proj = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    spec = proj["spec"]
    assert proj["kind"] == "AppProject"
    assert proj["metadata"]["name"] == "aiagents-nonprod"
    assert proj["metadata"]["namespace"] == "argocd-nonprod"
    assert spec["clusterResourceWhitelist"] == []
    dests = spec["destinations"]
    assert len(dests) == 1 and dests[0]["namespace"] == "aiagents-smoke-dev"
    assert all("*" not in r for r in spec["sourceRepos"])
    kinds = {w["kind"] for w in spec["namespaceResourceWhitelist"]}
    assert {"Deployment", "Service", "ConfigMap", "NetworkPolicy", "Job"} <= kinds
