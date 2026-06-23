#!/usr/bin/env bash
# Step 54.2 -- combined local security scan toolchain baseline.
#
# Chains the Step 51 + 52 + 53 + 54.1 baselines, then the local scan capability /
# boundary / target / secret / SAST / dependency / normalization / operations /
# Admin Console / safety verifiers and the targeted tests. LOCAL-ONLY: NO external
# scanner upload, NO network scanner call, NO token, NO GitHub write, NO image
# push, NO production gate, NO full regression.
#
# Marker: SECURITY_SCAN_TOOLCHAIN_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."

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

step "5. local scanner capabilities verify"
"$PY" scripts/verify_local_scanner_capabilities.py | tail -3; need ${PIPESTATUS[0]}

step "6. scanner execution boundary verify"
"$PY" scripts/verify_scanner_execution_boundary.py | tail -3; need ${PIPESTATUS[0]}

step "7. scan target catalog verify"
"$PY" scripts/verify_scan_target_catalog.py | tail -3; need ${PIPESTATUS[0]}

step "8. local secret scan baseline verify"
"$PY" scripts/verify_local_secret_scan_baseline.py | tail -3; need ${PIPESTATUS[0]}

step "9. local SAST baseline verify"
"$PY" scripts/verify_local_sast_baseline.py | tail -3; need ${PIPESTATUS[0]}

step "10. local dependency scan baseline verify"
"$PY" scripts/verify_local_dependency_scan_baseline.py | tail -3; need ${PIPESTATUS[0]}

step "11. scan result normalization verify"
"$PY" scripts/verify_security_scan_result_normalization.py | tail -3; need ${PIPESTATUS[0]}

step "12. scan operations visibility verify"
"$PY" scripts/verify_security_scan_operations_visibility.py | tail -3; need ${PIPESTATUS[0]}

step "13. Admin Console scan posture verify"
"$PY" scripts/verify_admin_console_scan_posture.py | tail -3; need ${PIPESTATUS[0]}

step "14. scan safety fields verify"
"$PY" scripts/verify_security_scan_safety_fields.py | tail -3; need ${PIPESTATUS[0]}

step "15. targeted scan toolchain tests"
"$PY" -m pytest -q \
  tests/test_local_scanner_capabilities.py \
  tests/test_scanner_execution_boundary.py \
  tests/test_scan_target_catalog.py \
  tests/test_scan_exclusion_policy.py \
  tests/test_security_finding_schema.py \
  tests/test_security_finding_normalizer.py \
  tests/test_local_secret_scan_baseline.py \
  tests/test_local_sast_baseline.py \
  tests/test_local_dependency_scan_baseline.py \
  tests/test_scan_result_artifact_schema.py \
  tests/test_security_scan_result_normalization.py \
  tests/test_security_scan_status_summary_model.py \
  tests/test_security_scan_operations_api.py \
  tests/test_security_scan_operations_read_only.py \
  tests/test_security_scan_safety_fields.py \
  tests/test_admin_console_scan_posture.py \
  tests/test_security_scan_no_mutation_actions.py \
  tests/test_security_scan_no_secret_leak.py \
  tests/test_security_scan_production_not_ready.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "16. safety posture: local scan baseline + production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('security_scan_external_upload_enabled'), d.get('security_scan_network_enabled'), d.get('security_scan_run_endpoint_enabled'), d.get('security_scan_production_ready'), d.get('security_local_scan_baseline_enabled'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x x x x x x")
case "$pa" in
  "False False False False True 0")
    echo "  [PASS] local scan baseline enabled; no upload/network/run-endpoint; not production ready; production_executed=0 ($pa)" ;;
  *)
    echo "  [FAIL] unexpected safety posture: $pa"; FAIL=1 ;;
esac

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "SECURITY_SCAN_TOOLCHAIN_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "SECURITY_SCAN_TOOLCHAIN_BASELINE_VERIFY: PASS"
