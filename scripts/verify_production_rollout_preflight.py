#!/usr/bin/env python3
"""Step 62 -- production rollout preflight verifier.

Marker: PRODUCTION_ROLLOUT_PREFLIGHT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.production_readiness import preflight  # noqa: E402

MARKER = "PRODUCTION_ROLLOUT_PREFLIGHT_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if preflight.rollout_execution_enabled():
        bad("rollout execution must be disabled")
    if preflight.rollout_status() not in ("not_started", "blocked", "planning_only"):
        bad(
            f"rollout status must be not_started/blocked/planning_only, got {preflight.rollout_status()}"
        )
    if not preflight.load_checks():
        bad("no preflight checks declared")
    # No check may claim production readiness.
    for c in preflight.load_checks():
        if c.get("status") in ("production_ready", "ready_production", "approved"):
            bad(f"preflight check {c.get('name')} claims production readiness")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] rollout preflight: modeled only; execution disabled; not_started")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
