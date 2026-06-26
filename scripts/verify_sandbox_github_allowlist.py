#!/usr/bin/env python3
"""Step 59 -- sandbox repository allowlist verifier (file-based + SDK resolution).

Marker: SANDBOX_GITHUB_ALLOWLIST_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ALLOWLIST = ROOT / "infra" / "github" / "sandbox-repository-allowlist.yaml"
MARKER = "SANDBOX_GITHUB_ALLOWLIST_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    data = yaml.safe_load(ALLOWLIST.read_text(encoding="utf-8")) or {}
    repos = data.get("repositories", []) or []
    if not repos:
        bad("allowlist must contain at least one sandbox repository")

    for r in repos:
        key = r.get("key")
        if not r.get("sandboxOnly"):
            bad(f"repo {key}: sandboxOnly must be true")
        if r.get("allowMerge") is not False:
            bad(f"repo {key}: allowMerge must be false")
        if r.get("allowRelease") is not False:
            bad(f"repo {key}: allowRelease must be false")
        if r.get("allowDeployment") is not False:
            bad(f"repo {key}: allowDeployment must be false")
        if "*" in str(r.get("owner", "")) or "*" in str(r.get("repo", "")):
            bad(f"repo {key}: wildcard owner/repo not allowed")
        if not (r.get("allowedHeadPrefix") or []):
            bad(f"repo {key}: must define allowedHeadPrefix")

    rules = data.get("rules", []) or []
    for required in ("repositoryKeyOnly", "noArbitraryRepo", "rejectRepoNotInAllowlist"):
        if required not in rules:
            bad(f"missing rule: {required}")

    # SDK resolution: known key resolves; unknown key + raw owner/repo never resolve.
    from shared.sdk.sandbox_github import allowlist as al

    if al.resolve_repository("ai-agents-sandbox") is None:
        bad("known repository key must resolve")
    if al.resolve_repository("definitely-not-a-key") is not None:
        bad("unknown repository key must NOT resolve")
    if al.resolve_repository("../../etc/passwd") is not None:
        bad("path-like key must NOT resolve")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] allowlist: sandbox-only, key-resolved, no wildcard, no merge/release/deploy")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
