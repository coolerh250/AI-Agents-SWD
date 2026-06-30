#!/usr/bin/env bash
# Step 62 (Stage 64A) -- combined production deployment readiness gate baseline.
#
# Chains the Step 61 combined (which dedupes Step 52-60 + the tenant strategy note + the
# backup/restore/DR verifiers), generates the readiness gate report, then runs the 13 Step
# 62 verifiers, the targeted tests, and the safety confirmations. Readiness + operator
# review ONLY: NO production deploy, NO production sync, NO ArgoCD sync, NO GitHub merge, NO
# image push, NO production restore, NO production failover, NO production action.
#
# Final marker: PRODUCTION_DEPLOYMENT_READINESS_GATE_BASELINE_VERIFY: PASS | BLOCKED | FAIL
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

step "1-11. Step 52-61 baselines + tenant note (via Step 61 combined, deduped)"
s61="$(bash scripts/verify_backup_restore_dr_operations_baseline.sh 2>&1)"
echo "$s61" | grep -E "BACKUP_RESTORE_DR_OPERATIONS_BASELINE_VERIFY|classification" | tail -2
case "$(echo "$s61" | grep -E '^BACKUP_RESTORE_DR_OPERATIONS_BASELINE_VERIFY: ' | tail -1)" in
  *": PASS") echo "  -> Step 52-61 + tenant note PASS" ;;
  *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> Step 61 chain BLOCKED" ;;
  *) FAILS=$((FAILS+1)); echo "  -> Step 52-61 chain not PASS" ;;
esac

step "12. generate production readiness gate report"
"$PY" scripts/generate_production_readiness_gate_report.py 2>&1 | tail -2 || { echo "  -> report FAILED"; FAILS=$((FAILS+1)); }

step "13. readiness gate policy";          runv PRODUCTION_READINESS_GATE_POLICY_VERIFY "$PY" scripts/verify_production_readiness_gate_policy.py
step "14. checklist";                      runv PRODUCTION_READINESS_CHECKLIST_VERIFY "$PY" scripts/verify_production_readiness_checklist.py
step "15. evidence inventory";             runv READINESS_EVIDENCE_INVENTORY_VERIFY "$PY" scripts/verify_readiness_evidence_inventory.py
step "16. blocking rules";                 runv PRODUCTION_READINESS_BLOCKING_RULES_VERIFY "$PY" scripts/verify_production_readiness_blocking_rules.py
step "17. production prerequisites";       runv PRODUCTION_ENVIRONMENT_PREREQUISITES_VERIFY "$PY" scripts/verify_production_environment_prerequisites.py
step "18. authorization boundary";         runv DEPLOYMENT_AUTHORIZATION_BOUNDARY_VERIFY "$PY" scripts/verify_deployment_authorization_boundary.py
step "19. operator review package";        runv OPERATOR_REVIEW_PACKAGE_VERIFY "$PY" scripts/verify_operator_review_package.py
step "20. readiness decision";             runv PRODUCTION_READINESS_DECISION_VERIFY "$PY" scripts/verify_production_readiness_decision.py
step "21. rollout preflight";              runv PRODUCTION_ROLLOUT_PREFLIGHT_VERIFY "$PY" scripts/verify_production_rollout_preflight.py
step "22. runtime report";                 runv PRODUCTION_READINESS_RUNTIME_VERIFY "$PY" scripts/verify_production_readiness_runtime.py
step "23. operations visibility (live)";   runv PRODUCTION_READINESS_OPERATIONS_VISIBILITY_VERIFY "$PY" scripts/verify_production_readiness_operations_visibility.py
step "24. Admin Console";                  runv ADMIN_CONSOLE_PRODUCTION_READINESS_VERIFY "$PY" scripts/verify_admin_console_production_readiness.py
step "25. safety fields (live)";           runv PRODUCTION_READINESS_SAFETY_FIELDS_VERIFY "$PY" scripts/verify_production_readiness_safety_fields.py

step "26. targeted Step 62 tests"
"$PY" -m pytest -q \
  tests/test_production_readiness_gate_policy.py \
  tests/test_production_readiness_checklist.py \
  tests/test_readiness_evidence_inventory.py \
  tests/test_production_readiness_blocking_rules.py \
  tests/test_production_environment_prerequisites.py \
  tests/test_deployment_authorization_boundary.py \
  tests/test_operator_review_package.py \
  tests/test_production_readiness_decision.py \
  tests/test_production_rollout_preflight.py \
  tests/test_production_readiness_runtime.py \
  tests/test_production_readiness_operations_api.py \
  tests/test_admin_console_production_readiness.py \
  tests/test_production_readiness_safety_fields.py \
  tests/test_production_readiness_no_production_actions.py 2>&1 | tail -4
if [ "${PIPESTATUS[0]}" -ne 0 ]; then echo "  -> tests FAILED"; FAILS=$((FAILS+1)); fi

step "27. safety posture: production never ready/approved; counts 0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('production_readiness_gate_enabled'), d.get('production_readiness_gate_production_ready'), d.get('production_readiness_gate_production_approved'), d.get('production_readiness_gate_allows_production_action'), d.get('production_readiness_gate_allows_deploy'), d.get('production_readiness_gate_allows_sync'), d.get('production_readiness_gate_allows_merge'), d.get('production_readiness_gate_allows_restore'), d.get('production_readiness_gate_allows_failover'), d.get('production_readiness_operator_review_is_approval'), d.get('production_rollout_execution_enabled'), d.get('production_deployment_executed_count'), d.get('production_sync_executed_count'), d.get('production_restore_executed_count'), d.get('production_failover_executed_count'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x")
case "$pa" in
  "True False False False False False False False False False False 0 0 0 0 0")
    echo "  [PASS] gate enabled; production never ready/approved; no deploy/sync/merge/restore/failover; rollout off; counts 0 ($pa)" ;;
  *) echo "  [FAIL] unexpected production readiness safety posture: $pa"; FAILS=$((FAILS+1)) ;;
esac

echo ""
echo "=== classification: FAILS=$FAILS BLOCKED=$BLOCKED ==="
if [ "$FAILS" -ne 0 ]; then echo "PRODUCTION_DEPLOYMENT_READINESS_GATE_BASELINE_VERIFY: FAIL"; exit 1; fi
if [ "$BLOCKED" -ne 0 ]; then echo "PRODUCTION_DEPLOYMENT_READINESS_GATE_BASELINE_VERIFY: BLOCKED"; exit 0; fi
echo "PRODUCTION_DEPLOYMENT_READINESS_GATE_BASELINE_VERIFY: PASS"
exit 0
