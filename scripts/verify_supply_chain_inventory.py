#!/usr/bin/env python3
"""Step 54.1 -- supply chain inventory verifier.

Marker: SUPPLY_CHAIN_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "supply-chain-inventory.yaml"

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
        print("SUPPLY_CHAIN_INVENTORY_VERIFY: FAIL")
        return 1
    sc = (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("supplyChain", {})
    if not sc:
        bad("supplyChain section missing")
        print("SUPPLY_CHAIN_INVENTORY_VERIFY: FAIL")
        return 1
    ok("supply chain inventory present")

    src = sc.get("sourceControl", {})
    if src.get("writeEnabled") is not False:
        bad("sourceControl.writeEnabled must be false")
    if src.get("prCreationEnabled") is not False:
        bad("sourceControl.prCreationEnabled must be false")
    if not [f for f in failures if "sourceControl" in f]:
        ok("source control write=false, PR creation=false")

    py = sc.get("dependencies", {}).get("python", {})
    node = sc.get("dependencies", {}).get("node", {})
    if not py.get("packageFiles"):
        bad("python package files not discovered")
    if not node.get("packageFiles"):
        bad("node package files not discovered")
    if not [f for f in failures if "package files" in f]:
        ok("python + node package files discovered")

    containers = sc.get("containers", {})
    if not containers.get("dockerfiles"):
        bad("dockerfiles not discovered")
    if not (containers.get("composeImages") or containers.get("helmImages")):
        bad("compose/helm images not discovered")
    if not [f for f in failures if "dockerfiles" in f or "images" in f]:
        ok("dockerfiles + compose/helm images discovered")

    scanners = sc.get("scanners", {})
    for key in (
        "sastConfigured",
        "dependencyScanConfigured",
        "secretScanConfigured",
        "imageScanConfigured",
    ):
        if scanners.get(key) is not False:
            bad(f"scanner {key} must be false (no committed scanner toolchain)")
    if not [f for f in failures if "scanner" in f]:
        ok("scanner configured flags all false")

    if sc.get("imagePush", {}).get("enabled") is not False:
        bad("imagePush.enabled must be false")
    if sc.get("registryLogin", {}).get("enabled") is not False:
        bad("registryLogin.enabled must be false")
    if sc.get("externalScannerUpload", {}).get("enabled") is not False:
        bad("externalScannerUpload.enabled must be false")
    if not [f for f in failures if "enabled must be false" in f]:
        ok("image push, registry login, external scanner upload all false")

    if containers.get("latestTagAllowed") is not False:
        bad("latestTagAllowed must be false")
    else:
        ok("latest tag not allowed before runtime smoke")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SUPPLY_CHAIN_INVENTORY_VERIFY: FAIL")
        return 1
    print("SUPPLY_CHAIN_INVENTORY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
