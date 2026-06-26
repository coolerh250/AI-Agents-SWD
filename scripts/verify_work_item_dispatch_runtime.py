#!/usr/bin/env python3
"""Step 57 -- work-item dispatch RUNTIME verifier (live API).

Exercises the real flow: test-login -> create project -> create work item -> dispatch,
and a production_effect work item -> waiting_approval (never dispatched). Confirms the
dispatch triggers NO GitHub write / ArgoCD sync / external send / production action.

Marker: WORK_ITEM_DISPATCH_RUNTIME_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")
MARKER = "WORK_ITEM_DISPATCH_RUNTIME_VERIFY"

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
    with _opener.open(req, timeout=15) as r:  # noqa: S310
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

    # create project
    proj = _req(
        "POST",
        "/operations/delivery/projects",
        {"name": "Runtime Verify Project", "reason": "step57 runtime verify"},
    )
    pid = (proj.get("project") or {}).get("project_id")
    if proj.get("status") != "created" or not pid:
        bad(f"project create failed: {proj}")
        print(f"{MARKER}: FAIL")
        return 1

    # non-production work item -> dispatch
    wi = _req(
        "POST",
        f"/operations/delivery/projects/{pid}/work-items",
        {"title": "impl item", "reason": "rv", "work_type": "implementation"},
    )
    wid = (wi.get("work_item") or {}).get("id")
    if not wid:
        bad(f"work item create failed: {wi}")
        print(f"{MARKER}: FAIL")
        return 1
    dsp = _req("POST", f"/operations/delivery/work-items/{wid}/dispatch", {"reason": "rv dispatch"})
    if dsp.get("status") != "dispatched" or dsp.get("dispatched") is not True:
        bad(f"dispatch did not succeed: {dsp}")
    for k in (
        "production_executed",
        "github_write_performed",
        "argocd_sync_performed",
        "external_notification_send_performed",
    ):
        if dsp.get(k) not in (False, None) and dsp.get(k) is not False:
            bad(f"dispatch must not perform {k}")
    if dsp.get("production_executed") is not False:
        bad("dispatch production_executed must be false")

    dispatches = _req("GET", f"/operations/delivery/work-items/{wid}/dispatches").get(
        "dispatches", []
    )
    if not dispatches or dispatches[0].get("target_agent") != "development-agent":
        bad(f"dispatch record missing / wrong target: {dispatches}")
    events = _req("GET", f"/operations/delivery/work-items/{wid}/events").get("events", [])
    if not any(e.get("event_type") == "work_item_dispatched" for e in events):
        bad("no work_item_dispatched event recorded")

    # production_effect work item -> waiting_approval, NOT dispatched
    wi2 = _req(
        "POST",
        f"/operations/delivery/projects/{pid}/work-items",
        {
            "title": "prod item",
            "reason": "rv",
            "work_type": "implementation",
            "production_effect": True,
        },
    )
    wid2 = (wi2.get("work_item") or {}).get("id")
    dsp2 = _req("POST", f"/operations/delivery/work-items/{wid2}/dispatch", {"reason": "rv"})
    if dsp2.get("status") != "waiting_approval" or dsp2.get("dispatched") is not False:
        bad(f"production_effect work item must NOT dispatch: {dsp2}")

    # missing reason rejected
    nore = _req("POST", f"/operations/delivery/projects/{pid}/work-items", {"title": "x"})
    if nore.get("reason") != "reason_required":
        bad("work item create without reason must be rejected")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        "  [OK] real dispatch ok; production_effect->waiting_approval; no prod/external side effect"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
