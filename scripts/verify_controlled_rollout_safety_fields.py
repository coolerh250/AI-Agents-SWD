#!/usr/bin/env python3
"""Step 63A -- controlled rollout safety fields verifier (live /operations/safety).

Marker: CONTROLLED_ROLLOUT_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

MARKER = "CONTROLLED_ROLLOUT_SAFETY_FIELDS_VERIFY"
URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/safety"

EXPECTED = {
    "controlled_rollout_review_enabled": True,
    "controlled_rollout_review_report_generated": True,
    "controlled_rollout_recommendation_is_approval": False,
    "controlled_rollout_allows_production_action": False,
    "controlled_rollout_allows_deploy": False,
    "controlled_rollout_allows_sync": False,
    "controlled_rollout_allows_merge": False,
    "controlled_rollout_allows_image_push": False,
    "controlled_rollout_allows_restore": False,
    "controlled_rollout_allows_failover": False,
    "controlled_rollout_operator_review_enabled": True,
    "controlled_rollout_operator_review_is_approval": False,
    "controlled_rollout_production_action_executed_count": 0,
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
        if data.get(key) != want:
            failures.append(key)
            print(f"  [FAIL] {key}={data.get(key)!r} (expected {want!r})")
    # The recommendation must be one of the valid statuses (no_go expected at this stage).
    if data.get("controlled_rollout_recommendation") not in ("go", "conditional_go", "no_go"):
        failures.append("controlled_rollout_recommendation")
        print(
            f"  [FAIL] controlled_rollout_recommendation={data.get('controlled_rollout_recommendation')!r}"
        )
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        "  [OK] controlled rollout safety fields: recommendation not approval; "
        "no production action; counts 0"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
