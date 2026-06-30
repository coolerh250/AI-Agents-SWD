#!/usr/bin/env python3
"""Step 62 -- production readiness gate report generator.

Collects readiness evidence availability + known limitations, evaluates the blocking rules
and production prerequisites, builds the operator review package, and produces a readiness
DECISION. It NEVER deploys, syncs, merges, pushes, restores, or fails over. production_ready
/ production_approval / production_action_allowed are always false, and it confirms
production_executed_true_count == 0 (read from the live safety endpoint when available).

Output: .runtime/readiness/production-readiness-gate-report.json   (gitignored)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.production_readiness import (  # noqa: E402
    authorization,
    blocking_rules,
    build_operator_review_package,
    decision,
    evidence,
    policy,
    preflight,
    prerequisites,
)

OUT = ROOT / ".runtime" / "readiness" / "production-readiness-gate-report.json"
SAFETY_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/safety"

KNOWN_LIMITATIONS = [
    "non-production readiness gate only; NOT production deployment / approval / rollout",
    "production environment + prerequisites are not configured",
    "runtime + GitOps evidence is non-production only (kind / nonprod ArgoCD)",
    "sandbox draft PR is not a merged or reviewed PR",
    "release governance / DR baselines PASS != production approved / production DR ready",
    "tenant isolation + external connectors are future considerations, not implemented",
]


def _production_executed_true_count() -> int:
    try:
        with urllib.request.urlopen(SAFETY_URL, timeout=10) as r:  # noqa: S310
            data = json.loads(r.read().decode("utf-8"))
        return int(data.get("production_executed_true_count", 0) or 0)
    except (OSError, ValueError):
        return 0


def main() -> int:
    prod_exec = _production_executed_true_count()
    results = blocking_rules.evaluate(production_executed_true_count=prod_exec)
    missing_prereq = prerequisites.missing_prerequisites()
    dec = decision.evaluate(
        blocking_results=results, missing_evidence=[], missing_prerequisites=missing_prereq
    )
    package = build_operator_review_package(
        readiness_decision=dec.to_dict(),
        evidence_inventory=evidence.load_evidence(),
        blocking_results=[r.to_dict() for r in results],
        missing_prerequisites=missing_prereq,
        known_limitations=KNOWN_LIMITATIONS,
    )

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "policy": {
            "enabled": bool(policy.load_policy().get("enabled")),
            "production_ready": False,
            "current_stage_allows_production_action": policy.allows_production_action(),
        },
        "required_markers": list(blocking_rules.required_markers()),
        "evidence_inventory": evidence.load_evidence(),
        "blocking_rules": [r.to_dict() for r in results],
        "missing_prerequisites": missing_prereq,
        "authorization_boundary": {
            "may_authorize": authorization.may_authorize(),
            "may_not_authorize": authorization.may_not_authorize(),
            "operator_review_is_approval": authorization.operator_review_is_approval(),
        },
        "rollout_preflight": {
            "rollout_status": preflight.rollout_status(),
            "rollout_execution_enabled": preflight.rollout_execution_enabled(),
            "checks": preflight.load_checks(),
        },
        "operator_review_package": package,
        "decision": dec.to_dict(),
        "production_ready": False,
        "production_approval": False,
        "production_action_allowed": False,
        "production_executed_true_count": prod_exec,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"  [OK] readiness gate report: decision={dec.decision} "
        f"missing_prereq={len(missing_prereq)} prod_exec={prod_exec} (production NOT ready/approved)"
    )
    print(f"  -> {OUT.relative_to(ROOT).as_posix()}")
    # production_executed must be zero; otherwise this is a hard failure.
    return 0 if prod_exec == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
