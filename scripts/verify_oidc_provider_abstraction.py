#!/usr/bin/env python3
"""Step 52.2 -- OIDC provider abstraction verifier (source-level, NO network).

Validates that the OIDC abstraction + disabled production config exist, parse,
and describe a disabled/unconfigured production provider: no real issuer, client
ID, client secret literal, redirect URI; discovery/JWKS fetch off; unknown user
denied; platform_admin not auto-granted; role claim not authoritative; callback
disabled; token validation inactive. Performs NO network call.

Marker: OIDC_PROVIDER_ABSTRACTION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"
sys.path.insert(0, str(ROOT))  # noqa: E402

from shared.sdk.identity import load_oidc_config  # noqa: E402

REQUIRED = [
    "oidc-provider-catalog.yaml",
    "production-oidc-disabled-config.yaml",
    "oidc-discovery-contract.yaml",
    "jwks-reference-model.yaml",
    "oidc-claim-contract.yaml",
    "oidc-role-mapping-contract.yaml",
    "oidc-callback-boundary.yaml",
    "oidc-state-nonce-pkce-contract.yaml",
    "oidc-token-validation-boundary.yaml",
    "oidc-safety-policy-catalog.yaml",
]

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def load(name: str) -> dict:
    return yaml.safe_load((IDENT / name).read_text(encoding="utf-8"))


def main() -> int:
    for rel in REQUIRED:
        p = IDENT / rel
        if not p.is_file():
            bad(f"missing OIDC file: {rel}")
        else:
            try:
                yaml.safe_load(p.read_text(encoding="utf-8"))
            except yaml.YAMLError as e:
                bad(f"{rel} does not parse: {e}")
    if not failures:
        ok(f"all {len(REQUIRED)} OIDC files exist and parse")

    prov = load("oidc-provider-catalog.yaml")["providers"]["production-oidc-placeholder"]
    if prov["enabled"] is not False:
        bad("provider enabled must be false")
    if prov["productionAllowed"] is not False:
        bad("provider productionAllowed must be false")
    if prov["configured"] is not False:
        bad("provider configured must be false")
    if prov["status"] != "disabled_unconfigured":
        bad("provider status must be disabled_unconfigured")
    if prov["issuer"]["value"]:
        bad("provider issuer must be empty (no real issuer)")
    if prov["discovery"]["fetchEnabled"] is not False:
        bad("discovery fetch must be disabled")
    if prov["jwks"]["fetchEnabled"] is not False:
        bad("JWKS fetch must be disabled")
    if prov["client"]["clientId"]["valueRef"]:
        bad("client ID must be empty (no real client ID)")
    cs = prov["client"]["clientSecret"]["secretRef"]
    if cs["name"] or cs["key"]:
        bad("client secret ref must be empty (no real secret)")
    if prov["redirectUris"]["values"]:
        bad("redirect URIs must be empty (no real redirect URI)")
    if not failures:
        ok("provider disabled/unconfigured: no real issuer/client/secret/redirect; fetch off")

    disabled = load("production-oidc-disabled-config.yaml")
    a = disabled["auth"]
    if a["enabled"] or a["productionEnabled"] or a["testLocalFallbackAllowed"]:
        bad("disabled config: enabled/productionEnabled/testLocalFallbackAllowed must be false")
    if a["failClosed"] is not True:
        bad("disabled config failClosed must be true")
    if disabled["status"]["ready"] is not False:
        bad("disabled config ready must be false")
    else:
        ok("disabled production config is enabled=false, failClosed=true, ready=false")

    rm = load("oidc-role-mapping-contract.yaml")["roleMapping"]
    if rm["unknownUserBehavior"] != "deny":
        bad("role mapping unknown user behavior must be deny")
    if rm["defaultRole"] != "none":
        bad("role mapping default role must be none")
    forb = load("oidc-role-mapping-contract.yaml")["forbiddenAutoGrant"]
    if "platform_admin" not in forb:
        bad("platform_admin must be forbidden from auto-grant")
    else:
        ok("unknown user denied; default role none; platform_admin auto-grant forbidden")

    claim = load("oidc-claim-contract.yaml")
    if claim["frontendRoleAuthority"] is not False:
        bad("frontend role authority must be false")
    if not {"role", "is_admin", "platform_admin"} <= set(claim["forbiddenClaimsAsAuthority"]):
        bad("role/is_admin/platform_admin must be forbidden as authority claims")
    for c in ("subject", "email", "emailVerified", "groups"):
        if c not in claim["requiredClaims"]:
            bad(f"claim contract missing required claim: {c}")
    if not [f for f in failures if "claim" in f or "authority" in f]:
        ok(
            "claim contract: token role claim not authoritative; sub/email/email_verified/groups required"
        )

    cb = load("oidc-callback-boundary.yaml")["callback"]
    if cb["enabled"] is not False or cb["authorizationCodeExchange"] is not False:
        bad("callback must be disabled with no code exchange")
    else:
        ok("callback disabled; no authorization-code exchange")

    tv = load("oidc-token-validation-boundary.yaml")["tokenValidation"]
    if tv["enabled"] is not False or tv["realTokenValidationPerformed"] is not False:
        bad("token validation must be inactive")
    else:
        ok("token validation inactive (no real token validated)")

    # config loader must parse all files and report disabled_unconfigured
    res = load_oidc_config(ROOT)
    if res.status != "disabled_unconfigured":
        bad(f"config loader status must be disabled_unconfigured, got {res.status}")
    elif res.errors:
        bad(f"config loader reported errors: {res.errors}")
    else:
        ok("config loader parses all files; status=disabled_unconfigured; no errors")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("OIDC_PROVIDER_ABSTRACTION_VERIFY: FAIL")
        return 1
    print("OIDC_PROVIDER_ABSTRACTION_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
