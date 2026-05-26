#!/usr/bin/env bash
# Verify the terminal-failure -> incident -> workflow.failed flow end-to-end.
# Local/test only — no real off-host notifier is contacted. Run from the
# repository root.
set -uo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
GATEWAY="${GATEWAY_URL:-http://localhost:8004}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
AUDIT="${AUDIT_SERVICE_URL:-http://localhost:8003}"

echo "### verify_incident_flow: $(date '+%Y-%m-%d %H:%M:%S %Z')"

ts=$(date +%s)
task_id="incident-verify-$ts"
echo
echo "=== seed task_id=$task_id with simulate_failure=true ==="
seed=$(curl -sS -m 30 -X POST "$GATEWAY/intake/mock" -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$task_id\",\"request\":{\"type\":\"dev.test\",\"simulate_failure\":true,\"description\":\"incident flow verify\"}}" \
  || echo '{}')
echo "$seed" | head -c 600 || true
echo

echo
echo "=== wait for terminal failure incident to land in /incidents?task_id=$task_id ==="
incident_id=""
incident_status=""
for i in $(seq 1 60); do
  list=$(curl -sS -m 10 "$ORCH/incidents?task_id=$task_id" || echo '{}')
  incident_id=$(echo "$list" | sed -n 's/.*"incident_id": *"\([a-f0-9-]*\)".*/\1/p' | head -n1)
  incident_status=$(echo "$list" | sed -n 's/.*"status": *"\([a-z]*\)".*/\1/p' | head -n1)
  if [ -n "$incident_id" ]; then break; fi
  sleep 2
done
echo "incident_id=$incident_id incident_status=$incident_status"
if [ -z "$incident_id" ]; then
  echo "INCIDENT_FLOW_SMOKE: FAIL (no incident created for task $task_id)"
  exit 0
fi

echo
echo "=== verify workflow stage flipped to failed ==="
wf=$(curl -sS -m 10 "$ORCH/workflow/$task_id" || echo '{}')
echo "$wf" | head -c 600 || true
echo
if echo "$wf" | grep -q '"stage": *"failed"'; then
  echo "  workflow stage=failed: PRESENT"
else
  echo "  workflow stage=failed: MISSING"
fi

echo
echo "=== verify workflow.failed notification on stream.notifications ==="
notifs=$(curl -sS -m 10 "$GATEWAY/notifications?count=200" || echo '{}')
if echo "$notifs" | grep -q '"event_type": *"workflow.failed"' \
   && echo "$notifs" | grep -q "$task_id"; then
  echo "  workflow.failed notification: PRESENT"
else
  echo "  workflow.failed notification: MISSING"
fi

echo
echo "=== verify audit_logs has workflow_failed for $task_id ==="
audit=$(curl -sS -m 10 "$AUDIT/audit/events/$task_id" || echo '{}')
if echo "$audit" | grep -q '"decision_type": *"workflow_failed"'; then
  echo "  audit decision_type=workflow_failed: PRESENT"
else
  echo "  audit decision_type=workflow_failed: MISSING"
fi

echo
echo "=== ack incident $incident_id ==="
ack=$(curl -sS -m 10 -X POST "$ORCH/incidents/$incident_id/ack" || echo '{}')
echo "$ack" | head -c 400 || true
echo
if echo "$ack" | grep -q '"status": *"acknowledged"'; then
  echo "  incident ack: PASS"
else
  echo "  incident ack: FAIL"
fi

echo
echo "=== resolve incident $incident_id ==="
res=$(curl -sS -m 10 -X POST "$ORCH/incidents/$incident_id/resolve" || echo '{}')
echo "$res" | head -c 400 || true
echo
if echo "$res" | grep -q '"status": *"resolved"'; then
  echo "  incident resolve: PASS"
else
  echo "  incident resolve: FAIL"
fi

echo
checks=0
[ -n "$incident_id" ] && checks=$((checks+1))
echo "$wf" | grep -q '"stage": *"failed"' && checks=$((checks+1))
echo "$notifs" | grep -q '"event_type": *"workflow.failed"' && checks=$((checks+1))
echo "$audit" | grep -q '"decision_type": *"workflow_failed"' && checks=$((checks+1))
echo "$ack"  | grep -q '"status": *"acknowledged"' && checks=$((checks+1))
echo "$res"  | grep -q '"status": *"resolved"' && checks=$((checks+1))
echo "checks passed: $checks / 6"
if [ "$checks" -ge 6 ]; then
  echo "INCIDENT_FLOW_SMOKE: PASS"
else
  echo "INCIDENT_FLOW_SMOKE: CHECK"
fi

echo
echo "VERIFY_INCIDENT_FLOW_DONE"
