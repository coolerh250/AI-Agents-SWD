#!/usr/bin/env python3
"""Step 60 -- release governance operations visibility verifier (live API).

Confirms the read-only GET endpoints respond, carry production_ready=false, never leak a
token, and that there is NO deploy / sync / merge / image-push / production-approval route.

Marker: RELEASE_GOVERNANCE_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")
MARKER = "RELEASE_GOVERNANCE_OPERATIONS_VISIBILITY_VERIFY"

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
            "/operations/release/overview",
            "/operations/release/policy",
            "/operations/release/candidates",
            "/operations/release/deployment-intents",
            "/operations/release/readiness-summary",
            "/operations/release/safety",
            "/operations/release/limitations",
        ):
            d = _get(path)
            if d.get("production_ready") is not False:
                bad(f"{path}: production_ready must be false")
            blob = json.dumps(d).lower()
            for shape in ("ghp_", "github_pat_", '"authorization"', "kubeconfig"):
                if shape in blob:
                    bad(f"{path}: token/credential shape leaked ({shape})")

        # policy: production blocked
        pol = _get("/operations/release/policy")
        if pol.get("allow_production_deploy") is not False:
            bad("policy allow_production_deploy must be false")
        if "production" in (pol.get("allowed_environments") or []):
            bad("policy must not allow production environment")

        # OpenAPI: no deploy / sync / merge / image-push / production route under the prefix
        schema = _get("/openapi.json")
        paths = schema.get("paths", {})
        rel_paths = [p for p in paths if "/operations/release" in p]
        for p in rel_paths:
            low = p.lower()
            for forbidden in (
                "deploy-now",
                "sync",
                "merge",
                "image-push",
                "promote",
                "approve-production",
            ):
                if forbidden in low:
                    bad(f"forbidden release route present: {p}")
            # only candidates + deployment-intents creation may POST
            methods = {m.lower() for m in paths[p]}
            if "post" in methods and not (
                p.endswith("/candidates") or p.endswith("/deployment-intents")
            ):
                bad(f"unexpected POST route: {p}")
    except OSError as exc:
        print(f"  [FAIL] cannot reach orchestrator: {exc}")
        print(f"{MARKER}: FAIL")
        return 1

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        "  [OK] GET endpoints visible; production_ready=false; no deploy/sync/merge route; no token"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
