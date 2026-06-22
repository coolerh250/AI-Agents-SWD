#!/usr/bin/env python3
"""Step 52.3 -- unknown user policy verifier (NO network).

Validates the unknown-user policy + that the engine denies every unsafe claim
shape: missing sub/email, unverified email, no groups, unknown group, a token
role claim, and a frontend-supplied role; no default role; no auto-provision.

Marker: UNKNOWN_USER_POLICY_VERIFY: PASS | FAIL
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
    load_rules,
    load_safe_fixture,
    map_identity_to_role,
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
    if not (IDENT / "unknown-user-policy.yaml").is_file():
        bad("missing unknown-user-policy.yaml")
    else:
        u = yaml.safe_load((IDENT / "unknown-user-policy.yaml").read_text(encoding="utf-8"))[
            "unknownUser"
        ]
        for k in (
            "missingSubject",
            "missingEmail",
            "emailNotVerified",
            "missingGroups",
            "noGroupMatch",
        ):
            if u["denyRules"][k] != "deny":
                bad(f"unknown-user denyRules.{k} must be deny")
        if u["defaultRole"] != "none":
            bad("unknown-user defaultRole must be none")
        for k in (
            "autoViewer",
            "selfRegistration",
            "justInTimeProvisioning",
            "platformAdminFallback",
            "tokenRoleClaimAuthority",
        ):
            if u[k] is not False:
                bad(f"unknown-user {k} must be false")
        if not failures:
            ok("unknown-user policy: all deny rules + no default/auto-provision/fallback")

    rules = load_rules(load_safe_fixture())

    cases = {
        "missing_subject": IdentityClaims(
            email="a@example.com", email_verified=True, groups=["group-viewer-placeholder"]
        ),
        "missing_email": IdentityClaims(
            subject="s", email_verified=True, groups=["group-viewer-placeholder"]
        ),
        "email_not_verified": IdentityClaims(
            subject="s", email="a@example.com", groups=["group-viewer-placeholder"]
        ),
        "missing_groups": IdentityClaims(subject="s", email="a@example.com", email_verified=True),
        "unknown_group": IdentityClaims(
            subject="s", email="a@example.com", email_verified=True, groups=["unknown-group"]
        ),
    }
    for label, claims in cases.items():
        d = map_identity_to_role(claims, rules)
        if d.allowed or d.role is not None:
            bad(f"engine must deny case: {label}")
    if not [f for f in failures if "case" in f]:
        ok("engine denies missing sub/email, unverified email, no groups, unknown group")

    # a token role claim cannot be supplied to the engine (IdentityClaims has no role field)
    if "role" in IdentityClaims.model_fields or "is_admin" in IdentityClaims.model_fields:
        bad("IdentityClaims must not carry a role/is_admin field")
    else:
        ok("token role claim is structurally impossible (IdentityClaims has no role field)")

    # frontend-supplied role: even a 'role'-looking group never grants without an explicit rule
    d = map_identity_to_role(
        IdentityClaims(
            subject="s",
            email="a@example.com",
            email_verified=True,
            groups=["platform_admin"],
            provider_key="p",
        ),
        rules,
    )
    if d.allowed:
        bad("a frontend-supplied 'platform_admin' group must not grant a role")
    else:
        ok("frontend-supplied role-like group is not authoritative (denied)")

    # audit records denied attempt without raw token (policy declares it)
    audit = yaml.safe_load((IDENT / "unknown-user-policy.yaml").read_text(encoding="utf-8"))[
        "audit"
    ]
    if audit["deniedAttemptRecorded"] is True and audit["rawTokenRecorded"] is False:
        ok("denied attempt is auditable without raw token")
    else:
        bad("denied attempt must be auditable without raw token")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("UNKNOWN_USER_POLICY_VERIFY: FAIL")
        return 1
    print("UNKNOWN_USER_POLICY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
