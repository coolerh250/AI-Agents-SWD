#!/usr/bin/env python3
"""Step 56 -- non-production ArgoCD preflight verifier.

Validates the committed manual-sync plan (always), then confirms a SAFE
non-production context + the aiagents-smoke-dev namespace + that the Step 55 runtime
smoke is still PASS (via its live report). Never prints a kubeconfig / token /
context name. With no safe cluster it reports BLOCKED.

Marker: NONPROD_ARGOCD_PREFLIGHT_VERIFY: PASS | BLOCKED | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.nonprod_cluster_detect import detect_cluster  # noqa: E402
from scripts.lib.nonprod_smoke_report import section_status  # noqa: E402

MARKER = "NONPROD_ARGOCD_PREFLIGHT_VERIFY"
PLAN = ROOT / "infra" / "gitops" / "nonproduction-argocd-manual-sync-plan.yaml"


def main() -> int:
    if not PLAN.is_file():
        print("  [FAIL] missing nonproduction-argocd-manual-sync-plan.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    plan = (yaml.safe_load(PLAN.read_text(encoding="utf-8")) or {}).get(
        "nonProductionArgocdManualSyncPlan", {}
    )
    if (plan.get("syncPolicy", {}) or {}).get("manualOnly") is not True:
        print("  [FAIL] plan must be manual-sync only")
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] manual-sync plan present; manual-only")

    available, safe, reason = detect_cluster()
    if not (available and safe):
        print(f"  [BLOCKED] no safe non-production cluster ({reason})")
        print(f"{MARKER}: BLOCKED")
        return 0

    # Step 55 runtime smoke must still be PASS (pods running in the destination ns).
    pods = section_status("podStatus")
    if pods is None:
        print("  [BLOCKED] no Step 55 runtime smoke report (run the Step 55 smoke first)")
        print(f"{MARKER}: BLOCKED")
        return 0
    if pods != "pass":
        print(f"  [FAIL] Step 55 runtime smoke not PASS (podStatus={pods})")
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] safe non-production context; Step 55 runtime smoke still PASS")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
