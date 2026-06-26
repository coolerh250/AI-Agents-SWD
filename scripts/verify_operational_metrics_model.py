#!/usr/bin/env python3
"""Step 58 -- operational metrics model verifier (static).

Marker: OPERATIONAL_METRICS_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = "OPERATIONAL_METRICS_MODEL_VERIFY"
MODEL = ROOT / "infra" / "operations" / "operational-metrics-model.yaml"

REQUIRED_DOMAINS = {
    "delivery",
    "work_items",
    "dispatch",
    "agents",
    "workflows",
    "runtime",
    "gitops",
    "security",
    "approval",
    "audit",
    "safety",
}
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not MODEL.is_file():
        bad("missing operational-metrics-model.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    m = (yaml.safe_load(MODEL.read_text(encoding="utf-8")) or {}).get("operationalMetrics", {})
    if m.get("productionReady") is not False:
        bad("model productionReady must be false")
    if not REQUIRED_DOMAINS <= set(m.get("domains", [])):
        bad(f"model missing domains: {sorted(REQUIRED_DOMAINS - set(m.get('domains', [])))}")
    if not m.get("metricTypes"):
        bad("model must declare metricTypes")
    rules = m.get("rules", {})
    for r in (
        "metricsAreVisibilityOnly",
        "metricsAreNotProductionApproval",
        "metricsMayShowStaleOrUnavailable",
        "missingDataMustNotBeHidden",
        "noSecretOutput",
        "doesNotClaimProductionReadiness",
    ):
        if rules.get(r) is not True:
            bad(f"model rule {r} must be true")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] metrics model: 11 domains, visibility-only, productionReady=false")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
