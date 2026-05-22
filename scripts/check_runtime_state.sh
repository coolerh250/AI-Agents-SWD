#!/usr/bin/env bash
# Check the state of the local/test runtime: containers, PostgreSQL tables,
# Redis streams, and the orchestrator health endpoint.
# Run from the repository root.
set -euo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"

echo "### runtime state check: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== docker compose ps ==="
$COMPOSE ps

echo
echo "=== PostgreSQL tables (database: aiagents) ==="
$COMPOSE exec -T postgres psql -U postgres -d aiagents -c '\dt'
tcount=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d '[:space:]')
echo "public table count: $tcount"

echo
echo "=== Redis streams & consumer groups ==="
streams=$($COMPOSE exec -T redis redis-cli --scan --pattern 'stream.*' </dev/null 2>/dev/null | sort)
for s in $streams; do
  grp=$($COMPOSE exec -T redis redis-cli XINFO GROUPS "$s" </dev/null 2>/dev/null | grep -cF 'name' || true)
  echo "  $s  ->  $grp consumer group(s)"
done

echo
echo "=== orchestrator /health ==="
if curl -sS -m 10 http://localhost:8000/health; then
  echo
  echo "HEALTH: PASS"
else
  echo
  echo "HEALTH: FAIL"
fi

echo
echo "=== orchestrator /workflow/schema ==="
curl -sS -m 10 http://localhost:8000/workflow/schema || echo "(schema unavailable)"
echo

