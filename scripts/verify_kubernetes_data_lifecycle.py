#!/usr/bin/env python3
"""Step 51.2C1 -- data lifecycle classification verifier.

Asserts the lifecycle / durability / rebuildability / integrity rules over the
storage ownership catalog: no fake durability, audit-critical integrity
preserved, infrastructure state never ephemeral, evidence vs cache separated,
workspace lifecycle boundaries honest, backup separated. No cluster.

Marker: KUBERNETES_DATA_LIFECYCLE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "infra" / "kubernetes" / "storage-ownership-catalog.yaml"

failures: list[str] = []
passes: list[str] = []


def ok(msg: str) -> None:
    passes.append(msg)
    print(f"  [PASS] {msg}")


def bad(msg: str) -> None:
    failures.append(msg)
    print(f"  [FAIL] {msg}")


def main() -> int:
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    stores = cat["stores"]

    # 1. infrastructure_state never ephemeral
    bads = [
        n
        for n, s in stores.items()
        if s["lifecycle"] == "infrastructure_state" and s["durability"] == "ephemeral"
    ]
    if bads:
        bad(f"infrastructure_state stores must not be ephemeral: {bads}")
    else:
        ok("infrastructure_state stores are durable (not ephemeral)")

    # 2. database never fully_rebuildable
    bads = [
        n
        for n, s in stores.items()
        if s["dataCategory"] == "database" and s.get("rebuildable") == "fully_rebuildable"
    ]
    if bads:
        bad(f"database state must not be fully_rebuildable: {bads}")
    else:
        ok("database state is not fully_rebuildable")

    # 3. audit-critical / audit evidence never low integrity
    bads = [
        n
        for n, s in stores.items()
        if (s["lifecycle"] == "audit_retained" or s["dataCategory"] == "audit_evidence")
        and s["integrityRequirement"] in ("low", "standard")
    ]
    if bads:
        bad(f"audit-retained/audit-evidence stores must be high/audit_critical integrity: {bads}")
    else:
        ok("audit-retained/audit-evidence stores keep high/audit_critical integrity")

    # 4. delivery evidence not mixed with cache/redis store
    da = stores.get("delivery-artifacts", {})
    if da.get("dataCategory") in ("redis", "cache"):
        bad("delivery artifacts must not share the cache/redis store")
    else:
        ok("delivery evidence is separate from cache/redis")

    # 5. workspace lifecycle boundary honest (created/destroyed, not durable, not solved)
    ws = stores["workspace-scratch"]
    lb = ws.get("lifecycleBoundary", {})
    if not lb.get("created") or not lb.get("destroyed"):
        bad("workspace store must declare create + destroy boundaries")
    elif lb.get("durableAcrossRestart") is not False:
        bad("workspace store must declare durableAcrossRestart=false")
    elif ws.get("durability") != "ephemeral" or ws.get("persistenceSolved") is not False:
        bad("workspace store must stay ephemeral with persistenceSolved=false (no fake durability)")
    else:
        ok("workspace lifecycle boundaries honest (ephemeral, not durable, persistence unsolved)")

    # 6. temporary reports rebuildable
    rr = stores["runtime-reports"]
    if rr.get("rebuildable") != "fully_rebuildable":
        bad("runtime-reports must be fully_rebuildable")
    else:
        ok("temporary runtime reports are fully_rebuildable")

    # 7. persistent / unresolved evidence has a future target
    for n, s in stores.items():
        envstrats = set(s["strategyByEnvironment"].values())
        if "unresolved" in envstrats and not s.get("futureTarget"):
            bad(f"unresolved store {n} must record a futureTarget")
    if not [f for f in failures if "futureTarget" in f]:
        ok("unresolved/persistent-evidence stores record a future target")

    # 8. backup lifecycle separate from active data
    backup = cat["deferred"]["backup-artifacts"]
    if not backup.get("separateFromActiveWorkspace"):
        bad("backup lifecycle must be separate from active workspace")
    else:
        ok("backup lifecycle separated from active workspace data")

    # 9. production unresolved stores fail closed (never productionConfigured)
    bads = [
        n
        for n, s in stores.items()
        if s["strategyByEnvironment"]["production"] == "unresolved"
        and s.get("productionConfigured")
    ]
    if bads:
        bad(f"production unresolved stores must fail closed (productionConfigured=false): {bads}")
    else:
        ok("production unresolved stores fail closed")

    # 10. no fake durability claim: ephemeral durability implies not 'durable' rebuild promise
    for n, s in stores.items():
        if s["durability"] == "ephemeral" and s.get("persistenceSolved") is True:
            bad(f"{n} claims persistenceSolved while ephemeral (fake durability)")
    if not [f for f in failures if "fake durability" in f]:
        ok("no fake durability claims")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("KUBERNETES_DATA_LIFECYCLE_VERIFY: FAIL")
        return 1
    print("KUBERNETES_DATA_LIFECYCLE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
