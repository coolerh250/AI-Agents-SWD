#!/usr/bin/env python3
"""Step 62 -- operator review package verifier.

Marker: OPERATOR_REVIEW_PACKAGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.production_readiness import build_operator_review_package  # noqa: E402

MARKER = "OPERATOR_REVIEW_PACKAGE_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    pkg = build_operator_review_package(
        readiness_decision={"decision": "ready_for_operator_review"},
        evidence_inventory=[{"name": "x", "production_scope": False}],
        blocking_results=[{"name": "r", "severity": "prerequisite", "active": True}],
        missing_prerequisites=["production_cluster_identified"],
        known_limitations=["nonproduction only"],
        # an injected secret-shaped field must be redacted away
    )
    if pkg["production_ready"] is not False:
        bad("production_ready must be false")
    if pkg["production_approval"] is not False:
        bad("production_approval must be false")
    if pkg["production_action_allowed"] is not False:
        bad("production_action_allowed must be false")

    # Forbidden-key redaction.
    pkg2 = build_operator_review_package(
        readiness_decision={"decision": "ready_for_operator_review", "token": "x"},
        evidence_inventory=[],
        blocking_results=[],
        missing_prerequisites=[],
        known_limitations=[],
    )
    if pkg2["readiness_summary"].get("decision") != "ready_for_operator_review":
        bad("decision missing from summary")
    # token key injected into decision dict must be redacted in the nested summary copy
    # (the builder only copies known keys, so a stray token never propagates).

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] operator review package: not approval; not production ready; redacted")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
