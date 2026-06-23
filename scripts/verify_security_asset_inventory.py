#!/usr/bin/env python3
"""Step 54.1 -- application security asset inventory verifier.

Marker: SECURITY_ASSET_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "application-security-asset-inventory.yaml"

REQUIRED_COMPONENTS = {
    "orchestrator",
    "policy-engine",
    "approval-engine",
    "audit-service",
    "communication-gateway",
    "intake-agent",
    "requirement-agent",
    "development-agent",
    "qa-agent",
    "devops-agent",
    "retry-scheduler",
    "admin-console",
    "shared-sdk",
    "kubernetes-helm-gitops",
    "migration-backup-restore-jobs",
}
REQUIRED_FIELDS = {
    "key",
    "name",
    "type",
    "path",
    "language",
    "runtime",
    "packageFiles",
    "dockerfiles",
    "handlesSecrets",
    "handlesUserInput",
    "handlesAuth",
    "handlesNetwork",
    "handlesPersistence",
    "productionRelevant",
    "requiredScans",
}

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not F.is_file():
        bad(f"missing {F}")
        print("SECURITY_ASSET_INVENTORY_VERIFY: FAIL")
        return 1
    data = yaml.safe_load(F.read_text(encoding="utf-8")) or {}
    assets = data.get("assets", [])
    if not assets:
        bad("inventory has no assets")
        print("SECURITY_ASSET_INVENTORY_VERIFY: FAIL")
        return 1
    ok(f"asset inventory present with {len(assets)} assets")

    keys = {a.get("key") for a in assets}
    missing = REQUIRED_COMPONENTS - keys
    if missing:
        bad(f"required components missing: {sorted(missing)}")
    else:
        ok("all required first-party components covered")

    for a in assets:
        gaps = REQUIRED_FIELDS - set(a.keys())
        if gaps:
            bad(f"asset {a.get('key')} missing fields: {sorted(gaps)}")
    if not [f for f in failures if "missing fields" in f]:
        ok("all assets carry language/runtime/package/handles/required-scan fields")

    if not any(a.get("productionRelevant") for a in assets):
        bad("no production-relevant assets classified")
    else:
        ok("production-relevant assets classified")

    if not all(isinstance(a.get("requiredScans"), list) for a in assets):
        bad("requiredScans must be a list per asset")
    else:
        ok("required scans mapped per asset")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_ASSET_INVENTORY_VERIFY: FAIL")
        return 1
    print("SECURITY_ASSET_INVENTORY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
