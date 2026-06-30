#!/usr/bin/env python3
"""Step 63A -- controlled rollout operator decision package verifier.

Marker: CONTROLLED_ROLLOUT_OPERATOR_DECISION_PACKAGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import build_operator_decision_package  # noqa: E402

MARKER = "CONTROLLED_ROLLOUT_OPERATOR_DECISION_PACKAGE_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    pkg = build_operator_decision_package()
    if pkg.get("production_ready") is not False:
        bad("production_ready must be false")
    if pkg.get("production_approval") is not False:
        bad("production_approval must be false")
    if pkg.get("production_action_allowed") is not False:
        bad("production_action_allowed must be false")
    if pkg.get("summary", {}).get("recommendation_is_approval") is not False:
        bad("summary recommendation_is_approval must be false")
    for sec in (
        "go_no_go_criteria",
        "production_target_assessment",
        "credential_readiness",
        "gitops_readiness",
        "approval_channel_readiness",
        "rollback_dr_readiness",
        "pilot_scope",
        "risk_register",
        "missing_items",
        "recommendation",
    ):
        if sec not in pkg:
            bad(f"decision package missing section: {sec}")

    # Forbidden-key redaction (inject a token into the readiness gate result).
    pkg2 = build_operator_decision_package(readiness_gate_result={"decision": "x", "token": "abc"})
    if pkg2["readiness_gate_result"].get("token") != "[redacted]":
        bad("token in readiness gate result not redacted")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] operator decision package: not approval; not production ready; redacted")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
