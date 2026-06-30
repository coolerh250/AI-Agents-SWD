#!/usr/bin/env python3
"""Step 63A -- controlled rollout pilot scope verifier.

Marker: CONTROLLED_ROLLOUT_PILOT_SCOPE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import loaders  # noqa: E402

MARKER = "CONTROLLED_ROLLOUT_PILOT_SCOPE_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    s = loaders.load("scope")
    constraints = set(s.get("constraints", []))
    for required in (
        "single_service",
        "single_environment",
        "manual_approval",
        "manual_rollback",
        "no_auto_promotion",
    ):
        if required not in constraints:
            bad(f"missing scope constraint: {required}")
    if s.get("auto_promotion") is not False:
        bad("auto_promotion must be false")
    if s.get("external_customer_traffic") is not False:
        bad("external_customer_traffic must be false")
    if not s.get("blast_radius"):
        bad("blast radius must be describable")
    if not s.get("rollback_trigger"):
        bad("rollback trigger must be describable")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] pilot scope: single service/env, manual approval+rollback, no auto-promotion")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
