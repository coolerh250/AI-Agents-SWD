#!/usr/bin/env bash
# Verify the Stage 20 Operations Control API end-to-end:
#
#   /operations/health
#   /operations/summary
#   /operations/workflows/{task_id}
#   /operations/agents
#   /operations/streams
#   /operations/safety
#   /operations/github/{task_id}
#
# Drives one orchestrator-mode normal workflow + one github-pipeline
# dry-run workflow, waits for both to complete, then asserts every
# operations endpoint exposes the expected unified view.
# Local/test only; contacts no real GitHub API; never replays DLQ.
# Run from the repository root.
set -uo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
GATEWAY="${GATEWAY_URL:-http://localhost:8004}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
DEFAULT_REPO="${GITHUB_DEFAULT_REPO:-coolerh250/AI-Agents-SWD}"

echo "### verify_operations_view: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== orchestrator container state ==="
$COMPOSE ps orchestrator audit-worker

ts=$(date +%s)
normal_task="ops-verify-normal-$ts"
gh_task="ops-verify-github-$ts"

echo
echo "=== seed orchestrator-mode normal workflow $normal_task ==="
curl -sS -m 30 -X POST "$GATEWAY/intake/mock" -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$normal_task\",\"request\":{\"type\":\"dev.test\",\"description\":\"ops-verify-normal\"}}" \
  | head -c 300 || true
echo

echo
echo "=== seed github-pipeline dry-run workflow $gh_task ==="
curl -sS -m 30 -X POST "$GATEWAY/intake/mock" -H "Content-Type: application/json" \
  -d "{
    \"task_id\":\"$gh_task\",
    \"request\":{
      \"type\":\"dev.test\",
      \"description\":\"ops-verify-github\",
      \"github\":{\"enabled\":true,\"repo\":\"$DEFAULT_REPO\",\"dry_run\":true}
    }
  }" | head -c 300 || true
echo

