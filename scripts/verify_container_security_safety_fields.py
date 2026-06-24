#!/usr/bin/env python3
"""Step 54.3 -- container / SBOM safety fields verifier.

Asserts /operations/safety carries the SBOM / image / container security fields
with a local-only, non-production posture.

Marker: CONTAINER_SECURITY_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

EXPECT_TRUE = [
    "security_sbom_baseline_enabled",
    "security_sbom_generation_local_only",
    "security_container_image_inventory_present",
    "security_image_digest_policy_defined",
    "security_dockerfile_security_inventory_present",
    "security_container_runtime_alignment_present",
    "security_image_policy_scan_enabled",
    "security_image_policy_findings_present",
]
EXPECT_FALSE = [
    "security_sbom_external_upload_enabled",
    "security_sbom_runtime_reports_committed",
    "security_sbom_production_ready",
    "security_image_digest_pinning_complete",
    "security_latest_tag_detected",
    "security_dockerfile_non_root_complete",
    "security_image_vulnerability_cve_scan_performed",
    "security_image_signing_configured",
    "security_image_attestation_configured",
    "security_registry_login_enabled",
    "security_image_push_enabled",
    "security_container_production_ready",
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
        print("CONTAINER_SECURITY_SAFETY_FIELDS_VERIFY: FAIL")
        return 1

    all_fields = (
        EXPECT_TRUE
        + EXPECT_FALSE
        + ["security_image_vulnerability_scan_configured", "production_executed_true_count"]
    )
    missing = [f for f in all_fields if f not in data]
    if missing:
        bad(f"missing container safety fields: {missing}")
    else:
        ok(f"all {len(all_fields)} container/SBOM safety fields present")

    for f in EXPECT_TRUE:
        if data.get(f) is not True:
            bad(f"{f} must be true, got {data.get(f)!r}")
    if not [x for x in failures if "must be true" in x]:
        ok("baseline/inventory/policy/alignment fields true; policy findings present")

    for f in EXPECT_FALSE:
        if data.get(f) is not False:
            bad(f"{f} must be false, got {data.get(f)!r}")
    if not [x for x in failures if "must be false" in x]:
        ok(
            "upload/committed/digest-complete/latest/non-root/cve/signing/registry/push/production false"
        )

    vc = data.get("security_image_vulnerability_scan_configured")
    if vc not in (False, "limited_policy_baseline"):
        bad(f"security_image_vulnerability_scan_configured unexpected: {vc!r}")
    else:
        ok("image vulnerability scan = limited_policy_baseline (no CVE verdict)")

    if data.get("production_executed_true_count") not in (0, None):
        bad(
            f"production_executed_true_count must be 0, got {data.get('production_executed_true_count')}"
        )
    else:
        ok("production_executed_true_count=0")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("CONTAINER_SECURITY_SAFETY_FIELDS_VERIFY: FAIL")
        return 1
    print("CONTAINER_SECURITY_SAFETY_FIELDS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
