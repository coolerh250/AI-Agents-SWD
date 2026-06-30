#!/usr/bin/env python3
"""Step 61 -- backup / restore / DR safety fields verifier (live /operations/safety).

Marker: BACKUP_RESTORE_DR_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

MARKER = "BACKUP_RESTORE_DR_SAFETY_FIELDS_VERIFY"
URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/safety"

EXPECTED = {
    "backup_restore_dr_enabled": True,
    "backup_inventory_enabled": True,
    "controlled_cleanup_review_enabled": True,
    "restore_plan_enabled": True,
    "restore_validation_enabled": True,
    "recovery_evidence_enabled": True,
    "backup_restore_dr_production_ready": False,
    "backup_restore_dr_allow_production_restore": False,
    "backup_restore_dr_allow_production_failover": False,
    "backup_restore_dr_allow_external_backup_upload": False,
    "backup_restore_dr_allow_cloud_provider_write": False,
    "backup_restore_dr_allow_argocd_production_sync": False,
    "backup_restore_dr_allow_kubernetes_production_mutation": False,
    "cleanup_execution_enabled": False,
    "restore_execution_enabled": False,
    "cleanup_teardown_kind_enabled": False,
    "cleanup_teardown_argocd_enabled": False,
    "production_restore_plan_count": 0,
    "production_failover_plan_count": 0,
    "production_restore_executed_count": 0,
    "production_failover_executed_count": 0,
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
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] backup/restore/DR safety fields: production blocked; all counts 0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
