#!/usr/bin/env python3
"""Step 60 -- deployment intent model verifier (file + SDK).

Marker: DEPLOYMENT_INTENT_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODEL = ROOT / "infra" / "release" / "deployment-intent-model.yaml"
MARKER = "DEPLOYMENT_INTENT_MODEL_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    data = yaml.safe_load(MODEL.read_text(encoding="utf-8")) or {}
    di = data.get("deploymentIntent", {}) or {}
    allowed = di.get("requestedActions") or []
    forbidden = di.get("forbiddenActions") or []
    for a in ("validate_only", "prepare_nonproduction", "request_operator_review"):
        if a not in allowed:
            bad(f"missing allowed action: {a}")
    for a in ("deploy_production", "sync_production", "merge_pr", "push_image", "create_release"):
        if a not in forbidden:
            bad(f"missing forbidden action: {a}")

    from shared.sdk.release_governance import build_intent

    # validate_only on nonprod -> validated, never executes
    ok = build_intent(release_candidate_id="rc", requested_action="validate_only")
    if ok.status != "validated" or ok.to_dict()["production_executed"] is not False:
        bad(f"validate_only must validate without execution: {ok.status}")
    if ok.to_dict()["deploy_performed"] is not False:
        bad("deployment intent must never perform a deploy")

    # forbidden action -> blocked
    fb = build_intent(release_candidate_id="rc", requested_action="deploy_production")
    if fb.status != "blocked" or not (fb.blocked_reason or "").startswith("forbidden_action"):
        bad(f"forbidden action must be blocked: {fb.status}/{fb.blocked_reason}")

    # production target -> blocked
    pt = build_intent(
        release_candidate_id="rc", requested_action="validate_only", target_environment="production"
    )
    if pt.status != "blocked" or pt.blocked_reason != "production_environment_forbidden":
        bad(f"production target must be blocked: {pt.status}/{pt.blocked_reason}")

    # request_operator_review != approval
    rr = build_intent(release_candidate_id="rc", requested_action="request_operator_review")
    if rr.status != "operator_review_requested" or rr.requires_human_approval is not True:
        bad("request_operator_review must require human approval (not granted)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] deployment intent: validate-only ok; forbidden/production blocked; never deploys")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
