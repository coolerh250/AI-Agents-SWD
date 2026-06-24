#!/usr/bin/env python3
"""Step 54.3 -- SBOM capability inventory verifier.

Marker: SBOM_CAPABILITY_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "sbom-capability-inventory.yaml"

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
        print("SBOM_CAPABILITY_INVENTORY_VERIFY: FAIL")
        return 1
    data = yaml.safe_load(F.read_text(encoding="utf-8")) or {}
    tools = data.get("sbomTools", [])
    if not tools:
        bad("no SBOM tools listed")
        print("SBOM_CAPABILITY_INVENTORY_VERIFY: FAIL")
        return 1
    ok(f"SBOM capability inventory present with {len(tools)} tools")

    bundled = [t for t in tools if t.get("installed")]
    if not bundled:
        bad("no bundled local SBOM baseline tool")
    elif not all(t.get("localOnly") for t in bundled):
        bad("a bundled SBOM tool is not local-only")
    else:
        ok("local-only SBOM baseline available")

    for t in tools:
        if t.get("key", "").startswith("custom_") and not t.get("installed"):
            bad(f"custom SBOM baseline not installed: {t.get('key')}")
        if not t.get("key", "").startswith("custom_") and t.get("installed"):
            bad(f"external SBOM tool dishonestly installed: {t.get('key')}")
    if not [f for f in failures if "installed" in f]:
        ok("custom baselines installed; external tools recorded honestly")

    if data.get("externalUploadEnabled") is not False:
        bad("externalUploadEnabled must be false")
    if any(t.get("tokenRequired") for t in bundled):
        bad("a bundled SBOM tool requires a token")
    if any(t.get("sourceUpload") for t in tools):
        bad("a SBOM tool declares sourceUpload=true")
    if any(t.get("productionReady") for t in tools) or data.get("productionReady") is not False:
        bad("productionReady must be false")
    if not [f for f in failures if "upload" in f or "token" in f or "productionReady" in f]:
        ok("external upload false, token false for baseline, production ready false")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SBOM_CAPABILITY_INVENTORY_VERIFY: FAIL")
        return 1
    print("SBOM_CAPABILITY_INVENTORY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
