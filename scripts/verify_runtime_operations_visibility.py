#!/usr/bin/env python3
"""Step 51.4 -- runtime operations visibility verifier.

Asserts the read-only /operations/runtime/* API is reachable, GET-only, exposes
no deploy/sync/apply/install endpoint, reports a non-production
validated-not-deployed baseline, and never leaks a secret. Combines a live HTTP
check (when the orchestrator is up) with a source-level guard over
runtime_baseline_api.py. No cluster, no verifier execution.

Marker: RUNTIME_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
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
API_SRC = ROOT / "apps" / "orchestrator" / "src" / "runtime_baseline_api.py"
BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")
GET_ENDPOINTS = [
    "/operations/runtime/kubernetes/baseline",
    "/operations/runtime/kubernetes/components",
    "/operations/runtime/kubernetes/security",
    "/operations/runtime/kubernetes/network",
    "/operations/runtime/kubernetes/storage",
    "/operations/runtime/kubernetes/batch-jobs",
    "/operations/runtime/helm/status",
    "/operations/runtime/gitops/status",
    "/operations/runtime/argocd/status",
    "/operations/runtime/environments",
    "/operations/runtime/readiness",
    "/operations/runtime/report",
]
SECRET_PAT = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|kubeconfig)",
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


def _get(path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=8) as resp:  # noqa: S310
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError):
        return 0, ""


def main() -> int:
    # 1. source-level: API is GET-only, no mutation verbs
    src = API_SRC.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        if verb in src:
            bad(f"runtime API must not define {verb}")
    for word in ("deploy", "sync", "apply", "install", "kubectl", "subprocess"):
        if re.search(rf"def .*{word}|/{word}\b", src):
            bad(f"runtime API must not expose a {word} operation")
    if not [f for f in failures]:
        ok("runtime API source is GET-only with no deploy/sync/apply/install operation")

    # 2. live endpoints (skip-as-fail only if orchestrator unreachable)
    status0, _ = _get("/operations/runtime/readiness")
    if status0 == 0:
        bad(f"orchestrator not reachable at {BASE} (runtime endpoints require the live stack)")
        print("RUNTIME_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    for path in GET_ENDPOINTS:
        code, body = _get(path)
        if code != 200:
            bad(f"GET {path} returned {code}")
            continue
        if SECRET_PAT.search(body):
            bad(f"GET {path} leaked a secret-like value")
    if not [f for f in failures if "GET " in f or "leaked" in f]:
        ok(f"all {len(GET_ENDPOINTS)} runtime GET endpoints return 200 with no secret leak")

    # 3. write/deploy endpoints must NOT exist
    for path in (
        "/operations/runtime/deploy",
        "/operations/runtime/sync",
        "/operations/runtime/apply",
    ):
        code, _ = _get(path)
        if code == 200:
            bad(f"forbidden runtime endpoint exists: {path}")
    if not [f for f in failures if "forbidden runtime" in f]:
        ok("no deploy/sync/apply runtime endpoint exists")

    # 4. readiness posture
    code, body = _get("/operations/runtime/readiness")
    data = json.loads(body) if code == 200 and body else {}
    if data.get("productionReady") is not False:
        bad("runtime readiness productionReady must be false")
    if data.get("status") not in (
        "validated_not_deployed",
        "passed_with_non_production_limitations",
    ):
        bad(f"runtime status unexpected: {data.get('status')}")
    if not data.get("validatedNotDeployed"):
        bad("runtime must report validatedNotDeployed=true")
    if not [f for f in failures if "readiness" in f or "status" in f or "validated" in f]:
        ok("runtime baseline is validated_not_deployed, production NOT ready")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("RUNTIME_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    print("RUNTIME_OPERATIONS_VISIBILITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
