#!/usr/bin/env python3
"""Step 63A -- controlled rollout go/no-go criteria verifier.

Marker: CONTROLLED_ROLLOUT_GO_NO_GO_CRITERIA_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import loaders  # noqa: E402

MARKER = "CONTROLLED_ROLLOUT_GO_NO_GO_CRITERIA_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    c = loaders.load("criteria")
    outcomes = set(c.get("outcomes", []))
    if outcomes != {"go", "conditional_go", "no_go"}:
        bad(f"unexpected outcomes: {outcomes}")
    criteria = c.get("criteria", [])
    if not criteria:
        bad("no criteria defined")
    for item in criteria:
        if "name" not in item or "status" not in item or "hard" not in item:
            bad(f"criterion missing fields: {item}")
    # The hard production gates must be present.
    names = {x["name"] for x in criteria}
    for required in (
        "production_target_identified",
        "production_credentials_configured",
        "production_gitops_app_defined",
        "production_approval_channel_defined",
    ):
        if required not in names:
            bad(f"missing hard criterion: {required}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] go/no-go criteria: {len(criteria)} criteria; outcomes go/conditional_go/no_go")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
