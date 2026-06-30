#!/usr/bin/env python3
"""Step 63A -- controlled rollout operations visibility verifier (live API).

Confirms the read-only /operations/readiness/controlled-rollout/* endpoints respond, report
production blocked + recommendation not approval, and that there is NO rollout / deploy /
sync / approval / release / restore / failover / merge / image-push endpoint.

Marker: CONTROLLED_ROLLOUT_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

MARKER = "CONTROLLED_ROLLOUT_OPERATIONS_VISIBILITY_VERIFY"
BASE = (
    os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")
    + "/operations/readiness/controlled-rollout"
)
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
        "/policy",
        "/criteria",
        "/production-target",
        "/credentials",
        "/gitops",
        "/approval-channel",
        "/rollback-dr",
        "/scope",
        "/risks",
        "/decision-package",
        "/recommendation",
        "/safety",
    ):
        status, data = _get(path)
        if status != 200:
            bad(f"GET {path} -> HTTP {status}")
            continue
        if data.get("production_ready") not in (False, None):
            bad(f"{path} production_ready not false")

    _, rec = _get("/recommendation")
    if rec.get("recommendation_is_approval") is not False:
        bad("recommendation must not be an approval")
    if rec.get("authorizes_production_action") is not False:
        bad("recommendation must not authorize production action")

    _, pol = _get("/policy")
    for k in (
        "allows_production_action",
        "allows_production_deploy",
        "allows_production_sync",
        "allows_production_restore",
        "allows_production_failover",
        "operator_review_is_approval",
        "go_recommendation_is_approval",
    ):
        if pol.get(k) is not False:
            bad(f"policy {k} must be false")

    # No forbidden production-action endpoints.
    for path in (
        "/rollout",
        "/deploy",
        "/sync",
        "/approve",
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
    print("  [OK] controlled rollout visibility: read-only; recommendation not approval; no action")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
