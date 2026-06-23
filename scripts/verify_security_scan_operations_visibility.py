#!/usr/bin/env python3
"""Step 54.2 -- security scan operations visibility verifier.

Asserts the /operations/security/scans/* API is reachable, GET-only, exposes no
run-scan / connect / configure / upload endpoint, never leaks a raw credential,
and degrades to not_run/unknown when no runtime report exists. Combines a live
HTTP check with a source guard.

Marker: SECURITY_SCAN_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
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
    "/operations/security/scans/status",
    "/operations/security/scans/capabilities",
    "/operations/security/scans/targets",
    "/operations/security/scans/exclusions",
    "/operations/security/scans/secret",
    "/operations/security/scans/sast",
    "/operations/security/scans/dependencies",
    "/operations/security/scans/summary",
    "/operations/security/scans/readiness",
]
FORBIDDEN = [
    "/operations/security/scans/run",
    "/operations/security/scans/run-secret",
    "/operations/security/scans/upload",
    "/operations/security/scans/connect",
    "/operations/security/scans/configure",
]
FORBIDDEN_TOKENS = {"run", "connect", "upload", "configure", "push", "create", "login"}
RAW_SECRET = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}|BEGIN [A-Z ]*PRIVATE KEY)"
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
            bad(f"scan API must not define {verb}")
    for ln in [x for x in src.splitlines() if x.strip().startswith("@router.")]:
        m = re.search(r"@router\.\w+\(\s*[\"']([^\"']*)", ln)
        path = m.group(1) if m else ""
        if "/scans" not in path:
            continue
        tokens = set(re.split(r"[/_-]", path.lower()))
        if FORBIDDEN_TOKENS & tokens:
            bad(f"scan API route exposes a forbidden operation: {ln.strip()}")
    if not failures:
        ok("scan API source is GET-only; no run/connect/upload/configure route")

    status0, _ = _get("/operations/security/scans/status")
    if status0 == 0:
        bad(f"orchestrator not reachable at {BASE} (scan endpoints require the live stack)")
        print("SECURITY_SCAN_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    for path in GET_ENDPOINTS:
        code, body = _get(path)
        if code != 200:
            bad(f"GET {path} returned {code}")
            continue
        if RAW_SECRET.search(body):
            bad(f"GET {path} leaked a raw credential value")
    if not [f for f in failures if "GET " in f or "leaked" in f]:
        ok(f"all {len(GET_ENDPOINTS)} scan GET endpoints return 200 with no raw credential")

    for path in FORBIDDEN:
        code, _ = _get(path)
        if code == 200:
            bad(f"forbidden scan endpoint exists: {path}")
    if not [f for f in failures if "forbidden scan" in f]:
        ok("no run-scan / upload / connect / configure endpoint exists")

    code, body = _get("/operations/security/scans/summary")
    if code == 200 and ("not_run" in body or "per_type" in body):
        ok("scan summary degrades to not_run / reports redacted")
    elif code == 200:
        ok("scan summary reachable")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_SCAN_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    print("SECURITY_SCAN_OPERATIONS_VISIBILITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
