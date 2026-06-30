#!/usr/bin/env python3
"""Step 62 -- production readiness gate policy verifier.

Marker: PRODUCTION_READINESS_GATE_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.production_readiness import policy  # noqa: E402

MARKER = "PRODUCTION_READINESS_GATE_POLICY_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    p = policy.load_policy()
    if not p.get("enabled"):
        bad("gate not enabled")
    for key in (
        "productionReady",
        "allowProductionDeploy",
        "allowProductionSync",
        "allowProductionRestore",
        "allowProductionFailover",
        "allowAutoPromotion",
        "allowGitHubMerge",
        "allowImagePush",
        "allowRegistryLogin",
        "currentStageAllowsProductionAction",
    ):
        if p.get(key, False) is not False:
            bad(f"{key} must be false")
    for key in ("requireHumanApprovalBeforeProduction", "requireExplicitProductionRolloutPhase"):
        if p.get(key) is not True:
            bad(f"{key} must be true")
    if policy.allows_production_action():
        bad("current stage must not allow production action")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] readiness gate policy: production never ready/approved; no production action")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
