#!/usr/bin/env python3
"""Step 53 -- secret safety fields verifier.

Asserts /operations/safety carries the expected read-only secret management
fields with a non-production, fail-closed posture.

Marker: SECRET_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

EXPECT_FALSE = [
    "secrets_production_store_configured",
    "secrets_production_store_enabled",
    "secrets_read_value_enabled",
    "secrets_write_value_enabled",
    "secrets_rotation_enabled",
    "secrets_inline_values_detected",
    "secrets_client_secret_committed",
    "secrets_jwt_committed",
    "secrets_private_key_committed",
    "secrets_kubeconfig_committed",
    "secrets_github_token_committed",
    "secrets_argocd_token_committed",
    "secrets_registry_credential_committed",
    "secrets_backup_key_committed",
    "secrets_session_key_committed",
    "secrets_audit_key_committed",
    "secrets_production_ready",
]
EXPECT_TRUE = [
    "secrets_foundation_enabled",
    "secrets_redaction_policy_enabled",
    "secrets_secret_refs_valid",
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
        print("SECRET_SAFETY_FIELDS_VERIFY: FAIL")
        return 1

    all_fields = (
        EXPECT_FALSE + EXPECT_TRUE + ["secrets_foundation_status", "production_executed_true_count"]
    )
    missing = [f for f in all_fields if f not in data]
    if missing:
        bad(f"missing secret safety fields: {missing}")
    else:
        ok(f"all {len(all_fields)} expected secret safety fields present")

    for f in EXPECT_FALSE:
        if data.get(f) is not False:
            bad(f"{f} must be false, got {data.get(f)!r}")
    if not [x for x in failures if "must be false" in x]:
        ok("all production/store/value/rotation/committed fields are false")

    for f in EXPECT_TRUE:
        if data.get(f) is not True:
            bad(f"{f} must be true, got {data.get(f)!r}")
    if not [x for x in failures if "must be true" in x]:
        ok("foundation enabled, redaction policy enabled, secret refs valid")

    if data.get("secrets_foundation_status") not in (
        "modeled_fail_closed_not_configured",
        "unknown",
    ):
        bad(f"secrets_foundation_status unexpected: {data.get('secrets_foundation_status')}")
    if data.get("production_executed_true_count") not in (0, None):
        bad(
            f"production_executed_true_count must be 0, got {data.get('production_executed_true_count')}"
        )
    if not [x for x in failures if "status" in x or "production_executed" in x]:
        ok("foundation status modeled/unknown; production_executed_true_count=0")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECRET_SAFETY_FIELDS_VERIFY: FAIL")
        return 1
    print("SECRET_SAFETY_FIELDS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
