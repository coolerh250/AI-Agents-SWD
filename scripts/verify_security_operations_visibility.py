#!/usr/bin/env python3
"""Step 54.1 -- security operations visibility verifier.

Asserts the read-only /operations/security/* API is reachable, GET-only, exposes
no run-scan / connect-scanner / upload-source / GitHub-write / image-push
endpoint, reports a non-production modeled_not_enforced posture, and never leaks
a secret. Combines a live HTTP check with a source guard over
security_posture_api.py.

Marker: SECURITY_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
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
API_SRC = ROOT / "apps" / "orchestrator" / "src" / "security_posture_api.py"
BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

GET_ENDPOINTS = [
    "/operations/security/foundation",
    "/operations/security/assets",
    "/operations/security/supply-chain",
    "/operations/security/dependencies",
    "/operations/security/scan-policies",
    "/operations/security/sast",
    "/operations/security/dependency-scan",
    "/operations/security/secret-scan",
    "/operations/security/sbom",
    "/operations/security/container-images",
    "/operations/security/threat-model",
    "/operations/security/release-risk",
    "/operations/security/evidence",
    "/operations/security/findings-taxonomy",
    "/operations/security/gate-policy",
    "/operations/security/readiness",
    "/operations/security/report",
]
SECRET_PAT = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.|kubeconfig:)",
)
FORBIDDEN = [
    "/operations/security/run-scan",
    "/operations/security/scan",
    "/operations/security/connect",
    "/operations/security/upload",
    "/operations/security/configure",
    "/operations/security/create-pr",
    "/operations/security/push-image",
    "/operations/security/gate-toggle",
]
# route-path tokens that would imply a mutating / external operation. NB: 'scan'
# is a legitimate read-only noun here (scan-policies, dependency-scan, secret-scan)
# so it is intentionally NOT forbidden; only mutating verbs are.
FORBIDDEN_TOKENS = {
    "run",
    "connect",
    "upload",
    "configure",
    "push",
    "create",
    "toggle",
    "login",
    "write",
    "delete",
    "sync",
    "deploy",
    "apply",
    "install",
    "provider",
    "reveal",
}

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
            bad(f"security API must not define {verb}")
    route_lines = [ln for ln in src.splitlines() if ln.strip().startswith("@router.")]
    for ln in route_lines:
        m = re.search(r"@router\.\w+\(\s*[\"']([^\"']*)", ln)
        tokens = set(re.split(r"[/_-]", (m.group(1) if m else "").lower()))
        hit = FORBIDDEN_TOKENS & tokens
        if hit:
            bad(f"security API route exposes a forbidden operation ({hit}): {ln.strip()}")
    if "subprocess" in src or "requests" in src or "httpx" in src:
        bad("security API must not use subprocess / an HTTP client (no scanner/registry call)")
    if not failures:
        ok("security API source is GET-only; no run-scan/connect/upload/push/create route")

    status0, _ = _get("/operations/security/readiness")
    if status0 == 0:
        bad(f"orchestrator not reachable at {BASE} (security endpoints require the live stack)")
        print("SECURITY_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    for path in GET_ENDPOINTS:
        code, body = _get(path)
        if code != 200:
            bad(f"GET {path} returned {code}")
            continue
        if SECRET_PAT.search(body):
            bad(f"GET {path} leaked a secret-like value")
    if not [f for f in failures if "GET " in f or "leaked" in f]:
        ok(f"all {len(GET_ENDPOINTS)} security GET endpoints return 200 with no secret leak")

    for path in FORBIDDEN:
        code, _ = _get(path)
        if code == 200:
            bad(f"forbidden security endpoint exists: {path}")
    if not [f for f in failures if "forbidden security" in f]:
        ok("no run-scan/connect-scanner/upload/create-PR/push-image endpoint exists")

    code, body = _get("/operations/security/readiness")
    data = json.loads(body) if code == 200 and body else {}
    if data.get("productionReady") is not False:
        bad("security readiness productionReady must be false")
    if data.get("status") not in ("modeled_not_enforced", "unknown"):
        bad(f"security status unexpected: {data.get('status')}")
    if not [f for f in failures if "readiness" in f or "status" in f]:
        ok("security foundation is modeled_not_enforced; production NOT ready")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    print("SECURITY_OPERATIONS_VISIBILITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
