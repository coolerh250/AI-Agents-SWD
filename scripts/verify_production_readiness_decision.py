#!/usr/bin/env python3
"""Step 62 -- production readiness decision verifier.

Marker: PRODUCTION_READINESS_DECISION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.production_readiness import blocking_rules, decision, prerequisites  # noqa: E402

MARKER = "PRODUCTION_READINESS_DECISION_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    missing_prereq = prerequisites.missing_prerequisites()

    # Default: evidence complete, prerequisites missing -> ready_for_operator_review (the cap).
    res = blocking_rules.evaluate()
    d = decision.evaluate(blocking_results=res, missing_prerequisites=missing_prereq)
    if d.decision != "ready_for_operator_review":
        bad(f"expected ready_for_operator_review, got {d.decision}")
    dd = d.to_dict()
    if dd["production_ready"] or dd["production_approved"] or dd["production_action_allowed"]:
        bad("decision must never be production ready/approved/action-allowed")

    # Production action requested -> blocked_by_policy.
    res2 = blocking_rules.evaluate(production_action_requested=True)
    if decision.evaluate(blocking_results=res2).decision != "blocked_by_policy":
        bad("production action requested must be blocked_by_policy")

    # production_executed nonzero -> blocked_by_policy.
    res3 = blocking_rules.evaluate(production_executed_true_count=1)
    if decision.evaluate(blocking_results=res3).decision != "blocked_by_policy":
        bad("production_executed nonzero must be blocked_by_policy")

    # Missing evidence -> blocked_by_missing_evidence.
    res4 = blocking_rules.evaluate(
        marker_status={"RELEASE_DEPLOYMENT_GOVERNANCE_BASELINE_VERIFY": "FAIL"}
    )
    if decision.evaluate(blocking_results=res4).decision != "blocked_by_missing_evidence":
        bad("missing evidence must be blocked_by_missing_evidence")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] decision: max ready_for_operator_review; never production ready/approved")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
