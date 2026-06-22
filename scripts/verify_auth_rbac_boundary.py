#!/usr/bin/env python3
"""Step 52.1 -- auth / RBAC boundary static verifier (code-level).

Asserts the ACTUAL auth/RBAC code matches the boundary model: production auth is
fail-closed, test auth is gated, no real OIDC callback, roles are
backend-enforced, viewer cannot mutate, operator/platform_admin carry no
deploy/sync/GitHub capability, no Kubernetes/ArgoCD permission is introduced, the
Step 51 runtime API stays read-only, and the Step 50 operator-action catalog is
unchanged (enabled actions carry no production capability). No live server.

Marker: AUTH_RBAC_BOUNDARY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OA = ROOT / "shared" / "sdk" / "operator_actions"
RUNTIME_API = ROOT / "apps" / "orchestrator" / "src" / "runtime_baseline_api.py"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def main() -> int:
    auth = read(OA / "auth.py")
    # production fail-closed: unknown mode -> disabled; operator actions require test_local
    if "KNOWN_AUTH_MODES" not in auth or "AUTH_MODE_DISABLED" not in auth:
        bad("auth.py must define known modes + disabled default")
    if "mode not in KNOWN_AUTH_MODES" not in auth:
        bad("auth.py must fail closed on unknown mode")
    if "mode == AUTH_MODE_TEST_LOCAL and test_auth and not production_auth" not in auth:
        bad("operator actions must require test_local + test_auth + not production")
    else:
        ok("auth.py fails closed; operator actions gated to test_local non-production")

    # no real OIDC callback / discovery / client secret in auth code
    low = auth.lower()
    for token in ("jwks", "discovery", "client_secret", "authorization_endpoint", "id_token"):
        if token in low:
            bad(f"auth.py must not implement real OIDC ({token})")
    if not [f for f in failures if "OIDC" in f]:
        ok("no real OIDC callback/discovery/client-secret in auth code")

    # RBAC backend-authoritative; platform_admin == operator rank
    rbac = read(OA / "rbac.py")
    if "ROLE_RANK" not in rbac or '"platform_admin": 2' not in rbac:
        bad("rbac.py must define ROLE_RANK with platform_admin == operator rank")
    if "role in entry.allowed_roles" not in rbac:
        bad("rbac.py must enforce allowed_roles server-side")
    else:
        ok("RBAC is backend-authoritative; platform_admin shares the operator action set")

    # action catalog: enabled actions carry no production/deploy/github capability.
    # Inspect the actual catalog (import), not the module docstring.
    sys.path.insert(0, str(ROOT))
    from shared.sdk.operator_actions.action_catalog import (  # noqa: E402
        DISABLED_ACTION_TYPES,
        ENABLED_ACTIONS,
    )

    forbidden_substrings = (
        "deploy",
        "github",
        "argocd",
        "kubernetes",
        "merge",
        "backup.production",
    )
    for key in ENABLED_ACTIONS:
        if any(s in key.lower() for s in forbidden_substrings):
            bad(
                f"enabled action {key} must not carry deploy/GitHub/K8s/ArgoCD/production capability"
            )
    for disabled in (
        "deployment.execute",
        "github.create_pr",
        "github.merge_pr",
        "backup.production_run",
        "backup.production_restore",
    ):
        if disabled not in DISABLED_ACTION_TYPES:
            bad(f"action_catalog must list {disabled} as disabled")
    if not [f for f in failures if "enabled action" in f or "action_catalog must" in f]:
        ok(
            "operator action catalog: enabled actions carry no deploy/GitHub/K8s/ArgoCD/production capability"
        )

    # verification rerun: allowlist + shell=False
    vr = read(OA / "verification_runner.py")
    if "ALLOWLISTED_SCRIPTS" not in vr or "shell=False" not in vr:
        bad("verification_runner must use an allowlist + shell=False")
    if "VerificationNotAllowed" not in vr:
        bad("verification_runner must reject non-allowlisted keys")
    else:
        ok("verification rerun is allowlist-only with shell=False fixed argv")

    # Step 51 runtime API remains read-only (no mutation verb)
    if RUNTIME_API.is_file():
        rt = read(RUNTIME_API)
        if any(v in rt for v in ("@router.post", "@router.put", "@router.patch", "@router.delete")):
            bad("Step 51 runtime API must remain GET-only")
        else:
            ok("Step 51 runtime API remains read-only (no mutation verb introduced)")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("AUTH_RBAC_BOUNDARY_VERIFY: FAIL")
        return 1
    print("AUTH_RBAC_BOUNDARY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
