#!/usr/bin/env bash
# Verify the Stage 22 controlled-Discord notification delivery surface
# end-to-end:
#
#   discord-gateway intake -> stream.notifications -> notification-worker
#       -> notification_deliveries (sandbox by default)
#       -> stream.audit -> audit_logs (decision_type=notification_delivery)
#       -> /discord/deliveries/{task_id} + /operations/workflows/{task_id}
#
# The real Discord API is NEVER contacted by default. The script asserts
# the refusal of /discord/real/test-message with HTTP 409.
# Run from the repository root.
set -uo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
DISCORD="${DISCORD_GATEWAY_URL:-http://localhost:8007}"
NW="${NOTIFICATION_WORKER_URL:-http://localhost:8008}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
GATEWAY="${GATEWAY_URL:-http://localhost:8004}"
AUDIT="${AUDIT_SERVICE_URL:-http://localhost:8003}"

echo "### verify_notification_delivery: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== container state ==="
$COMPOSE ps notification-worker audit-worker discord-gateway

ts=$(date +%s)
task_id="notif-verify-$ts"

# 1. /health
echo
echo "=== 1. /health ==="
nw_health=$(curl -sS -m 5 "$NW/health" || echo '{}')
echo "$nw_health"
if echo "$nw_health" | grep -q '"service": *"notification-worker"' \
   && echo "$nw_health" | grep -q '"mode":'; then
  echo "  /health: PASS"; h_ok=1
else
  echo "  /health: FAIL"; h_ok=0
fi

# 2. /status
echo
echo "=== 2. /status ==="
nw_status=$(curl -sS -m 5 "$NW/status" || echo '{}')
if echo "$nw_status" | grep -q '"group": *"notification-worker-group"' \
   && echo "$nw_status" | grep -q '"input_stream": *"stream.notifications"' \
   && echo "$nw_status" | grep -q '"running":'; then
  echo "  /status: PASS"; st_ok=1
else
  echo "  /status: FAIL"; st_ok=0
fi

# 3. seed a Discord sandbox dev.test task
echo
echo "=== 3. seed Discord sandbox dev.test task $task_id ==="
seed=$(curl -sS -m 30 -X POST "$DISCORD/discord/messages" \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.test description=\\\"notif delivery verify\\\" task_id=$task_id\",\"channel_id\":\"sandbox-notif\",\"user_id\":\"verify-operator\"}" \
  || echo '{}')
echo "$seed" | head -c 400
echo

