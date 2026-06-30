#!/usr/bin/env python3
"""Step 61 -- DR operation model verifier.

Marker: DR_OPERATION_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.backup_restore_dr import build_dr_operation, evaluate_readiness  # noqa: E402
from shared.sdk.backup_restore_dr.models import (  # noqa: E402
    DR_OPERATION_TYPES,
    FORBIDDEN_DR_OPERATION_TYPES,
)

MARKER = "DR_OPERATION_MODEL_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    # Forbidden operation types blocked.
    for op in FORBIDDEN_DR_OPERATION_TYPES:
        o = build_dr_operation(operation_type=op, target_environment="nonprod")
        if o.status != "blocked" or "forbidden_operation_type" not in (o.blocked_reason or ""):
            bad(f"forbidden operation {op} not blocked")
        d = o.to_dict()
        if d["production_restore"] or d["production_failover"] or d["production_executed"]:
            bad(f"{op} must report production flags false")

    # Allowed operation recorded.
    for op in DR_OPERATION_TYPES:
        o = build_dr_operation(operation_type=op, target_environment="nonprod")
        if o.status != "recorded":
            bad(f"allowed operation {op} should be recorded")

    # Production target blocked.
    o = build_dr_operation(operation_type="backup_inventory", target_environment="production")
    if o.status != "blocked":
        bad("production target operation not blocked")

    # Readiness: missing evidence blocks; never production ready.
    r = evaluate_readiness(target_environment="nonprod", evidence={})
    if r.decision != "blocked_by_missing_evidence":
        bad("missing evidence should block readiness")
    if r.to_dict()["production_ready"] or r.to_dict()["production_restore_ready"]:
        bad("readiness must never be production ready")
    r2 = evaluate_readiness(target_environment="production", evidence={})
    if r2.decision != "blocked_by_policy":
        bad("production target readiness should be blocked_by_policy")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] DR operation: production failover/restore blocked; readiness != production ready")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
