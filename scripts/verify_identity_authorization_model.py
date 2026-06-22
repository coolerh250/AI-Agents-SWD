#!/usr/bin/env python3
"""Step 52.3 -- identity authorization decision model verifier (NO network).

Validates the authorization decision chain is defined with the required
separations: role mapping != RBAC, RBAC != policy approval, confirmation !=
permission, human acceptance != deployment, platform_admin != infrastructure
admin, and production actions are future-gated / not currently executable.

Marker: IDENTITY_AUTHORIZATION_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    f = IDENT / "identity-authorization-decision-model.yaml"
    if not f.is_file():
        bad("missing identity-authorization-decision-model.yaml")
        print("IDENTITY_AUTHORIZATION_MODEL_VERIFY: FAIL")
        return 1
    m = yaml.safe_load(f.read_text(encoding="utf-8"))

    stages = [s["stage"] for s in m["decisionChain"]]
    for required in (
        "authentication",
        "role_mapping",
        "rbac",
        "policy_engine",
        "confirmation",
        "idempotency",
        "audit",
        "final_authorization",
    ):
        if required not in stages:
            bad(f"decision chain missing stage: {required}")
    if not failures:
        ok(f"authorization decision chain defined ({len(stages)} stages)")

    sep = m["separations"]
    for k in (
        "roleMappingIsNotRbac",
        "rbacIsNotPolicyApproval",
        "confirmationIsNotPermission",
        "humanAcceptanceIsNotDeploymentApproval",
        "platformAdminIsNotInfrastructureAdmin",
    ):
        if sep[k] is not True:
            bad(f"separation {k} must be true")
    if not [x for x in failures if "separation" in x]:
        ok(
            "role mapping != RBAC != policy approval; confirmation != permission; "
            "human acceptance != deployment; platform_admin != infrastructure admin"
        )

    pa = m["productionActions"]
    if (
        pa["requireFutureProductionApprovalGate"] is not True
        or pa["currentlyExecutable"] is not False
    ):
        bad("production actions must be future-gated and not currently executable")
    else:
        ok("production actions future-gated; not currently executable")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("IDENTITY_AUTHORIZATION_MODEL_VERIFY: FAIL")
        return 1
    print("IDENTITY_AUTHORIZATION_MODEL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
