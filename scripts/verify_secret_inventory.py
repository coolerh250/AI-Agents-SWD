#!/usr/bin/env python3
"""Step 53 -- secret inventory verifier (source-level, NO value access).

Validates the inventory + ownership + usage mapping: all required categories
covered, every production secret unconfigured / no value in repo / secret store
required, ownership + usage present.

Marker: SECRET_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SDIR = ROOT / "infra" / "secrets"
REQUIRED_CATEGORIES = {
    "identity",
    "session",
    "csrf",
    "database",
    "redis",
    "backup",
    "audit",
    "gitops",
    "kubernetes",
    "github",
    "registry",
    "llm",
    "notification",
    "storage",
    "break_glass",
}

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def load(name: str) -> dict:
    return yaml.safe_load((SDIR / name).read_text(encoding="utf-8"))


def main() -> int:
    for n in (
        "secret-inventory.yaml",
        "secret-ownership-catalog.yaml",
        "secret-usage-mapping.yaml",
    ):
        if not (SDIR / n).is_file():
            bad(f"missing file: {n}")
    if failures:
        print("SECRET_INVENTORY_VERIFY: FAIL")
        return 1

    inv = load("secret-inventory.yaml")
    secrets = inv.get("secrets", [])
    cats = {s.get("category") for s in secrets}
    if not REQUIRED_CATEGORIES <= cats:
        bad(f"missing categories: {sorted(REQUIRED_CATEGORIES - cats)}")
    else:
        ok(f"all {len(REQUIRED_CATEGORIES)} required secret categories covered")

    for s in secrets:
        if s.get("valueStoredInRepo") is not False:
            bad(f"{s.get('key')}: valueStoredInRepo must be false")
        if s.get("productionRequired") and s.get("productionConfigured") is not False:
            bad(f"{s.get('key')}: production secret must be productionConfigured=false")
        if s.get("productionRequired") and s.get("secretStoreRequired") is not True:
            bad(f"{s.get('key')}: production secret must require a secret store")
        if not s.get("owner"):
            bad(f"{s.get('key')}: missing owner")
    if not [f for f in failures if ":" in f]:
        ok("no value in repo; production secrets unconfigured + store-required; owners present")

    owners = {o.get("secretKey") for o in load("secret-ownership-catalog.yaml").get("owners", [])}
    usages = {u.get("secretKey") for u in load("secret-usage-mapping.yaml").get("usages", [])}
    if not owners:
        bad("ownership catalog empty")
    if not usages:
        bad("usage mapping empty")
    if owners and usages:
        ok(f"ownership ({len(owners)}) + usage mapping ({len(usages)}) present")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECRET_INVENTORY_VERIFY: FAIL")
        return 1
    print("SECRET_INVENTORY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