echo
echo "=== /workflow/test (non-production smoke) ==="
np=$(curl -sS -m 20 -X POST http://localhost:8000/workflow/test \
  -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-dev","source":"check","request":{"type":"dev.test"}}' || echo '{}')
echo "$np"
if echo "$np" | grep -q '"stage": *"completed"'; then
  echo "NON_PROD_SMOKE: PASS"
else
  echo "NON_PROD_SMOKE: CHECK"
fi

echo
echo "=== /workflow/test (production.deploy approval smoke) ==="
pd=$(curl -sS -m 20 -X POST http://localhost:8000/workflow/test \
  -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-prod","source":"check","request":{"type":"production.deploy"}}' || echo '{}')
echo "$pd"
if echo "$pd" | grep -q '"stage": *"waiting_approval"'; then
  echo "PROD_APPROVAL_SMOKE: PASS"
else
  echo "PROD_APPROVAL_SMOKE: CHECK"
fi

echo
echo "=== governance services /health ==="
for entry in policy-engine:8001 approval-engine:8002 audit-service:8003; do
  name="${entry%%:*}"
  port="${entry##*:}"
  if curl -sS -m 10 "http://localhost:${port}/health" >/dev/null 2>&1; then
    echo "  ${name} (:${port})  ->  HEALTH: PASS"
  else
    echo "  ${name} (:${port})  ->  HEALTH: FAIL"
  fi
done

echo
echo "=== approval-engine flow smoke (request -> approve) ==="
appr=$(curl -sS -m 15 -X POST http://localhost:8002/approval/request \
  -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-approval","action":"production.deploy","risk_level":"high","reason":"runtime smoke test","requested_by":"check-runtime"}' || echo '{}')
echo "$appr"
rid=$(echo "$appr" | sed -n 's/.*"request_id": *"\([^"]*\)".*/\1/p')
if [ -n "$rid" ]; then
  appr2=$(curl -sS -m 15 -X POST http://localhost:8002/approval/approve \
    -H "Content-Type: application/json" \
    -d "{\"request_id\":\"$rid\",\"decided_by\":\"check-runtime\"}" || echo '{}')
  echo "$appr2"
  if echo "$appr2" | grep -q '"status": *"approved"'; then
    echo "APPROVAL_SMOKE: PASS"
  else
    echo "APPROVAL_SMOKE: CHECK"
  fi
else
  echo "APPROVAL_SMOKE: CHECK"
fi

echo
echo "=== audit-service insert smoke (insert -> query) ==="
aud=$(curl -sS -m 15 -X POST http://localhost:8003/audit/events \
  -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-audit","agent":"check-runtime","decision_type":"smoke","summary":"runtime smoke test","result":"ok","artifact_refs":{}}' || echo '{}')
echo "$aud"
aud2=$(curl -sS -m 15 http://localhost:8003/audit/events/smoke-audit || echo '{}')
echo "$aud2"
if echo "$aud2" | grep -q '"count"'; then
  echo "AUDIT_SMOKE: PASS"
else
  echo "AUDIT_SMOKE: CHECK"
fi

echo
echo "=== workflow persistence smoke (run -> GET /workflow/{id}) ==="
wf_task="smoke-persist-$$"
curl -sS -m 25 -X POST http://localhost:8000/workflow/test -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$wf_task\",\"source\":\"check\",\"request\":{\"type\":\"dev.test\"}}" \
  >/dev/null 2>&1 || true
persisted=$(curl -sS -m 10 "http://localhost:8000/workflow/$wf_task" || echo '{}')
echo "$persisted"
if echo "$persisted" | grep -q "\"task_id\":\"$wf_task\""; then
  echo "WORKFLOW_PERSISTENCE_SMOKE: PASS"
else
  echo "WORKFLOW_PERSISTENCE_SMOKE: CHECK"
fi

echo
echo "=== workflow replay smoke (GET /workflow/replay/{id}) ==="
replay=$(curl -sS -m 10 "http://localhost:8000/workflow/replay/$wf_task" || echo '{}')
echo "$replay"
if echo "$replay" | grep -q '"executed":false'; then
  echo "WORKFLOW_REPLAY_SMOKE: PASS"
else
  echo "WORKFLOW_REPLAY_SMOKE: CHECK"
fi

echo
echo "=== approval resume smoke (production.deploy -> approve -> resume) ==="
rs_task="smoke-resume-$$"
rs_wf=$(curl -sS -m 25 -X POST http://localhost:8000/workflow/test -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$rs_task\",\"source\":\"check\",\"request\":{\"type\":\"production.deploy\"}}" \
  || echo '{}')
echo "$rs_wf"
rs_req=$(echo "$rs_wf" | sed -n 's/.*"approval_request_id": *"\([^"]*\)".*/\1/p')
if [ -n "$rs_req" ]; then
  curl -sS -m 15 -X POST http://localhost:8002/approval/approve -H "Content-Type: application/json" \
    -d "{\"request_id\":\"$rs_req\",\"decided_by\":\"check-runtime\"}" >/dev/null 2>&1 || true
  rs_resumed=$(curl -sS -m 15 -X POST "http://localhost:8000/workflow/resume/$rs_task" || echo '{}')
  echo "$rs_resumed"
  if echo "$rs_resumed" | grep -q '"stage": *"completed"'; then
    echo "APPROVAL_RESUME_SMOKE: PASS"
  else
    echo "APPROVAL_RESUME_SMOKE: CHECK"
  fi
else
  echo "APPROVAL_RESUME_SMOKE: CHECK"
fi

echo
echo "=== communication-gateway /health ==="
if curl -sS -m 10 http://localhost:8004/health >/dev/null 2>&1; then
  echo "  communication-gateway (:8004)  ->  HEALTH: PASS"
else
  echo "  communication-gateway (:8004)  ->  HEALTH: FAIL"
fi

echo
echo "=== /intake/mock non-production smoke ==="
gw_dev=$(curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-gw-dev","request":{"type":"dev.test"}}' || echo '{}')
echo "$gw_dev"
if echo "$gw_dev" | grep -q '"stage": *"completed"'; then
  echo "INTAKE_NONPROD_SMOKE: PASS"
else
  echo "INTAKE_NONPROD_SMOKE: CHECK"
fi

echo
echo "=== /intake/mock production.deploy smoke ==="
gw_prod=$(curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-gw-prod","request":{"type":"production.deploy"}}' || echo '{}')
echo "$gw_prod"
if echo "$gw_prod" | grep -q '"stage": *"waiting_approval"'; then
  echo "INTAKE_PROD_SMOKE: PASS"
else
  echo "INTAKE_PROD_SMOKE: CHECK"
fi

echo
echo "=== /notifications/test + /notifications smoke ==="
nt=$(curl -sS -m 15 -X POST http://localhost:8004/notifications/test -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-gw-notif","event_type":"runtime.smoke","message":"runtime check"}' || echo '{}')
echo "$nt"
notif=$(curl -sS -m 15 "http://localhost:8004/notifications?count=20" || echo '{}')
echo "$notif"
if echo "$notif" | grep -q 'smoke-gw-notif'; then
  echo "NOTIFICATIONS_SMOKE: PASS"
else
  echo "NOTIFICATIONS_SMOKE: CHECK"
fi

echo
echo "=== agent services /health ==="
for entry in intake-agent:8010 requirement-agent:8011 development-agent:8012 \
             qa-agent:8013 devops-agent:8014; do
  name="${entry%%:*}"
  port="${entry##*:}"
  if curl -sS -m 10 "http://localhost:${port}/health" >/dev/null 2>&1; then
    echo "  ${name} (:${port})  ->  HEALTH: PASS"
  else
    echo "  ${name} (:${port})  ->  HEALTH: FAIL"
  fi
done

echo
echo "=== full agent pipeline smoke (tasks -> intake -> requirement -> development -> qa -> devops) ==="
pl_task="smoke-pipeline-$$"
dep_before=$($COMPOSE exec -T redis redis-cli XLEN stream.deployments | tr -d '[:space:]')
curl -sS -m 20 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$pl_task\",\"request\":{\"type\":\"dev.test\"},\"publish_to_stream\":true}" \
  >/dev/null 2>&1 || true
dep_after="${dep_before:-0}"
for i in $(seq 1 20); do
  dep_after=$($COMPOSE exec -T redis redis-cli XLEN stream.deployments | tr -d '[:space:]')
  if [ "${dep_after:-0}" -gt "${dep_before:-0}" ]; then break; fi
  sleep 2
done
echo "stream.deployments: before=${dep_before:-0} after=${dep_after:-0}"
if [ "${dep_after:-0}" -gt "${dep_before:-0}" ]; then
  echo "FULL_PIPELINE_SMOKE: PASS"
else
  echo "FULL_PIPELINE_SMOKE: CHECK"
fi
sleep 3

echo
echo "=== agent_executions for $pl_task ==="
$COMPOSE exec -T postgres psql -U postgres -d aiagents -c \
  "SELECT agent, status FROM agent_executions WHERE task_id='$pl_task' ORDER BY created_at;"
exec_count=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM agent_executions WHERE task_id='$pl_task' AND status='completed';" \
  | tr -d '[:space:]')
echo "completed executions for $pl_task: ${exec_count:-0}"
if [ "${exec_count:-0}" -ge 5 ]; then
  echo "AGENT_EXECUTIONS_SMOKE: PASS"
else
  echo "AGENT_EXECUTIONS_SMOKE: CHECK"
fi

echo
echo "=== deployment_records for $pl_task ==="
$COMPOSE exec -T postgres psql -U postgres -d aiagents -c \
  "SELECT task_id, environment, status FROM deployment_records WHERE task_id='$pl_task';"
dep_rows=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE task_id='$pl_task';" | tr -d '[:space:]')
if [ "${dep_rows:-0}" -ge 1 ]; then
  echo "DEPLOYMENT_RECORD_SMOKE: PASS"
else
  echo "DEPLOYMENT_RECORD_SMOKE: CHECK"
fi

echo
echo "CHECK_RUNTIME_STATE_DONE"
