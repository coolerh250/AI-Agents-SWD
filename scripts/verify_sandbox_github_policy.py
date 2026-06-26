#!/usr/bin/env python3
"""Step 59 -- sandbox GitHub policy verifier (file-based).

Marker: SANDBOX_GITHUB_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "infra" / "github" / "sandbox-github-draft-pr-policy.yaml"
MARKER = "SANDBOX_GITHUB_POLICY_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    data = yaml.safe_load(POLICY.read_text(encoding="utf-8")) or {}
    p = data.get("sandboxGitHub", {}) or {}

    if not p.get("enabled"):
        bad("sandboxGitHub.enabled must be true")
    if p.get("productionReady") is not False:
        bad("productionReady must be false")
    if p.get("defaultMode") != "dry_run":
        bad("defaultMode must be dry_run")
    if "dry_run" not in (p.get("allowedMode") or []):
        bad("dry_run must be an allowed mode")

    # Every dangerous toggle must be explicitly false.
    for key in (
        "allowMerge",
        "allowReadyForReview",
        "allowNonSandboxRepo",
        "allowProductionBranch",
        "allowWorkflowDispatch",
        "allowIssueWrite",
        "allowReleaseWrite",
        "allowDeploymentWrite",
    ):
        if p.get(key) is not False:
            bad(f"{key} must be false (got {p.get(key)!r})")

    live = p.get("liveSandbox", {}) or {}
    if not live.get("blockedWhenNoCredential"):
        bad("liveSandbox.blockedWhenNoCredential must be true")
    if not live.get("requiresCredential"):
        bad("liveSandbox.requiresCredential must be true")

    if "production" not in (p.get("forbiddenBaseBranches") or []):
        bad("production must be a forbidden base branch")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] sandbox policy: dry_run default; no merge/review/workflow/non-sandbox/production")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
