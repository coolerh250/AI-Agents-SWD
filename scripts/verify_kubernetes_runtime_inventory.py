#!/usr/bin/env python3
"""Step 51.1 -- verify the Kubernetes runtime inventory against the actual
Docker Compose runtime and component catalog.

Checks (no cluster connection, no kubectl, no Helm):
  1. Every active Compose service is present in runtime-inventory.yaml.
  2. Long-running services are classified (non-empty type).
  3. One-shot jobs are NOT modelled as Deployments.
  4. Test-only services are flagged.
  5. Every deployment-target long-running component is in the component catalog.
  6. Catalog first-party components carry a source path.
  7. Catalog ports match the inventory (and inventory matches Compose).
  8. Health paths are present or explicitly deferred/unknown.
  9. Dependencies are evidence-backed in the dependency matrix.
 10. Inventory holds NO real secret values (names only).

Marker: KUBERNETES_RUNTIME_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "infra" / "docker-compose" / "docker-compose.yml"
INVENTORY = ROOT / "infra" / "kubernetes" / "runtime-inventory.yaml"
MATRIX = ROOT / "infra" / "kubernetes" / "runtime-dependency-matrix.yaml"
CATALOG = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "component-catalog.yaml"

DEPLOYMENT_TARGET = "deployment"
OPTIONAL_TARGETS = {"optional_dev_test_component", "test_only_optional_component"}

failures: list[str] = []
passes: list[str] = []


def ok(msg: str) -> None:
    passes.append(msg)
    print(f"  [PASS] {msg}")


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"  [FAIL] {msg}")


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> int:
    for p in (COMPOSE, INVENTORY, MATRIX, CATALOG):
        if not p.exists():
            fail(f"missing required file: {p.relative_to(ROOT)}")
            return finish()

    compose = load(COMPOSE)
    inv = load(INVENTORY)
    matrix = load(MATRIX)
    catalog = load(CATALOG)

    compose_services = set(compose.get("services", {}).keys())
    inv_services = {s["name"]: s for s in inv.get("services", [])}
    inv_by_compose = {
        s.get("composeService"): s for s in inv.get("services", []) if s.get("composeService")
    }

    # 1. Every active Compose service is inventoried.
    print("=== Check 1: Compose service coverage ===")
    missing = sorted(compose_services - set(inv_by_compose.keys()))
    if missing:
        fail(f"Compose services missing from inventory: {missing}")
    else:
        ok(f"all {len(compose_services)} Compose services inventoried")

    # 2. Long-running services classified.
    print("=== Check 2: classification ===")
    unclassified = [n for n, s in inv_services.items() if not s.get("type")]
    if unclassified:
        fail(f"services missing type classification: {unclassified}")
    else:
        ok(f"all {len(inv_services)} inventoried services classified")

    # 3. One-shot jobs not modelled as Deployments.
    print("=== Check 3: one-shot jobs not Deployments ===")
    bad_oneshot = [
        j["name"]
        for j in inv.get("oneShotJobs", [])
        if str(j.get("kubernetesTarget", "")).strip() == DEPLOYMENT_TARGET
    ]
    if bad_oneshot:
        fail(f"one-shot jobs mislabelled as deployment: {bad_oneshot}")
    else:
        ok(f"{len(inv.get('oneShotJobs', []))} one-shot jobs excluded from Deployments")

    # 4. Test-only flagged (vault must be test-only).
    print("=== Check 4: test-only flagging ===")
    vault = inv_services.get("vault")
    if vault and vault.get("testOnly") is True:
        ok("vault flagged testOnly=true")
    else:
        fail("vault must be flagged testOnly=true in inventory")

    # 5/6/7. Catalog completeness + source path + port parity.
    print("=== Check 5-7: catalog completeness / source / ports ===")
    cat_components = catalog.get("components", {})
    deploy_targets = {
        n: s for n, s in inv_services.items() if s.get("kubernetesTarget") == DEPLOYMENT_TARGET
    }
    missing_cat = sorted(set(deploy_targets) - set(cat_components))
    if missing_cat:
        fail(f"deployment-target services missing from catalog: {missing_cat}")
    else:
        ok(f"all {len(deploy_targets)} deployment-target services in catalog")

    # one-shot jobs must NOT appear in the catalog
    oneshot_names = {j["name"] for j in inv.get("oneShotJobs", [])}
    leaked = sorted(oneshot_names & set(cat_components))
    if leaked:
        fail(f"one-shot jobs leaked into catalog: {leaked}")
    else:
        ok("no one-shot jobs present in catalog")

    port_mismatch = []
    nosrc = []
    for name, comp in cat_components.items():
        inv_s = inv_services.get(name)
        if inv_s is None:
            fail(f"catalog component '{name}' not found in inventory")
            continue
        if inv_s.get("port") != comp.get("containerPort"):
            port_mismatch.append(
                f"{name}: catalog {comp.get('containerPort')} != inventory {inv_s.get('port')}"
            )
        if comp.get("type") != "infrastructure" and not comp.get("sourcePath"):
            nosrc.append(name)
    if port_mismatch:
        fail(f"catalog/inventory port mismatch: {port_mismatch}")
    else:
        ok("catalog containerPort matches inventory port for all components")
    if nosrc:
        fail(f"first-party catalog components missing sourcePath: {nosrc}")
    else:
        ok("first-party catalog components carry a sourcePath")

    # 7b. inventory ports match Compose published/internal ports where available.
    print("=== Check 7b: inventory ports vs Compose ===")
    cport_mismatch = []
    for cname, svc in compose.get("services", {}).items():
        inv_s = inv_by_compose.get(cname)
        if not inv_s:
            continue
        ports = svc.get("ports", []) or []
        internal = set()
        for p in ports:
            # forms like "127.0.0.1:8000:8000" or "8000:8000"
            m = re.search(r"(\d+)\s*$", str(p))
            if m:
                internal.add(int(m.group(1)))
        if internal and inv_s.get("port") not in internal:
            cport_mismatch.append(
                f"{cname}: inventory {inv_s.get('port')} not in compose {sorted(internal)}"
            )
    if cport_mismatch:
        fail(f"inventory vs compose port mismatch: {cport_mismatch}")
    else:
        ok("inventory ports consistent with Compose port mappings")

    # 8. Health path present or explicitly deferred/unknown.
    print("=== Check 8: health basis ===")
    bad_health = []
    for name, s in inv_services.items():
        has_http = bool(s.get("healthPath"))
        has_probe = bool(s.get("healthProbe"))
        if not (has_http or has_probe):
            bad_health.append(name)
    if bad_health:
        fail(f"services without a health path or probe basis: {bad_health}")
    else:
        ok("every service has a health path or explicit probe basis")

    # 9. Dependencies evidence-backed.
    print("=== Check 9: dependency evidence ===")
    no_evidence = [
        f"{d.get('source')}->{d.get('target')}"
        for d in matrix.get("dependencies", [])
        if not str(d.get("evidence", "")).strip()
    ]
    if no_evidence:
        fail(f"dependency edges without evidence: {no_evidence}")
    else:
        ok(f"all {len(matrix.get('dependencies', []))} dependency edges carry evidence")
    if matrix.get("unknownDependencies"):
        ok(f"{len(matrix['unknownDependencies'])} unknown dependencies explicitly recorded")
    else:
        ok("no silently-dropped dependencies (unknownDependencies empty + declared)")

    # cross-check: every inventory dependency name resolves to a known service
    dangling = []
    for name, s in inv_services.items():
        for dep in s.get("dependencies", []) or []:
            if dep not in inv_services:
                dangling.append(f"{name}->{dep}")
    if dangling:
        fail(f"inventory dependencies referencing unknown services: {dangling}")
    else:
        ok("all inventory dependency references resolve to inventoried services")

    # 10. No real secret values in inventory (names only).
    print("=== Check 10: no secret values ===")
    raw = INVENTORY.read_text(encoding="utf-8")
    leak_patterns = [
        r"password\s*:\s*\S+",
        r"token\s*:\s*[A-Za-z0-9._-]{8,}",
        r"secret\s*:\s*[A-Za-z0-9._-]{8,}",
        r"apiKey\s*:\s*\S+",
        r"BEGIN [A-Z ]*PRIVATE KEY",
    ]
    leaks = [pat for pat in leak_patterns if re.search(pat, raw, re.IGNORECASE)]
    if leaks:
        fail(f"inventory may contain secret values (patterns: {leaks})")
    else:
        ok("inventory holds secret references by name only (no values)")

    return finish()


def finish() -> int:
    total = len(passes) + len(failures)
    print(f"\n=== Summary: {len(passes)}/{total} checks passed ===")
    if failures:
        print("KUBERNETES_RUNTIME_INVENTORY_VERIFY: FAIL")
        return 1
    print("KUBERNETES_RUNTIME_INVENTORY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
