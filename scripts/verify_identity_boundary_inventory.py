#!/usr/bin/env python3
"""Step 52.1 -- identity boundary inventory verifier (source-level).

Validates the infra/identity inventories: required files exist + parse,
test-local auth is non-production, production auth + OIDC disabled/unconfigured,
no raw session token persistence, no localStorage token, the 4-role matrix with
platform_admin carrying no infrastructure authority, human acceptance != deploy,
verification rerun allowlist-only, and no secret-like value in any identity file.

Marker: IDENTITY_BOUNDARY_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"
REQUIRED = [
    "authentication-inventory.yaml",
    "session-inventory.yaml",
    "csrf-inventory.yaml",
    "rbac-inventory.yaml",
    "operator-action-authorization.yaml",
    "identity-boundary-model.yaml",
    "auth-boundary-policy.yaml",
    "identity-audit-mapping.yaml",
    "human-acceptance-identity-boundary.yaml",
    "verification-rerun-identity-boundary.yaml",
    "production-oidc-prerequisites.yaml",
    "identity-risk-register.yaml",
    "identity-policy-catalog.yaml",
]
INFRA_PERMS = {
    "deploy",
    "sync",
    "github_write",
    "pr",
    "argocd_sync",
    "kubernetes_apply",
    "production_backup",
    "production_restore",
    "root",
    "production",
}
SECRET = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|"
    r"(client_secret|clientsecret|password|secret_key|signing_secret|refresh_token)\s*[:=]\s*[A-Za-z0-9/+=._-]{6,})",
    re.IGNORECASE,
)

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
            bad(f"missing identity file: {rel}")
        else:
            try:
                yaml.safe_load(p.read_text(encoding="utf-8"))
            except yaml.YAMLError as e:
                bad(f"{rel} does not parse: {e}")
    if not failures:
        ok(f"all {len(REQUIRED)} identity inventory files exist and parse")

    auth = load("authentication-inventory.yaml")
    modes = {m["key"]: m for m in auth["authenticationModes"]}
    if modes["test_local_signed_session"]["productionAllowed"] is not False:
        bad("test-local auth must have productionAllowed=false")
    if modes["test_local_signed_session"]["environmentEligibility"]["production"] != "forbidden":
        bad("test-local auth must be forbidden in production")
    if auth["meta"]["productionAuthEnabled"] is not False:
        bad("production auth must be disabled")
    if auth["meta"]["oidcConfigured"] is not False:
        bad("OIDC must be unconfigured")
    if auth["behaviors"]["frontendLocalStorageToken"] is not False:
        bad("frontend must not store token in localStorage")
    if auth["behaviors"]["urlToken"] is not False:
        bad("token must not appear in URL")
    if not failures:
        ok("test-local non-production; production auth + OIDC disabled; no localStorage/URL token")

    sess = load("session-inventory.yaml")
    if sess["sessions"]["serverSide"]["rawTokenPersisted"] is not False:
        bad("raw session token must not be persisted")
    if sess["sessions"]["serverSide"]["tokenHashPersisted"] is not True:
        bad("session token hash must be persisted (sha256)")
    else:
        ok("session stores hash only; no raw session token persisted")

    rbac = load("rbac-inventory.yaml")
    roles = {r["key"] for r in rbac["roles"]}
    if roles != {"viewer", "reviewer", "operator", "platform_admin"}:
        bad(f"role set unexpected: {roles}")
    pa = next(r for r in rbac["roles"] if r["key"] == "platform_admin")
    if INFRA_PERMS & set(pa.get("permissions", [])):
        bad("platform_admin must not have infrastructure/deploy permissions")
    if pa["productionAuthority"] != "none":
        bad("platform_admin productionAuthority must be none")
    if not [f for f in failures if "role" in f or "platform_admin" in f]:
        ok(
            "role matrix has viewer/reviewer/operator/platform_admin; platform_admin has no infra authority"
        )

    ha = load("human-acceptance-identity-boundary.yaml")["humanAcceptance"]
    if ha["isProductionApproval"] is not False or "deploy" not in ha["acceptanceDoesNot"]:
        bad("human acceptance must not be deployment/production approval")
    else:
        ok("human acceptance is not deployment / production approval")

    vr = load("verification-rerun-identity-boundary.yaml")["verificationRerun"]
    if (
        vr["execution"]["shell"] is not False
        or vr["execution"]["arbitraryCommandProhibited"] is not True
    ):
        bad("verification rerun must be allowlist-only, no shell, no arbitrary command")
    else:
        ok("verification rerun is allowlist-only with no shell/arbitrary command")

    oidc = load("production-oidc-prerequisites.yaml")
    prov = oidc["oidcPrerequisites"]["provider"]
    if any(
        prov[k]["configured"]
        for k in ("issuerUrl", "jwksUri", "clientId", "clientSecret", "redirectUris")
    ):
        bad("OIDC provider prerequisites must all be unconfigured")
    else:
        ok("OIDC prerequisites listed but unconfigured (no issuer/JWKS/client/secret)")

    # risk register + policy catalog non-empty
    if not load("identity-risk-register.yaml").get("risks"):
        bad("risk register must list risks")
    if not load("identity-policy-catalog.yaml").get("policies"):
        bad("policy catalog must list policies")
    if not [f for f in failures if "register" in f or "catalog" in f]:
        ok("risk register + policy catalog present and non-empty")

    # secret scan across all identity files
    hit = False
    for p in IDENT.glob("*.yaml"):
        for ln in p.read_text(encoding="utf-8").splitlines():
            if SECRET.search(ln):
                bad(f"secret-like value in {p.name}: {ln.strip()[:60]}")
                hit = True
    if not hit:
        ok("no secret-like / token-like values in identity files")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("IDENTITY_BOUNDARY_INVENTORY_VERIFY: FAIL")
        return 1
    print("IDENTITY_BOUNDARY_INVENTORY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
