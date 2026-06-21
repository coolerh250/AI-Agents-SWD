"""Step 51.3 -- ArgoCD Project resource scope (no cluster-scoped, no Secret)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJ = ROOT / "infra" / "gitops" / "argocd" / "project.yaml"
POLICY = ROOT / "infra" / "gitops" / "policies" / "argocd-project-policy.yaml"
FORBIDDEN = {
    "Namespace",
    "ClusterRole",
    "ClusterRoleBinding",
    "CustomResourceDefinition",
    "PersistentVolume",
    "StorageClass",
    "MutatingWebhookConfiguration",
    "ValidatingWebhookConfiguration",
    "APIService",
    "Node",
    "Secret",
}


def _p() -> dict:
    return yaml.safe_load(PROJ.read_text(encoding="utf-8"))


def test_no_cluster_scoped_resources() -> None:
    assert _p()["spec"]["clusterResourceWhitelist"] == []


def test_namespace_whitelist_excludes_forbidden() -> None:
    kinds = {e["kind"] for e in _p()["spec"]["namespaceResourceWhitelist"]}
    assert not (kinds & FORBIDDEN)


def test_policy_lists_forbidden_kinds() -> None:
    pol = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    assert pol["clusterScopedResourcesAllowed"] is False
    assert pol["secretResourceAllowed"] is False
    assert set(pol["forbiddenResourceKinds"]) >= FORBIDDEN
