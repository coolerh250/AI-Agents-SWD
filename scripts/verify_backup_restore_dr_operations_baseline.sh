#!/usr/bin/env bash
# Step 61 (Stage 63A) -- combined backup / restore / DR operations baseline.
#
# Chains the Step 60 combined (which dedupes Step 52-59 + the tenant strategy note + the
# release governance verifiers), generates the runtime inventory / cleanup review / restore
# validation artifacts, then runs the 12 Step 61 verifiers, the targeted tests, and the
# safety confirmations. Governance only: NO production restore, NO production failover, NO
# cleanup execution, NO restore execution, NO kind / ArgoCD teardown, NO ArgoCD sync, NO
# external / cloud upload, NO production action.
#
# Final marker: BACKUP_RESTORE_DR_OPERATIONS_BASELINE_VERIFY: PASS | BLOCKED | FAIL
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
  echo "$out" | tail -3
  marker="$(echo "$out" | grep -E "^${name}: " | tail -1)"
  case "$marker" in
    *": PASS") : ;;
    *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> classified BLOCKED" ;;
    *) FAILS=$((FAILS+1)); echo "  -> classified FAIL ($marker)" ;;
  esac
}

step "1-10. Step 52-60 baselines + tenant note (via Step 60 combined, deduped)"
s60="$(bash scripts/verify_release_deployment_governance_baseline.sh 2>&1)"
echo "$s60" | grep -E "RELEASE_DEPLOYMENT_GOVERNANCE_BASELINE_VERIFY|classification" | tail -2
case "$(echo "$s60" | grep -E '^RELEASE_DEPLOYMENT_GOVERNANCE_BASELINE_VERIFY: ' | tail -1)" in
  *": PASS") echo "  -> Step 52-60 + tenant note PASS" ;;
  *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> Step 60 chain BLOCKED" ;;
  *) FAILS=$((FAILS+1)); echo "  -> Step 52-60 chain not PASS" ;;
esac

step "11. generate backup/restore/DR runtime inventory"
"$PY" scripts/generate_backup_dr_runtime_inventory.py 2>&1 | tail -2 || { echo "  -> inventory FAILED"; FAILS=$((FAILS+1)); }
step "12. generate controlled cleanup review"
"$PY" scripts/generate_controlled_cleanup_review.py 2>&1 | tail -2 || { echo "  -> cleanup review FAILED"; FAILS=$((FAILS+1)); }
step "13. run non-production restore validation"
"$PY" scripts/run_nonproduction_restore_validation.py 2>&1 | tail -2 || { echo "  -> restore validation FAILED"; FAILS=$((FAILS+1)); }

step "14. DR policy";                    runv BACKUP_RESTORE_DR_POLICY_VERIFY "$PY" scripts/verify_backup_restore_dr_policy.py
step "15. backup target inventory";      runv BACKUP_TARGET_INVENTORY_VERIFY "$PY" scripts/verify_backup_target_inventory.py
step "16. artifact classification";      runv BACKUP_ARTIFACT_CLASSIFICATION_VERIFY "$PY" scripts/verify_backup_artifact_classification.py
step "17. controlled cleanup review";    runv CONTROLLED_CLEANUP_REVIEW_VERIFY "$PY" scripts/verify_controlled_cleanup_review.py
step "18. restore plan model";           runv RESTORE_PLAN_MODEL_VERIFY "$PY" scripts/verify_restore_plan_model.py
step "19. restore validation";           runv NONPRODUCTION_RESTORE_VALIDATION_VERIFY "$PY" scripts/verify_nonproduction_restore_validation.py
step "20. DR operation model";           runv DR_OPERATION_MODEL_VERIFY "$PY" scripts/verify_dr_operation_model.py
step "21. recovery evidence package";    runv RECOVERY_EVIDENCE_PACKAGE_VERIFY "$PY" scripts/verify_recovery_evidence_package.py
step "22. runtime artifacts";            runv BACKUP_RESTORE_DR_RUNTIME_VERIFY "$PY" scripts/verify_backup_restore_dr_runtime.py
step "23. operations visibility (live)"; runv BACKUP_RESTORE_DR_OPERATIONS_VISIBILITY_VERIFY "$PY" scripts/verify_backup_restore_dr_operations_visibility.py
step "24. Admin Console";                runv ADMIN_CONSOLE_BACKUP_DR_VERIFY "$PY" scripts/verify_admin_console_backup_dr.py
step "25. safety fields (live)";         runv BACKUP_RESTORE_DR_SAFETY_FIELDS_VERIFY "$PY" scripts/verify_backup_restore_dr_safety_fields.py

step "26. targeted Step 61 tests"
"$PY" -m pytest -q \
  tests/test_backup_restore_dr_policy.py \
  tests/test_backup_target_inventory.py \
  tests/test_backup_artifact_classification.py \
  tests/test_controlled_cleanup_review.py \
  tests/test_restore_plan_model.py \
  tests/test_nonproduction_restore_validation.py \
  tests/test_dr_operation_model.py \
  tests/test_recovery_evidence_package.py \
  tests/test_backup_restore_dr_runtime.py \
  tests/test_backup_restore_dr_operations_api.py \
  tests/test_admin_console_backup_dr.py \
  tests/test_backup_restore_dr_safety_fields.py \
  tests/test_backup_restore_dr_no_production_actions.py 2>&1 | tail -4
if [ "${PIPESTATUS[0]}" -ne 0 ]; then echo "  -> tests FAILED"; FAILS=$((FAILS+1)); fi

step "27. safety posture: production restore/failover blocked; counts 0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('backup_restore_dr_enabled'), d.get('backup_restore_dr_production_ready'), d.get('backup_restore_dr_allow_production_restore'), d.get('backup_restore_dr_allow_production_failover'), d.get('cleanup_execution_enabled'), d.get('restore_execution_enabled'), d.get('cleanup_teardown_kind_enabled'), d.get('cleanup_teardown_argocd_enabled'), d.get('production_restore_plan_count'), d.get('production_failover_plan_count'), d.get('production_restore_executed_count'), d.get('production_failover_executed_count'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x")
case "$pa" in
  "True False False False False False False False 0 0 0 0 0")
    echo "  [PASS] DR governance enabled; production restore/failover blocked; no cleanup/restore exec/teardown; counts 0 ($pa)" ;;
  *) echo "  [FAIL] unexpected backup/restore/DR safety posture: $pa"; FAILS=$((FAILS+1)) ;;
esac

echo ""
echo "=== classification: FAILS=$FAILS BLOCKED=$BLOCKED ==="
if [ "$FAILS" -ne 0 ]; then echo "BACKUP_RESTORE_DR_OPERATIONS_BASELINE_VERIFY: FAIL"; exit 1; fi
if [ "$BLOCKED" -ne 0 ]; then echo "BACKUP_RESTORE_DR_OPERATIONS_BASELINE_VERIFY: BLOCKED"; exit 0; fi
echo "BACKUP_RESTORE_DR_OPERATIONS_BASELINE_VERIFY: PASS"
exit 0