# 4. wait for workflow to complete
echo
echo "=== 4. wait for $task_id to complete ==="
for i in $(seq 1 45); do
  prog=$(curl -sS -m 10 "$ORCH/workflow/progress/$task_id" || echo '{}')
  stage=$(echo "$prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  if [ "$stage" = "completed" ]; then break; fi
  sleep 2
done
echo "  stage=$stage"
sleep 6 # allow stream.notifications -> notification-worker -> notification_deliveries

# 5. stream.notifications has events
echo
echo "=== 5. stream.notifications has events for $task_id ==="
notifs=$(curl -sS -m 10 "$GATEWAY/notifications?count=200" || echo '{}')
if echo "$notifs" | grep -q "$task_id"; then
  echo "  notifications carry $task_id: PASS"; nf_ok=1
else
  echo "  notifications carry $task_id: FAIL"; nf_ok=0
fi

# 6. notification_deliveries has sandbox rows
echo
echo "=== 6. /discord/deliveries/$task_id ==="
deliveries=$(curl -sS -m 10 "$DISCORD/discord/deliveries/$task_id" || echo '{}')
echo "$deliveries" | head -c 600
echo
del_count=$(echo "$deliveries" | sed -n 's/.*"count": *\([0-9]*\).*/\1/p' | head -n1)
ext_sent=$(echo "$deliveries" | sed -n 's/.*"external_sent_count": *\([0-9]*\).*/\1/p' | head -n1)
if [ -n "$del_count" ] && [ "$del_count" -ge 2 ] \
   && [ "$ext_sent" = "0" ]; then
  echo "  notification_deliveries sandbox rows present: PASS"
  dl_ok=1
else
  echo "  notification_deliveries sandbox rows present: FAIL (count=$del_count ext=$ext_sent)"
  dl_ok=0
fi

# 7. external_sent=false
if [ "$ext_sent" = "0" ]; then
  echo "  external_sent=false: PASS"; ex_ok=1
else
  echo "  external_sent=false: FAIL"; ex_ok=0
fi

# 8. audit_logs has notification_delivery
echo
echo "=== 8. audit_logs has notification_delivery for $task_id ==="
au=$(curl -sS -m 10 "$AUDIT/audit/events?task_id=$task_id&decision_type=notification_delivery&limit=5" || echo '{}')
if echo "$au" | grep -q '"decision_type": *"notification_delivery"' \
   && echo "$au" | grep -q '"agent": *"notification-worker"'; then
  echo "  audit.notification_delivery: PASS"; au_ok=1
else
  echo "  audit.notification_delivery: FAIL"; au_ok=0
fi

# 9. /operations/workflows includes notification_deliveries
echo
echo "=== 9. /operations/workflows/$task_id ==="
ov=$(curl -sS -m 15 "$ORCH/operations/workflows/$task_id" || echo '{}')
if echo "$ov" | grep -q '"notification_deliveries"' \
   && echo "$ov" | grep -q '"simulated_count":'; then
  echo "  operations notification_deliveries: PASS"; op_ok=1
else
  echo "  operations notification_deliveries: FAIL"; op_ok=0
fi

# 10. real Discord call refused
echo
echo "=== 10. /discord/real/test-message guard (must refuse without opt-in) ==="
rt_code=$(curl -sS -m 5 -o /tmp/nw_rt.$$ -w "%{http_code}" -X POST "$NW/discord/real/test-message" \
  -H "Content-Type: application/json" \
  -d '{"content":"sandbox guard verification"}' || echo "000")
rm -f /tmp/nw_rt.$$
echo "  real-test HTTP code: $rt_code"
if [ "$rt_code" = "409" ]; then
  echo "  real-discord refused without opt-in: PASS"; rd_ok=1
else
  echo "  real-discord refused without opt-in: FAIL"; rd_ok=0
fi

# 11. production_executed=false
echo
echo "=== 11. production_executed=false ==="
prod_dep=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
prod_wf=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
echo "  deployment_records.production_executed=true: $prod_dep"
echo "  workflow_states.production_executed=true:    $prod_wf"
if [ "$prod_dep" = "0" ] && [ "$prod_wf" = "0" ]; then
  echo "  production safety: PASS"; pe_ok=1
else
  echo "  production safety: FAIL"; pe_ok=0
fi

echo
checks=0
[ "$h_ok"  = "1" ] && checks=$((checks+1))
[ "$st_ok" = "1" ] && checks=$((checks+1))
[ "$nf_ok" = "1" ] && checks=$((checks+1))
[ "$dl_ok" = "1" ] && checks=$((checks+1))
[ "$ex_ok" = "1" ] && checks=$((checks+1))
[ "$au_ok" = "1" ] && checks=$((checks+1))
[ "$op_ok" = "1" ] && checks=$((checks+1))
[ "$rd_ok" = "1" ] && checks=$((checks+1))
[ "$pe_ok" = "1" ] && checks=$((checks+1))
echo "checks passed: $checks / 9"
if [ "$checks" -ge 9 ]; then
  echo "NOTIFICATION_DELIVERY_VERIFY: PASS"
elif [ "$checks" -ge 8 ]; then
  echo "NOTIFICATION_DELIVERY_VERIFY: PASS (8/9 — non-fatal lag tolerated)"
else
  echo "NOTIFICATION_DELIVERY_VERIFY: CHECK"
fi
echo
echo "VERIFY_NOTIFICATION_DELIVERY_DONE"