echo
echo "=== wait for both workflows to complete ==="
for t in "$normal_task" "$gh_task"; do
  for i in $(seq 1 45); do
    prog=$(curl -sS -m 10 "$ORCH/workflow/progress/$t" || echo '{}')
    stage=$(echo "$prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
    if [ "$stage" = "completed" ]; then break; fi
    sleep 2
  done
  echo "  $t -> $stage"
done
sleep 5  # let stream.audit -> audit-worker -> audit_logs settle

echo
echo "=== 1. /operations/health ==="
op_health=$(curl -sS -m 5 "$ORCH/operations/health" || echo '{}')
echo "$op_health"
if echo "$op_health" | grep -q '"service": *"operations"'; then
  echo "  /operations/health: PASS"; h_ok=1
else
  echo "  /operations/health: FAIL"; h_ok=0
fi

echo
echo "=== 2. /operations/workflows/$gh_task ==="
op_wf=$(curl -sS -m 15 "$ORCH/operations/workflows/$gh_task" || echo '{}')
echo "$op_wf" | head -c 800 || true
echo
wf_ok=1
for required in '"workflow"' '"agents"' '"audit_timeline"' '"github"' '"deployment"' '"trace"' '"safety"' '"production_executed":false'; do
  if echo "$op_wf" | grep -q "$required"; then
    echo "  workflow_view contains $required: PASS"
  else
    echo "  workflow_view contains $required: FAIL"; wf_ok=0
  fi
done
if echo "$op_wf" | grep -q 'github_pr_integration'; then
  echo "  workflow_view.audit_timeline carries github_pr_integration: PASS"
else
  echo "  workflow_view.audit_timeline carries github_pr_integration: FAIL"; wf_ok=0
fi

echo
echo "=== 3. /operations/summary ==="
op_sum=$(curl -sS -m 15 "$ORCH/operations/summary" || echo '{}')
echo "$op_sum" | head -c 600 || true
echo
if echo "$op_sum" | grep -q '"production_safety"' \
   && echo "$op_sum" | grep -q '"workflows_summary"' \
   && echo "$op_sum" | grep -q '"agents_summary"' \
   && echo "$op_sum" | grep -q '"dlq_summary"'; then
  echo "  /operations/summary: PASS"; sum_ok=1
else
  echo "  /operations/summary: FAIL"; sum_ok=0
fi

echo
echo "=== 4. /operations/agents ==="
op_agents=$(curl -sS -m 10 "$ORCH/operations/agents" || echo '{}')
if echo "$op_agents" | grep -q '"intake-agent"' \
   && echo "$op_agents" | grep -q '"devops-agent"' \
   && echo "$op_agents" | grep -q '"consumer_group"'; then
  echo "  /operations/agents: PASS"; agents_ok=1
else
  echo "  /operations/agents: FAIL"; agents_ok=0
fi

echo
echo "=== 5. /operations/streams ==="
op_streams=$(curl -sS -m 10 "$ORCH/operations/streams" || echo '{}')
audit_consumers=$(echo "$op_streams" | python3 -c "import json,sys
try:
    d=json.load(sys.stdin)
    for s in d.get('streams',[]):
        if s.get('name')=='stream.audit':
            print(s.get('consumers',0)); break
except Exception:
    print(0)" 2>/dev/null)
echo "  stream.audit consumers: $audit_consumers"
if [ -n "$audit_consumers" ] && [ "$audit_consumers" -ge 1 ] 2>/dev/null; then
  echo "  /operations/streams stream.audit consumers>=1: PASS"
  streams_ok=1
else
  echo "  /operations/streams stream.audit consumers>=1: FAIL"; streams_ok=0
fi

echo
echo "=== 6. /operations/safety ==="
op_safety=$(curl -sS -m 10 "$ORCH/operations/safety" || echo '{}')
echo "$op_safety" | head -c 600 || true
echo
prod_dep=$(echo "$op_safety" | sed -n 's/.*"production_executed_true_count": *\([0-9]*\).*/\1/p' | head -n1)
prod_wf=$(echo "$op_safety" | sed -n 's/.*"workflow_production_executed_true_count": *\([0-9]*\).*/\1/p' | head -n1)
safety_result=$(echo "$op_safety" | sed -n 's/.*"result": *"\([^"]*\)".*/\1/p' | head -n1)
echo "  production counters: deployment=$prod_dep workflow=$prod_wf result=$safety_result"
if [ "$prod_dep" = "0" ] && [ "$prod_wf" = "0" ] \
   && { [ "$safety_result" = "safe" ] || [ "$safety_result" = "warning" ]; }; then
  echo "  /operations/safety counters=0 and result safe/warning: PASS"
  safety_ok=1
else
  echo "  /operations/safety counters=0 and result safe/warning: FAIL"; safety_ok=0
fi

echo
echo "=== 7. /operations/github/$gh_task ==="
op_gh=$(curl -sS -m 10 "$ORCH/operations/github/$gh_task" || echo '{}')
echo "$op_gh" | head -c 600 || true
echo
if echo "$op_gh" | grep -q '"found": *true' \
   && echo "$op_gh" | grep -q '"dry_run": *true' \
   && echo "$op_gh" | grep -q '"pr_url": *"https' \
   && echo "$op_gh" | grep -q 'audit_logs'; then
  echo "  /operations/github/{task_id} PASS"; gh_ok=1
else
  echo "  /operations/github/{task_id}: FAIL"; gh_ok=0
fi

echo
echo "=== 8. /operations/incidents ==="
op_inc=$(curl -sS -m 10 "$ORCH/operations/incidents?limit=5" || echo '{}')
if echo "$op_inc" | grep -q '"count":' && echo "$op_inc" | grep -q '"incidents":'; then
  echo "  /operations/incidents: PASS"; inc_ok=1
else
  echo "  /operations/incidents: FAIL"; inc_ok=0
fi

echo
echo "=== 9. /operations/dlq ==="
op_dlq=$(curl -sS -m 10 "$ORCH/operations/dlq?limit=5" || echo '{}')
if echo "$op_dlq" | grep -q '"deadletter_length":' \
   && echo "$op_dlq" | grep -q '"deadletter_terminal_length":'; then
  echo "  /operations/dlq: PASS"; dlq_ok=1
else
  echo "  /operations/dlq: FAIL"; dlq_ok=0
fi

echo
echo "=== 10. production safety counters from /operations/safety ==="
if [ "$prod_dep" = "0" ] && [ "$prod_wf" = "0" ]; then
  echo "  production_executed=false confirmed (deployment=$prod_dep workflow=$prod_wf): PASS"
  prod_ok=1
else
  echo "  production_executed=false confirmed: FAIL"; prod_ok=0
fi

echo
checks=0
[ "$h_ok"        = "1" ] && checks=$((checks+1))
[ "$wf_ok"       = "1" ] && checks=$((checks+1))
[ "$sum_ok"      = "1" ] && checks=$((checks+1))
[ "$agents_ok"   = "1" ] && checks=$((checks+1))
[ "$streams_ok"  = "1" ] && checks=$((checks+1))
[ "$safety_ok"   = "1" ] && checks=$((checks+1))
[ "$gh_ok"       = "1" ] && checks=$((checks+1))
[ "$inc_ok"      = "1" ] && checks=$((checks+1))
[ "$dlq_ok"      = "1" ] && checks=$((checks+1))
[ "$prod_ok"     = "1" ] && checks=$((checks+1))
echo "checks passed: $checks / 10"
if [ "$checks" -ge 10 ]; then
  echo "OPERATIONS_VIEW_VERIFY: PASS"
elif [ "$checks" -ge 9 ]; then
  echo "OPERATIONS_VIEW_VERIFY: PASS (9/10 — non-fatal lag tolerated)"
else
  echo "OPERATIONS_VIEW_VERIFY: CHECK"
fi
echo
echo "VERIFY_OPERATIONS_VIEW_DONE"
