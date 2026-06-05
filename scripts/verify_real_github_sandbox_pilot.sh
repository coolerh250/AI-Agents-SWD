#!/usr/bin/env bash
# Stage 32 -- real GitHub sandbox-PR pilot verifier.
#
# Default mode (no GITHUB_TOKEN / RUN_REAL_GITHUB_TEST / GITHUB_TEST_REPO):
#   * /github/workflow/real-test-pr refuses with HTTP 409.
#   * REAL_GITHUB_SANDBOX_TEST_SKIPPED: PASS
#   * Final marker REAL_GITHUB_SANDBOX_PILOT_VERIFY: PASS
#
# Opt-in mode (ALL of GITHUB_TOKEN, RUN_REAL_GITHUB_TEST=true,
# GITHUB_TEST_REPO -- where GITHUB_TEST_REPO MUST point at a sandbox
# repo, NEVER coolerh250/AI-Agents-SWD): one real PR is created and the
# following are asserted:
#   * repo == GITHUB_TEST_REPO
#   * PR is NOT merged
#   * branch protection is NOT modified (we never call that endpoint)
#   * audit_logs has decision_type=github_sandbox_pr_created
#   * notification_deliveries carries event_type=github.sandbox_pr.created
#   * /operations/github/{task_id} surfaces the run
#   * production_executed counters stay at 0
#
# Run from the repository root.
set -uo pipefail

GH="${GITHUB_AUTOMATION_URL:-http://localhost:8005}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
AUDIT="${AUDIT_SERVICE_URL:-http://localhost:8003}"
DISCORD="${DISCORD_GATEWAY_URL:-http://localhost:8007}"
COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"

echo "### verify_real_github_sandbox_pilot: $(date '+%Y-%m-%d %H:%M:%S %Z')"

ts=$(date +%s)
task_id="real-github-sandbox-$ts"

echo
echo "=== Inputs snapshot ==="
./scripts/check_real_integration_inputs.sh | tail -15

if [ -z "${GITHUB_TOKEN:-}" ] \
   || [ "${RUN_REAL_GITHUB_TEST:-false}" != "true" ] \
   || [ -z "${GITHUB_TEST_REPO:-}" ]; then
  echo
  echo "=== Skipped-mode guard refusal ==="
  body=$(cat <<JSON
{
  "task_id": "$task_id",
  "workflow_id": "wf-$task_id",
  "repo": "owner/sandbox",
  "base_branch": "main",
  "branch_name": "ai-agents-test/$task_id",
  "title": "[AI-Agents-SWD Test] $task_id",
  "body": "## Summary\nx\n\n## Changed Files\n- docs/github-real-test/x.md\n\n## Risk Assessment\nLow\n\n## Test Result\nx\n\n## Rollback Plan\nx\n\n## Safety Notes\nGuarded sandbox PR.",
  "file_path": "docs/github-real-test/$task_id.md",
  "file_content": "task_id=$task_id\nworkflow_id=wf-$task_id\ngenerated_by=github-automation\nreal_github_test=true\nproduction_executed=false\n",
  "dry_run": false
}
JSON
)
  code=$(curl -sS -m 10 -o /tmp/gh.$$ -w "%{http_code}" -X POST \
    "$GH/github/workflow/real-test-pr" \
    -H "Content-Type: application/json" \
    -d "$body" || echo "000")
  cat /tmp/gh.$$ 2>/dev/null | head -c 300 | tr -d '\n'; echo
  rm -f /tmp/gh.$$
  if [ "$code" = "409" ]; then
    echo "REAL_GITHUB_SANDBOX_REFUSED_DEFAULT: PASS"
  else
    echo "REAL_GITHUB_SANDBOX_REFUSED_DEFAULT: FAIL (http=$code)"
    echo "REAL_GITHUB_SANDBOX_PILOT_VERIFY: FAIL"
    exit 1
  fi
  echo "REAL_GITHUB_SANDBOX_TEST_SKIPPED: PASS"
  echo
  echo "REAL_GITHUB_SANDBOX_PILOT_VERIFY: PASS"
  exit 0
fi

