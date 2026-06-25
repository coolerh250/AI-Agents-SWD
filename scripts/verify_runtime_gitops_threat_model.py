#!/usr/bin/env python3
"""Step 54.4 -- runtime / Kubernetes / GitOps threat model verifier.

Marker: RUNTIME_GITOPS_THREAT_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"

REQUIRED_SCENARIOS = {
    "kubernetes_manifest_drift",
    "argocd_sync_misuse",
    "helm_values_secret_leakage",
    "networkpolicy_bypass",
    "privilege_escalation",
    "serviceaccount_token_misuse",
    "pvc_data_exposure",
    "migration_backup_job_misuse",
    "runtime_non_root_incompatibility",
    "pg_dump_psql_job_missing_runtime_dependency",
    "production_placeholder_accidentally_deployed",
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
    p = SEC / "runtime-gitops-threat-model.yaml"
    if not p.is_file():
        bad("missing runtime-gitops-threat-model.yaml")
        print("RUNTIME_GITOPS_THREAT_MODEL_VERIFY: FAIL")
        return 1
    model = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get(
        "runtimeGitopsThreatModel", {}
    )

    if model.get("productionReady") is not False:
        bad("runtimeGitopsThreatModel.productionReady must be false")
    else:
        ok("productionReady=false")

    scenarios = {t.get("scenario") for t in model.get("threats", [])}
    missing = REQUIRED_SCENARIOS - scenarios
    if missing:
        bad(f"missing runtime/gitops scenarios: {sorted(missing)}")
    else:
        ok(f"all {len(REQUIRED_SCENARIOS)} required runtime/gitops scenarios covered")

    caveat = " ".join(model.get("staticBaselineCaveat", [])).lower()
    if "step 55" not in caveat or "step 56" not in caveat:
        bad("staticBaselineCaveat must reference Step 55 + Step 56")
    else:
        ok("static baseline caveat references Step 55 (smoke) + Step 56 (ArgoCD)")

    nxt = model.get("requiredFutureSteps", [])
    if "step_55_non_production_cluster_smoke" not in nxt:
        bad("requiredFutureSteps missing step_55_non_production_cluster_smoke")
    else:
        ok("requiredFutureSteps includes Step 55 cluster smoke")

    blob = str(model).lower()
    if "production_ready" in blob or "production_approved" in blob:
        bad("runtime/gitops threat model contains production_ready/production_approved")
    else:
        ok("no production-ready / approval language")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("RUNTIME_GITOPS_THREAT_MODEL_VERIFY: FAIL")
        return 1
    print("RUNTIME_GITOPS_THREAT_MODEL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
