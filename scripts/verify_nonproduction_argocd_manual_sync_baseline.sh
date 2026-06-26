#!/usr/bin/env bash
# Step 56 (Stage 58A) -- combined non-production ArgoCD manual-sync baseline.
#
# Regenerates the live Step 55 + Step 56 reports, runs the Step 51/52/53/54/55
# baselines (via the deduped Step 55 combined), the 9 ArgoCD verifiers, the targeted
# tests, and the safety confirmations. NO production namespace / auto-sync / prune /
# self-heal / public ingress / LoadBalancer / production action. production_executed=0.
#
# Final marker: NONPRODUCTION_ARGOCD_MANUAL_SYNC_BASELINE_VERIFY: PASS | BLOCKED | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAILS=0
BLOCKED=0
step() { echo ""; echo "########## $1 ##########"; }

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

step "0. (re)generate live Step 55 + Step 56 reports"
runv NONPROD_RUNTIME_SMOKE_RUN "$PY" scripts/run_nonproduction_runtime_smoke.py
runv NONPROD_ARGOCD_SYNC_REPORT_RUN "$PY" scripts/run_nonproduction_argocd_manual_sync_report.py

step "1-5. Step 51/52/53/54/55 baselines (deduped via Step 55 combined)"
s55="$(bash scripts/verify_nonproduction_kubernetes_runtime_smoke.sh 2>&1)"
echo "$s55" | grep -E "NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY|classification" | tail -2
case "$(echo "$s55" | grep -E '^NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY: ' | tail -1)" in
  *": PASS") echo "  -> Step 51-55 PASS" ;;
  *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> Step 55 BLOCKED" ;;
  *) FAILS=$((FAILS+1)); echo "  -> Step 51-55 not PASS" ;;
esac

step "6. ArgoCD preflight";          runv NONPROD_ARGOCD_PREFLIGHT_VERIFY "$PY" scripts/verify_nonproduction_argocd_preflight.py
step "7. ArgoCD install boundary";   runv NONPROD_ARGOCD_INSTALL_BOUNDARY_VERIFY "$PY" scripts/verify_nonproduction_argocd_install_boundary.py
step "8. ArgoCD project policy";     runv NONPROD_ARGOCD_PROJECT_POLICY_VERIFY "$PY" scripts/verify_nonproduction_argocd_project_policy.py
step "9. ArgoCD application";        runv NONPROD_ARGOCD_APPLICATION_VERIFY "$PY" scripts/verify_nonproduction_argocd_application.py
step "10. ArgoCD manual sync";       runv NONPROD_ARGOCD_MANUAL_SYNC_VERIFY "$PY" scripts/verify_nonproduction_argocd_manual_sync.py
step "11. ArgoCD safety";            runv NONPROD_ARGOCD_SAFETY_VERIFY "$PY" scripts/verify_nonproduction_argocd_safety.py
step "12. ArgoCD operations visibility"; runv NONPROD_ARGOCD_OPERATIONS_VISIBILITY_VERIFY "$PY" scripts/verify_nonproduction_argocd_operations_visibility.py
step "13. Admin Console ArgoCD";     runv ADMIN_CONSOLE_NONPROD_ARGOCD_VERIFY "$PY" scripts/verify_admin_console_nonproduction_argocd.py
step "14. ArgoCD safety fields (live)"; runv NONPROD_ARGOCD_SAFETY_FIELDS_VERIFY "$PY" scripts/verify_nonproduction_argocd_safety_fields.py

step "15. targeted Step 56 tests"
"$PY" -m pytest -q \
  tests/test_nonproduction_argocd_preflight.py \
  tests/test_nonproduction_argocd_install_boundary.py \
  tests/test_nonproduction_argocd_project_policy.py \
  tests/test_nonproduction_argocd_application.py \
  tests/test_nonproduction_argocd_manual_sync_report_schema.py \
  tests/test_nonproduction_argocd_operations_api.py \
  tests/test_nonproduction_argocd_operations_read_only.py \
  tests/test_nonproduction_argocd_safety_fields.py \
  tests/test_admin_console_nonproduction_argocd.py \
  tests/test_nonproduction_argocd_no_mutation_actions.py \
  tests/test_nonproduction_argocd_production_not_ready.py 2>&1 | tail -4
if [ "${PIPESTATUS[0]}" -ne 0 ]; then echo "  -> tests FAILED"; FAILS=$((FAILS+1)); fi

step "16. safety posture: argocd fields; no auto-sync; production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('nonprod_argocd_manual_sync_succeeded'), d.get('nonprod_argocd_auto_sync_enabled'), d.get('nonprod_argocd_production_namespace_touched'), d.get('argocd_production_sync_performed'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x x x x x")
case "$pa" in
  "True False False False 0")
    echo "  [PASS] manual sync succeeded; no auto-sync; no prod ns; no prod sync; production_executed=0 ($pa)" ;;
  *)
    echo "  [FAIL] unexpected argocd safety posture: $pa"; FAILS=$((FAILS+1)) ;;
esac

echo ""
echo "=== classification: FAILS=$FAILS BLOCKED=$BLOCKED ==="
if [ "$FAILS" -ne 0 ]; then echo "NONPRODUCTION_ARGOCD_MANUAL_SYNC_BASELINE_VERIFY: FAIL"; exit 1; fi
if [ "$BLOCKED" -ne 0 ]; then echo "NONPRODUCTION_ARGOCD_MANUAL_SYNC_BASELINE_VERIFY: BLOCKED"; exit 0; fi
echo "NONPRODUCTION_ARGOCD_MANUAL_SYNC_BASELINE_VERIFY: PASS"
exit 0
