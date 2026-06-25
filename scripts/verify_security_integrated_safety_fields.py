#!/usr/bin/env python3
"""Step 54.4 -- integrated security safety fields verifier.

Asserts /operations/safety carries the Step 54 integrated fields with a
non-production posture: threat models / risk model / evidence schema present;
evidence / risk / readiness generation wired; missing evidence + critical finding
block production; release gate disabled; step54 not production ready;
production_executed_true_count=0.

Marker: SECURITY_INTEGRATED_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

EXPECT_TRUE = [
    "security_threat_model_present",
    "security_agent_threat_model_present",
    "security_supply_chain_threat_model_present",
    "security_runtime_gitops_threat_model_present",
    "security_release_risk_summary_model_present",
    "security_release_risk_summary_generated",
    "security_evidence_package_schema_present",
    "security_evidence_package_generated",
    "security_readiness_report_generated",
    "security_missing_evidence_blocks_production",
    "security_critical_finding_blocks_production",
    "security_step54_integrated",
]
EXPECT_FALSE = [
    "security_release_gate_enabled",
    "security_step54_production_ready",
]

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    try:
        with urllib.request.urlopen(BASE + "/operations/safety", timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        bad(f"/operations/safety not reachable at {BASE}: {e}")
        print("SECURITY_INTEGRATED_SAFETY_FIELDS_VERIFY: FAIL")
        return 1

    all_fields = EXPECT_TRUE + EXPECT_FALSE + ["production_executed_true_count"]
    missing = [f for f in all_fields if f not in data]
    if missing:
        bad(f"missing integrated safety fields: {missing}")
    else:
        ok(f"all {len(all_fields)} integrated safety fields present")

    for f in EXPECT_TRUE:
        if data.get(f) is not True:
            bad(f"{f} must be true, got {data.get(f)!r}")
    if not [x for x in failures if "must be true" in x]:
        ok("threat models / risk model / evidence schema present; generation wired; blockers on")

    for f in EXPECT_FALSE:
        if data.get(f) is not False:
            bad(f"{f} must be false, got {data.get(f)!r}")
    if not [x for x in failures if "must be false" in x]:
        ok("release gate disabled; step54 not production ready")

    if data.get("production_executed_true_count") not in (0, None):
        bad(
            f"production_executed_true_count must be 0, got {data.get('production_executed_true_count')}"
        )
    else:
        ok("production_executed_true_count=0")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_INTEGRATED_SAFETY_FIELDS_VERIFY: FAIL")
        return 1
    print("SECURITY_INTEGRATED_SAFETY_FIELDS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
