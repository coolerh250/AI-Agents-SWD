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
echo "CHECK_RUNTIME_STATE_DONE"
