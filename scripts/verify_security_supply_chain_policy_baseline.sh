#!/usr/bin/env bash
# Step 54.1 -- combined application security & supply chain policy baseline.
#
# Chains the Step 51 + Step 52 + Step 53 integrated baselines, then the security
# asset / supply-chain / scan-policy / evidence / gate / operations-visibility /
# Admin Console / safety verifiers and the targeted tests. NO scanner run, NO
# external upload, NO GitHub write, NO image push, NO registry login, NO
# production action, NO full regression.
#
# Marker: SECURITY_SUPPLY_CHAIN_POLICY_BASELINE_VERIFY: PASS | FAIL
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

step "4. security asset inventory verify"
"$PY" scripts/verify_security_asset_inventory.py | tail -3; need ${PIPESTATUS[0]}

step "5. supply chain inventory verify"
"$PY" scripts/verify_supply_chain_inventory.py | tail -3; need ${PIPESTATUS[0]}

step "6. security scan policy baseline verify"
"$PY" scripts/verify_security_scan_policy_baseline.py | tail -3; need ${PIPESTATUS[0]}

step "7. security evidence model verify"
"$PY" scripts/verify_security_evidence_model.py | tail -3; need ${PIPESTATUS[0]}

step "8. security gate policy verify"
"$PY" scripts/verify_security_gate_policy.py | tail -3; need ${PIPESTATUS[0]}

step "9. security operations visibility verify"
"$PY" scripts/verify_security_operations_visibility.py | tail -3; need ${PIPESTATUS[0]}

step "10. Admin Console security posture verify"
"$PY" scripts/verify_admin_console_security_posture.py | tail -3; need ${PIPESTATUS[0]}

step "11. security safety fields verify"
"$PY" scripts/verify_security_safety_fields.py | tail -3; need ${PIPESTATUS[0]}

step "12. targeted security tests"
"$PY" -m pytest -q \
  tests/test_security_asset_inventory.py \
  tests/test_supply_chain_inventory.py \
  tests/test_dependency_surface_inventory.py \
  tests/test_security_scan_policy_catalog.py \
  tests/test_sast_policy_model.py \
  tests/test_dependency_scan_policy_model.py \
  tests/test_secret_scan_policy_model.py \
  tests/test_sbom_policy_model.py \
  tests/test_container_image_security_policy.py \
  tests/test_threat_model_input_catalog.py \
  tests/test_release_risk_input_catalog.py \
  tests/test_security_evidence_model.py \
  tests/test_security_finding_taxonomy.py \
  tests/test_security_gate_fail_closed_policy.py \
  tests/test_security_operations_api.py \
  tests/test_security_operations_read_only.py \
  tests/test_security_safety_fields.py \
  tests/test_admin_console_security_posture.py \
  tests/test_security_no_mutation_actions.py \
  tests/test_security_production_not_ready.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "13. safety posture: security foundation + production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('security_production_ready'), d.get('supply_chain_github_write_enabled'), d.get('supply_chain_image_push_enabled'), d.get('supply_chain_external_scanner_upload_enabled'), d.get('security_foundation_status'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x x x x x x")
case "$pa" in
  "False False False False modeled_not_enforced 0")
    echo "  [PASS] security not ready; no github write/image push/scanner upload; modeled_not_enforced; production_executed=0 ($pa)" ;;
  *)
    echo "  [FAIL] unexpected safety posture: $pa"; FAIL=1 ;;
esac

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "SECURITY_SUPPLY_CHAIN_POLICY_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "SECURITY_SUPPLY_CHAIN_POLICY_BASELINE_VERIFY: PASS"
