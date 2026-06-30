#!/usr/bin/env python3
"""Step 62 -- production readiness checklist verifier.

Marker: PRODUCTION_READINESS_CHECKLIST_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.production_readiness import checklist  # noqa: E402

MARKER = "PRODUCTION_READINESS_CHECKLIST_VERIFY"
FIELDS = (
    "required",
    "evidence_source",
    "status",
    "blocking_if_missing",
    "production_ready_claim_allowed",
)
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    cats = checklist.load_categories()
    if not cats:
        bad("no checklist categories")
    for c in cats:
        name = c.get("name", "?")
        for f in FIELDS:
            if f not in c:
                bad(f"category {name} missing field {f}")
        if c.get("production_ready_claim_allowed") is not False:
            bad(f"category {name} must not allow a production-ready claim")
    if checklist.production_ready_claim_count() != 0:
        bad("a category allows a production-ready claim (must be 0)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] checklist: {len(cats)} categories; no production-ready claim allowed anywhere")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
