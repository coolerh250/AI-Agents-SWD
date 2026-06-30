#!/usr/bin/env python3
"""Step 62 -- production readiness safety fields verifier (live /operations/safety).

Marker: PRODUCTION_READINESS_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

MARKER = "PRODUCTION_READINESS_SAFETY_FIELDS_VERIFY"
URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/safety"

EXPECTED = {
    "production_readiness_gate_enabled": True,
    "production_readiness_gate_report_generated": True,
    "production_readiness_gate_production_ready": False,
    "production_readiness_gate_production_approved": False,
    "production_readiness_gate_allows_production_action": False,
    "production_readiness_gate_allows_deploy": False,
    "production_readiness_gate_allows_sync": False,
    "production_readiness_gate_allows_merge": False,
    "production_readiness_gate_allows_image_push": False,
    "production_readiness_gate_allows_restore": False,
    "production_readiness_gate_allows_failover": False,
    "production_readiness_operator_review_enabled": True,
    "production_readiness_operator_review_is_approval": False,
    "production_rollout_execution_enabled": False,
    "production_deployment_executed_count": 0,
    "production_sync_executed_count": 0,
    "production_restore_executed_count": 0,
    "production_failover_executed_count": 0,
    "production_executed_true_count": 0,
}
failures: list[str] = []


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=10) as r:  # noqa: S310
            data = json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"  [FAIL] could not read {URL}: {exc}")
        print(f"{MARKER}: FAIL")
        return 1
    for key, want in EXPECTED.items():
        if data.get(key) != want:
            failures.append(key)
            print(f"  [FAIL] {key}={data.get(key)!r} (expected {want!r})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] production readiness safety fields: production blocked/unapproved; all counts 0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
