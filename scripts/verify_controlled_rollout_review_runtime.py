#!/usr/bin/env python3
"""Step 63A -- controlled rollout review runtime verifier.

Verifies the generated review report (when present) is well-formed and SAFE: recommendation
is not an approval, not production ready/approved/action-allowed, production_executed 0, no
secret. The report lives under .runtime/ and is never committed.

Marker: CONTROLLED_ROLLOUT_REVIEW_RUNTIME_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".runtime" / "readiness" / "controlled-rollout-go-no-go-review.json"

MARKER = "CONTROLLED_ROLLOUT_REVIEW_RUNTIME_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not REPORT.is_file():
        bad(f"missing review report: {REPORT.relative_to(ROOT).as_posix()} (run the generator)")
        print(f"{MARKER}: FAIL")
        return 1
    d = json.loads(REPORT.read_text(encoding="utf-8"))
    if d.get("production_ready") is not False:
        bad("report production_ready must be false")
    if d.get("production_approval") is not False:
        bad("report production_approval must be false")
    if d.get("production_action_allowed") is not False:
        bad("report production_action_allowed must be false")
    if int(d.get("production_executed_true_count", 0) or 0) != 0:
        bad("report production_executed_true_count must be 0")
    rec = d.get("recommendation", {})
    if rec.get("recommendation") not in ("go", "conditional_go", "no_go"):
        bad(f"invalid recommendation: {rec.get('recommendation')}")
    if rec.get("recommendation_is_approval") is not False:
        bad("recommendation must not be an approval")
    raw = json.dumps(d)
    for shape in ("ghp_", "-----BEGIN", "AKIA"):
        if shape in raw:
            bad(f"report contains secret-shaped content: {shape}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        f"  [OK] review report: recommendation={rec.get('recommendation')}; not approval; prod_exec=0"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
