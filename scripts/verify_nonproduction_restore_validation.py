#!/usr/bin/env python3
"""Step 61 -- non-production restore validation verifier.

Verifies the restore validation SDK behaviour and (when present) the generated validation
result JSON. Marker: NONPRODUCTION_RESTORE_VALIDATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.backup_restore_dr import build_restore_validation_result  # noqa: E402

MARKER = "NONPRODUCTION_RESTORE_VALIDATION_VERIFY"
RESULT_JSON = ROOT / ".runtime" / "backup-dr" / "nonproduction-restore-validation-result.json"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    # Production target blocked.
    r = build_restore_validation_result(
        restore_plan_id="p", target_environment="production", validation_types=["schema_validation"]
    )
    if r.status != "blocked":
        bad("production target validation not blocked")

    # Passing validation never touches active runtime.
    ok = build_restore_validation_result(
        restore_plan_id="p",
        target_environment="nonprod",
        validation_types=["manifest_integrity_check", "redaction_validation"],
        checks=[{"name": "x", "passed": True}],
    )
    d = ok.to_dict()
    if d["status"] != "passed":
        bad("valid non-production validation should pass")
    for k in (
        "active_database_overwritten",
        "active_redis_overwritten",
        "argocd_sync_performed",
        "kind_cluster_mutated",
        "production_executed",
    ):
        if d[k] is not False:
            bad(f"{k} must be false")

    # Failure is not hidden.
    f = build_restore_validation_result(
        restore_plan_id="p",
        target_environment="nonprod",
        validation_types=["schema_validation"],
        checks=[{"name": "x", "passed": False}],
    )
    if f.status != "failed":
        bad("failing check must produce failed status")

    # Generated result (if present) must not have touched active runtime.
    if RESULT_JSON.is_file():
        g = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
        for k in (
            "active_database_overwritten",
            "active_redis_overwritten",
            "argocd_sync_performed",
            "kind_cluster_mutated",
            "production_executed",
        ):
            if g.get(k) is not False:
                bad(f"generated result {k}=true")
        if g.get("status") not in ("passed", "failed", "blocked", "skipped"):
            bad(f"generated result invalid status: {g.get('status')}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] restore validation: production blocked; no active overwrite/sync/mutation")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
