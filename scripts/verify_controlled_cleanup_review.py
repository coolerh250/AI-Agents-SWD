#!/usr/bin/env python3
"""Step 61 -- controlled cleanup review verifier.

Verifies the cleanup review model + SDK behaviour, and (when present) the generated
review JSON. Marker: CONTROLLED_CLEANUP_REVIEW_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.backup_restore_dr import (  # noqa: E402
    CleanupReviewError,
    build_cleanup_review,
    classify_candidate,
    is_path_allowlisted,
)

MARKER = "CONTROLLED_CLEANUP_REVIEW_VERIFY"
REVIEW_JSON = ROOT / ".runtime" / "backup-dr" / "controlled-cleanup-review.json"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    # Arbitrary / traversal / absolute paths rejected.
    if is_path_allowlisted("/etc/passwd") or is_path_allowlisted("../secrets"):
        bad("arbitrary / traversal path accepted")
    if not is_path_allowlisted(".runtime/backup-dr/x.json"):
        bad("allowlisted runtime path rejected")

    # Blocked classifications must be blocked even under an allowlisted path.
    for cls in ("database_dump", "redis_snapshot", "audit_export", "cluster_runtime_state"):
        row = classify_candidate(".runtime/backup-dr/x", cls)
        if row["decision"] != "blocked":
            bad(f"classification {cls} should be blocked, got {row['decision']}")

    # Temporary trace allowed.
    if classify_candidate(".runtime/tracing/x.trace", "temporary_trace")["decision"] != "allowed":
        bad("temporary_trace under allowlisted root should be allowed")

    # Forbidden scope blocks the whole review.
    for scope in ("kind_cluster", "argocd", "active_database", "active_redis"):
        try:
            build_cleanup_review(scope=scope, candidates=[])
            bad(f"forbidden scope {scope} should raise")
        except CleanupReviewError:
            pass

    # A review never executes a cleanup.
    review = build_cleanup_review(
        scope="runtime_artifacts",
        candidates=[
            {"path": ".runtime/tracing/a", "classification": "temporary_trace", "size_bytes": 1}
        ],
    )
    if review.to_dict()["cleanup_executed"] is not False:
        bad("cleanup_executed must be false")

    # Generated review JSON (if present) must not have executed cleanup.
    if REVIEW_JSON.is_file():
        d = json.loads(REVIEW_JSON.read_text(encoding="utf-8"))
        if d.get("cleanup_executed") is not False:
            bad("generated review reports cleanup_executed=true")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] cleanup review: arbitrary paths rejected; dumps/cluster blocked; never executes")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
