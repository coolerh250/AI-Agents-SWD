#!/usr/bin/env python3
"""Step 61 -- non-production restore validation runner.

Performs SAFE, non-destructive validation: backup target metadata validation, schema
validation where possible, evidence redaction validation, restore plan validation, and an
optional dry-run only. It NEVER overwrites an active Postgres or Redis, NEVER uses
production data, NEVER triggers an ArgoCD sync, and NEVER mutates the kind cluster. A
production target is blocked and an arbitrary restore path is rejected. Validation failure
is reported, never hidden.

Output: .runtime/backup-dr/nonproduction-restore-validation-result.json (gitignored)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.backup_restore_dr import (  # noqa: E402
    build_recovery_evidence,
    build_restore_plan,
    build_restore_validation_result,
    load_targets,
    production_restore_allowed_count,
)

OUT = ROOT / ".runtime" / "backup-dr" / "nonproduction-restore-validation-result.json"


def main() -> int:
    checks: list[dict] = []

    # 1. backup target metadata: no production restore target.
    prod_targets = production_restore_allowed_count()
    checks.append(
        {
            "name": "backup_target_metadata",
            "passed": prod_targets == 0,
            "detail": f"production_restore_allowed_targets={prod_targets}",
        }
    )

    # 2. no secret-bearing backup target.
    secret_backup = sum(
        1 for t in load_targets() if t.get("contains_secret") and t.get("backup_allowed")
    )
    checks.append(
        {
            "name": "no_secret_bearing_backup",
            "passed": secret_backup == 0,
            "detail": f"secret_bearing_backup_targets={secret_backup}",
        }
    )

    # 3. restore plan for a non-production dry-run is planned (never executes).
    plan = build_restore_plan(
        target="postgresql", restore_type="dry_run_restore", target_environment="nonprod"
    )
    checks.append(
        {
            "name": "restore_plan_nonproduction_dry_run",
            "passed": plan.status == "planned" and plan.to_dict()["production_restore"] is False,
            "detail": f"status={plan.status}",
        }
    )

    # 4. a production restore plan is blocked.
    blocked_plan = build_restore_plan(
        target="postgresql", restore_type="validate_backup", target_environment="production"
    )
    checks.append(
        {
            "name": "production_restore_plan_blocked",
            "passed": blocked_plan.status == "blocked",
            "detail": f"blocked_reason={blocked_plan.blocked_reason}",
        }
    )

    # 5. evidence redaction: a token-shaped field is redacted.
    ev = build_recovery_evidence(
        {"backup_inventory": {"actor": "op"}, "operator_decisions": {"token": "x"}}
    )
    redacted = ev["evidence"].get("operator_decisions", {}).get("token") == "[redacted]"
    checks.append(
        {
            "name": "evidence_redaction",
            "passed": redacted and ev["production_ready"] is False,
            "detail": "token redacted; production_ready false",
        }
    )

    missing = [c["name"] for c in checks if not c["passed"]]
    plan_obj = build_restore_plan(
        target="postgresql", restore_type="validate_backup", target_environment="nonprod"
    )
    result = build_restore_validation_result(
        restore_plan_id=plan_obj.restore_plan_id,
        target_environment="nonprod",
        validation_types=[
            "manifest_integrity_check",
            "redaction_validation",
            "artifact_freshness_check",
        ],
        checks=checks,
        missing=missing,
    )
    out = result.to_dict()
    out["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    status = out["status"]
    print(
        f"  [{'OK' if status == 'passed' else 'FAIL'}] non-production restore validation: {status}"
    )
    print(f"  -> {OUT.relative_to(ROOT).as_posix()}")
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
