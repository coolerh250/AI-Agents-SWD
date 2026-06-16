#!/usr/bin/env python3
"""Step 51.2B -- network topology verifier.

Cross-checks the dependency matrix, the canonical connectivity catalog, and the
chart's networkPolicy.internalEdges for consistency and evidence. Source-level
only -- no rendering, no cluster.

Marker: KUBERNETES_NETWORK_TOPOLOGY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "infra" / "kubernetes" / "runtime-dependency-matrix.yaml"
CATALOG = ROOT / "infra" / "kubernetes" / "network-connectivity-catalog.yaml"
COMPONENT_CATALOG = (
    ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "component-catalog.yaml"
)
VALUES = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "values.yaml"

OBS_TARGETS = {"tempo", "prometheus", "grafana", "alertmanager"}
OBS_SOURCES = {"prometheus", "grafana", "alertmanager"}

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


def edge_key(e: dict) -> tuple:
    return (e["source"], e["target"], int(e["port"]))


def main() -> int:
    matrix = load(MATRIX)
    catalog = load(CATALOG)
    components = set(load(COMPONENT_CATALOG)["components"])
    values = load(VALUES)

    deps = matrix["dependencies"]
    internal = [
        e for e in deps if e["target"] not in OBS_TARGETS and e["source"] not in OBS_SOURCES
    ]
    observ = [e for e in deps if e["target"] in OBS_TARGETS or e["source"] in OBS_SOURCES]

    print(
        f"=== Dependency matrix: {len(deps)} edges ({len(internal)} internal, {len(observ)} observability-deferred) ==="
    )

    # 1. matrix evidence + fields
    for e in deps:
        for f in ("source", "target", "protocol", "port", "purpose", "evidence"):
            if not str(e.get(f, "")).strip() and e.get(f) is not False:
                bad(f"matrix edge missing {f}: {e}")
    if not failures:
        ok("every matrix edge has source/target/protocol/port/purpose/evidence")

    # 2. no duplicates, no unexpected self-edges
    keys = [edge_key(e) for e in deps]
    dups = {k for k in keys if keys.count(k) > 1}
    if dups:
        bad(f"duplicate edges: {dups}")
    else:
        ok("no duplicate edges")
    selfedges = [e for e in deps if e["source"] == e["target"]]
    if selfedges:
        bad(f"unexpected self-edges: {selfedges}")
    else:
        ok("no self-edges")

    # 3. components known (internal endpoints must be catalog components)
    unknown = set()
    for e in internal:
        for end in (e["source"], e["target"]):
            if end not in components:
                unknown.add(end)
    if unknown:
        bad(f"internal edges reference unknown components: {unknown}")
    else:
        ok("all internal edge endpoints are known catalog components")

    # 4. catalog internalEdges == matrix internal edges
    cat_edges = catalog["internalEdges"]
    cat_keys = {edge_key(e) for e in cat_edges}
    mat_keys = {edge_key(e) for e in internal}
    if cat_keys != mat_keys:
        bad(
            f"catalog vs matrix internal-edge mismatch: only-catalog={cat_keys - mat_keys} only-matrix={mat_keys - cat_keys}"
        )
    else:
        ok(f"connectivity catalog matches matrix internal edges ({len(cat_keys)})")

    # 5. values internalEdges == catalog internalEdges
    val_edges = values["networkPolicy"]["internalEdges"]
    val_keys = {edge_key(e) for e in val_edges}
    if val_keys != cat_keys:
        bad(
            f"values vs catalog internal-edge mismatch: only-values={val_keys - cat_keys} only-catalog={cat_keys - val_keys}"
        )
    else:
        ok(f"chart values.networkPolicy.internalEdges match the catalog ({len(val_keys)})")

    # 6. external dependencies all disabled
    ext = catalog.get("externalDependencies", [])
    enabled_ext = [d for d in ext if d.get("enabled") or d.get("policyGenerated")]
    if enabled_ext:
        bad(f"external dependencies must all be disabled: {enabled_ext}")
    else:
        ok(f"all {len(ext)} external dependencies disabled (no egress generated)")

    # 7. infrastructure allowedSources consistent with edges
    for infra in ("postgres", "redis"):
        want = sorted({e["source"] for e in internal if e["target"] == infra})
        got = sorted(catalog["infrastructure"][infra]["allowedSources"])
        if want != got:
            bad(f"{infra} allowedSources mismatch: catalog={got} matrix={want}")
        else:
            ok(f"{infra} allowedSources match matrix ({len(got)} sources)")
        if catalog["infrastructure"][infra]["externalExposureAllowed"] is not False:
            bad(f"{infra} externalExposureAllowed must be false")

    # 8. observability deferred consistent
    defrd = catalog["deferred"]["observability"]
    if defrd.get("prometheusScrape") is not False or defrd.get("otlpExport") is not False:
        bad("observability prometheusScrape/otlpExport must be deferred (false)")
    else:
        ok("observability scrape + OTLP export deferred (no policy generated)")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    print(
        f"corrected_edge_count: total={len(deps)} internal={len(internal)} observability_deferred={len(observ)}"
    )
    if failures:
        print("KUBERNETES_NETWORK_TOPOLOGY_VERIFY: FAIL")
        return 1
    print("KUBERNETES_NETWORK_TOPOLOGY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
