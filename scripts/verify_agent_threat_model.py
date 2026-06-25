#!/usr/bin/env python3
"""Step 54.4 -- agent-specific threat model verifier.

Marker: AGENT_THREAT_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"

REQUIRED_SCENARIOS = {
    "agent_modifies_workspace",
    "agent_generates_code",
    "agent_generates_deployment_recommendation",
    "agent_runs_verification",
    "agent_produces_delivery_package",
    "agent_misjudges_approval",
    "agent_references_wrong_context",
    "prompt_injection",
    "tool_misuse",
    "unauthorized_production_action",
    "human_approval_bypass",
    "audit_omission",
    "secret_exfiltration",
    "github_write_future_risk",
    "argocd_sync_future_risk",
}
REQUIRED_MITIGATIONS = {
    "production_changes_require_human_approval",
    "production_executed_flag",
    "hard_safety_actions",
    "operator_action_allowlist",
    "audit_trail",
    "no_github_write",
    "no_deploy_or_sync",
    "no_external_scanner_upload",
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
    p = SEC / "agent-threat-model.yaml"
    if not p.is_file():
        bad("missing agent-threat-model.yaml")
        print("AGENT_THREAT_MODEL_VERIFY: FAIL")
        return 1
    model = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("agentThreatModel", {})

    if model.get("productionReady") is not False:
        bad("agentThreatModel.productionReady must be false")
    else:
        ok("productionReady=false")

    scenarios = {t.get("scenario") for t in model.get("threats", [])}
    missing = REQUIRED_SCENARIOS - scenarios
    if missing:
        bad(f"missing agentic threat scenarios: {sorted(missing)}")
    else:
        ok(f"all {len(REQUIRED_SCENARIOS)} required agentic scenarios covered")

    mit = set(model.get("existingMitigations", []))
    miss_mit = REQUIRED_MITIGATIONS - mit
    if miss_mit:
        bad(f"missing existing mitigations: {sorted(miss_mit)}")
    else:
        ok("existing mitigations enumerated (approval / flag / allowlist / no-deploy / no-upload)")

    if not model.get("remainingBlockers"):
        bad("remainingBlockers empty")
    else:
        ok("remaining blockers listed")

    blob = str(model).lower()
    if "production_ready" in blob or "production_approved" in blob:
        bad("agent threat model contains production_ready/production_approved")
    else:
        ok("no production-ready / approval language")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("AGENT_THREAT_MODEL_VERIFY: FAIL")
        return 1
    print("AGENT_THREAT_MODEL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
