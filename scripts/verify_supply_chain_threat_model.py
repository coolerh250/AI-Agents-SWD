#!/usr/bin/env python3
"""Step 54.4 -- supply-chain threat model verifier.

Marker: SUPPLY_CHAIN_THREAT_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"

REQUIRED_SCENARIOS = {
    "dependency_compromise",
    "missing_python_lockfile",
    "malicious_package",
    "docker_base_image_compromise",
    "mutable_tag",
    "missing_image_digest",
    "root_container",
    "missing_sbom",
    "missing_image_vulnerability_scan",
    "missing_signing_attestation",
    "scanner_tool_compromise",
    "secret_leakage_in_reports",
    "registry_credential_compromise",
    "future_github_pr_manipulation",
}

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    p = SEC / "supply-chain-threat-model.yaml"
    if not p.is_file():
        bad("missing supply-chain-threat-model.yaml")
        print("SUPPLY_CHAIN_THREAT_MODEL_VERIFY: FAIL")
        return 1
    model = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("supplyChainThreatModel", {})

    if model.get("productionReady") is not False:
        bad("supplyChainThreatModel.productionReady must be false")
    else:
        ok("productionReady=false")

    scenarios = {t.get("scenario") for t in model.get("threats", [])}
    missing = REQUIRED_SCENARIOS - scenarios
    if missing:
        bad(f"missing supply-chain scenarios: {sorted(missing)}")
    else:
        ok(f"all {len(REQUIRED_SCENARIOS)} required supply-chain scenarios covered")

    linked = model.get("linkedBaselineBlockers", {})
    if not all(k in linked for k in ("step_54_1", "step_54_2", "step_54_3")):
        bad("linkedBaselineBlockers must reference Step 54.1/54.2/54.3")
    else:
        ok("linked to Step 54.1/54.2/54.3 blockers")

    blob = str(model).lower()
    if "production_ready" in blob or "production_approved" in blob:
        bad("supply-chain threat model contains production_ready/production_approved")
    else:
        ok("no production-ready / approval language")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SUPPLY_CHAIN_THREAT_MODEL_VERIFY: FAIL")
        return 1
    print("SUPPLY_CHAIN_THREAT_MODEL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
