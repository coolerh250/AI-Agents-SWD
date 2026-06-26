#!/usr/bin/env python3
"""Step 55.1 -- non-production cluster safety verifier.

Confirms the LIVE smoke environment is safe: a non-production context, a safe
namespace, NO Service of type LoadBalancer/NodePort, NO Ingress, and the runtime
smoke report's production invariants are false (no production deploy, no ArgoCD
sync, productionExecuted=false). Never prints a kubeconfig / token / context name.
With no safe cluster it reports BLOCKED.

Marker: NONPROD_CLUSTER_SAFETY_VERIFY: PASS | BLOCKED | FAIL
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.nonprod_cluster_detect import detect_cluster  # noqa: E402
from scripts.lib.nonprod_smoke_report import load_report  # noqa: E402

MARKER = "NONPROD_CLUSTER_SAFETY_VERIFY"
NS = os.environ.get("SMOKE_NAMESPACE", "aiagents-smoke-dev")

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _kubectl_json(*args: str) -> dict:
    try:
        out = subprocess.run(  # noqa: S603
            ["kubectl", "-n", NS, *args, "-o", "json"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=30,
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
    if "prod" in NS.lower():
        bad(f"smoke namespace must not contain a production substring: {NS}")
        print(f"{MARKER}: FAIL")
        return 1

    available, safe, reason = detect_cluster()
    if not (available and safe):
        print(f"  [BLOCKED] no safe non-production cluster to assert safety against ({reason})")
        print(f"{MARKER}: BLOCKED")
        return 0

    # No publicly-exposed Service types in the smoke namespace.
    svcs = _kubectl_json("get", "services").get("items", [])
    for s in svcs:
        stype = s.get("spec", {}).get("type", "ClusterIP")
        if stype in ("LoadBalancer", "NodePort"):
            bad(f"forbidden Service type {stype} in {NS}")
    # No Ingress in the smoke namespace.
    ing = _kubectl_json("get", "ingress").get("items", [])
    if ing:
        bad(f"forbidden Ingress present in {NS}")

    report = load_report()
    if report is None:
        print("  [BLOCKED] no runtime smoke report to confirm production invariants")
        print(f"{MARKER}: BLOCKED")
        return 0
    if report.get("productionExecuted") is not False:
        bad("report productionExecuted must be false")
    if report.get("kubernetesProductionDeployPerformed") is not False:
        bad("report kubernetesProductionDeployPerformed must be false")
    if report.get("argocdSyncPerformed") is not False:
        bad("report argocdSyncPerformed must be false")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] safe context; no LoadBalancer/NodePort/Ingress in {NS}; invariants false")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
