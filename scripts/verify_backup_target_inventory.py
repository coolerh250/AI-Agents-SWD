#!/usr/bin/env python3
"""Step 61 -- backup target inventory verifier.

Marker: BACKUP_TARGET_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.backup_restore_dr import load_targets  # noqa: E402

MARKER = "BACKUP_TARGET_INVENTORY_VERIFY"
REQUIRED_FIELDS = (
    "name",
    "source",
    "classification",
    "contains_secret",
    "contains_customer_data",
    "contains_runtime_state",
    "contains_audit_evidence",
    "backup_allowed",
    "restore_allowed_nonprod",
    "restore_allowed_production",
    "retention_class",
    "cleanup_allowed",
)
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    targets = load_targets()
    if not targets:
        bad("no backup targets")
    for t in targets:
        name = t.get("name", "?")
        for f in REQUIRED_FIELDS:
            if f not in t:
                bad(f"target {name} missing field {f}")
        # No target may be production-restorable.
        if t.get("restore_allowed_production"):
            bad(f"target {name} has restore_allowed_production=true")
        # A secret-bearing target must not be backed up as plaintext.
        if t.get("contains_secret") and t.get("backup_allowed"):
            bad(f"target {name} contains_secret but backup_allowed")
        # Customer data must not be backed up by this baseline.
        if t.get("contains_customer_data"):
            bad(f"target {name} contains_customer_data=true (must be false)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        f"  [OK] {len(targets)} backup targets; none production-restorable; no secret/customer data"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
