"""Step 56 -- non-production ArgoCD install boundary."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT / "infra" / "gitops" / "nonproduction-argocd-install-boundary.yaml"


def _b() -> dict:
    return (yaml.safe_load(BOUNDARY.read_text(encoding="utf-8")) or {})[
        "nonProductionArgocdInstallBoundary"
    ]


def test_namespace_and_clusterip() -> None:
    b = _b()
    assert b["namespace"] == "argocd-nonprod"
    assert b["serverServiceType"] == "ClusterIP"
    assert b["cluster"] == "local-kind-only"


def test_no_exposure_no_sso_no_committed_credentials() -> None:
    b = _b()
    for flag in (
        "publicIngress",
        "loadBalancer",
        "nodePort",
        "serverExposedExternally",
        "ssoEnabled",
        "externalOidcEnabled",
        "adminPasswordCommitted",
        "adminTokenCommitted",
        "kubeconfigCommitted",
        "registryCredentialCommitted",
        "productionRepoCredential",
        "productionSecret",
        "productionAppProject",
        "productionApplication",
        "autoSyncEnabled",
        "productionReady",
    ):
        assert b[flag] is False, flag


def test_forbidden_namespaces() -> None:
    forb = set(_b()["forbiddenNamespaces"])
    assert {"argocd", "default", "kube-system", "production", "prod"} <= forb
