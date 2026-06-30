#!/usr/bin/env python3
"""Step 61 -- backup / restore / DR policy verifier.

Marker: BACKUP_RESTORE_DR_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.backup_restore_dr import policy  # noqa: E402

MARKER = "BACKUP_RESTORE_DR_POLICY_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    p = policy.load_policy()
    if not p.get("enabled"):
        bad("policy not enabled")
    # Every dangerous toggle must be false.
    for key in (
        "productionReady",
        "allowProductionRestore",
        "allowProductionFailover",
        "allowProductionBackupMutation",
        "allowExternalBackupUpload",
        "allowCloudProviderWrite",
        "allowArgoCDProductionSync",
        "allowKubernetesProductionMutation",
        "allowUnreviewedCleanup",
        "allowCleanupExecution",
        "allowRestoreExecution",
        "allowKindTeardown",
        "allowArgoCDTeardown",
    ):
        if p.get(key, False) is not False:
            bad(f"{key} must be false")
    # Guards that must be true.
    for key in (
        "requireInventoryBeforeCleanup",
        "requireRestoreValidation",
        "requireHumanApprovalForProductionRestore",
    ):
        if p.get(key) is not True:
            bad(f"{key} must be true")
    # Environment policy.
    if "production" not in p.get("forbiddenEnvironments", []) or "prod" not in p.get(
        "forbiddenEnvironments", []
    ):
        bad("production/prod must be forbidden environments")
    for e in ("production", "prod"):
        _, blocked = policy.validate_environment(e)
        if blocked != "production_environment_forbidden":
            bad(f"environment {e} not blocked")
    for e in ("local", "dev", "test", "nonprod"):
        _, blocked = policy.validate_environment(e)
        if blocked is not None:
            bad(f"environment {e} should be allowed")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] DR policy: production restore/failover blocked; cleanup/restore execution off")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
