#!/usr/bin/env python3
"""Step 62 -- deployment authorization boundary verifier.

Marker: DEPLOYMENT_AUTHORIZATION_BOUNDARY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.production_readiness import authorization  # noqa: E402

MARKER = "DEPLOYMENT_AUTHORIZATION_BOUNDARY_VERIFY"
MUST_NOT = (
    "production_deploy",
    "production_sync",
    "production_restore",
    "production_failover",
    "pr_merge",
    "image_push",
    "release_creation",
    "tag_creation",
)
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    may = set(authorization.may_authorize())
    may_not = set(authorization.may_not_authorize())
    for forbidden in MUST_NOT:
        if forbidden not in may_not:
            bad(f"{forbidden} must be in may_not_authorize")
        if forbidden in may:
            bad(f"{forbidden} must NOT be authorizable")
    if authorization.operator_review_is_approval():
        bad("operator review request must not be an approval")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] authorization boundary: no production deploy/sync/restore/failover/merge/push")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
