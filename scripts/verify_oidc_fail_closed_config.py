#!/usr/bin/env python3
"""Step 52.2 -- OIDC fail-closed config verifier (NO network).

Confirms the committed production OIDC config is disabled and that the validator
rejects every unsafe shape: production-enabled, test-local fallback, missing
required fields while enabled, a client-secret literal, unknown-user=allow, a
privileged default role, and discovery/JWKS/callback enabled.

Marker: OIDC_FAIL_CLOSED_CONFIG_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # noqa: E402

from shared.sdk.identity import load_oidc_config, validate_oidc_inputs  # noqa: E402

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


# A baseline of safe primitive inputs; each fixture overrides one field.
_BASE = dict(
    enabled=False,
    production_enabled=False,
    test_local_fallback_allowed=False,
    required_satisfied=False,
    any_required_configured=False,
    unknown_user_behavior="deny",
    default_role="none",
    discovery_fetch_enabled=False,
    jwks_fetch_enabled=False,
    callback_enabled=False,
    raw_text="",
)


def expect_invalid(name: str, **overrides: object) -> None:
    res = validate_oidc_inputs(**{**_BASE, **overrides})  # type: ignore[arg-type]
    if res.status == "invalid":
        ok(f"fixture rejected (invalid): {name}")
    else:
        bad(f"fixture should be invalid but got {res.status}: {name}")


def main() -> int:
    # Committed production config must be disabled / not ready.
    res = load_oidc_config(ROOT)
    if res.status == "disabled_unconfigured" and not res.ready and not res.production_enabled:
        ok("committed production OIDC config is disabled_unconfigured and not ready")
    else:
        bad(f"committed config unexpected: status={res.status} ready={res.ready}")

    expect_invalid("production_enabled=true", production_enabled=True)
    expect_invalid("test_local_fallback_allowed=true", test_local_fallback_allowed=True)
    expect_invalid("enabled without required fields", enabled=True, required_satisfied=False)
    expect_invalid("client_secret literal", raw_text="client_secret: hunter2supersecret")
    expect_invalid("unknown_user_behavior=allow", unknown_user_behavior="allow")
    expect_invalid("default_role=operator", default_role="operator")
    expect_invalid("default_role=platform_admin", default_role="platform_admin")
    expect_invalid("discovery fetch enabled", discovery_fetch_enabled=True)
    expect_invalid("JWKS fetch enabled", jwks_fetch_enabled=True)
    expect_invalid("callback enabled", callback_enabled=True)

    # Sanity: the safe baseline itself must NOT be invalid.
    base_res = validate_oidc_inputs(**_BASE)  # type: ignore[arg-type]
    if base_res.status == "disabled_unconfigured":
        ok("safe baseline validates as disabled_unconfigured (not over-rejecting)")
    else:
        bad(f"safe baseline unexpectedly {base_res.status}")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("OIDC_FAIL_CLOSED_CONFIG_VERIFY: FAIL")
        return 1
    print("OIDC_FAIL_CLOSED_CONFIG_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
