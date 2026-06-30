#!/usr/bin/env python3
"""Step 61 -- backup / restore / DR operations visibility verifier (live API).

Confirms the read-only /operations/dr/* endpoints respond, report production blocked, and
that there is NO cleanup-execute / restore-execute / failover / teardown / ArgoCD-sync /
cloud-upload endpoint. Marker: BACKUP_RESTORE_DR_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

MARKER = "BACKUP_RESTORE_DR_OPERATIONS_VISIBILITY_VERIFY"
BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/dr"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _get(path: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as r:  # noqa: S310
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        return e.code, {}
    except (OSError, ValueError) as exc:
        bad(f"GET {path} failed: {exc}")
        return 0, {}


def main() -> int:
    # Read endpoints respond and report production blocked.
    for path in (
        "/policy",
        "/safety",
        "/overview",
        "/inventory",
        "/targets",
        "/artifacts",
        "/cleanup-review",
        "/restore-plans",
        "/restore-validations",
        "/evidence",
        "/readiness",
        "/limitations",
    ):
        status, data = _get(path)
        if status != 200:
            bad(f"GET {path} -> HTTP {status}")
            continue
        if data.get("production_ready") not in (False, None):
            bad(f"{path} production_ready not false")

    # Policy: every dangerous toggle false.
    _, pol = _get("/policy")
    for k in (
        "allow_production_restore",
        "allow_production_failover",
        "allow_cleanup_execution",
        "allow_restore_execution",
        "allow_kind_teardown",
        "allow_argocd_teardown",
        "allow_external_backup_upload",
        "allow_cloud_provider_write",
    ):
        if pol.get(k) is not False:
            bad(f"policy {k} must be false")

    # There must be NO execute / failover / teardown / sync / cloud-upload endpoint.
    for path in (
        "/cleanup-execute",
        "/restore-execute",
        "/failover",
        "/teardown-kind",
        "/argocd-sync",
        "/cloud-upload",
    ):
        status, _ = _get(path)
        if status not in (404, 405):
            bad(f"forbidden endpoint {path} responded HTTP {status} (must not exist)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] DR visibility: read-only; production blocked; no execute/failover/teardown")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