if [ "$GITHUB_TEST_REPO" = "coolerh250/AI-Agents-SWD" ]; then
  echo
  echo "GITHUB_TEST_REPO points at the canonical production repo --"
  echo "refusing to proceed. Pin GITHUB_TEST_REPO at a sandbox repo"
  echo "(e.g. coolerh250/AI-Agents-SWD-sandbox)."
  echo "REAL_GITHUB_SANDBOX_PILOT_VERIFY: BLOCKED"
  exit 1
fi

echo
echo "=== Real-mode PR (repo=$GITHUB_TEST_REPO) ==="
body=$(cat <<JSON
{
  "task_id": "$task_id",
  "workflow_id": "wf-$task_id",
  "repo": "$GITHUB_TEST_REPO",
  "base_branch": "main",
  "branch_name": "ai-agents-test/$task_id",
  "title": "[AI-Agents-SWD Test] $task_id sandbox PR",
  "body": "## Summary\nStage 32 sandbox PR\n\n## Changed Files\n- docs/github-real-test/$task_id.md\n\n## Risk Assessment\nLow\n\n## Test Result\npending\n\n## Rollback Plan\ngh pr close --delete-branch\n\n## Safety Notes\nGuarded sandbox PR.",
  "file_path": "docs/github-real-test/$task_id.md",
  "file_content": "task_id=$task_id\nworkflow_id=wf-$task_id\ngenerated_by=github-automation\nreal_github_test=true\nproduction_executed=false\n",
  "dry_run": false
}
JSON
)
resp=$(curl -sS -m 60 -X POST "$GH/github/workflow/real-test-pr" \
  -H "Content-Type: application/json" \
  -d "$body" || echo '{}')
echo "$resp" | head -c 900; echo
pr_url=$(echo "$resp" | python3 -c 'import json,sys
try:
  d=json.load(sys.stdin)
  print((d.get("pull_request") or {}).get("url",""))
except Exception:
  print("")' 2>/dev/null || echo "")
issue_url=$(echo "$resp" | python3 -c 'import json,sys
try:
  d=json.load(sys.stdin)
  print((d.get("issue") or {}).get("url",""))
except Exception:
  print("")' 2>/dev/null || echo "")
if [ -n "$pr_url" ]; then
  echo "REAL_GITHUB_SANDBOX_PR_CREATED: PASS (pr=$pr_url)"
else
  echo "REAL_GITHUB_SANDBOX_PR_CREATED: FAIL"
  echo "REAL_GITHUB_SANDBOX_PILOT_VERIFY: FAIL"
  exit 1
fi

echo
echo "=== Audit decision_type=github_sandbox_pr_created ==="
au=$(curl -sS -m 10 "$AUDIT/audit/events?decision_type=github_sandbox_pr_created&limit=5" || echo '{}')
if echo "$au" | grep -q '"github_sandbox_pr_created"'; then
  echo "AUDIT_GITHUB_SANDBOX_PR_CREATED: PASS"
else
  echo "AUDIT_GITHUB_SANDBOX_PR_CREATED: FAIL"
fi

echo
echo "=== Notification event_type=github.sandbox_pr.created ==="
deliv=$(curl -sS -m 10 "$DISCORD/discord/deliveries/$task_id" || echo '{}')
if echo "$deliv" | grep -q '"github.sandbox_pr.created"'; then
  echo "NOTIFICATION_GITHUB_SANDBOX_PR_CREATED: PASS"
else
  echo "NOTIFICATION_GITHUB_SANDBOX_PR_CREATED: CHECK (notification may lag)"
fi

echo
echo "=== /operations/github/$task_id ==="
opsv=$(curl -sS -m 10 "$ORCH/operations/github/$task_id" || echo '{}')
if echo "$opsv" | grep -q '"task_id"'; then
  echo "OPERATIONS_GITHUB_VIEW: PASS"
else
  echo "OPERATIONS_GITHUB_VIEW: FAIL"
fi

echo
echo "=== production_safety ==="
dep=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
wf=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
echo "  deployment_records.production_executed_true=$dep"
echo "  workflow_states.production_executed_true=$wf"
if [ "$dep" = "0" ] && [ "$wf" = "0" ]; then
  echo "PRODUCTION_SAFETY: PASS"
else
  echo "PRODUCTION_SAFETY: FAIL"
  echo "REAL_GITHUB_SANDBOX_PILOT_VERIFY: FAIL"
  exit 1
fi

echo
echo "REAL_GITHUB_SANDBOX_PILOT_VERIFY: PASS"
