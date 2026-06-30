#!/usr/bin/env python3
"""Step 62 -- production readiness operations visibility verifier (live API).

Confirms the read-only /operations/readiness/* endpoints respond, report production blocked
+ never approved, and that there is NO deploy / sync / approval / release / restore /
failover / merge / image-push endpoint.

Marker: PRODUCTION_READINESS_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

MARKER = "PRODUCTION_READINESS_OPERATIONS_VISIBILITY_VERIFY"
BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/readiness"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _get(path: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as r:  # noqa: S310
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {}
    except (OSError, ValueError) as exc:
        bad(f"GET {path} failed: {exc}")
        return 0, {}


def main() -> int:
    for path in (
        "/overview",
        "/policy",
        "/checklist",
        "/evidence",
        "/blocking-rules",
        "/blockers",
        "/prerequisites",
        "/authorization",
        "/operator-review-package",
        "/decision",
        "/preflight",
        "/report",
        "/safety",
        "/limitations",
    ):
        status, data = _get(path)
        if status != 200:
            bad(f"GET {path} -> HTTP {status}")
            continue
        if data.get("production_ready") not in (False, None):
            bad(f"{path} production_ready not false")

    _, pol = _get("/policy")
    for k in (
        "allow_production_deploy",
        "allow_production_sync",
        "allow_production_restore",
        "allow_production_failover",
        "allow_github_merge",
        "allow_image_push",
        "current_stage_allows_production_action",
    ):
        if pol.get(k) is not False:
            bad(f"policy {k} must be false")

    _, dec = _get("/decision")
    if dec.get("decision") == "production_ready" or dec.get("production_ready"):
        bad("decision must never be production_ready")

    # No forbidden production-action endpoints.
    for path in (
        "/deploy",
        "/sync",
        "/approve",
        "/approval",
        "/release",
        "/restore",
        "/failover",
        "/merge",
        "/image-push",
    ):
        status, _ = _get(path)
        if status not in (404, 405):
            bad(f"forbidden endpoint {path} responded HTTP {status} (must not exist)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        "  [OK] readiness visibility: read-only; production blocked/unapproved; no action endpoint"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
