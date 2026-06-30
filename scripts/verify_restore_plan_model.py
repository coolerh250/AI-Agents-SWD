#!/usr/bin/env python3
"""Step 61 -- restore plan model verifier.

Marker: RESTORE_PLAN_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.backup_restore_dr import build_restore_plan  # noqa: E402
from shared.sdk.backup_restore_dr.models import FORBIDDEN_RESTORE_TYPES  # noqa: E402

MARKER = "RESTORE_PLAN_MODEL_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    # Forbidden restore types blocked.
    for rt in FORBIDDEN_RESTORE_TYPES:
        p = build_restore_plan(target="pg", restore_type=rt, target_environment="nonprod")
        if p.status != "blocked" or "forbidden_restore_type" not in (p.blocked_reason or ""):
            bad(f"forbidden restore type {rt} not blocked")
        if p.to_dict()["production_restore"] is not False:
            bad(f"{rt} production_restore must be false")

    # Production target blocked for every allowed restore type.
    for env in ("production", "prod"):
        p = build_restore_plan(target="pg", restore_type="validate_backup", target_environment=env)
        if p.status != "blocked" or p.blocked_reason != "production_environment_forbidden":
            bad(f"production target {env} not blocked")

    # Allowed non-production plan is planned (never executed).
    p = build_restore_plan(
        target="pg", restore_type="dry_run_restore", target_environment="nonprod"
    )
    if p.status != "planned":
        bad("non-production dry-run plan should be planned")
    d = p.to_dict()
    if d["restore_executed"] is not False or d["production_restore"] is not False:
        bad("restore plan must not execute / must not be production")
    if not d["validation_required"] or not d["rollback_plan_required"]:
        bad("validation + rollback plan must be required")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] restore plan: production + forbidden types blocked; never executes a restore")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
