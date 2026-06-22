#!/usr/bin/env python3
"""Step 52.3 -- role mapping policy verifier (NO network, local fixtures only).

Validates the role mapping engine + policy: default role none, unknown user
deny, frontend role authority false, platform_admin requires explicit mapping,
no wildcard groups, no real group IDs, safe fixture maps only placeholder
groups, unsafe rule sets fail validation.

Marker: ROLE_MAPPING_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"
sys.path.insert(0, str(ROOT))  # noqa: E402

from shared.sdk.identity import (  # noqa: E402
    IdentityClaims,
    RoleMappingRule,
    load_rules,
    load_safe_fixture,
    map_identity_to_role,
    validate_rules,
)

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for n in ("role-mapping-policy.yaml", "unknown-user-policy.yaml"):
        if not (IDENT / n).is_file():
            bad(f"missing file: {n}")
    if not (IDENT / "test-fixtures" / "role-mapping-safe-fixture.yaml").is_file():
        bad("missing safe role-mapping fixture")
    try:
        from shared.sdk.identity import map_identity_to_role as _m  # noqa: F401

        ok("role mapping engine + policy + safe fixture present")
    except Exception as e:  # noqa: BLE001
        bad(f"role mapping engine missing: {e}")

    pol = yaml.safe_load((IDENT / "role-mapping-policy.yaml").read_text(encoding="utf-8"))[
        "roleMapping"
    ]
    if pol["defaultRole"] != "none":
        bad("policy default role must be none")
    if pol["unknownUserBehavior"] != "deny":
        bad("policy unknown user behavior must be deny")
    if pol["frontendRoleAuthority"] is not False:
        bad("policy frontend role authority must be false")
    if set(pol["requiresExplicitMapping"]) != {"viewer", "reviewer", "operator", "platform_admin"}:
        bad("all 4 roles must require explicit mapping")
    fb = pol["forbidden"]
    if not all(
        fb[k]
        for k in (
            "wildcardGroups",
            "defaultOperator",
            "defaultPlatformAdmin",
            "tokenRoleClaimAuthority",
            "autoProvisionUsers",
        )
    ):
        bad("policy forbidden flags must all be true")
    if pol["rules"]:
        bad("production policy rules must be empty (unconfigured)")
    if not failures:
        ok(
            "default none; unknown deny; no frontend authority; explicit mapping; forbidden flags set; rules empty"
        )

    # safe fixture maps only placeholder groups; no real group IDs
    fixture = load_safe_fixture()
    rules = load_rules(fixture)
    if validate_rules(rules):
        bad(f"safe fixture failed validation: {validate_rules(rules)}")
    for r in rules:
        if "placeholder" not in r.match_group:
            bad(f"safe fixture rule uses non-placeholder group: {r.match_group}")
    # confirm a placeholder group maps to its role
    d = map_identity_to_role(
        IdentityClaims(
            subject="s",
            email="a@example.com",
            email_verified=True,
            groups=["group-platform-admin-placeholder"],
            provider_key="production-oidc-placeholder",
        ),
        rules,
    )
    if not (d.allowed and d.role == "platform_admin" and d.matched_rule):
        bad("safe fixture platform_admin placeholder mapping failed")
    if not [f for f in failures if "fixture" in f.lower()]:
        ok("safe fixture maps only placeholder groups; explicit platform_admin mapping works")

    # unsafe rule sets fail validation
    unsafe = [
        [RoleMappingRule(rule_id="w", match_group="*", role="platform_admin")],
        [RoleMappingRule(rule_id="w2", match_group=".*", role="operator")],
    ]
    if all(validate_rules(rs) for rs in unsafe):
        ok("unsafe (wildcard) rule sets are rejected by validate_rules")
    else:
        bad("a wildcard rule set was not rejected")

    # platform_admin never auto-granted: unknown group denies even with rules present
    deny = map_identity_to_role(
        IdentityClaims(
            subject="s",
            email="a@example.com",
            email_verified=True,
            groups=["totally-unknown"],
            provider_key="p",
        ),
        rules,
    )
    if deny.allowed or deny.role is not None:
        bad("unknown group must deny (no platform_admin auto-grant)")
    else:
        ok("unknown group denies; no default/auto-granted role")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ROLE_MAPPING_POLICY_VERIFY: FAIL")
        return 1
    print("ROLE_MAPPING_POLICY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
