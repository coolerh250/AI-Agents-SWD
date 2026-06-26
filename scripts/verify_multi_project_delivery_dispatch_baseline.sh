#!/usr/bin/env bash
# Step 57 (Stage 59A) -- combined multi-project delivery + work-item dispatch baseline.
#
# Runs the Step 56 combined (which chains Step 51/52/53/54/55 + ArgoCD), then the 10
# Step 57 verifiers, the targeted tests, and the safety confirmations. NO GitHub write,
# NO ArgoCD sync, NO external notification send, NO production deploy. production_executed=0.
#
# Final marker: MULTI_PROJECT_DELIVERY_DISPATCH_BASELINE_VERIFY: PASS | BLOCKED | FAIL
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

step "1-6. Step 51/52/53/54/55/56 baselines (via Step 56 combined, deduped)"
s56="$(bash scripts/verify_nonproduction_argocd_manual_sync_baseline.sh 2>&1)"
echo "$s56" | grep -E "NONPRODUCTION_ARGOCD_MANUAL_SYNC_BASELINE_VERIFY|classification" | tail -2
case "$(echo "$s56" | grep -E '^NONPRODUCTION_ARGOCD_MANUAL_SYNC_BASELINE_VERIFY: ' | tail -1)" in
  *": PASS") echo "  -> Step 51-56 PASS" ;;
  *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> prior baselines BLOCKED" ;;
  *) FAILS=$((FAILS+1)); echo "  -> prior baselines not PASS" ;;
esac

step "7. multi-project schema";        runv MULTI_PROJECT_SCHEMA_VERIFY "$PY" scripts/verify_multi_project_schema.py
step "8. work-item lifecycle";         runv WORK_ITEM_LIFECYCLE_VERIFY "$PY" scripts/verify_work_item_lifecycle.py
step "9. dispatch policy";             runv WORK_ITEM_DISPATCH_POLICY_VERIFY "$PY" scripts/verify_work_item_dispatch_policy.py
step "10. dispatch runtime (live)";    runv WORK_ITEM_DISPATCH_RUNTIME_VERIFY "$PY" scripts/verify_work_item_dispatch_runtime.py
step "11. project delivery state";     runv PROJECT_DELIVERY_STATE_VERIFY "$PY" scripts/verify_project_delivery_state.py
step "12. delivery package linkage";   runv DELIVERY_PACKAGE_PROJECT_LINKAGE_VERIFY "$PY" scripts/verify_delivery_package_project_linkage.py
step "13. audit mapping";              runv PROJECT_WORK_ITEM_AUDIT_MAPPING_VERIFY "$PY" scripts/verify_project_work_item_audit_mapping.py
step "14. operations visibility";      runv MULTI_PROJECT_OPERATIONS_VISIBILITY_VERIFY "$PY" scripts/verify_multi_project_operations_visibility.py
step "15. Admin Console";              runv ADMIN_CONSOLE_MULTI_PROJECT_VERIFY "$PY" scripts/verify_admin_console_multi_project.py
step "16. safety fields (live)";       runv MULTI_PROJECT_SAFETY_FIELDS_VERIFY "$PY" scripts/verify_multi_project_safety_fields.py

step "17. targeted Step 57 tests"
"$PY" -m pytest -q \
  tests/test_multi_project_schema.py \
  tests/test_project_registry.py \
  tests/test_work_item_lifecycle.py \
  tests/test_work_item_decomposition_policy.py \
  tests/test_work_item_dispatch_policy.py \
  tests/test_work_item_sdk.py \
  tests/test_project_delivery_state.py \
  tests/test_delivery_package_project_linkage.py \
  tests/test_project_work_item_audit_mapping.py \
  tests/test_project_notification_model.py \
  tests/test_multi_project_operations_api.py \
  tests/test_admin_console_multi_project.py \
  tests/test_multi_project_no_production_actions.py \
  tests/test_multi_project_safety_fields.py 2>&1 | tail -4
if [ "${PIPESTATUS[0]}" -ne 0 ]; then echo "  -> tests FAILED"; FAILS=$((FAILS+1)); fi

step "18. safety posture: dispatch fields off; production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('work_item_dispatch_enabled'), d.get('work_item_dispatch_github_write_enabled'), d.get('work_item_dispatch_argocd_sync_enabled'), d.get('work_item_dispatch_production_action_enabled'), d.get('work_item_notification_external_send_enabled'), d.get('multi_project_production_ready'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x")
case "$pa" in
  "True False False False False False 0")
    echo "  [PASS] dispatch enabled; no github/argocd/production/external; not prod ready; production_executed=0 ($pa)" ;;
  *) echo "  [FAIL] unexpected multi-project safety posture: $pa"; FAILS=$((FAILS+1)) ;;
esac

echo ""
echo "=== classification: FAILS=$FAILS BLOCKED=$BLOCKED ==="
if [ "$FAILS" -ne 0 ]; then echo "MULTI_PROJECT_DELIVERY_DISPATCH_BASELINE_VERIFY: FAIL"; exit 1; fi
if [ "$BLOCKED" -ne 0 ]; then echo "MULTI_PROJECT_DELIVERY_DISPATCH_BASELINE_VERIFY: BLOCKED"; exit 0; fi
echo "MULTI_PROJECT_DELIVERY_DISPATCH_BASELINE_VERIFY: PASS"
exit 0
