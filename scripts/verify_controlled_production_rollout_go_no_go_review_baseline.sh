#!/usr/bin/env bash
# Step 63A (Stage 65A) -- combined controlled production rollout pilot go/no-go review baseline.
#
# Chains the Step 62 combined (which dedupes Step 52-61 + the tenant strategy note + the
# production readiness gate verifiers), generates the go/no-go review report, then runs the
# 15 Step 63A verifiers, the targeted tests, and the safety confirmations. Review +
# recommendation + operator review ONLY: NO production deploy, NO production sync, NO ArgoCD
# sync, NO GitHub merge, NO image push, NO production restore/failover, NO production action.
# The go / conditional_go / no_go recommendation is NOT an approval.
#
# Final marker: CONTROLLED_PRODUCTION_ROLLOUT_GO_NO_GO_REVIEW_BASELINE_VERIFY: PASS|BLOCKED|FAIL
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

step "1-12. Step 52-62 baselines + tenant note (via Step 62 combined, deduped)"
s62="$(bash scripts/verify_production_deployment_readiness_gate_baseline.sh 2>&1)"
echo "$s62" | grep -E "PRODUCTION_DEPLOYMENT_READINESS_GATE_BASELINE_VERIFY|classification" | tail -2
case "$(echo "$s62" | grep -E '^PRODUCTION_DEPLOYMENT_READINESS_GATE_BASELINE_VERIFY: ' | tail -1)" in
  *": PASS") echo "  -> Step 52-62 + tenant note PASS" ;;
  *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> Step 62 chain BLOCKED" ;;
  *) FAILS=$((FAILS+1)); echo "  -> Step 52-62 chain not PASS" ;;
esac

step "13. generate controlled rollout go/no-go review"
"$PY" scripts/generate_controlled_rollout_go_no_go_review.py 2>&1 | tail -2 || { echo "  -> review FAILED"; FAILS=$((FAILS+1)); }

step "14. review policy";              runv CONTROLLED_ROLLOUT_REVIEW_POLICY_VERIFY "$PY" scripts/verify_controlled_rollout_review_policy.py
step "15. go/no-go criteria";          runv CONTROLLED_ROLLOUT_GO_NO_GO_CRITERIA_VERIFY "$PY" scripts/verify_controlled_rollout_go_no_go_criteria.py
step "16. production target";          runv PRODUCTION_TARGET_ASSESSMENT_VERIFY "$PY" scripts/verify_production_target_assessment.py
step "17. credential readiness";       runv PRODUCTION_CREDENTIAL_READINESS_VERIFY "$PY" scripts/verify_production_credential_readiness.py
step "18. GitOps readiness";           runv PRODUCTION_GITOPS_READINESS_VERIFY "$PY" scripts/verify_production_gitops_readiness.py
step "19. approval channel readiness"; runv PRODUCTION_APPROVAL_CHANNEL_READINESS_VERIFY "$PY" scripts/verify_production_approval_channel_readiness.py
step "20. rollback/DR readiness";      runv ROLLBACK_DR_PILOT_READINESS_VERIFY "$PY" scripts/verify_rollback_dr_pilot_readiness.py
step "21. pilot scope";                runv CONTROLLED_ROLLOUT_PILOT_SCOPE_VERIFY "$PY" scripts/verify_controlled_rollout_pilot_scope.py
step "22. risk register";              runv CONTROLLED_ROLLOUT_RISK_REGISTER_VERIFY "$PY" scripts/verify_controlled_rollout_risk_register.py
step "23. operator decision package";  runv CONTROLLED_ROLLOUT_OPERATOR_DECISION_PACKAGE_VERIFY "$PY" scripts/verify_controlled_rollout_operator_decision_package.py
step "24. recommendation";             runv CONTROLLED_ROLLOUT_RECOMMENDATION_VERIFY "$PY" scripts/verify_controlled_rollout_recommendation.py
step "25. review runtime";             runv CONTROLLED_ROLLOUT_REVIEW_RUNTIME_VERIFY "$PY" scripts/verify_controlled_rollout_review_runtime.py
step "26. operations visibility (live)"; runv CONTROLLED_ROLLOUT_OPERATIONS_VISIBILITY_VERIFY "$PY" scripts/verify_controlled_rollout_operations_visibility.py
step "27. Admin Console";              runv ADMIN_CONSOLE_CONTROLLED_ROLLOUT_REVIEW_VERIFY "$PY" scripts/verify_admin_console_controlled_rollout_review.py
step "28. safety fields (live)";       runv CONTROLLED_ROLLOUT_SAFETY_FIELDS_VERIFY "$PY" scripts/verify_controlled_rollout_safety_fields.py

step "29. targeted Step 63A tests"
"$PY" -m pytest -q \
  tests/test_controlled_rollout_review_policy.py \
  tests/test_controlled_rollout_go_no_go_criteria.py \
  tests/test_production_target_assessment.py \
  tests/test_production_credential_readiness.py \
  tests/test_production_gitops_readiness.py \
  tests/test_production_approval_channel_readiness.py \
  tests/test_rollback_dr_pilot_readiness.py \
  tests/test_controlled_rollout_pilot_scope.py \
  tests/test_controlled_rollout_risk_register.py \
  tests/test_controlled_rollout_operator_decision_package.py \
  tests/test_controlled_rollout_recommendation.py \
  tests/test_controlled_rollout_review_runtime.py \
  tests/test_controlled_rollout_operations_api.py \
  tests/test_admin_console_controlled_rollout_review.py \
  tests/test_controlled_rollout_safety_fields.py \
  tests/test_controlled_rollout_no_production_actions.py 2>&1 | tail -4
if [ "${PIPESTATUS[0]}" -ne 0 ]; then echo "  -> tests FAILED"; FAILS=$((FAILS+1)); fi

step "30. safety posture: recommendation not approval; no production action; counts 0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('controlled_rollout_review_enabled'), d.get('controlled_rollout_recommendation_is_approval'), d.get('controlled_rollout_allows_production_action'), d.get('controlled_rollout_allows_deploy'), d.get('controlled_rollout_allows_sync'), d.get('controlled_rollout_allows_merge'), d.get('controlled_rollout_allows_restore'), d.get('controlled_rollout_allows_failover'), d.get('controlled_rollout_operator_review_is_approval'), d.get('controlled_rollout_production_action_executed_count'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x")
case "$pa" in
  "True False False False False False False False False 0 0")
    echo "  [PASS] review enabled; recommendation/operator-review not approval; no deploy/sync/merge/restore/failover; counts 0 ($pa)" ;;
  *) echo "  [FAIL] unexpected controlled rollout safety posture: $pa"; FAILS=$((FAILS+1)) ;;
esac

echo ""
echo "=== classification: FAILS=$FAILS BLOCKED=$BLOCKED ==="
if [ "$FAILS" -ne 0 ]; then echo "CONTROLLED_PRODUCTION_ROLLOUT_GO_NO_GO_REVIEW_BASELINE_VERIFY: FAIL"; exit 1; fi
if [ "$BLOCKED" -ne 0 ]; then echo "CONTROLLED_PRODUCTION_ROLLOUT_GO_NO_GO_REVIEW_BASELINE_VERIFY: BLOCKED"; exit 0; fi
echo "CONTROLLED_PRODUCTION_ROLLOUT_GO_NO_GO_REVIEW_BASELINE_VERIFY: PASS"
exit 0
