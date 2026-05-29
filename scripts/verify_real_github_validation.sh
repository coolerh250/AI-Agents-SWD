#!/usr/bin/env bash
# Verify the Stage 23 controlled-real GitHub validation surface.
#
# Default mode (which is what the test cluster runs) ASSERTS the
# safety guard refuses every real GitHub write — no token / no opt-in
# / no GITHUB_TEST_REPO ⇒ HTTP 409. The script emits
# ``REAL_GITHUB_TEST_SKIPPED: PASS`` and finishes.
#
# Opt-in: setting ALL of GITHUB_TOKEN, RUN_REAL_GITHUB_TEST=true, and
# GITHUB_TEST_REPO (e.g. coolerh250/AI-Agents-SWD) makes the script
# additionally run ONE controlled-real PR flow. Even then it forbids
# merging, never modifies branch protection, never deletes branches,
# never targets a production base branch.
#
# Run from the repository root.
set -uo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
GH="${GITHUB_AUTOMATION_URL:-http://localhost:8005}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
AUDIT="${AUDIT_SERVICE_URL:-http://localhost:8003}"
GATEWAY="${GATEWAY_URL:-http://localhost:8004}"
DISCORD="${DISCORD_GATEWAY_URL:-http://localhost:8007}"

echo "### verify_real_github_validation: $(date '+%Y-%m-%d %H:%M:%S %Z')"

ts=$(date +%s)
task_id="real-github-verify-$ts"

# 1. /health
echo
echo "=== 1. github-automation /health ==="
health=$(curl -sS -m 5 "$GH/health" || echo '{}')
echo "$health" | head -c 400
echo
if echo "$health" | grep -q '"service": *"github-automation"' \
   && echo "$health" | grep -q '"real_github_test_enabled":' \
   && echo "$health" | grep -q '"test_repo_configured":'; then
  echo "GITHUB_HEALTH: PASS"; h_ok=1
else
  echo "GITHUB_HEALTH: FAIL"; h_ok=0
fi

# token MUST NOT appear in /health response
if echo "$health" | grep -qiE 'ghp_|github_pat_|"token":'; then
  echo "  health token leak check: FAIL"; tk_ok=0
else
  echo "  health token leak check: PASS"; tk_ok=1
fi

# 2. /operations/safety carries the four github_* booleans
echo
echo "=== 2. /operations/safety github_* fields ==="
safety=$(curl -sS -m 10 "$ORCH/operations/safety" || echo '{}')
echo "$safety" | head -c 600
echo
if echo "$safety" | grep -q '"github_has_token":' \
   && echo "$safety" | grep -q '"real_github_test_enabled":' \
   && echo "$safety" | grep -q '"github_test_repo_configured":' \
   && echo "$safety" | grep -q '"github_external_write_enabled":'; then
  echo "OPERATIONS_SAFETY_FIELDS: PASS"; sf_ok=1
else
  echo "OPERATIONS_SAFETY_FIELDS: FAIL"; sf_ok=0
fi
# token MUST NOT appear in safety response
if echo "$safety" | grep -qiE 'ghp_|github_pat_|"github_token":'; then
  echo "  safety token leak check: FAIL"; tk2_ok=0
else
  echo "  safety token leak check: PASS"; tk2_ok=1
fi

# 3. Guard: missing required envs (default mode) — must be 409
echo
echo "=== 3. /github/workflow/real-test-pr (default mode — must be blocked) ==="
blocked_task="real-github-guard-default-$ts"
blocked_body=$(cat <<JSON
{
  "task_id":"$blocked_task",
  "workflow_id":"wf-$blocked_task",
  "repo":"coolerh250/AI-Agents-SWD",
  "base_branch":"main",
  "branch_name":"ai-agents-test/$blocked_task",
  "title":"[AI-Agents-SWD Test] default guard refusal",
  "body":"## Summary\nGuard default refusal\n\n## Changed Files\n- docs/github-real-test/$blocked_task.md\n\n## Risk Assessment\nLow\n\n## Test Result\nGuard only\n\n## Rollback Plan\nNo write expected\n\n## Safety Notes\nShould be refused unless env is explicitly enabled.",
  "file_path":"docs/github-real-test/$blocked_task.md",
  "file_content":"task_id=$blocked_task\nworkflow_id=wf-$blocked_task\ngenerated_by=github-automation\nreal_github_test=true\nproduction_executed=false\n",
  "dry_run":false
}
JSON
)
rt_code=$(curl -sS -m 10 -o /tmp/rgv_default.$$ -w "%{http_code}" \
  -X POST "$GH/github/workflow/real-test-pr" \
  -H "Content-Type: application/json" \
  -d "$blocked_body" || echo "000")
blocked_resp=$(cat /tmp/rgv_default.$$ 2>/dev/null || echo '{}')
rm -f /tmp/rgv_default.$$
echo "  default-mode HTTP: $rt_code"
echo "  default-mode response: $(echo "$blocked_resp" | head -c 400)"
echo
if [ "$rt_code" = "409" ] && echo "$blocked_resp" | grep -q '"safety_guard_result"' \
   && echo "$blocked_resp" | grep -q '"allowed":false'; then
  echo "GUARD_DEFAULT_BLOCKED: PASS"; gb_ok=1
