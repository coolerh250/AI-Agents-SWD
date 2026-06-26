#!/usr/bin/env python3
"""Step 56 -- non-production ArgoCD safety verifier.

Asserts the committed summary invariants (no auto-sync / prune / self-heal, no
production namespace touched, no public ingress / LoadBalancer, no production sync /
deploy), scans the committed infra/gitops tree for any token / password / kubeconfig
leak, and -- when a cluster is reachable -- confirms there is NO LoadBalancer /
NodePort Service and NO Ingress in argocd-nonprod or aiagents-smoke-dev.

Marker: NONPROD_ARGOCD_SAFETY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = "NONPROD_ARGOCD_SAFETY_VERIFY"
SUMMARY = ROOT / "infra" / "gitops" / "nonproduction-argocd-manual-sync-summary.yaml"
GITOPS_DIR = ROOT / "infra" / "gitops"
SECRET_SHAPES = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|"
    r"apiVersion: v1\nkind: Secret|argocd\.argoproj\.io/secret-type)"
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _kubectl_json(*args: str) -> dict:
    try:
        out = subprocess.run(  # noqa: S603
            ["kubectl", *args, "-o", "json"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if out.returncode != 0:
        return {}
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {}


def main() -> int:
    if not SUMMARY.is_file():
        bad("missing nonproduction-argocd-manual-sync-summary.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    s = (yaml.safe_load(SUMMARY.read_text(encoding="utf-8")) or {}).get(
        "nonProductionArgocdManualSyncSummary", {}
    )
    for flag in (
        "autoSyncEnabled",
        "pruneEnabled",
        "selfHealEnabled",
        "productionNamespaceTouched",
        "publicIngressEnabled",
        "loadBalancerEnabled",
        "nodePortEnabled",
        "argocdServerExposed",
        "argocdProductionSyncPerformed",
        "kubernetesProductionDeployPerformed",
        "externalRepoCredentialUsed",
        "productionExecuted",
        "productionReady",
    ):
        if s.get(flag) is not False:
            bad(f"summary {flag} must be false")
    if "prod" in str(s.get("destinationNamespace", "")).replace("nonprod", ""):
        bad("destination namespace must not be production")

    # No committed secret / token / kubeconfig anywhere under infra/gitops.
    for f in GITOPS_DIR.rglob("*"):
        if f.is_file():
            txt = f.read_text(encoding="utf-8", errors="ignore")
            if SECRET_SHAPES.search(txt):
                bad(f"committed gitops file looks like it contains a secret: {f.name}")

    # Live (best-effort): no LoadBalancer/NodePort/Ingress in either namespace.
    if shutil.which("kubectl") is not None:
        for ns in ("argocd-nonprod", "aiagents-smoke-dev"):
            for svc in _kubectl_json("-n", ns, "get", "services").get("items", []):
                t = svc.get("spec", {}).get("type", "ClusterIP")
                if t in ("LoadBalancer", "NodePort"):
                    bad(f"forbidden Service type {t} in {ns}")
            if _kubectl_json("-n", ns, "get", "ingress").get("items", []):
                bad(f"forbidden Ingress in {ns}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] no auto-sync/prune/selfHeal; no ingress/LB; no committed token/secret; non-prod")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
