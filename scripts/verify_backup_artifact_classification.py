#!/usr/bin/env python3
"""Step 61 -- backup artifact classification verifier.

Marker: BACKUP_ARTIFACT_CLASSIFICATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.backup_restore_dr import load_classes  # noqa: E402
from shared.sdk.backup_restore_dr.models import ARTIFACT_CLASSES  # noqa: E402

MARKER = "BACKUP_ARTIFACT_CLASSIFICATION_VERIFY"
FIELDS = (
    "retention_days",
    "cleanup_allowed",
    "cleanup_requires_approval",
    "backup_required",
    "restore_validation_required",
    "commit_allowed",
    "secret_scan_required",
)
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    classes = load_classes()
    for name in ARTIFACT_CLASSES:
        if name not in classes:
            bad(f"missing classification class: {name}")
            continue
        for f in FIELDS:
            if f not in classes[name]:
                bad(f"class {name} missing field {f}")
    # Dumps may never be committed.
    for name in ("database_dump", "redis_snapshot"):
        if classes.get(name, {}).get("commit_allowed", False):
            bad(f"{name} commit_allowed must be false")
    # Temporary classes are cleanup-allowed without approval.
    for name in ("temporary_trace", "temporary_build_cache"):
        c = classes.get(name, {})
        if not c.get("cleanup_allowed") or c.get("cleanup_requires_approval"):
            bad(f"{name} should be cleanup_allowed without approval")
    # Cluster runtime state must never be auto-cleaned.
    if classes.get("cluster_runtime_state", {}).get("cleanup_allowed", False):
        bad("cluster_runtime_state cleanup_allowed must be false")
    # Scheduled DR report: not auto-cleanable.
    if classes.get("scheduled_dr_report", {}).get("cleanup_allowed", False):
        bad("scheduled_dr_report cleanup_allowed must be false (retained copy required)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] artifact classification: dumps never committed; cluster state never auto-cleaned")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
