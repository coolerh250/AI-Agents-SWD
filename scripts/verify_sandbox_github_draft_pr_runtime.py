#!/usr/bin/env python3
"""Step 59 -- sandbox draft PR RUNTIME verifier (live API).

Exercises the real flow: test-login -> create project -> create work item -> request a
dry_run sandbox draft PR (planned, with a sandbox branch + audit), and a production_effect
work item -> blocked (never a PR). Confirms NO merge / ready-for-review / workflow dispatch
/ non-sandbox write / production action.

Marker: SANDBOX_GITHUB_DRAFT_PR_RUNTIME_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")
MARKER = "SANDBOX_GITHUB_DRAFT_PR_RUNTIME_VERIFY"

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
        {"name": "Sandbox PR Verify Project", "reason": "step59 runtime verify"},
    )
    pid = (proj.get("project") or {}).get("project_id")
    if not pid:
        bad(f"project create failed: {proj}")
        print(f"{MARKER}: FAIL")
        return 1

    wi = _req(
        "POST",
        f"/operations/delivery/projects/{pid}/work-items",
        {"title": "sandbox pr item", "reason": "rv", "work_type": "implementation"},
    )
    wid = (wi.get("work_item") or {}).get("id")
    if not wid:
        bad(f"work item create failed: {wi}")
        print(f"{MARKER}: FAIL")
        return 1

    # dry_run sandbox draft PR -> planned
    res = _req(
        "POST",
        "/operations/github/sandbox-draft-pr",
        {
            "repository_key": "ai-agents-sandbox",
            "project_id": pid,
            "work_item_id": wid,
            "reason": "rv draft pr",
            "mode": "dry_run",
        },
    )
    if res.get("status") != "planned":
        bad(f"dry_run draft PR must be planned: {res}")
    if not str(res.get("branch_name") or "").startswith("sandbox/ai-agents/"):
        bad(f"draft PR branch must be a sandbox branch: {res.get('branch_name')}")
    if res.get("mode") != "dry_run":
        bad(f"mode must be dry_run: {res.get('mode')}")
    for k in (
        "production_executed",
        "merge_performed",
        "ready_for_review_performed",
        "workflow_dispatch_performed",
        "non_sandbox_repo_write_performed",
    ):
        if res.get(k) is not False:
            bad(f"draft PR must not perform {k} (got {res.get(k)!r})")
    rid = res.get("request_id")

    # detail GET
    if rid:
        rec = _req("GET", f"/operations/github/sandbox-draft-pr/{rid}")
        if rec.get("repository_key") != "ai-agents-sandbox" or rec.get("mode") != "dry_run":
            bad(f"request detail mismatch: {rec}")

    # arbitrary / unknown repo key -> blocked
    bad_repo = _req(
        "POST",
        "/operations/github/sandbox-draft-pr",
        {"repository_key": "evil/repo", "project_id": pid, "work_item_id": wid, "reason": "x"},
    )
    if bad_repo.get("status") not in ("blocked", "policy_blocked", "error"):
        bad(f"unknown repo key must be blocked: {bad_repo}")
    if bad_repo.get("branch_name"):
        bad("unknown repo must not yield a branch")

    # production_effect work item -> blocked, never a PR
    wi2 = _req(
        "POST",
        f"/operations/delivery/projects/{pid}/work-items",
        {"title": "prod item", "reason": "rv", "production_effect": True},
    )
    wid2 = (wi2.get("work_item") or {}).get("id")
    res2 = _req(
        "POST",
        "/operations/github/sandbox-draft-pr",
        {
            "repository_key": "ai-agents-sandbox",
            "project_id": pid,
            "work_item_id": wid2,
            "reason": "x",
        },
    )
    if (
        res2.get("status") != "blocked"
        or res2.get("reason") != "production_effect_requires_approval"
    ):
        bad(f"production_effect work item must be blocked: {res2}")

    # missing reason rejected
    nore = _req(
        "POST",
        "/operations/github/sandbox-draft-pr",
        {"repository_key": "ai-agents-sandbox", "project_id": pid, "work_item_id": wid},
    )
    if nore.get("reason") != "reason_required":
        bad(f"missing reason must be rejected: {nore}")

    # no token / credential shape leaked anywhere in the responses (a token shape, not the
    # word "authorization" -- the PR body legitimately says "No merge authorization").
    blob = json.dumps([res, bad_repo, res2]).lower()
    for shape in ("ghp_", "github_pat_", "gho_", "sandbox_github_token", "bearer "):
        if shape in blob:
            bad(f"a token / credential shape leaked into a response: {shape!r}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] dry_run planned; unknown/production blocked; no merge/review/workflow/token")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
