#!/usr/bin/env bash
# Step 55 (Stage 57A) -- combined non-production Kubernetes runtime smoke.
#
# Chains the Step 51 + 52 + 53 + 54 baselines (deduped), the cluster preflight, the
# runtime smoke verifiers (which honestly emit BLOCKED_NO_SAFE_CLUSTER with no safe
# cluster), the operations + Admin Console + safety-field verifiers and the targeted
# tests. NO production namespace / deploy / ArgoCD sync / GitHub write / image push /
# production action. Never fakes a cluster smoke.
#
# Final marker: NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY: PASS | BLOCKED_NO_SAFE_CLUSTER | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib/baseline_run_guard.sh
baseline_run_once "$(basename "$0")"

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAILS=0
BLOCKED=0
step() { echo ""; echo "########## $1 ##########"; }

# runv NAME CMD... -- run a python verifier, show its tail, classify its marker.
runv() {
  local name="$1"; shift
  local out marker
  out="$("$@" 2>&1)"
  echo "$out" | tail -4
  marker="$(echo "$out" | grep -E "^${name}: " | tail -1)"
  case "$marker" in
    *": PASS") : ;;
    *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> classified BLOCKED" ;;
    *) FAILS=$((FAILS+1)); echo "  -> classified FAIL ($marker)" ;;
  esac
}

step "1-4. Step 51/52/53/54 baselines (deduped via Step 54 combined)"
b="$(bash scripts/verify_application_security_supply_chain_baseline.sh 2>&1)"
echo "$b" | grep -E '_BASELINE_VERIFY: (PASS|FAIL)|APPLICATION_SECURITY_SUPPLY_CHAIN_BASELINE_VERIFY' | tail -8
if ! echo "$b" | grep -q "APPLICATION_SECURITY_SUPPLY_CHAIN_BASELINE_VERIFY: PASS"; then
  echo "  -> prior baselines FAILED"; FAILS=$((FAILS+1))
fi

step "5. non-production cluster preflight"
runv NONPROD_CLUSTER_PREFLIGHT_VERIFY "$PY" scripts/verify_nonproduction_cluster_preflight.py

step "6. namespace plan"
runv NONPROD_NAMESPACE_PLAN_VERIFY "$PY" scripts/verify_nonproduction_namespace_plan.py

step "7. helm runtime smoke (render/install gated on safe cluster)"
runv NONPROD_HELM_RUNTIME_SMOKE_VERIFY "$PY" scripts/verify_nonproduction_helm_runtime_smoke.py

step "8. pod startup smoke"
runv NONPROD_POD_STARTUP_SMOKE_VERIFY "$PY" scripts/verify_nonproduction_pod_startup.py

step "9. service health smoke"
runv NONPROD_SERVICE_HEALTH_SMOKE_VERIFY "$PY" scripts/verify_nonproduction_service_health.py

step "10. service connectivity smoke"
runv NONPROD_SERVICE_CONNECTIVITY_SMOKE_VERIFY "$PY" scripts/verify_nonproduction_service_connectivity.py

step "11. NetworkPolicy smoke"
runv NONPROD_NETWORKPOLICY_SMOKE_VERIFY "$PY" scripts/verify_nonproduction_networkpolicy_smoke.py

step "12. storage smoke"
runv NONPROD_STORAGE_SMOKE_VERIFY "$PY" scripts/verify_nonproduction_storage_smoke.py

step "13. securityContext smoke"
runv NONPROD_SECURITYCONTEXT_SMOKE_VERIFY "$PY" scripts/verify_nonproduction_securitycontext_smoke.py

step "14. batch job dependency smoke"
runv NONPROD_BATCH_JOB_SMOKE_VERIFY "$PY" scripts/verify_nonproduction_batch_job_smoke.py

step "15. runtime smoke report"
runv NONPROD_RUNTIME_SMOKE_REPORT_VERIFY "$PY" scripts/verify_nonproduction_runtime_smoke_report.py

step "16. runtime operations visibility (live)"
runv NONPROD_RUNTIME_OPERATIONS_VISIBILITY_VERIFY "$PY" scripts/verify_nonproduction_runtime_operations_visibility.py

step "17. Admin Console non-production runtime smoke"
runv ADMIN_CONSOLE_NONPROD_RUNTIME_SMOKE_VERIFY "$PY" scripts/verify_admin_console_nonproduction_runtime_smoke.py

step "18. runtime smoke safety fields (live)"
runv NONPROD_RUNTIME_SAFETY_FIELDS_VERIFY "$PY" scripts/verify_nonproduction_runtime_safety_fields.py

step "19. targeted non-production runtime smoke tests"
"$PY" -m pytest -q \
  tests/test_nonproduction_cluster_preflight.py \
  tests/test_nonproduction_namespace_plan.py \
  tests/test_nonproduction_helm_smoke_guardrails.py \
  tests/test_nonproduction_runtime_smoke_report_schema.py \
  tests/test_nonproduction_runtime_operations_api.py \
  tests/test_nonproduction_runtime_operations_read_only.py \
  tests/test_nonproduction_runtime_safety_fields.py \
  tests/test_admin_console_nonproduction_runtime_smoke.py \
  tests/test_nonproduction_runtime_no_mutation_actions.py \
  tests/test_nonproduction_runtime_production_not_ready.py 2>&1 | tail -4
if [ "${PIPESTATUS[0]}" -ne 0 ]; then echo "  -> tests FAILED"; FAILS=$((FAILS+1)); fi

step "20. safety posture: no production deploy / ArgoCD sync; production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('nonprod_kubernetes_smoke_enabled'), d.get('nonprod_runtime_smoke_production_ready'), d.get('kubernetes_production_deploy_performed'), d.get('argocd_sync_performed'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x x x x x")
case "$pa" in
  "True False False False 0")
    echo "  [PASS] smoke enabled; not production ready; no deploy; no argocd sync; production_executed=0 ($pa)" ;;
  *)
    echo "  [FAIL] unexpected runtime safety posture: $pa"; FAILS=$((FAILS+1)) ;;
esac

echo ""
echo "=== classification: FAILS=$FAILS BLOCKED=$BLOCKED ==="
if [ "$FAILS" -ne 0 ]; then
  echo "NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY: FAIL"
  exit 1
fi
if [ "$BLOCKED" -ne 0 ]; then
  echo "NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY: BLOCKED_NO_SAFE_CLUSTER"
  exit 0
fi
echo "NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY: PASS"
exit 0
