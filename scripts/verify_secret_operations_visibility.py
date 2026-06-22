#!/usr/bin/env python3
"""Step 53 -- secret operations visibility verifier.

Asserts the read-only /operations/secrets/* API is reachable, GET-only, exposes
no read-value / write / rotate / configure-provider endpoint, reports a
non-production fail-closed posture, and never leaks a secret. Combines a live
HTTP check with a source guard over secret_posture_api.py.

Marker: SECRET_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
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
API_SRC = ROOT / "apps" / "orchestrator" / "src" / "secret_posture_api.py"
BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")
GET_ENDPOINTS = [
    "/operations/secrets/foundation",
    "/operations/secrets/inventory",
    "/operations/secrets/classification",
    "/operations/secrets/ownership",
    "/operations/secrets/references",
    "/operations/secrets/lifecycle",
    "/operations/secrets/rotation",
    "/operations/secrets/access-boundary",
    "/operations/secrets/audit-model",
    "/operations/secrets/redaction",
    "/operations/secrets/usage",
    "/operations/secrets/readiness",
    "/operations/secrets/report",
]
SECRET_PAT = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.|kubeconfig:)",
)
FORBIDDEN = [
    "/operations/secrets/read",
    "/operations/secrets/value",
    "/operations/secrets/write",
    "/operations/secrets/rotate",
    "/operations/secrets/configure",
    "/operations/secrets/provider",
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
    src = API_SRC.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        if verb in src:
            bad(f"secret API must not define {verb}")
    route_lines = [ln for ln in src.splitlines() if ln.strip().startswith("@router.")]
    forbidden = {"read", "value", "write", "rotate", "configure", "provider", "reveal"}
    for ln in route_lines:
        m = re.search(r"@router\.\w+\(\s*[\"']([^\"']*)", ln)
        tokens = set(re.split(r"[/_-]", (m.group(1) if m else "").lower()))
        hit = (
            forbidden & tokens
        )  # 'readiness'/'rotation' tokenize to themselves, not 'read'/'rotate'
        if hit:
            bad(f"secret API route exposes a forbidden operation ({hit}): {ln.strip()}")
    if "subprocess" in src or "hvac" in src:
        bad("secret API must not use subprocess / a real store client")
    if not failures:
        ok("secret API source is GET-only; no read-value/write/rotate/configure route")

    status0, _ = _get("/operations/secrets/readiness")
    if status0 == 0:
        bad(f"orchestrator not reachable at {BASE} (secret endpoints require the live stack)")
        print("SECRET_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    for path in GET_ENDPOINTS:
        code, body = _get(path)
        if code != 200:
            bad(f"GET {path} returned {code}")
            continue
        if SECRET_PAT.search(body):
            bad(f"GET {path} leaked a secret-like value")
    if not [f for f in failures if "GET " in f or "leaked" in f]:
        ok(f"all {len(GET_ENDPOINTS)} secret GET endpoints return 200 with no secret leak")

    for path in FORBIDDEN:
        code, _ = _get(path)
        if code == 200:
            bad(f"forbidden secret endpoint exists: {path}")
    if not [f for f in failures if "forbidden secret" in f]:
        ok("no read-value/write/rotate/configure-provider endpoint exists")

    code, body = _get("/operations/secrets/readiness")
    data = json.loads(body) if code == 200 and body else {}
    if data.get("productionReady") is not False:
        bad("secret readiness productionReady must be false")
    if data.get("status") not in ("modeled_fail_closed_not_configured", "unknown"):
        bad(f"secret status unexpected: {data.get('status')}")
    if not [f for f in failures if "readiness" in f or "status" in f]:
        ok("secret foundation is modeled_fail_closed_not_configured; production NOT ready")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECRET_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    print("SECRET_OPERATIONS_VISIBILITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
