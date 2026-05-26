#!/usr/bin/env bash
# Verify the github-automation service end-to-end in dry-run mode.
# Local/test only — contacts no real GitHub API by default. Run from
# the repository root.
#
# Opt-in: setting both GITHUB_TOKEN and RUN_REAL_GITHUB_TEST=true makes
# the script issue ONE additional real-GitHub demo PR against the test
# repo. Even then the PR title is forced to begin with
# "[AI-Agents-SWD Test]" and is left open — this script never merges,
# never modifies branch protection, never touches production.
set -uo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
GH_AUTOMATION="${GITHUB_AUTOMATION_URL:-http://localhost:8005}"
GATEWAY="${GATEWAY_URL:-http://localhost:8004}"
AUDIT="${AUDIT_SERVICE_URL:-http://localhost:8003}"
DEFAULT_REPO="${GITHUB_DEFAULT_REPO:-coolerh250/AI-Agents-SWD}"

echo "### verify_github_automation: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== github-automation container state ==="
$COMPOSE ps github-automation

echo
echo "=== /health ==="
health=$(curl -sS -m 5 "$GH_AUTOMATION/health" || echo '{}')
echo "$health" | head -c 400 || true
echo
if echo "$health" | grep -q '"status":"ok"' && echo "$health" | grep -q '"default_dry_run":true'; then
  echo "GITHUB_HEALTH: PASS"
else
  echo "GITHUB_HEALTH: FAIL"
fi

ts=$(date +%s)
task_id="github-verify-$ts"

echo
echo "=== /github/workflow/demo-pr (dry-run, task=$task_id) ==="
demo=$(curl -sS -m 20 -X POST "$GH_AUTOMATION/github/workflow/demo-pr" \
  -H "Content-Type: application/json" \
  -d "{
    \"task_id\":\"$task_id\",
    \"workflow_id\":\"wf-$task_id\",
    \"repo\":\"$DEFAULT_REPO\",
    \"base_branch\":\"main\",
    \"branch_name\":\"ai-agents-swd/verify-$ts\",
    \"title\":\"[AI-Agents-SWD Test] verify_github_automation\",
    \"body_summary\":\"github-automation verify smoke\",
    \"file_path\":\"docs/automation-demo.md\",
    \"file_content\":\"# verify smoke\\n\",
    \"risk_assessment\":\"Low - dry-run only\",
    \"test_result\":\"verify_github_automation.sh\",
    \"rollback_plan\":\"none required for dry-run\",
    \"dry_run\":true
  }" || echo '{}')
echo "$demo" | head -c 1500 || true
echo

# 1. dry_run flag
if echo "$demo" | grep -q '"dry_run":true'; then
  echo "  dry_run=true: PASS"
  dr_ok=1
else
  echo "  dry_run=true: FAIL"; dr_ok=0
fi

# 2. issue / branch / file / pr / checks objects present
sub_ok=1
for step in issue branch file pull_request checks; do
  if echo "$demo" | grep -q "\"$step\""; then
    echo "  step.$step: PRESENT"
  else
    echo "  step.$step: MISSING"
    sub_ok=0
  fi
done

# 3. PR body sections
pr_body=$(echo "$demo" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['pull_request']['body'])" 2>/dev/null || echo '')
body_ok=1
for sec in '## Summary' '## Changed Files' '## Risk Assessment' '## Test Result' '## Rollback Plan'; do
  if echo "$pr_body" | grep -qF "$sec"; then
    echo "  pr_body.$sec: PRESENT"
  else
    echo "  pr_body.$sec: MISSING"
    body_ok=0
  fi
done

# 4. notification on stream.notifications
echo
echo "=== notification (event_type=github.pr.dry_run) ==="
notifs=$(curl -sS -m 10 "$GATEWAY/notifications?count=200" || echo '{}')
if echo "$notifs" | grep -q '"event_type": *"github.pr.dry_run"' \
   && echo "$notifs" | grep -q "$task_id"; then
  echo "  notification: PRESENT"
  notif_ok=1
else
  echo "  notification: MISSING"
  notif_ok=0
fi

# 5. audit log
echo
echo "=== audit (decision_type=github_automation) ==="
audit=$(curl -sS -m 10 "$AUDIT/audit/events/$task_id" || echo '{}')
echo "$audit" | head -c 400 || true
echo
if echo "$audit" | grep -q '"decision_type": *"github_automation"'; then
  echo "  audit: PRESENT"
  audit_ok=1
