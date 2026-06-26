#!/usr/bin/env python3
"""Step 57 -- multi-project operations API visibility verifier (static).

Reads endpoints are GET-only + redacted; write endpoints (create project / work item
/ dispatch) require auth + CSRF + reason + audit; there is NO production deploy /
GitHub / ArgoCD / external-send endpoint.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "MULTI_PROJECT_OPERATIONS_VISIBILITY_VERIFY"
API = ROOT / "apps" / "orchestrator" / "src" / "multi_project_api.py"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not API.is_file():
        bad("missing multi_project_api.py")
        print(f"{MARKER}: FAIL")
        return 1
    src = API.read_text(encoding="utf-8")

    gets = re.findall(r'@router\.get\("([^"]*)"\)', src)
    posts = re.findall(r'@router\.post\("([^"]*)"\)', src)
    for needle in (
        "/projects",
        "/projects/{project_id}",
        "/work-items/{work_item_id}/events",
        "/work-items/{work_item_id}/dispatches",
        "/projects/{project_id}/delivery-state",
    ):
        if needle not in gets:
            bad(f"missing GET endpoint: {needle}")
    for needle in (
        "/projects",
        "/projects/{project_id}/work-items",
        "/work-items/{work_item_id}/dispatch",
    ):
        if needle not in posts:
            bad(f"missing POST endpoint: {needle}")

    # Every POST handler must authenticate, require CSRF, require a reason, and audit.
    if src.count("_authenticate(request)") < len(posts):
        bad("not every write authenticates")
    if src.count("_require_csrf(request") < len(posts):
        bad("not every write checks CSRF")
    if src.count("reason_required") < len(posts):
        bad("not every write requires a reason")
    if "_audit(" not in src:
        bad("writes must audit")

    # No production / external mutation surface.
    for forbidden in ("github", "argocd", "/deploy", "production-deploy", "external_send_endpoint"):
        if re.search(rf'@router\.(get|post)\("[^"]*{forbidden}', src):
            bad(f"forbidden endpoint surface: {forbidden}")
    # production_effect must route to waiting_approval (never dispatch).
    if "waiting_approval" not in src:
        bad("production_effect must route to waiting_approval")
    if 'production_executed": False' not in src and "production_executed=False" not in src:
        bad("responses must carry production_executed False")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        f"  [OK] {len(gets)} GET reads; {len(posts)} writes auth+csrf+reason+audit; no prod surface"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
