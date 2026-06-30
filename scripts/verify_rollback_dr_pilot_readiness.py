#!/usr/bin/env python3
"""Step 63A -- rollback / DR pilot readiness verifier.

Marker: ROLLBACK_DR_PILOT_READINESS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import loaders  # noqa: E402

MARKER = "ROLLBACK_DR_PILOT_READINESS_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    r = loaders.load("rollback_dr")
    if r.get("step61_pass_is_production_dr_ready") is not False:
        bad("Step 61 PASS must not be treated as production DR ready")
    if r.get("executes_restore") is not False:
        bad("must not execute restore")
    if r.get("executes_failover") is not False:
        bad("must not execute failover")
    if not loaders.rollback_dr_incomplete():
        bad("rollback/DR should be incomplete at this stage")
    refs = r.get("references", [])
    if not refs:
        bad("must reference Step 60 rollback + Step 61 DR")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] rollback/DR readiness: Step 61 PASS != production DR ready; no restore/failover")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
