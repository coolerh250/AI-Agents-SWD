#!/usr/bin/env python3
"""Step 55.1 -- non-production Kubernetes tooling verifier.

Validates the committed tooling inventory (always) and confirms the required
tools are actually installed. Never logs into a registry, never pushes an image,
never reads a kubeconfig / token. With the tools absent it reports BLOCKED.

Marker: NONPROD_KUBERNETES_TOOLING_VERIFY: PASS | BLOCKED | FAIL
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = "NONPROD_KUBERNETES_TOOLING_VERIFY"
INVENTORY = ROOT / "infra" / "kubernetes" / "nonproduction-tooling-inventory.yaml"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not INVENTORY.is_file():
        bad("missing nonproduction-tooling-inventory.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    inv = (yaml.safe_load(INVENTORY.read_text(encoding="utf-8")) or {}).get(
        "nonProductionToolingInventory", {}
    )
    if inv.get("registryLoginPerformed") is not False:
        bad("inventory must record registryLoginPerformed=false")
    if inv.get("imagePushPerformed") is not False:
        bad("inventory must record imagePushPerformed=false")
    tools = {t.get("name"): t for t in inv.get("tools", [])}
    for required in ("kubectl", "helm", "kind"):
        t = tools.get(required)
        if not t:
            bad(f"inventory missing required tool: {required}")
            continue
        if t.get("required") is not True:
            bad(f"{required} must be marked required")
        if t.get("productionCredentialRequired") is not False:
            bad(f"{required} must not require a production credential")
    if not failures:
        print("  [OK] tooling inventory valid; no registry login / image push; no prod credential")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    missing = [t for t in ("kubectl", "helm", "kind") if shutil.which(t) is None]
    if missing:
        print(f"  [BLOCKED] required tools not installed: {missing}")
        print(f"{MARKER}: BLOCKED")
        return 0
    print("  [OK] kubectl + helm + kind installed")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
