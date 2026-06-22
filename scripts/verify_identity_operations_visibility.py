#!/usr/bin/env python3
"""Step 52.4 -- identity operations visibility verifier.

Asserts the read-only /operations/identity/* API is reachable, GET-only, exposes
no login/callback/authorize/token/logout/role-mapping-mutation/break-glass
endpoint, reports a non-production fail-closed posture, and never leaks a secret /
raw email / real group ID. Combines a live HTTP check with a source-level guard
over identity_posture_api.py. No IdP connection, no verifier execution.

Marker: IDENTITY_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "orchestrator" / "src" / "identity_posture_api.py"
BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")
GET_ENDPOINTS = [
    "/operations/identity/posture",
    "/operations/identity/authentication",
    "/operations/identity/session",
    "/operations/identity/csrf",
    "/operations/identity/rbac",
    "/operations/identity/operator-actions",
    "/operations/identity/oidc",
    "/operations/identity/role-mapping",
    "/operations/identity/break-glass",
    "/operations/identity/audit-mapping",
    "/operations/identity/risks",
    "/operations/identity/readiness",
    "/operations/identity/report",
]
SECRET_PAT = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.|"
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b)",
)
# forbidden identity mutation / auth-flow endpoints that must NOT exist
FORBIDDEN = [
    "/operations/identity/login",
    "/operations/identity/callback",
    "/operations/identity/authorize",
    "/operations/identity/token",
    "/operations/identity/logout",
    "/operations/identity/connect",
    "/operations/identity/role-mapping/apply",
    "/operations/identity/break-glass/activate",
]

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _get(path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=8) as resp:  # noqa: S310
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError):
        return 0, ""


def main() -> int:
    # 1. source-level: API is GET-only with no auth-flow / mutation routes.
    src = API_SRC.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        if verb in src:
            bad(f"identity API must not define {verb}")
    route_lines = [ln for ln in src.splitlines() if ln.strip().startswith("@router.")]
    for ln in route_lines:
        for word in (
            "login",
            "callback",
            "authorize",
            "token",
            "logout",
            "connect",
            "apply",
            "activate",
        ):
            if word in ln.lower():
                bad(f"identity API route exposes a forbidden operation ({word}): {ln.strip()}")
    if "subprocess" in src or "requests" in src or "httpx" in src:
        bad("identity API must not use subprocess / an HTTP client")
    if not failures:
        ok("identity API source is GET-only; no login/callback/token/connect/mutation route")

    # 2. live endpoints
    status0, _ = _get("/operations/identity/readiness")
    if status0 == 0:
        bad(f"orchestrator not reachable at {BASE} (identity endpoints require the live stack)")
        print("IDENTITY_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    for path in GET_ENDPOINTS:
        code, body = _get(path)
        if code != 200:
            bad(f"GET {path} returned {code}")
            continue
        if SECRET_PAT.search(body):
            bad(f"GET {path} leaked a secret / raw email / group ID")
    if not [f for f in failures if "GET " in f or "leaked" in f]:
        ok(f"all {len(GET_ENDPOINTS)} identity GET endpoints return 200 with no secret leak")

    # 3. forbidden mutation / auth-flow endpoints must NOT exist
    for path in FORBIDDEN:
        code, _ = _get(path)
        if code == 200:
            bad(f"forbidden identity endpoint exists: {path}")
    if not [f for f in failures if "forbidden identity" in f]:
        ok("no login/callback/token/connect/role-mapping-mutation/break-glass endpoint exists")

    # 4. posture + readiness
    code, body = _get("/operations/identity/readiness")
    data = json.loads(body) if code == 200 and body else {}
    if data.get("productionIdentityReady") is not False:
        bad("identity readiness productionIdentityReady must be false")
    if data.get("productionAuthEnabled") is not False:
        bad("identity readiness productionAuthEnabled must be false")
    if data.get("oidcEnabled") is not False:
        bad("identity readiness oidcEnabled must be false")
    if data.get("status") not in ("modeled_fail_closed_not_enabled", "unknown"):
        bad(f"identity status unexpected: {data.get('status')}")
    if not [f for f in failures if "readiness" in f or "status" in f]:
        ok("identity posture is modeled_fail_closed_not_enabled; production identity NOT ready")

    # 5. safety posture: production_executed_true_count must be 0
    code, body = _get("/operations/safety")
    sdata = json.loads(body) if code == 200 and body else {}
    if sdata.get("identity_production_ready") is not False:
        bad("identity_production_ready must be false in /operations/safety")
    if sdata.get("production_executed_true_count") not in (0, None):
        bad(
            f"production_executed_true_count must be 0, got {sdata.get('production_executed_true_count')}"
        )
    if not [f for f in failures if "identity_production_ready" in f or "production_executed" in f]:
        ok("/operations/safety: identity_production_ready=false; production_executed_true_count=0")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("IDENTITY_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    print("IDENTITY_OPERATIONS_VISIBILITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
