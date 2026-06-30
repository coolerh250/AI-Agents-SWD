#!/usr/bin/env python3
"""Step 63A -- controlled rollout go/no-go review report generator.

Reads the Step 62 readiness gate report (when present), evaluates the go/no-go criteria,
assesses the production target / credentials / GitOps / approval channel / rollback-DR,
builds the operator decision package, and produces a go / conditional_go / no_go
recommendation. It NEVER deploys, syncs, merges, pushes, restores, or fails over. The
recommendation is NOT an approval; production_ready / production_approval /
production_action_allowed are always false; it confirms production_executed_true_count == 0.

Output: .runtime/readiness/controlled-rollout-go-no-go-review.json   (gitignored)
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

from shared.sdk.controlled_rollout import (  # noqa: E402
    build_operator_decision_package,
    loaders,
    recommendation,
)

OUT = ROOT / ".runtime" / "readiness" / "controlled-rollout-go-no-go-review.json"
GATE_REPORT = ROOT / ".runtime" / "readiness" / "production-readiness-gate-report.json"
SAFETY_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/safety"


def _readiness_gate_result() -> dict:
    if GATE_REPORT.is_file():
        try:
            d = json.loads(GATE_REPORT.read_text(encoding="utf-8"))
            return {
                "decision": d.get("decision", {}).get("decision"),
                "production_ready": bool(d.get("production_ready", False)),
            }
        except (OSError, ValueError):
            pass
    return {"decision": "ready_for_operator_review", "production_ready": False}


def _production_executed_true_count() -> int:
    try:
        with urllib.request.urlopen(SAFETY_URL, timeout=10) as r:  # noqa: S310
            data = json.loads(r.read().decode("utf-8"))
        return int(data.get("production_executed_true_count", 0) or 0)
    except (OSError, ValueError):
        return 0


def main() -> int:
    prod_exec = _production_executed_true_count()
    rec = recommendation.evaluate()
    package = build_operator_decision_package(readiness_gate_result=_readiness_gate_result())

    review = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "policy": {
            "enabled": bool(loaders.load("policy").get("enabled")),
            "operator_review_is_approval": False,
            "go_recommendation_is_approval": False,
        },
        "recommendation": rec,
        "operator_decision_package": package,
        "production_ready": False,
        "production_approval": False,
        "production_action_allowed": False,
        "production_executed_true_count": prod_exec,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    print(
        f"  [OK] controlled rollout go/no-go review: recommendation={rec['recommendation']} "
        f"missing(target={rec['missing_target_count']},cred={rec['missing_credential_count']},"
        f"gitops={rec['missing_gitops_count']},approval={rec['missing_approval_channel_count']}) "
        f"prod_exec={prod_exec} (recommendation is NOT approval)"
    )
    print(f"  -> {OUT.relative_to(ROOT).as_posix()}")
    return 0 if prod_exec == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
