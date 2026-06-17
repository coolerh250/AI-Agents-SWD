#!/usr/bin/env python3
"""Step 51.2C1 -- storage consumer + ownership inventory verifier.

Source-level checks over storage-consumer-inventory.yaml and
storage-ownership-catalog.yaml: completeness, ownership, lifecycle, generated
PVC safety (dev/test only, single-writer, RWO), unresolved honesty, and backup
deferral. No rendering, no cluster.

Marker: KUBERNETES_STORAGE_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "infra" / "kubernetes" / "storage-consumer-inventory.yaml"
CATALOG = ROOT / "infra" / "kubernetes" / "storage-ownership-catalog.yaml"

STRATEGIES = {
    "ephemeralEmptyDir",
    "generatedPVC",
    "existingClaim",
    "externalService",
    "externalObjectStorePlaceholder",
    "imageContained",
    "unresolved",
}
REQUIRED_CATEGORIES = {
    "database",
    "redis",
    "workspace",
    "reports",
    "audit_evidence",
    "delivery_artifacts",
    "static_asset",
    "backup",
}
FORBIDDEN_MOUNTS = {"/", "/app", "/etc", "/bin", "/sbin", "/usr", "/proc", "/sys", "/dev"}
SECRET_PAT = re.compile(
    r"(password|passwd|secret[_-]?key|api[_-]?key|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,})"
    r"\s*[:=]\s*\S",
    re.IGNORECASE,
)

failures: list[str] = []
passes: list[str] = []


def ok(msg: str) -> None:
    passes.append(msg)
    print(f"  [PASS] {msg}")


def bad(msg: str) -> None:
    failures.append(msg)
    print(f"  [FAIL] {msg}")


def load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def main() -> int:
    inv = load(INVENTORY)
    cat = load(CATALOG)
    consumers = inv["consumers"]
    stores = cat["stores"]

    # 1. consumer completeness
    req_fields = [
        "component",
        "dataCategory",
        "path",
        "ownership",
        "writers",
        "readers",
        "lifecycle",
        "durability",
        "rebuildable",
        "confidentiality",
        "integrityRequirement",
        "targetStrategy",
        "evidence",
    ]
    inv_ok = True
    for c in consumers:
        for f in req_fields:
            if f not in c or c[f] in (None, ""):
                bad(f"consumer {c.get('component')} missing field {f}")
                inv_ok = False
        if not c.get("writers"):
            bad(f"consumer {c.get('component')} has no writers")
            inv_ok = False
        if c.get("targetStrategy") not in STRATEGIES:
            bad(f"consumer {c.get('component')} bad targetStrategy {c.get('targetStrategy')}")
            inv_ok = False
    if inv_ok:
        ok(
            f"all {len(consumers)} consumers have owner/writers/readers/lifecycle/durability/strategy/evidence"
        )

    # 2. required categories covered
    cats = {c["dataCategory"] for c in consumers}
    missing = REQUIRED_CATEGORIES - cats
    if missing:
        bad(f"storage consumer categories missing: {sorted(missing)}")
    else:
        ok(f"all required storage categories inventoried ({len(REQUIRED_CATEGORIES)})")

    # 3. ownership-catalog store completeness
    store_fields = [
        "owner",
        "writers",
        "readers",
        "dataCategory",
        "lifecycle",
        "durability",
        "confidentiality",
        "integrityRequirement",
        "strategyByEnvironment",
        "productionConfigured",
    ]
    store_ok = True
    for name, s in stores.items():
        for f in store_fields:
            if f not in s:
                bad(f"store {name} missing field {f}")
                store_ok = False
        sbe = s.get("strategyByEnvironment", {})
        if set(sbe) != {"dev", "test", "staging", "production"}:
            bad(f"store {name} strategyByEnvironment must cover dev/test/staging/production")
            store_ok = False
    if store_ok:
        ok(f"all {len(stores)} stores fully classified with per-environment strategy")

    # 4. generated PVC stores: dev/test only, single-writer, RWO, safe mount, unique
    gen = cat["generatedPvcStores"]
    mounts: dict[str, str] = {}
    for name in gen:
        s = stores[name]
        sbe = s["strategyByEnvironment"]
        if sbe["dev"] != "generatedPVC" or sbe["test"] != "generatedPVC":
            bad(f"{name} must be generatedPVC in dev+test")
        if sbe["staging"] == "generatedPVC" or sbe["production"] == "generatedPVC":
            bad(f"{name} must NOT be generatedPVC in staging/production")
        if len(s["writers"]) != 1:
            bad(f"{name} is generatedPVC (RWO) but has multiple writers {s['writers']}")
        if s.get("accessMode") != "ReadWriteOnce":
            bad(f"{name} generatedPVC must use ReadWriteOnce")
        mp = s.get("mountPath", "")
        if mp in FORBIDDEN_MOUNTS or not mp.startswith("/"):
            bad(f"{name} unsafe mountPath {mp}")
        if mp in mounts.values():
            bad(f"duplicate generated-PVC mountPath {mp}")
        mounts[name] = mp
    if not failures:
        ok(
            f"generated-PVC stores {gen} are dev/test-only single-writer RWO with safe distinct mounts"
        )

    # 5. unresolved honesty: never productionConfigured, always blockers
    for name, s in stores.items():
        envstrats = set(s["strategyByEnvironment"].values())
        if "unresolved" in envstrats:
            if s.get("productionConfigured"):
                bad(f"unresolved store {name} must not be productionConfigured")
            if not s.get("unresolved"):
                bad(f"unresolved store {name} must record blockers")
    if "unresolved" in {v for s in stores.values() for v in s["strategyByEnvironment"].values()}:
        if not [f for f in failures if "unresolved store" in f]:
            ok("unresolved stores record blockers and stay productionConfigured=false")

    # 6. no duplicate ownership (owner + mountPath)
    pairs = [(s["owner"], s.get("mountPath", name)) for name, s in stores.items()]
    dups = {p for p in pairs if pairs.count(p) > 1}
    if dups:
        bad(f"duplicate store ownership: {dups}")
    else:
        ok("no duplicate store ownership")

    # 7. backup deferred to 51.2C2 and separate from active workspace
    backup = cat["deferred"]["backup-artifacts"]
    if backup.get("deferredTo") != "51.2C2":
        bad("backup-artifacts must be deferred to 51.2C2")
    elif not backup.get("separateFromActiveWorkspace"):
        bad("backup-artifacts must be marked separate from active workspace")
    else:
        ok("backup-artifacts deferred to 51.2C2 and separate from active workspace")

    # 8. no secret-like literals in either file
    secret_hit = False
    for p in (INVENTORY, CATALOG):
        for ln in p.read_text(encoding="utf-8").splitlines():
            if SECRET_PAT.search(ln):
                bad(f"secret-like literal in {p.name}: {ln.strip()[:60]}")
                secret_hit = True
    if not secret_hit:
        ok("no secret-like literals in storage inventory/catalog")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("KUBERNETES_STORAGE_INVENTORY_VERIFY: FAIL")
        return 1
    print("KUBERNETES_STORAGE_INVENTORY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
