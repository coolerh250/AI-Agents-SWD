#!/usr/bin/env python3
"""Step 56 -- non-production ArgoCD install boundary verifier (static).

Validates the committed install boundary descriptor: namespace argocd-nonprod (never
the production-like `argocd`), ClusterIP only, no ingress / LoadBalancer / NodePort /
external exposure, no SSO / OIDC, no committed token / password / kubeconfig, no
production AppProject / Application / repo credential / secret, no auto-sync.

Marker: NONPROD_ARGOCD_INSTALL_BOUNDARY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = "NONPROD_ARGOCD_INSTALL_BOUNDARY_VERIFY"
BOUNDARY = ROOT / "infra" / "gitops" / "nonproduction-argocd-install-boundary.yaml"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not BOUNDARY.is_file():
        bad("missing nonproduction-argocd-install-boundary.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    b = (yaml.safe_load(BOUNDARY.read_text(encoding="utf-8")) or {}).get(
        "nonProductionArgocdInstallBoundary", {}
    )
    if b.get("namespace") != "argocd-nonprod":
        bad("install namespace must be argocd-nonprod")
    if b.get("serverServiceType") != "ClusterIP":
        bad("argocd-server service type must be ClusterIP")
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
        if b.get(flag) is not False:
            bad(f"{flag} must be false")
    forbidden = set(b.get("forbiddenNamespaces", []))
    if not {"argocd", "default", "kube-system", "production", "prod"} <= forbidden:
        bad("forbiddenNamespaces must include argocd/default/kube-system/production/prod")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] install boundary: ClusterIP only; no ingress/LB/SSO; no committed token/password")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
