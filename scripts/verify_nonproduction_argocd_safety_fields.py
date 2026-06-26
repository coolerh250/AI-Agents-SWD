#!/usr/bin/env python3
"""Step 56 -- non-production ArgoCD safety fields verifier (live).

Hits the live ``/operations/safety`` and asserts the Step 56 ArgoCD fields reflect a
non-production manual-sync posture with all the dangerous toggles off and
``production_executed_true_count == 0``.

Marker: NONPROD_ARGOCD_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

MARKER = "NONPROD_ARGOCD_SAFETY_FIELDS_VERIFY"
URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/safety"

EXPECTED = {
    "nonprod_argocd_enabled": True,
    "nonprod_argocd_namespace": "argocd-nonprod",
    "nonprod_argocd_installed": True,
    "nonprod_argocd_project_created": True,
    "nonprod_argocd_application_created": True,
    "nonprod_argocd_manual_sync_performed": True,
    "nonprod_argocd_manual_sync_succeeded": True,
    "nonprod_argocd_auto_sync_enabled": False,
    "nonprod_argocd_prune_enabled": False,
    "nonprod_argocd_self_heal_enabled": False,
    "nonprod_argocd_destination_namespace": "aiagents-smoke-dev",
    "nonprod_argocd_production_namespace_touched": False,
    "nonprod_argocd_public_ingress_enabled": False,
    "nonprod_argocd_loadbalancer_enabled": False,
    "argocd_production_sync_performed": False,
    "production_executed_true_count": 0,
}

failures: list[str] = []


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=10) as r:  # noqa: S310
            data = json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"  [FAIL] could not read {URL}: {exc}")
        print(f"{MARKER}: FAIL")
        return 1

    for key, want in EXPECTED.items():
        got = data.get(key)
        if got != want:
            failures.append(key)
            print(f"  [FAIL] {key}={got!r} (expected {want!r})")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] live ArgoCD safety fields are non-production; production_executed_true_count=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
