#!/usr/bin/env bash
# Step 59 (Stage 61A) -- combined sandbox GitHub draft PR baseline.
#
# Chains the Step 58 combined (which itself dedupes Step 52-57 + the tenant strategy
# note + the 6 metrics verifiers), then runs the 9 Step 59 sandbox-GitHub verifiers, the
# targeted tests, and the safety confirmations. Read-only / sandbox-only: NO PR merge, NO
# ready-for-review, NO workflow dispatch, NO non-sandbox repo write, NO production branch,
# NO ArgoCD sync, NO Kubernetes mutation, NO external send, NO production action.
#
# Final marker: SANDBOX_GITHUB_DRAFT_PR_BASELINE_VERIFY: PASS | BLOCKED | FAIL
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

step "1-8. Step 52-58 baselines + tenant note (via Step 58 combined, deduped)"
s58="$(bash scripts/verify_admin_console_v2_operational_metrics_baseline.sh 2>&1)"
echo "$s58" | grep -E "ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_BASELINE_VERIFY|classification" | tail -2
case "$(echo "$s58" | grep -E '^ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_BASELINE_VERIFY: ' | tail -1)" in
  *": PASS") echo "  -> Step 52-58 + tenant note PASS" ;;
  *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> Step 58 chain BLOCKED" ;;
  *) FAILS=$((FAILS+1)); echo "  -> Step 52-58 chain not PASS" ;;
esac

step "9. sandbox policy";              runv SANDBOX_GITHUB_POLICY_VERIFY "$PY" scripts/verify_sandbox_github_policy.py
step "10. repository allowlist";       runv SANDBOX_GITHUB_ALLOWLIST_VERIFY "$PY" scripts/verify_sandbox_github_allowlist.py
step "11. branch policy";              runv SANDBOX_GITHUB_BRANCH_POLICY_VERIFY "$PY" scripts/verify_sandbox_github_branch_policy.py
step "12. PR metadata";                runv SANDBOX_GITHUB_PR_METADATA_VERIFY "$PY" scripts/verify_sandbox_github_pr_metadata.py
step "13. client";                     runv SANDBOX_GITHUB_CLIENT_VERIFY "$PY" scripts/verify_sandbox_github_client.py
step "14. draft PR runtime (live)";    runv SANDBOX_GITHUB_DRAFT_PR_RUNTIME_VERIFY "$PY" scripts/verify_sandbox_github_draft_pr_runtime.py
step "15. operations visibility";      runv SANDBOX_GITHUB_OPERATIONS_VISIBILITY_VERIFY "$PY" scripts/verify_sandbox_github_operations_visibility.py
step "16. Admin Console";              runv ADMIN_CONSOLE_SANDBOX_GITHUB_VERIFY "$PY" scripts/verify_admin_console_sandbox_github.py
step "17. safety fields (live)";       runv SANDBOX_GITHUB_SAFETY_FIELDS_VERIFY "$PY" scripts/verify_sandbox_github_safety_fields.py

step "18. targeted Step 59 tests"
"$PY" -m pytest -q \
  tests/test_sandbox_github_policy.py \
  tests/test_sandbox_github_allowlist.py \
  tests/test_sandbox_github_branch_policy.py \
  tests/test_sandbox_github_pr_metadata.py \
  tests/test_sandbox_github_client.py \
  tests/test_sandbox_github_dry_run.py \
  tests/test_sandbox_github_runtime.py \
  tests/test_sandbox_github_operations_api.py \
  tests/test_sandbox_github_operations_read_only.py \
  tests/test_admin_console_sandbox_github.py \
  tests/test_sandbox_github_safety_fields.py \
  tests/test_sandbox_github_no_production_actions.py 2>&1 | tail -4
if [ "${PIPESTATUS[0]}" -ne 0 ]; then echo "  -> tests FAILED"; FAILS=$((FAILS+1)); fi

step "19. safety posture: sandbox fields off; production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('sandbox_github_draft_pr_enabled'), d.get('sandbox_github_merge_enabled'), d.get('sandbox_github_ready_for_review_enabled'), d.get('sandbox_github_workflow_dispatch_enabled'), d.get('sandbox_github_arbitrary_repo_allowed'), d.get('sandbox_github_token_exposed'), d.get('sandbox_github_non_sandbox_repo_write_performed'), d.get('sandbox_github_production_branch_allowed'), d.get('sandbox_github_production_ready'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x")
case "$pa" in
  "True False False False False False False False False 0")
    echo "  [PASS] sandbox enabled; no merge/review/workflow/arbitrary/token/non-sandbox/prod-branch; not prod ready; production_executed=0 ($pa)" ;;
  *) echo "  [FAIL] unexpected sandbox github safety posture: $pa"; FAILS=$((FAILS+1)) ;;
esac

echo ""
echo "=== classification: FAILS=$FAILS BLOCKED=$BLOCKED ==="
if [ "$FAILS" -ne 0 ]; then echo "SANDBOX_GITHUB_DRAFT_PR_BASELINE_VERIFY: FAIL"; exit 1; fi
if [ "$BLOCKED" -ne 0 ]; then echo "SANDBOX_GITHUB_DRAFT_PR_BASELINE_VERIFY: BLOCKED"; exit 0; fi
echo "SANDBOX_GITHUB_DRAFT_PR_BASELINE_VERIFY: PASS"
exit 0
