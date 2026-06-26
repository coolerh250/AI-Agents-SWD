#!/usr/bin/env python3
"""Step 58 -- operational metrics source inventory verifier (static).

Marker: OPERATIONAL_METRICS_SOURCES_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = "OPERATIONAL_METRICS_SOURCES_VERIFY"
INV = ROOT / "infra" / "operations" / "operational-metrics-source-inventory.yaml"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not INV.is_file():
        bad("missing operational-metrics-source-inventory.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    inv = (yaml.safe_load(INV.read_text(encoding="utf-8")) or {}).get(
        "operationalMetricsSourceInventory", {}
    )
    if inv.get("productionReady") is not False:
        bad("source inventory productionReady must be false")
    sources = inv.get("sources", [])
    if not sources:
        bad("no sources declared")
    for s in sources:
        for field in ("name", "type", "freshness", "availability"):
            if field not in s:
                bad(f"source {s.get('name', '?')} missing {field}")
        if s.get("secretExposureRisk") is not False:
            bad(f"source {s.get('name')} must declare secretExposureRisk=false")
    rules = inv.get("rules", {})
    for r in (
        "missingRuntimeReportShownAsStale",
        "runtimeReportsNeverCommitted",
        "noArbitraryPath",
        "onlyAllowlistedPaths",
        "noSecretExposure",
    ):
        if rules.get(r) is not True:
            bad(f"rule {r} must be true")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] {len(sources)} sources inventoried; missing-as-stale; no secret exposure")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
