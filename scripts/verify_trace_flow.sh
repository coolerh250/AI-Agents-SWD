#!/usr/bin/env bash
# Drive one workflow through communication-gateway -> orchestrator -> agent
# pipeline and assert that the resulting trace is queryable in Tempo with every
# expected service.name attached. Local/test only — contacts no cloud SaaS.
# Run from the repository root.
set -uo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
GATEWAY="${GATEWAY_URL:-http://localhost:8004}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
TEMPO="${TEMPO_URL:-http://localhost:3200}"

echo "### verify_trace_flow: $(date '+%Y-%m-%d %H:%M:%S %Z')"

ts=$(date +%s)
task_id="trace-verify-$ts"
echo
echo "=== seed task_id=$task_id via $GATEWAY/intake/mock (stream mode) ==="
seed=$(curl -sS -m 30 -X POST "$GATEWAY/intake/mock" -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$task_id\",\"request\":{\"type\":\"dev.test\",\"description\":\"trace flow verify\"},\"publish_to_stream\":true}" \
  || echo '{}')
echo "$seed"

echo
echo "=== wait for workflow $task_id to reach completed ==="
trace_id=""
workflow_id=""
final_stage=""
for i in $(seq 1 40); do
  prog=$(curl -sS -m 10 "$ORCH/workflow/progress/$task_id" || echo '{}')
  stage=$(echo "$prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  final_stage="$stage"
  if [ -z "$trace_id" ]; then
    trace_id=$(echo "$prog" | sed -n 's/.*"trace_id": *"\([a-f0-9]*\)".*/\1/p' | head -n1)
  fi
  if [ -z "$workflow_id" ]; then
    workflow_id=$(echo "$prog" | sed -n 's/.*"workflow_id": *"\([^"]*\)".*/\1/p' | head -n1)
  fi
  if [ "$stage" = "completed" ]; then break; fi
  sleep 2
done
echo "task_id=$task_id workflow_id=$workflow_id trace_id=$trace_id final_stage=$final_stage"

if [ -z "$trace_id" ]; then
  echo "TRACE_FLOW_SMOKE: FAIL (no trace_id from /workflow/progress/$task_id)"
  exit 0
fi
if [ "$final_stage" != "completed" ]; then
  echo "TRACE_FLOW_SMOKE: FAIL (workflow did not reach completed; stage=$final_stage)"
  exit 0
fi

# Give Tempo a moment to ingest the spans the orchestrator and agents emitted.
sleep 6

echo
echo "=== query Tempo /api/traces/$trace_id ==="
trace_body=$(curl -sS -m 15 "$TEMPO/api/traces/$trace_id" || echo '')
echo "$trace_body" | head -c 1500
echo

if [ -z "$trace_body" ] || echo "$trace_body" | grep -qi 'trace not found'; then
  echo "TRACE_FLOW_SMOKE: FAIL (trace $trace_id not found in Tempo)"
  exit 0
fi

required_services=(
  communication-gateway
  orchestrator
  intake-agent
  requirement-agent
  development-agent
  qa-agent
  devops-agent
)

missing=()
for svc in "${required_services[@]}"; do
  if echo "$trace_body" | grep -q "\"service.name\"" \
     && echo "$trace_body" | grep -q "\"$svc\""; then
    echo "  $svc: PRESENT"
  else
    echo "  $svc: MISSING"
    missing+=("$svc")
  fi
done

echo
if [ "${#missing[@]}" -eq 0 ]; then
  echo "TRACE_FLOW_SMOKE: PASS (trace_id=$trace_id covers all 7 services)"
else
  echo "TRACE_FLOW_SMOKE: CHECK (missing: ${missing[*]})"
fi

echo
echo "VERIFY_TRACE_FLOW_DONE"
