#!/usr/bin/env python3
"""Step 57 -- delivery-package project linkage verifier."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = "DELIVERY_PACKAGE_PROJECT_LINKAGE_VERIFY"
LINK = ROOT / "infra" / "delivery" / "delivery-package-project-linkage.yaml"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not LINK.is_file():
        bad("missing delivery-package-project-linkage.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    d = (yaml.safe_load(LINK.read_text(encoding="utf-8")) or {}).get(
        "deliveryPackageProjectLinkage", {}
    )
    if d.get("productionReady") is not False:
        bad("productionReady must be false")
    for f in (
        "project_id",
        "work_item_id",
        "dispatch_id",
        "delivery_package_id",
        "acceptance_status",
    ):
        if f not in d.get("linkFields", []):
            bad(f"linkFields missing: {f}")
    inv = d.get("invariants", {})
    for key in (
        "deliveryPackageReadyIsNotProductionApproval",
        "workItemCompletedIsNotHumanAcceptance",
        "humanAcceptanceIsNotDeploymentApproval",
        "projectCompletedIsNotProductionRelease",
    ):
        if inv.get(key) is not True:
            bad(f"invariant must be asserted true: {key}")
    if inv.get("productionReady") is not False:
        bad("invariants.productionReady must be false")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        "  [OK] linkage invariants: package-ready != production-approval; completed != acceptance"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