else
  echo "  audit: MISSING"
  audit_ok=0
fi

# 6. /metrics carries github_* counters
echo
echo "=== /metrics (github_* counters) ==="
metrics=$(curl -sS -m 10 "$GH_AUTOMATION/metrics" || echo '')
metrics_ok=1
for counter in github_issue_created_total github_branch_created_total \
               github_pr_created_total github_checks_read_total \
               github_automation_failures_total; do
  if echo "$metrics" | grep -q "^$counter"; then
    echo "  metric.$counter: PRESENT"
  else
    echo "  metric.$counter: MISSING"
    metrics_ok=0
  fi
done

# 7. gateway proxy still works
echo
echo "=== communication-gateway /github/demo-pr proxy ==="
gw_demo=$(curl -sS -m 15 -X POST "$GATEWAY/github/demo-pr" \
  -H "Content-Type: application/json" \
  -d "{\"task_id\":\"gw-$task_id\",\"dry_run\":true,\"repo\":\"$DEFAULT_REPO\"}" \
  || echo '{}')
echo "$gw_demo" | head -c 400 || true
echo
if echo "$gw_demo" | grep -q '"dry_run":true' && echo "$gw_demo" | grep -q '"pull_request"'; then
  echo "  gateway.proxy: PASS"
  gw_ok=1
else
  echo "  gateway.proxy: FAIL"
  gw_ok=0
fi

real_url=""
if [ "${RUN_REAL_GITHUB_TEST:-false}" = "true" ] && [ -n "${GITHUB_TOKEN:-}" ]; then
  echo
  echo "=== OPTIONAL: real GitHub test (RUN_REAL_GITHUB_TEST=true) ==="
  real_task="github-real-$ts"
  real=$(curl -sS -m 30 -X POST "$GH_AUTOMATION/github/workflow/demo-pr" \
    -H "Content-Type: application/json" \
    -d "{
      \"task_id\":\"$real_task\",
      \"repo\":\"$DEFAULT_REPO\",
      \"base_branch\":\"main\",
      \"branch_name\":\"ai-agents-swd/real-$ts\",
      \"title\":\"[AI-Agents-SWD Test] real github automation verify\",
      \"body_summary\":\"opt-in real github test - do NOT merge\",
      \"file_path\":\"docs/automation-demo.md\",
      \"file_content\":\"# real verify $ts\\n\",
      \"risk_assessment\":\"Low - test branch, no merge\",
      \"test_result\":\"verify_github_automation.sh real path\",
      \"rollback_plan\":\"close PR + delete head branch\",
      \"dry_run\":false
    }" || echo '{}')
  echo "$real" | head -c 800 || true
  echo
  real_url=$(echo "$real" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('pull_request',{}).get('url',''))" 2>/dev/null || echo '')
  if [ -n "$real_url" ]; then
    echo "  real_pr_url=$real_url"
    echo "  REAL_GITHUB_TEST: PASS"
  else
    echo "  REAL_GITHUB_TEST: CHECK (no PR url in response)"
  fi
else
  echo
  echo "=== OPTIONAL: real GitHub test SKIPPED (set RUN_REAL_GITHUB_TEST=true and GITHUB_TOKEN to enable) ==="
fi

checks=0
[ "${dr_ok:-0}"     = "1" ] && checks=$((checks+1))
[ "${sub_ok:-0}"    = "1" ] && checks=$((checks+1))
[ "${body_ok:-0}"   = "1" ] && checks=$((checks+1))
[ "${notif_ok:-0}"  = "1" ] && checks=$((checks+1))
[ "${audit_ok:-0}"  = "1" ] && checks=$((checks+1))
[ "${metrics_ok:-0}" = "1" ] && checks=$((checks+1))
[ "${gw_ok:-0}"     = "1" ] && checks=$((checks+1))

echo
echo "checks passed: $checks / 7"
if [ "$checks" -eq 7 ]; then
  echo "GITHUB_AUTOMATION_VERIFY: PASS"
else
  echo "GITHUB_AUTOMATION_VERIFY: CHECK"
fi
if [ -n "$real_url" ]; then
  echo "REAL_GITHUB_TEST_PR_URL=$real_url"
fi
echo
echo "VERIFY_GITHUB_AUTOMATION_DONE"
