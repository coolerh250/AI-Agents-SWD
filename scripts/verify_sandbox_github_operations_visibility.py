#!/usr/bin/env python3
"""Step 59 -- sandbox draft PR operations visibility verifier (live API).

Confirms the read-only GET endpoints respond, carry production_ready=false, never leak a
token, and that there is NO merge / ready-for-review / workflow-dispatch endpoint in the
OpenAPI schema.

Marker: SANDBOX_GITHUB_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")
MARKER = "SANDBOX_GITHUB_OPERATIONS_VISIBILITY_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=15) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    try:
        for path in (
            "/operations/github/sandbox-draft-pr/policy",
            "/operations/github/sandbox-draft-pr/allowlist",
            "/operations/github/sandbox-draft-pr/readiness",
            "/operations/github/sandbox-draft-pr/safety",
            "/operations/github/sandbox-draft-pr/requests",
        ):
            d = _get(path)
            if d.get("production_ready") is not False and path.endswith(
                ("policy", "allowlist", "readiness", "safety")
            ):
                bad(f"{path}: production_ready must be false")
            blob = json.dumps(d).lower()
            if "ghp_" in blob or '"authorization"' in blob:
                bad(f"{path}: token/credential shape leaked")

        # readiness: default dry_run; live not effective without credential.
        rdy = _get("/operations/github/sandbox-draft-pr/readiness")
        if rdy.get("default_mode") != "dry_run":
            bad(f"readiness default_mode must be dry_run: {rdy.get('default_mode')}")

        # OpenAPI: no merge / ready-for-review / workflow-dispatch route under the prefix.
        schema = _get("/openapi.json")
        paths = schema.get("paths", {})
        sandbox_paths = [p for p in paths if "/operations/github/sandbox-draft-pr" in p]
        for p in sandbox_paths:
            if any(t in p.lower() for t in ("merge", "ready-for-review", "workflow", "dispatch")):
                bad(f"forbidden sandbox route present: {p}")
            methods = {m.lower() for m in paths[p]}
            # only the base path may expose POST (the controlled request); the rest are GET-only.
            if p != "/operations/github/sandbox-draft-pr" and (methods - {"get"}):
                bad(f"{p} must be GET-only (got {methods})")
    except OSError as exc:
        print(f"  [FAIL] cannot reach orchestrator: {exc}")
        print(f"{MARKER}: FAIL")
        return 1

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] GET endpoints visible, production_ready=false, no token, no merge/workflow route")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
