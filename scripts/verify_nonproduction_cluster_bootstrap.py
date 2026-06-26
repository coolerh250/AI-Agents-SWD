#!/usr/bin/env python3
"""Step 55.1 -- non-production cluster bootstrap verifier.

Validates the committed bootstrap plan (always): kind option, forbidden-action
flags, no image push / registry login, in-cluster secret not committed,
production invariants false. When a safe cluster + a live runtime smoke report are
present (i.e. the bootstrap actually produced a running release) it PASSes; with
no cluster / no deployed release it reports BLOCKED (never a faked bootstrap).

Marker: NONPROD_CLUSTER_BOOTSTRAP_VERIFY: PASS | BLOCKED | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.nonprod_cluster_detect import detect_cluster  # noqa: E402
from scripts.lib.nonprod_smoke_report import load_report  # noqa: E402

MARKER = "NONPROD_CLUSTER_BOOTSTRAP_VERIFY"
PLAN = ROOT / "infra" / "kubernetes" / "nonproduction-cluster-bootstrap-plan.yaml"
SCRIPT = ROOT / "scripts" / "bootstrap_nonproduction_kind_cluster.sh"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not PLAN.is_file():
        bad("missing nonproduction-cluster-bootstrap-plan.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    if not SCRIPT.is_file():
        bad("missing bootstrap_nonproduction_kind_cluster.sh")
    plan = (yaml.safe_load(PLAN.read_text(encoding="utf-8")) or {}).get(
        "nonProductionClusterBootstrapPlan", {}
    )
    if plan.get("clusterOption") not in ("kind", "k3d", "k3s", "existing-nonprod"):
        bad("plan must declare a non-production cluster option")
    if "prod" in str(plan.get("namespace", "")).lower():
        bad("plan namespace must not contain a production substring")
    img = plan.get("imageHandling", {})
    if img.get("pushPerformed") is not False or img.get("registryLoginPerformed") is not False:
        bad("plan must record no image push / no registry login")
    if plan.get("inClusterSecret", {}).get("committed") is not False:
        bad("plan must record the in-cluster secret as not committed")
    forb = plan.get("forbidden", {})
    for key in (
        "productionCluster",
        "publicIngress",
        "loadBalancer",
        "registryLogin",
        "imagePush",
        "argocdSync",
        "productionSecret",
    ):
        if forb.get(key) is not True:
            bad(f"plan must forbid {key}")
    inv = plan.get("safetyInvariants", {})
    if inv.get("productionExecuted") is not False:
        bad("plan must record productionExecuted=false")
    if inv.get("kubernetesProductionDeployPerformed") is not False:
        bad("plan must record kubernetesProductionDeployPerformed=false")
    if not failures:
        print("  [OK] bootstrap plan valid; no push/login/ingress/LB/argocd; invariants false")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    available, safe, reason = detect_cluster()
    if not (available and safe):
        print(f"  [BLOCKED] plan valid but no safe cluster bootstrapped yet ({reason})")
        print(f"{MARKER}: BLOCKED")
        return 0
    report = load_report()
    if report is None:
        print("  [BLOCKED] cluster present but no deployed release / runtime smoke report yet")
        print(f"{MARKER}: BLOCKED")
        return 0
    if report.get("namespace") != plan.get("namespace"):
        bad("live report namespace does not match the bootstrap plan")
        print(f"{MARKER}: FAIL")
        return 1
    deployed = (report.get("scope") or {}).get("deployedComponents") or []
    print(f"  [OK] non-production release bootstrapped ({len(deployed)} components deployed)")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
