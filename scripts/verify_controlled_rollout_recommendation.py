#!/usr/bin/env python3
"""Step 63A -- controlled rollout recommendation verifier.

Marker: CONTROLLED_ROLLOUT_RECOMMENDATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import recommendation  # noqa: E402

MARKER = "CONTROLLED_ROLLOUT_RECOMMENDATION_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    rec = recommendation.evaluate()
    if rec["recommendation"] not in ("go", "conditional_go", "no_go"):
        bad(f"invalid recommendation: {rec['recommendation']}")
    if rec["recommendation_is_approval"] is not False:
        bad("recommendation must not be an approval")
    if rec["authorizes_production_action"] is not False:
        bad("recommendation must not authorize a production action")
    if rec["production_ready"] is not False or rec["production_approved"] is not False:
        bad("recommendation must not be production ready/approved")
    # At this stage (no production target/credentials/GitOps/approval), expect no_go.
    if rec["recommendation"] != "no_go":
        bad(f"expected no_go at this stage, got {rec['recommendation']}")
    if not rec["no_go_reasons"]:
        bad("no_go must list reasons")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] recommendation={rec['recommendation']}; not approval; no production action")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
