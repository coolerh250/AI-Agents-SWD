#!/usr/bin/env python3
"""Step 63A -- controlled rollout review policy verifier.

Marker: CONTROLLED_ROLLOUT_REVIEW_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import loaders  # noqa: E402

MARKER = "CONTROLLED_ROLLOUT_REVIEW_POLICY_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    p = loaders.load("policy")
    if not p.get("enabled"):
        bad("review not enabled")
    for key in (
        "productionReady",
        "allowsProductionAction",
        "allowsProductionDeploy",
        "allowsProductionSync",
        "allowsProductionRestore",
        "allowsProductionFailover",
        "operatorReviewIsApproval",
        "goRecommendationIsApproval",
        "conditionalGoIsApproval",
    ):
        if p.get(key, False) is not False:
            bad(f"{key} must be false")
    for key in ("requiresExplicitOperatorApprovalForPilot", "requiresSeparatePilotExecutionStage"):
        if p.get(key) is not True:
            bad(f"{key} must be true")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] review policy: recommendation/operator-review not approval; no production action")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
