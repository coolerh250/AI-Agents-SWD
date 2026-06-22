#!/usr/bin/env python3
"""Step 52.4 -- identity safety fields verifier.

Asserts /operations/safety carries the expected read-only identity fields with a
non-production, fail-closed posture: production ready/auth/oidc all false, no
discovery/JWKS/callback/token-exchange, unknown user deny, default role none,
platform_admin no auto-grant / no infra authority, break-glass disabled,
production_executed_true_count=0.

Marker: IDENTITY_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

EXPECT_FALSE = [
    "identity_production_ready",
    "identity_production_auth_enabled",
    "identity_test_local_production_allowed",
    "identity_oidc_configured",
    "identity_oidc_enabled",
    "identity_oidc_production_enabled",
    "identity_oidc_discovery_fetched",
    "identity_oidc_jwks_fetched",
    "identity_oidc_callback_enabled",
    "identity_oidc_token_exchange_enabled",
    "identity_oidc_real_provider_configured",
    "identity_oidc_secret_committed",
    "identity_session_raw_token_persisted",
    "identity_session_concurrency_enforced",
    "identity_session_key_rotation_ready",
    "identity_session_production_secret_store_configured",
    "identity_role_mapping_configured",
    "identity_platform_admin_auto_grant",
    "identity_frontend_role_authority",
    "identity_break_glass_enabled",
    "identity_break_glass_route_present",
    "identity_human_acceptance_is_deployment",
    "identity_platform_admin_infrastructure_authority",
]
EXPECT_TRUE = [
    "identity_posture_enabled",
    "identity_test_local_enabled",
    "identity_oidc_abstraction_enabled",
    "identity_session_hardened",
    "identity_session_cleanup_available",
    "identity_session_forced_logout_supported",
    "identity_role_mapping_engine_present",
    "identity_break_glass_requires_future_approval",
    "identity_verification_rerun_allowlisted_only",
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
        print("IDENTITY_SAFETY_FIELDS_VERIFY: FAIL")
        return 1

    all_fields = (
        EXPECT_FALSE
        + EXPECT_TRUE
        + [
            "identity_posture_status",
            "identity_unknown_user_behavior",
            "identity_default_role",
            "production_executed_true_count",
        ]
    )
    missing = [f for f in all_fields if f not in data]
    if missing:
        bad(f"missing identity safety fields: {missing}")
    else:
        ok(f"all {len(all_fields)} expected identity safety fields present")

    for f in EXPECT_FALSE:
        if data.get(f) is not False:
            bad(f"{f} must be false, got {data.get(f)!r}")
    if not [x for x in failures if "must be false" in x]:
        ok("all production / oidc / break-glass / infra-authority fields are false")

    for f in EXPECT_TRUE:
        if data.get(f) is not True:
            bad(f"{f} must be true, got {data.get(f)!r}")
    if not [x for x in failures if "must be true" in x]:
        ok("posture/test-local/abstraction/session-hardening/engine/rerun fields are true")

    if data.get("identity_posture_status") not in ("modeled_fail_closed_not_enabled", "unknown"):
        bad(f"identity_posture_status unexpected: {data.get('identity_posture_status')}")
    if data.get("identity_unknown_user_behavior") != "deny":
        bad("identity_unknown_user_behavior must be deny")
    if data.get("identity_default_role") != "none":
        bad("identity_default_role must be none")
    if data.get("production_executed_true_count") not in (0, None):
        bad(
            f"production_executed_true_count must be 0, got {data.get('production_executed_true_count')}"
        )
    if not [
        x
        for x in failures
        if "status" in x or "behavior" in x or "default_role" in x or "production_executed" in x
    ]:
        ok("posture status modeled/unknown; unknown user deny; default none; prod_executed=0")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("IDENTITY_SAFETY_FIELDS_VERIFY: FAIL")
        return 1
    print("IDENTITY_SAFETY_FIELDS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
