#!/usr/bin/env python3
"""Step 59 -- sandbox GitHub safety fields verifier (live /operations/safety).

Marker: SANDBOX_GITHUB_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

MARKER = "SANDBOX_GITHUB_SAFETY_FIELDS_VERIFY"
URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/safety"

EXPECTED = {
    "sandbox_github_draft_pr_enabled": True,
    "sandbox_github_draft_pr_default_mode": "dry_run",
    "sandbox_github_repository_allowlist_enabled": True,
    "sandbox_github_arbitrary_repo_allowed": False,
    "sandbox_github_merge_enabled": False,
    "sandbox_github_ready_for_review_enabled": False,
    "sandbox_github_workflow_dispatch_enabled": False,
    "sandbox_github_issue_write_enabled": False,
    "sandbox_github_release_write_enabled": False,
    "sandbox_github_deployment_write_enabled": False,
    "sandbox_github_token_exposed": False,
    "sandbox_github_production_branch_allowed": False,
    "sandbox_github_non_sandbox_repo_write_performed": False,
    "sandbox_github_production_ready": False,
    "production_executed_true_count": 0,
}
failures: list[str] = []


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=10) as r:  # noqa: S310
            data = json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"  [FAIL] could not read {URL}: {exc}")
        print(f"{MARKER}: FAIL")
        return 1
    for key, want in EXPECTED.items():
        if data.get(key) != want:
            failures.append(key)
            print(f"  [FAIL] {key}={data.get(key)!r} (expected {want!r})")

    # live mode field must be present and boolean (false unless explicitly enabled).
    if not isinstance(data.get("sandbox_github_draft_pr_live_mode_enabled"), bool):
        failures.append("live_mode_enabled")
        print("  [FAIL] sandbox_github_draft_pr_live_mode_enabled must be a boolean")
    # created count must be a non-negative int.
    cnt = data.get("sandbox_github_draft_pr_created_count")
    if not isinstance(cnt, int) or cnt < 0:
        failures.append("created_count")
        print(f"  [FAIL] sandbox_github_draft_pr_created_count invalid: {cnt!r}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        "  [OK] sandbox GitHub safety fields: sandbox-only; no merge/review/workflow/token; prod=0"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
