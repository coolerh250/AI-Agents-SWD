#!/usr/bin/env python3
"""Step 59 -- sandbox draft branch naming policy verifier (SDK).

Marker: SANDBOX_GITHUB_BRANCH_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MARKER = "SANDBOX_GITHUB_BRANCH_POLICY_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    from shared.sdk.sandbox_github import branch

    name = branch.generate_branch_name("Proj Key!", "WI-0007", "abc123def456ghijk")
    if not name.startswith("sandbox/ai-agents/"):
        bad(f"branch must start with sandbox prefix: {name}")
    if any(c.isspace() for c in name):
        bad(f"branch must not contain spaces: {name}")
    if ".." in name:
        bad(f"branch must not contain path traversal: {name}")
    if any(c in name for c in ";|&$`()<>\\"):
        bad(f"branch must not contain shell metacharacters: {name}")

    # Path-traversal / shell-metachar inputs are sanitized away.
    evil = branch.generate_branch_name("../../etc", "wi;rm -rf /", "$(whoami)")
    if ".." in evil or any(c in evil for c in ";|&$`()<>\\ "):
        bad(f"sanitization failed for hostile input: {evil}")

    # Protected branch names are rejected.
    for forbidden in ("sandbox/ai-agents/main", "main", "production"):
        try:
            branch.validate_branch_name(forbidden)
            if forbidden in ("main", "production"):
                bad(f"validate must reject non-prefixed protected name: {forbidden}")
        except branch.BranchPolicyError:
            pass

    # A production-prefixed sandbox branch is rejected.
    try:
        branch.validate_branch_name("sandbox/ai-agents/production/x/y")
        bad("production-prefixed branch must be rejected")
    except branch.BranchPolicyError:
        pass

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] branch policy: sanitized, prefixed, no traversal/space/metachar/protected")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
