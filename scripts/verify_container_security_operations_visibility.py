#!/usr/bin/env python3
"""Step 54.3 -- SBOM / container security operations visibility verifier.

Asserts the /operations/security/{sbom,images}/* API is reachable, GET-only,
exposes no generate-SBOM / scan-image / registry-login / image-push / sign /
attest endpoint, leaks no credential, and degrades to not_run. Combines a live
HTTP check with a source guard.

Marker: CONTAINER_SECURITY_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

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
    "/operations/security/sbom/status",
    "/operations/security/sbom/capabilities",
    "/operations/security/sbom/report",
    "/operations/security/images/inventory",
    "/operations/security/images/digest-policy",
    "/operations/security/images/tag-policy",
    "/operations/security/images/dockerfiles",
    "/operations/security/images/runtime-alignment",
    "/operations/security/images/vulnerability-capability",
    "/operations/security/images/policy-report",
    "/operations/security/images/signing-attestation",
    "/operations/security/images/registry-boundary",
    "/operations/security/images/readiness",
]
FORBIDDEN = [
    "/operations/security/sbom/generate",
    "/operations/security/images/scan",
    "/operations/security/images/login",
    "/operations/security/images/push",
    "/operations/security/images/sign",
    "/operations/security/images/attest",
    "/operations/security/images/pull",
]
FORBIDDEN_TOKENS = {
    "generate",
    "scan",
    "login",
    "push",
    "pull",
    "sign",
    "attest",
    "connect",
    "upload",
}
RAW = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,})"
)

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
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError):
        return 0, ""


def main() -> int:
    src = API_SRC.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        if verb in src:
            bad(f"container security API must not define {verb}")
    for ln in [x for x in src.splitlines() if x.strip().startswith("@router.")]:
        m = re.search(r"@router\.\w+\(\s*[\"']([^\"']*)", ln)
        path = m.group(1) if m else ""
        if "/sbom/" not in path and "/images/" not in path:
            continue
        tokens = set(re.split(r"[/_-]", path.lower()))
        if FORBIDDEN_TOKENS & tokens:
            bad(f"container security route exposes a forbidden operation: {ln.strip()}")
    if not failures:
        ok("SBOM/image API source is GET-only; no generate/scan/login/push/sign/attest route")

    status0, _ = _get("/operations/security/images/readiness")
    if status0 == 0:
        bad(f"orchestrator not reachable at {BASE} (endpoints require the live stack)")
        print("CONTAINER_SECURITY_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    for path in GET_ENDPOINTS:
        code, body = _get(path)
        if code != 200:
            bad(f"GET {path} returned {code}")
            continue
        if RAW.search(body):
            bad(f"GET {path} leaked a credential value")
    if not [f for f in failures if "GET " in f or "leaked" in f]:
        ok(f"all {len(GET_ENDPOINTS)} SBOM/image GET endpoints return 200 with no credential leak")

    for path in FORBIDDEN:
        code, _ = _get(path)
        if code == 200:
            bad(f"forbidden endpoint exists: {path}")
    if not [f for f in failures if "forbidden endpoint" in f]:
        ok("no generate-SBOM / scan / login / push / sign / attest endpoint exists")

    code, body = _get("/operations/security/sbom/status")
    if code == 200 and ("not_run" in body or "baselineEnabled" in body):
        ok("SBOM status reachable; runtime report degrades to not_run")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("CONTAINER_SECURITY_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    print("CONTAINER_SECURITY_OPERATIONS_VISIBILITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
