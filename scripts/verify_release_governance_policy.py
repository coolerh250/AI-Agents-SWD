#!/usr/bin/env python3
"""Step 60 -- release governance policy verifier (file-based).

Marker: RELEASE_GOVERNANCE_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "infra" / "release" / "release-governance-policy.yaml"
MARKER = "RELEASE_GOVERNANCE_POLICY_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    data = yaml.safe_load(POLICY.read_text(encoding="utf-8")) or {}
    p = data.get("releaseGovernance", {}) or {}

    if not p.get("enabled"):
        bad("releaseGovernance.enabled must be true")
    if p.get("productionReady") is not False:
        bad("productionReady must be false")
    if p.get("requireHumanApprovalForProduction") is not True:
        bad("requireHumanApprovalForProduction must be true")
    if p.get("defaultEnvironment") != "nonprod":
        bad("defaultEnvironment must be nonprod")

    for key in (
        "allowProductionDeploy",
        "allowAutoPromotion",
        "allowGitHubMerge",
        "allowTagCreation",
        "allowReleaseCreation",
        "allowImagePush",
        "allowRegistryLogin",
        "allowArgoCDProductionSync",
    ):
        if p.get(key) is not False:
            bad(f"{key} must be false (got {p.get(key)!r})")

    allowed = p.get("allowedEnvironments") or []
    if "production" in allowed or "prod" in allowed:
        bad("production must not be an allowed environment")
    forbidden = p.get("forbiddenEnvironments") or []
    if "production" not in forbidden or "prod" not in forbidden:
        bad("production and prod must be forbidden environments")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] release policy: production blocked; no deploy/promotion/merge/sync/push/login")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
