#!/usr/bin/env python3
"""Step 62 -- production readiness blocking rules verifier.

Marker: PRODUCTION_READINESS_BLOCKING_RULES_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.production_readiness import blocking_rules  # noqa: E402

MARKER = "PRODUCTION_READINESS_BLOCKING_RULES_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    # With no production action, hard guards are inactive; prerequisite caps are active.
    res = blocking_rules.evaluate()
    hard_active = [r.name for r in res if r.severity == "hard" and r.active]
    if hard_active:
        bad(f"hard guard rules active with no production action: {hard_active}")
    prereq_active = [r.name for r in res if r.severity == "prerequisite" and r.active]
    if not prereq_active:
        bad("expected at least one active prerequisite blocker this stage")

    # A requested production action must activate the hard guard.
    res2 = blocking_rules.evaluate(production_action_requested=True)
    if not any(r.name == "production_action_requested" and r.active for r in res2):
        bad("production_action_requested did not activate")

    # A non-zero production_executed count must activate the hard guard.
    res3 = blocking_rules.evaluate(production_executed_true_count=1)
    if not any(r.name == "production_executed_true_count_nonzero" and r.active for r in res3):
        bad("production_executed_true_count_nonzero did not activate")

    # tenant isolation must be a (prerequisite) blocker, never an implemented capability.
    if not any(r.name == "tenant_isolation_not_implemented" and r.active for r in res):
        bad("tenant_isolation_not_implemented must be an active prerequisite blocker")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] blocking rules: hard guards inactive; prerequisite caps active; guards fire")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
