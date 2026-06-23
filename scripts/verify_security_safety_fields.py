#!/usr/bin/env python3
"""Step 54.1 -- security safety fields verifier.

Asserts /operations/safety carries the expected read-only application security &
supply chain fields with a non-production, modeled_not_enforced posture.

Marker: SECURITY_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

EXPECT_TRUE = [
    "security_foundation_enabled",
    "security_image_digest_policy_defined",
    "security_image_vulnerability_policy_defined",
    "security_threat_model_required",
    "security_release_risk_summary_required",
    "security_evidence_model_defined",
    "security_finding_taxonomy_defined",
    "security_gate_fail_closed_policy_defined",
    "supply_chain_inventory_present",
]
EXPECT_FALSE = [
    "security_sast_configured",
    "security_dependency_scan_configured",
    "security_secret_scan_configured",
    "security_sbom_configured",
    "security_production_ready",
    "supply_chain_github_write_enabled",
    "supply_chain_pr_creation_enabled",
    "supply_chain_image_push_enabled",
    "supply_chain_registry_login_enabled",
    "supply_chain_external_scanner_upload_enabled",
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
        print("SECURITY_SAFETY_FIELDS_VERIFY: FAIL")
        return 1

    all_fields = (
        EXPECT_TRUE
        + EXPECT_FALSE
        + ["security_foundation_status", "production_executed_true_count"]
    )
    missing = [f for f in all_fields if f not in data]
    if missing:
        bad(f"missing security safety fields: {missing}")
    else:
        ok(f"all {len(all_fields)} expected security safety fields present")

    for f in EXPECT_TRUE:
        if data.get(f) is not True:
            bad(f"{f} must be true, got {data.get(f)!r}")
    if not [x for x in failures if "must be true" in x]:
        ok("foundation enabled, policies defined, inventory present (all true)")

    for f in EXPECT_FALSE:
        if data.get(f) is not False:
            bad(f"{f} must be false, got {data.get(f)!r}")
    if not [x for x in failures if "must be false" in x]:
        ok("scanners/production/github-write/pr/image-push/registry/upload all false")

    if data.get("security_foundation_status") not in ("modeled_not_enforced", "unknown"):
        bad(f"security_foundation_status unexpected: {data.get('security_foundation_status')}")
    if data.get("production_executed_true_count") not in (0, None):
        bad(
            "production_executed_true_count must be 0, got "
            f"{data.get('production_executed_true_count')}"
        )
    if not [x for x in failures if "status" in x or "production_executed" in x]:
        ok("foundation status modeled_not_enforced/unknown; production_executed_true_count=0")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_SAFETY_FIELDS_VERIFY: FAIL")
        return 1
    print("SECURITY_SAFETY_FIELDS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
