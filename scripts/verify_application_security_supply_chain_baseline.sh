#!/usr/bin/env bash
# Step 54.4 (Stage 56D) -- combined application security & supply chain baseline.
#
# Integrates the Step 51 + 52 + 53 + 54.1 + 54.2 + 54.3 baselines, then the threat
# model / release risk / evidence package / readiness verifiers, the integrated
# operations + Admin Console + safety-field verifiers and the targeted tests.
# LOCAL-ONLY: NO GitHub write, NO PR creation, NO registry login, NO image push,
# NO signing/attestation, NO external upload, NO release gate, NO production action.
#
# Marker: APPLICATION_SECURITY_SUPPLY_CHAIN_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
# Establish the per-run dedup scope so the chained prior baselines (which overlap)
# each run exactly once; a failed baseline still propagates (exit-code replay).
source scripts/lib/baseline_run_guard.sh
baseline_run_once "$(basename "$0")"

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 51 Kubernetes/Helm/ArgoCD integrated baseline"
bash scripts/verify_kubernetes_helm_argocd_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "2. Step 52 identity foundation integrated baseline"
bash scripts/verify_identity_foundation_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "3. Step 53 secret management foundation baseline"
bash scripts/verify_secret_management_foundation_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "4. Step 54.1 security & supply chain policy baseline"
bash scripts/verify_security_supply_chain_policy_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "5. Step 54.2 local scan toolchain baseline"
bash scripts/verify_security_scan_toolchain_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "6. Step 54.3 SBOM / container security baseline"
bash scripts/verify_sbom_container_security_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "7. threat model baseline verify"
"$PY" scripts/verify_threat_model_baseline.py | tail -3; need ${PIPESTATUS[0]}

step "8. agent threat model verify"
"$PY" scripts/verify_agent_threat_model.py | tail -3; need ${PIPESTATUS[0]}

step "9. supply-chain threat model verify"
"$PY" scripts/verify_supply_chain_threat_model.py | tail -3; need ${PIPESTATUS[0]}

step "10. runtime / GitOps threat model verify"
"$PY" scripts/verify_runtime_gitops_threat_model.py | tail -3; need ${PIPESTATUS[0]}

step "11. release risk summary model verify"
"$PY" scripts/verify_release_risk_summary_model.py | tail -3; need ${PIPESTATUS[0]}

step "12. security evidence package verify"
"$PY" scripts/verify_security_evidence_package.py | tail -3; need ${PIPESTATUS[0]}

step "13. release risk summary verify"
"$PY" scripts/verify_release_risk_summary.py | tail -3; need ${PIPESTATUS[0]}

step "14. security readiness report verify"
"$PY" scripts/verify_security_readiness_report.py | tail -3; need ${PIPESTATUS[0]}

step "15. integrated security operations visibility verify"
"$PY" scripts/verify_security_integrated_operations_visibility.py | tail -3; need ${PIPESTATUS[0]}

step "16. Admin Console integrated security verify"
"$PY" scripts/verify_admin_console_security_integrated.py | tail -3; need ${PIPESTATUS[0]}

step "17. integrated security safety fields verify"
"$PY" scripts/verify_security_integrated_safety_fields.py | tail -3; need ${PIPESTATUS[0]}

step "18. targeted threat model / release risk / evidence tests"
"$PY" -m pytest -q \
  tests/test_threat_model_baseline.py \
  tests/test_agent_threat_model.py \
  tests/test_supply_chain_threat_model.py \
  tests/test_runtime_gitops_threat_model.py \
  tests/test_threat_category_taxonomy.py \
  tests/test_release_risk_summary_model.py \
  tests/test_release_risk_scoring_policy.py \
  tests/test_security_evidence_package_schema.py \
  tests/test_security_evidence_package_generator.py \
  tests/test_release_risk_summary_generator.py \
  tests/test_security_readiness_report.py \
  tests/test_security_integrated_operations_api.py \
  tests/test_security_integrated_operations_read_only.py \
  tests/test_security_integrated_safety_fields.py \
  tests/test_admin_console_security_integrated.py \
  tests/test_security_integrated_no_mutation_actions.py \
  tests/test_security_integrated_production_not_ready.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "19. safety posture: integrated security + no release gate + production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('security_step54_integrated'), d.get('security_release_gate_enabled'), d.get('security_step54_production_ready'), d.get('security_missing_evidence_blocks_production'), d.get('security_critical_finding_blocks_production'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x x x x x x")
case "$pa" in
  "True False False True True 0")
    echo "  [PASS] step54 integrated; no release gate; not production ready; fail-closed; production_executed=0 ($pa)" ;;
  *)
    echo "  [FAIL] unexpected integrated safety posture: $pa"; FAIL=1 ;;
esac

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "APPLICATION_SECURITY_SUPPLY_CHAIN_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "APPLICATION_SECURITY_SUPPLY_CHAIN_BASELINE_VERIFY: PASS"
