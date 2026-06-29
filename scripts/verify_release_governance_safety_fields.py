#!/usr/bin/env python3
"""Step 60 -- release governance safety fields verifier (live /operations/safety).

Marker: RELEASE_GOVERNANCE_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

MARKER = "RELEASE_GOVERNANCE_SAFETY_FIELDS_VERIFY"
URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/safety"

EXPECTED = {
    "release_governance_enabled": True,
    "release_candidate_enabled": True,
    "deployment_intent_enabled": True,
    "release_governance_production_ready": False,
    "release_governance_allow_production_deploy": False,
    "release_governance_allow_auto_promotion": False,
    "release_governance_allow_github_merge": False,
    "release_governance_allow_argocd_production_sync": False,
    "release_governance_allow_image_push": False,
    "release_governance_allow_registry_login": False,
    "release_candidate_production_ready_count": 0,
    "deployment_intent_production_target_count": 0,
    "deployment_intent_production_executed_count": 0,
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
    print("  [OK] release governance safety fields: production blocked; all counts 0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
