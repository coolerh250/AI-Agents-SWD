#!/usr/bin/env python3
"""Step 54.2 -- security scan safety fields verifier.

Asserts /operations/safety carries the local scan toolchain fields with a
local-only, non-production posture.

Marker: SECURITY_SCAN_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

EXPECT_FALSE = [
    "security_scan_external_upload_enabled",
    "security_scan_network_enabled",
    "security_scan_token_required",
    "security_scan_run_endpoint_enabled",
    "security_scan_reports_committed",
    "security_scan_production_gate_enabled",
    "security_scan_production_ready",
]
EXPECT_TRUE = [
    "security_local_scan_baseline_enabled",
    "security_scan_result_normalization_enabled",
    "security_local_secret_scan_configured",
]
CONFIG_FIELDS = {
    "security_local_sast_configured": (True, "configured", "limited_custom_baseline"),
    "security_local_dependency_scan_configured": (True, "configured", "limited_manifest_baseline"),
}
LAST_STATUS = [
    "security_secret_scan_last_status",
    "security_sast_last_status",
    "security_dependency_scan_last_status",
]
VALID_STATUS = {
    "not_configured",
    "tool_unavailable",
    "not_run",
    "completed_no_findings",
    "completed_with_findings",
    "failed",
    "passed",
}

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
        print("SECURITY_SCAN_SAFETY_FIELDS_VERIFY: FAIL")
        return 1

    all_fields = (
        EXPECT_FALSE
        + EXPECT_TRUE
        + list(CONFIG_FIELDS)
        + LAST_STATUS
        + ["production_executed_true_count"]
    )
    missing = [f for f in all_fields if f not in data]
    if missing:
        bad(f"missing scan safety fields: {missing}")
    else:
        ok(f"all {len(all_fields)} scan safety fields present")

    for f in EXPECT_FALSE:
        if data.get(f) is not False:
            bad(f"{f} must be false, got {data.get(f)!r}")
    if not [x for x in failures if "must be false" in x]:
        ok("external upload/network/token/run-endpoint/reports-committed/gate/production all false")

    if data.get("security_local_scan_baseline_enabled") is not True:
        bad("security_local_scan_baseline_enabled must be true")
    if data.get("security_scan_result_normalization_enabled") is not True:
        bad("security_scan_result_normalization_enabled must be true")
    if data.get("security_local_secret_scan_configured") not in (True, "configured"):
        bad("security_local_secret_scan_configured must be configured/true")
    if not [
        x
        for x in failures
        if "must be true" in x or "configured must" in x or "secret_scan_configured" in x
    ]:
        ok("baseline enabled, normalization enabled, secret scan configured")

    for field, allowed in CONFIG_FIELDS.items():
        if data.get(field) not in allowed:
            bad(f"{field} must be one of {allowed}, got {data.get(field)!r}")
    if not [x for x in failures if "must be one of" in x]:
        ok("sast/dependency configured as limited local baselines")

    for f in LAST_STATUS:
        if data.get(f) not in VALID_STATUS:
            bad(f"{f} invalid status: {data.get(f)!r}")
    if not [x for x in failures if "invalid status" in x]:
        ok("last-status fields honest (not_run / completed_* / tool_unavailable)")

    if data.get("production_executed_true_count") not in (0, None):
        bad(
            f"production_executed_true_count must be 0, got {data.get('production_executed_true_count')}"
        )
    else:
        ok("production_executed_true_count=0")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_SCAN_SAFETY_FIELDS_VERIFY: FAIL")
        return 1
    print("SECURITY_SCAN_SAFETY_FIELDS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
