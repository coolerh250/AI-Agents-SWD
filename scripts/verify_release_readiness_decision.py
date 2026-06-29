#!/usr/bin/env python3
"""Step 60 -- release readiness decision verifier (SDK).

Marker: RELEASE_READINESS_DECISION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MARKER = "RELEASE_READINESS_DECISION_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    from shared.sdk.release_governance import evaluate

    # production target -> hard blocked by policy, production_ready false
    prod = evaluate(target_environment="production")
    if prod.decision != "blocked_by_policy" or prod.production_ready is not False:
        bad(f"production target must be blocked_by_policy: {prod.decision}")

    # default nonprod with no evidence -> blocked by missing evidence
    empty = evaluate(target_environment="nonprod")
    if empty.decision != "blocked_by_missing_evidence" or empty.production_ready is not False:
        bad(f"missing evidence must block: {empty.decision}")
    if not empty.missing_evidence:
        bad("missing evidence list must be populated")

    # full evidence + healthy -> ready_for_operator_review, still production_ready false
    full = evaluate(
        target_environment="nonprod",
        evidence={"security_readiness": "pass", "rollback_plan": {"o": 1}, "audit_events": ["e"]},
        rollback_present=True,
        security_status="pass",
        runtime_status="healthy",
        gitops_status="healthy",
        sandbox_pr_reviewed=True,
    )
    if full.decision != "ready_for_operator_review":
        bad(f"complete evidence must reach operator review: {full.decision} ({full.blockers})")
    if full.production_ready is not False:
        bad("ready_for_operator_review must still be production_ready false")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        "  [OK] readiness: production blocked; missing-evidence blocks; ready != production ready"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
