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
echo "CHECK_RUNTIME_STATE_DONE"
