#!/usr/bin/env python3
"""Step 60 -- release evidence package verifier (SDK).

Marker: RELEASE_EVIDENCE_PACKAGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MARKER = "RELEASE_EVIDENCE_PACKAGE_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    from shared.sdk.release_governance import build_evidence_summary

    # empty evidence -> incomplete, missing required, never production approved
    empty = build_evidence_summary({})
    if empty["complete"] is not False:
        bad("empty evidence must be incomplete")
    if empty["production_approved"] is not False or empty["production_ready"] is not False:
        bad("evidence must never be production approved/ready")
    if not empty["missing_required"]:
        bad("empty evidence must report missing required references")

    # full evidence -> complete
    full = build_evidence_summary(
        {
            "security_readiness": "pass",
            "rollback_plan": {"rollback_owner": "ops"},
            "audit_events": ["e1"],
        }
    )
    if full["complete"] is not True:
        bad(f"full evidence must be complete: {full['missing_required']}")

    # secret-shaped values are redacted
    red = build_evidence_summary(
        {
            "security_readiness": "BEGIN RSA PRIVATE KEY",
            "rollback_plan": {"x": 1},
            "audit_events": ["e"],
        }
    )
    if red["evidence"].get("security_readiness") != "[redacted]":
        bad("secret-shaped evidence value must be redacted")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] evidence: missing blocks readiness; never production approved; secrets redacted")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