else
  echo "GUARD_DEFAULT_BLOCKED: FAIL"; gb_ok=0
fi
# response MUST NOT include token
if echo "$blocked_resp" | grep -qiE 'ghp_|github_pat_|"token":'; then
  echo "  response token leak check: FAIL"; tk3_ok=0
else
  echo "  response token leak check: PASS"; tk3_ok=1
fi

# 4. Metrics registered
echo
echo "=== 4. github-automation /metrics carries github_real_* counters ==="
metrics=$(curl -sS -m 10 "$GH/metrics" || echo '')
m_ok=1
for counter in github_real_test_attempts_total github_real_test_success_total \
               github_real_test_blocked_total github_real_test_failures_total \
               github_real_test_duration_seconds; do
  if echo "$metrics" | grep -qE "(^|# HELP |# TYPE )$counter"; then
    echo "  metric.$counter: PRESENT"
  else
    echo "  metric.$counter: MISSING"; m_ok=0
  fi
done
if [ "$m_ok" = "1" ]; then
  echo "GITHUB_REAL_METRICS: PASS"
else
  echo "GITHUB_REAL_METRICS: FAIL"
fi

# 5. Audit row for the blocked attempt
echo
echo "=== 5. audit_logs has github_real_test_blocked for $blocked_task ==="
sleep 2
audit=$(curl -sS -m 10 "$AUDIT/audit/events?task_id=$blocked_task&decision_type=github_real_test_blocked&limit=5" || echo '{}')
echo "$audit" | head -c 400
echo
if echo "$audit" | grep -q '"decision_type": *"github_real_test_blocked"' \
   && echo "$audit" | grep -q '"agent": *"github-automation"'; then
  echo "AUDIT_BLOCKED: PASS"; au_ok=1
else
  echo "AUDIT_BLOCKED: FAIL"; au_ok=0
fi

# 6. /operations/github/{task_id} surfaces the blocked event
echo
echo "=== 6. /operations/github/$blocked_task surfaces blocked event ==="
opv=$(curl -sS -m 10 "$ORCH/operations/github/$blocked_task" || echo '{}')
echo "$opv" | head -c 600
echo
if echo "$opv" | grep -q '"real_test"' \
   && echo "$opv" | grep -q '"latest_blocked"'; then
  echo "OPERATIONS_GITHUB_VIEW: PASS"; ov_ok=1
else
  echo "OPERATIONS_GITHUB_VIEW: FAIL"; ov_ok=0
fi

# 7. dry-run regression — /github/workflow/demo-pr must still work
echo
echo "=== 7. dry-run regression /github/workflow/demo-pr ==="
demo_task="real-github-verify-demo-$ts"
demo=$(curl -sS -m 20 -X POST "$GH/github/workflow/demo-pr" \
  -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$demo_task\",\"dry_run\":true,\"branch_name\":\"ai-agents-swd/$demo_task\"}" \
  || echo '{}')
if echo "$demo" | grep -q '"dry_run":true' \
   && echo "$demo" | grep -q '"pull_request"' \
   && echo "$demo" | grep -q '"event_type":"github.pr.dry_run"'; then
  echo "DRY_RUN_REGRESSION: PASS"; dr_ok=1
else
  echo "DRY_RUN_REGRESSION: FAIL"; dr_ok=0
fi

# 8. production safety — production_executed=false everywhere
echo
echo "=== 8. production safety (deployment_records + workflow_states) ==="
prod_dep=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
prod_wf=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
echo "  deployment_records.production_executed=true: $prod_dep"
echo "  workflow_states.production_executed=true:    $prod_wf"
if [ "$prod_dep" = "0" ] && [ "$prod_wf" = "0" ]; then
  echo "PRODUCTION_SAFETY: PASS"; pe_ok=1
else
  echo "PRODUCTION_SAFETY: FAIL"; pe_ok=0
fi

