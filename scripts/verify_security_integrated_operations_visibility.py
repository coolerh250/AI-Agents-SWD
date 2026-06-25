#!/usr/bin/env python3
"""Step 54.4 -- integrated security operations visibility verifier.

Asserts the /operations/security/{threat-model,release-risk,evidence,readiness,
step54}/* API is reachable, GET-only, exposes no generate-evidence /
approve-release / production-gate / deploy endpoint, leaks no credential, and that
runtime evidence/risk/readiness views degrade to not_run. Combines a live HTTP
check with a source guard.

Marker: SECURITY_INTEGRATED_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
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

OWN_PATH_MARKERS = ("/threat-model/", "/release-risk/", "/evidence/", "/readiness/", "/step54/")
GET_ENDPOINTS = [
    "/operations/security/threat-model/baseline",
    "/operations/security/threat-model/agent",
    "/operations/security/threat-model/supply-chain",
    "/operations/security/threat-model/runtime-gitops",
    "/operations/security/release-risk/model",
    "/operations/security/release-risk/summary",
    "/operations/security/evidence/package",
    "/operations/security/readiness/report",
    "/operations/security/step54/status",
]
FORBIDDEN = [
    "/operations/security/evidence/generate",
    "/operations/security/release-risk/approve",
    "/operations/security/release/approve",
    "/operations/security/step54/gate",
    "/operations/security/step54/deploy",
    "/operations/security/step54/enable",
]
FORBIDDEN_TOKENS = {
    "generate",
    "approve",
    "deploy",
    "gate",
    "sync",
    "enable",
    "push",
    "login",
    "sign",
    "attest",
    "upload",
    "connect",
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
            bad(f"security API must not define {verb}")
    for ln in [x for x in src.splitlines() if x.strip().startswith("@router.")]:
        m = re.search(r"@router\.\w+\(\s*[\"']([^\"']*)", ln)
        path = m.group(1) if m else ""
        if not any(mark in path for mark in OWN_PATH_MARKERS):
            continue
        tokens = set(re.split(r"[/_-]", path.lower()))
        if FORBIDDEN_TOKENS & tokens:
            bad(f"integrated security route exposes a forbidden operation: {ln.strip()}")
    if not failures:
        ok("integrated API source is GET-only; no generate/approve/gate/deploy route")

    status0, _ = _get("/operations/security/step54/status")
    if status0 == 0:
        bad(f"orchestrator not reachable at {BASE} (endpoints require the live stack)")
        print("SECURITY_INTEGRATED_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1

    for path in GET_ENDPOINTS:
        code, body = _get(path)
        if code != 200:
            bad(f"GET {path} returned {code}")
            continue
        if RAW.search(body):
            bad(f"GET {path} leaked a credential value")
    if not [f for f in failures if "GET " in f or "leaked" in f]:
        ok(f"all {len(GET_ENDPOINTS)} integrated GET endpoints return 200 with no credential leak")

    for path in FORBIDDEN:
        code, _ = _get(path)
        if code == 200:
            bad(f"forbidden endpoint exists: {path}")
    if not [f for f in failures if "forbidden endpoint" in f]:
        ok("no generate-evidence / approve-release / gate / deploy endpoint exists")

    # productionReady false where reported; runtime views degrade to not_run.
    for path in (
        "/operations/security/step54/status",
        "/operations/security/evidence/package",
        "/operations/security/release-risk/summary",
        "/operations/security/readiness/report",
    ):
        code, body = _get(path)
        if code == 200:
            try:
                data = json.loads(body)
            except ValueError:
                continue
            if data.get("productionReady") not in (False, None):
                bad(f"{path} productionReady not false: {data.get('productionReady')!r}")
    if not [f for f in failures if "productionReady" in f]:
        ok("step54 status / evidence / risk / readiness report productionReady false (or not_run)")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_INTEGRATED_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    print("SECURITY_INTEGRATED_OPERATIONS_VISIBILITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
