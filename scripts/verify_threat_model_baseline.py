#!/usr/bin/env python3
"""Step 54.4 -- threat model baseline verifier.

Marker: THREAT_MODEL_BASELINE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"

REQUIRED_ASSETS = {
    "admin_console",
    "operator_actions",
    "identity_oidc",
    "secret_management",
    "audit_integrity",
    "runtime_operations",
    "kubernetes_helm_gitops_baseline",
    "workspace_operator",
    "agent_execution_pipeline",
    "delivery_package",
    "local_scan_toolchain",
    "sbom_image_baseline",
    "backup_restore",
    "future_github_pr_flow",
    "future_argocd_sync",
    "future_production_deployment",
    "llm_integration",
    "notification_slack_email",
    "future_google_drive_integration",
}

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _load(name: str) -> dict:
    p = SEC / name
    if not p.is_file():
        bad(f"missing {name}")
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def main() -> int:
    tm = _load("threat-model-baseline.yaml").get("threatModel", {})
    taxonomy = _load("threat-category-taxonomy.yaml").get("threatCategories", {})
    cats = {c.get("id") for c in taxonomy.get("categories", [])}

    if tm.get("status") != "modeled_not_production_enforced":
        bad(f"threatModel.status unexpected: {tm.get('status')!r}")
    else:
        ok("status=modeled_not_production_enforced")

    if tm.get("productionReady") is not False:
        bad("threatModel.productionReady must be false")
    else:
        ok("productionReady=false")

    method = set(tm.get("methodology", []))
    if not {"stride_inspired", "agentic_ai_specific", "supply_chain_specific"} <= method:
        bad(f"methodology incomplete: {method}")
    else:
        ok("methodology covers stride + agentic + supply-chain")

    asset_ids = {a.get("id") for a in tm.get("assets", [])}
    missing_assets = REQUIRED_ASSETS - asset_ids
    if missing_assets:
        bad(f"threat model missing required assets: {sorted(missing_assets)}")
    else:
        ok(f"all {len(REQUIRED_ASSETS)} required assets covered")

    for field in ("trustBoundaries", "entrypoints", "dataFlows", "mitigations", "blockers"):
        if not tm.get(field):
            bad(f"threatModel.{field} empty")
    if not [f for f in failures if "empty" in f]:
        ok("trustBoundaries / entrypoints / dataFlows / mitigations / blockers present")

    threats = tm.get("threats", [])
    if not threats:
        bad("threatModel.threats empty")
    else:
        ok(f"{len(threats)} threats modeled")
        unknown = [t.get("id") for t in threats if t.get("category") not in cats]
        if unknown:
            bad(f"threats reference unknown categories: {unknown}")
        else:
            ok("every threat category is in the taxonomy")

    # Strictness: no production-ready / approval language anywhere.
    blob = str(tm).lower()
    if "production_ready" in blob or "production_approved" in blob:
        bad("threat model contains production_ready/production_approved")
    else:
        ok("no production-ready / approval language")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("THREAT_MODEL_BASELINE_VERIFY: FAIL")
        return 1
    print("THREAT_MODEL_BASELINE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