# 9. Optional real GitHub test
real_url=""
if [ "${RUN_REAL_GITHUB_TEST:-false}" = "true" ] \
   && [ -n "${GITHUB_TOKEN:-}" ] \
   && [ -n "${GITHUB_TEST_REPO:-}" ]; then
  echo
  echo "=== 9. OPTIONAL: real GitHub test (RUN_REAL_GITHUB_TEST=true + GITHUB_TEST_REPO=$GITHUB_TEST_REPO) ==="
  real_task="real-github-real-$ts"
  real_body=$(cat <<JSON
{
  "task_id":"$real_task",
  "workflow_id":"wf-$real_task",
  "repo":"$GITHUB_TEST_REPO",
  "base_branch":"main",
  "branch_name":"ai-agents-test/$real_task",
  "title":"[AI-Agents-SWD Test] controlled real validation",
  "body":"## Summary\nControlled real GitHub validation - do NOT merge.\n\n## Changed Files\n- docs/github-real-test/$real_task.md\n\n## Risk Assessment\nLow - sandbox repo, no merge, no production branch.\n\n## Test Result\nverify_real_github_validation.sh\n\n## Rollback Plan\nClose PR and delete head branch ai-agents-test/$real_task.\n\n## Safety Notes\nThis PR was opened by the AI-Agents-SWD platform under the Stage 23 controlled-real safety guard. The guard pins the sandbox repo to GITHUB_TEST_REPO, the branch prefix to ai-agents-test/, the title prefix to [AI-Agents-SWD Test], and the file path to docs/github-real-test/. No merge, no branch protection change, no production deploy.",
  "file_path":"docs/github-real-test/$real_task.md",
  "file_content":"task_id=$real_task\nworkflow_id=wf-$real_task\ngenerated_by=github-automation\nreal_github_test=true\nproduction_executed=false\ngenerated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)\n",
  "dry_run":false
}
JSON
)
  real=$(curl -sS -m 40 -X POST "$GH/github/workflow/real-test-pr" \
    -H "Content-Type: application/json" \
    -d "$real_body" || echo '{}')
  echo "$real" | head -c 1000
  echo
  real_url=$(echo "$real" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('pull_request',{}).get('url',''))" 2>/dev/null || echo '')
  real_issue=$(echo "$real" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('issue',{}).get('url',''))" 2>/dev/null || echo '')
  real_branch=$(echo "$real" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('branch',{}).get('name',''))" 2>/dev/null || echo '')
  if [ -n "$real_url" ]; then
    echo "  real_pr_url=$real_url"
    echo "  real_issue_url=$real_issue"
    echo "  real_branch=$real_branch"
    echo "REAL_GITHUB_TEST_EXECUTED: PASS"
    rt_ok=1
    # audit
    sleep 3
    real_audit=$(curl -sS -m 10 "$AUDIT/audit/events?task_id=$real_task&decision_type=github_real_test&limit=5" || echo '{}')
    if echo "$real_audit" | grep -q '"decision_type": *"github_real_test"'; then
      echo "REAL_GITHUB_TEST_AUDIT: PASS"
    else
      echo "REAL_GITHUB_TEST_AUDIT: CHECK"
    fi
    # notification
    real_notif=$(curl -sS -m 10 "$GATEWAY/notifications?count=200" || echo '{}')
    if echo "$real_notif" | grep -q '"event_type": *"github.real_test_pr.created"' \
       && echo "$real_notif" | grep -q "$real_task"; then
      echo "REAL_GITHUB_TEST_NOTIFICATION: PASS"
    else
      echo "REAL_GITHUB_TEST_NOTIFICATION: CHECK"
    fi
    # operations view
    real_opv=$(curl -sS -m 10 "$ORCH/operations/github/$real_task" || echo '{}')
    if echo "$real_opv" | grep -q '"latest_success"'; then
      echo "REAL_GITHUB_TEST_OPERATIONS_VIEW: PASS"
    else
      echo "REAL_GITHUB_TEST_OPERATIONS_VIEW: CHECK"
    fi
  else
    echo "REAL_GITHUB_TEST_EXECUTED: CHECK (no PR url)"
    rt_ok=0
  fi
else
  echo
  echo "=== 9. OPTIONAL: real GitHub test SKIPPED (default mode) ==="
  echo "REAL_GITHUB_TEST_SKIPPED: PASS"
  rt_ok=1
fi

echo
checks=0
[ "${h_ok:-0}"   = "1" ] && checks=$((checks+1))
[ "${tk_ok:-0}"  = "1" ] && checks=$((checks+1))
[ "${sf_ok:-0}"  = "1" ] && checks=$((checks+1))
[ "${tk2_ok:-0}" = "1" ] && checks=$((checks+1))
[ "${gb_ok:-0}"  = "1" ] && checks=$((checks+1))
[ "${tk3_ok:-0}" = "1" ] && checks=$((checks+1))
[ "${m_ok:-0}"   = "1" ] && checks=$((checks+1))
[ "${au_ok:-0}"  = "1" ] && checks=$((checks+1))
[ "${ov_ok:-0}"  = "1" ] && checks=$((checks+1))
[ "${dr_ok:-0}"  = "1" ] && checks=$((checks+1))
[ "${pe_ok:-0}"  = "1" ] && checks=$((checks+1))
[ "${rt_ok:-0}"  = "1" ] && checks=$((checks+1))

echo "checks passed: $checks / 12"
if [ "$checks" -ge 12 ]; then
  echo "REAL_GITHUB_VALIDATION_VERIFY: PASS"
else
  echo "REAL_GITHUB_VALIDATION_VERIFY: CHECK"
fi
if [ -n "$real_url" ]; then
  echo "REAL_GITHUB_TEST_PR_URL=$real_url"
fi
echo
echo "VERIFY_REAL_GITHUB_VALIDATION_DONE"
