#!/usr/bin/env python3
"""Step 60 -- release governance RUNTIME verifier (live API).

Exercises the real flow: test-login -> create project -> create release candidate
(nonprod) -> create deployment intents (validate_only ok; production target blocked;
forbidden action blocked). Confirms NO deploy / ArgoCD sync / merge / image push /
production action.

Marker: RELEASE_GOVERNANCE_RUNTIME_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")
MARKER = "RELEASE_GOVERNANCE_RUNTIME_VERIFY"

failures: list[str] = []
_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))
_csrf = ""


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if _csrf:
        req.add_header("X-CSRF-Token", _csrf)
    with _opener.open(req, timeout=20) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    global _csrf
    try:
        login = _req("POST", "/operations/admin-console/auth/test-login", {"role": "operator"})
    except OSError as exc:
        print(f"  [FAIL] cannot reach orchestrator: {exc}")
        print(f"{MARKER}: FAIL")
        return 1
    _csrf = login.get("csrf_token", "")
    if not _csrf:
        bad(f"test-login did not return csrf ({login.get('reason')})")
        print(f"{MARKER}: FAIL")
        return 1

    proj = _req(
        "POST",
        "/operations/delivery/projects",
        {"name": "Release Gov Verify Project", "reason": "step60 runtime verify"},
    )
    pid = (proj.get("project") or {}).get("project_id")
    if not pid:
        bad(f"project create failed: {proj}")
        print(f"{MARKER}: FAIL")
        return 1

    # release candidate (default nonprod)
    cand = _req(
        "POST",
        "/operations/release/candidates",
        {"project_id": pid, "version_label": "v0-rv", "reason": "rv candidate"},
    )
    cid = cand.get("release_candidate_id")
    if cand.get("status") != "created" or not cid:
        bad(f"candidate create failed: {cand}")
        print(f"{MARKER}: FAIL")
        return 1
    if cand.get("target_environment") != "nonprod" or cand.get("production_ready") is not False:
        bad(f"candidate must be nonprod + production_ready false: {cand}")

    # production target candidate -> blocked
    pc = _req(
        "POST",
        "/operations/release/candidates",
        {
            "project_id": pid,
            "version_label": "v0-prod",
            "reason": "rv",
            "target_environment": "production",
        },
    )
    if pc.get("status") not in ("policy_blocked", "error") or pc.get("reason") != (
        "production_environment_forbidden"
    ):
        bad(f"production candidate must be blocked: {pc}")

    # validate_only deployment intent -> validated, never executes
    di = _req(
        "POST",
        f"/operations/release/candidates/{cid}/deployment-intents",
        {"requested_action": "validate_only", "reason": "rv intent"},
    )
    if di.get("status") != "validated":
        bad(f"validate_only intent must be validated: {di}")
    for k in (
        "production_executed",
        "deploy_performed",
        "argocd_sync_performed",
        "merge_performed",
        "image_push_performed",
    ):
        if di.get(k) is not False:
            bad(f"deployment intent must not perform {k}")

    # forbidden action -> blocked
    fb = _req(
        "POST",
        f"/operations/release/candidates/{cid}/deployment-intents",
        {"requested_action": "deploy_production", "reason": "rv"},
    )
    if fb.get("status") != "blocked":
        bad(f"deploy_production intent must be blocked: {fb}")

    # production target intent -> blocked
    pt = _req(
        "POST",
        f"/operations/release/candidates/{cid}/deployment-intents",
        {"requested_action": "validate_only", "target_environment": "production", "reason": "rv"},
    )
    if (
        pt.get("status") != "blocked"
        or pt.get("blocked_reason") != "production_environment_forbidden"
    ):
        bad(f"production target intent must be blocked: {pt}")

    # readiness for the bare candidate -> not production ready
    rd = _req("GET", f"/operations/release/candidates/{cid}/readiness")
    if rd.get("production_ready") is not False:
        bad(f"readiness must be production_ready false: {rd}")

    # missing reason rejected
    nore = _req("POST", "/operations/release/candidates", {"version_label": "x"})
    if nore.get("reason") != "reason_required":
        bad(f"missing reason must be rejected: {nore}")

    # no token leaked
    blob = json.dumps([cand, di, fb, pt]).lower()
    for shape in ("ghp_", "github_pat_", "bearer ", "kubeconfig"):
        if shape in blob:
            bad(f"token/credential shape leaked: {shape!r}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] candidate nonprod; validate_only ok; production/forbidden blocked; no deploy")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
