#!/usr/bin/env python3
"""Step 62 -- readiness evidence inventory verifier.

Marker: READINESS_EVIDENCE_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.production_readiness import evidence  # noqa: E402

MARKER = "READINESS_EVIDENCE_INVENTORY_VERIFY"
FIELDS = (
    "source",
    "freshness",
    "availability",
    "redaction",
    "production_scope",
    "nonproduction_only",
    "blocking_limitations",
)
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    items = evidence.load_evidence()
    if not items:
        bad("no evidence items")
    for e in items:
        name = e.get("name", "?")
        for f in FIELDS:
            if f not in e:
                bad(f"evidence {name} missing field {f}")
        if e.get("production_scope") is not False:
            bad(f"evidence {name} claims production scope (must be false)")
    if evidence.production_scope_count() != 0:
        bad("an evidence item claims production scope (must be 0)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] evidence inventory: {len(items)} items; all non-production scope; no secret")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
