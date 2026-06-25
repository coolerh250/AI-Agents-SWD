#!/usr/bin/env python3
"""Step 55 -- non-production runtime smoke operations visibility verifier.

Asserts the /operations/runtime/nonprod-smoke/* API is reachable, GET-only, exposes
no deploy / helm-install / cleanup / kubectl-exec / ArgoCD-sync endpoint, leaks no
kubeconfig / token / cert / secret, and degrades to not_run. Live HTTP + source
guard.

Marker: NONPROD_RUNTIME_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
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
    "/operations/runtime/nonprod-smoke/preflight",
    "/operations/runtime/nonprod-smoke/namespace",
    "/operations/runtime/nonprod-smoke/helm",
    "/operations/runtime/nonprod-smoke/pods",
    "/operations/runtime/nonprod-smoke/services",
    "/operations/runtime/nonprod-smoke/connectivity",
    "/operations/runtime/nonprod-smoke/networkpolicy",
    "/operations/runtime/nonprod-smoke/storage",
    "/operations/runtime/nonprod-smoke/securitycontext",
    "/operations/runtime/nonprod-smoke/batch-jobs",
    "/operations/runtime/nonprod-smoke/report",
    "/operations/runtime/nonprod-smoke/readiness",
]
FORBIDDEN = [
    "/operations/runtime/nonprod-smoke/deploy",
    "/operations/runtime/nonprod-smoke/install",
    "/operations/runtime/nonprod-smoke/cleanup",
    "/operations/runtime/nonprod-smoke/exec",
    "/operations/runtime/nonprod-smoke/sync",
]
FORBIDDEN_TOKENS = {"deploy", "install", "cleanup", "exec", "sync", "apply", "uninstall", "delete"}
RAW = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|"
    r"apiVersion:\s*v1|current-context)"
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
            bad(f"runtime API must not define {verb}")
    for ln in [x for x in src.splitlines() if x.strip().startswith("@router.")]:
        m = re.search(r"@router\.\w+\(\s*[\"']([^\"']*)", ln)
        path = m.group(1) if m else ""
        if "nonprod-smoke" not in path:
            continue
        tokens = set(re.split(r"[/_-]", path.lower()))
        if FORBIDDEN_TOKENS & tokens:
            bad(f"nonprod-smoke route exposes a forbidden operation: {ln.strip()}")
    if not failures:
        ok("runtime API source GET-only; no deploy/install/cleanup/exec/sync route")

    status0, _ = _get("/operations/runtime/nonprod-smoke/readiness")
    if status0 == 0:
        bad(f"orchestrator not reachable at {BASE}")
        print("NONPROD_RUNTIME_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1

    for path in GET_ENDPOINTS:
        code, body = _get(path)
        if code != 200:
            bad(f"GET {path} returned {code}")
            continue
        if RAW.search(body):
            bad(f"GET {path} leaked a kubeconfig/secret value")
    if not [f for f in failures if "GET " in f or "leaked" in f]:
        ok(f"all {len(GET_ENDPOINTS)} nonprod-smoke GET endpoints return 200; no credential leak")

    for path in FORBIDDEN:
        code, _ = _get(path)
        if code == 200:
            bad(f"forbidden endpoint exists: {path}")
    if not [f for f in failures if "forbidden endpoint" in f]:
        ok("no deploy / install / cleanup / exec / sync endpoint exists")

    for path in (
        "/operations/runtime/nonprod-smoke/readiness",
        "/operations/runtime/nonprod-smoke/report",
    ):
        code, body = _get(path)
        if code == 200:
            try:
                data = json.loads(body)
            except ValueError:
                continue
            if data.get("productionReady") not in (False, None):
                bad(f"{path} productionReady not false")
    if not [f for f in failures if "productionReady" in f]:
        ok("readiness / report productionReady false (or not_run)")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("NONPROD_RUNTIME_OPERATIONS_VISIBILITY_VERIFY: FAIL")
        return 1
    print("NONPROD_RUNTIME_OPERATIONS_VISIBILITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
