"""Step 51.3 -- ArgoCD AppProject restrictions."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJ = ROOT / "infra" / "gitops" / "argocd" / "project.yaml"
REPO = "https://github.com/coolerh250/AI-Agents-SWD.git"
ALLOWED = {
    "Deployment",
    "Service",
    "ConfigMap",
    "ServiceAccount",
    "NetworkPolicy",
    "PersistentVolumeClaim",
    "Job",
    "CronJob",
}


def _p() -> dict:
    return yaml.safe_load(PROJ.read_text(encoding="utf-8"))


def test_kind_and_name() -> None:
    p = _p()
    assert p["kind"] == "AppProject"
    assert p["metadata"]["name"] == "ai-agents-platform"


def test_source_repo_restricted() -> None:
    assert _p()["spec"]["sourceRepos"] == [REPO]


def test_cluster_resource_whitelist_empty() -> None:
    assert _p()["spec"]["clusterResourceWhitelist"] == []


def test_namespace_whitelist_minimal() -> None:
    kinds = {e["kind"] for e in _p()["spec"]["namespaceResourceWhitelist"]}
    assert kinds == ALLOWED
    assert "Secret" not in kinds


def test_secret_blacklisted() -> None:
    blk = {e["kind"] for e in _p()["spec"].get("namespaceResourceBlacklist", [])}
    assert "Secret" in blk
