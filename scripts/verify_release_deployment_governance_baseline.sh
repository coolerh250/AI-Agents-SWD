#!/usr/bin/env bash
# Step 60 (Stage 62A) -- combined release & deployment governance baseline.
#
# Chains the Step 59 combined (which dedupes Step 52-58 + the tenant strategy note + the
# 9 sandbox-GitHub verifiers), then runs the 11 Step 60 verifiers, the targeted tests, and
# the safety confirmations. Governance only: NO production deploy, NO ArgoCD production
# sync, NO GitHub merge, NO image push, NO registry login, NO production action.
#
# Final marker: RELEASE_DEPLOYMENT_GOVERNANCE_BASELINE_VERIFY: PASS | BLOCKED | FAIL
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

step "1-9. Step 52-59 baselines + tenant note (via Step 59 combined, deduped)"
s59="$(bash scripts/verify_sandbox_github_draft_pr_baseline.sh 2>&1)"
echo "$s59" | grep -E "SANDBOX_GITHUB_DRAFT_PR_BASELINE_VERIFY|classification" | tail -2
case "$(echo "$s59" | grep -E '^SANDBOX_GITHUB_DRAFT_PR_BASELINE_VERIFY: ' | tail -1)" in
  *": PASS") echo "  -> Step 52-59 + tenant note PASS" ;;
  *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> Step 59 chain BLOCKED" ;;
  *) FAILS=$((FAILS+1)); echo "  -> Step 52-59 chain not PASS" ;;
esac

step "10. release governance policy";   runv RELEASE_GOVERNANCE_POLICY_VERIFY "$PY" scripts/verify_release_governance_policy.py
step "11. release candidate model";     runv RELEASE_CANDIDATE_MODEL_VERIFY "$PY" scripts/verify_release_candidate_model.py
step "12. deployment intent model";     runv DEPLOYMENT_INTENT_MODEL_VERIFY "$PY" scripts/verify_deployment_intent_model.py
step "13. promotion boundary";          runv PROMOTION_BOUNDARY_MODEL_VERIFY "$PY" scripts/verify_promotion_boundary_model.py
step "14. release evidence package";    runv RELEASE_EVIDENCE_PACKAGE_VERIFY "$PY" scripts/verify_release_evidence_package.py
step "15. release readiness decision";  runv RELEASE_READINESS_DECISION_VERIFY "$PY" scripts/verify_release_readiness_decision.py
step "16. rollback requirement";        runv ROLLBACK_REQUIREMENT_MODEL_VERIFY "$PY" scripts/verify_rollback_requirement_model.py
step "17. governance runtime (live)";   runv RELEASE_GOVERNANCE_RUNTIME_VERIFY "$PY" scripts/verify_release_governance_runtime.py
step "18. operations visibility";       runv RELEASE_GOVERNANCE_OPERATIONS_VISIBILITY_VERIFY "$PY" scripts/verify_release_governance_operations_visibility.py
step "19. Admin Console";               runv ADMIN_CONSOLE_RELEASE_GOVERNANCE_VERIFY "$PY" scripts/verify_admin_console_release_governance.py
step "20. safety fields (live)";        runv RELEASE_GOVERNANCE_SAFETY_FIELDS_VERIFY "$PY" scripts/verify_release_governance_safety_fields.py

step "21. targeted Step 60 tests"
"$PY" -m pytest -q \
  tests/test_release_governance_policy.py \
  tests/test_release_candidate_model.py \
  tests/test_deployment_intent_model.py \
  tests/test_promotion_boundary_model.py \
  tests/test_release_evidence_package.py \
  tests/test_release_readiness_decision.py \
  tests/test_rollback_requirement_model.py \
  tests/test_release_governance_runtime.py \
  tests/test_release_governance_operations_api.py \
  tests/test_admin_console_release_governance.py \
  tests/test_release_governance_safety_fields.py \
  tests/test_release_governance_no_production_actions.py 2>&1 | tail -4
if [ "${PIPESTATUS[0]}" -ne 0 ]; then echo "  -> tests FAILED"; FAILS=$((FAILS+1)); fi

step "22. safety posture: production blocked; production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('release_governance_enabled'), d.get('release_governance_production_ready'), d.get('release_governance_allow_production_deploy'), d.get('release_governance_allow_auto_promotion'), d.get('release_governance_allow_github_merge'), d.get('release_governance_allow_argocd_production_sync'), d.get('release_governance_allow_image_push'), d.get('release_governance_allow_registry_login'), d.get('deployment_intent_production_target_count'), d.get('deployment_intent_production_executed_count'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x")
case "$pa" in
  "True False False False False False False False 0 0 0")
    echo "  [PASS] governance enabled; production blocked; no deploy/promotion/merge/sync/push/login; counts 0 ($pa)" ;;
  *) echo "  [FAIL] unexpected release governance safety posture: $pa"; FAILS=$((FAILS+1)) ;;
esac

echo ""
echo "=== classification: FAILS=$FAILS BLOCKED=$BLOCKED ==="
if [ "$FAILS" -ne 0 ]; then echo "RELEASE_DEPLOYMENT_GOVERNANCE_BASELINE_VERIFY: FAIL"; exit 1; fi
if [ "$BLOCKED" -ne 0 ]; then echo "RELEASE_DEPLOYMENT_GOVERNANCE_BASELINE_VERIFY: BLOCKED"; exit 0; fi
echo "RELEASE_DEPLOYMENT_GOVERNANCE_BASELINE_VERIFY: PASS"
exit 0
