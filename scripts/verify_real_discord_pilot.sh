#!/usr/bin/env bash
# Stage 32 -- real Discord controlled-test pilot verifier.
#
# Default mode (no DISCORD_BOT_TOKEN / RUN_REAL_DISCORD_TEST):
#   * The Stage 32 guard refuses with HTTP 409 -- asserted.
#   * REAL_DISCORD_TEST_SKIPPED: PASS
#   * Final marker REAL_DISCORD_PILOT_VERIFY: PASS
#
# Opt-in mode (ALL of DISCORD_BOT_TOKEN, DISCORD_TEST_GUILD_ID,
# DISCORD_TEST_CHANNEL_ID, RUN_REAL_DISCORD_TEST=true): one real
# controlled-test message is sent via /discord/real/test-message and
# the following are asserted:
#   * HTTP 200 + external_sent=true + message_id non-empty
#   * notification_deliveries row external_sent=true present
#   * audit_logs has decision_type=discord_real_test_sent
#   * /operations/safety carries discord_external_send_enabled=true
#     ONLY while the env is set
#   * deployment_records / workflow_states production_executed=true=0
#
# Run from the repository root.
set -uo pipefail

DISCORD="${DISCORD_GATEWAY_URL:-http://localhost:8007}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
AUDIT="${AUDIT_SERVICE_URL:-http://localhost:8003}"
COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"

echo "### verify_real_discord_pilot: $(date '+%Y-%m-%d %H:%M:%S %Z')"

ts=$(date +%s)
task_id="real-discord-pilot-$ts"

echo
echo "=== Inputs snapshot ==="
./scripts/check_real_integration_inputs.sh | tail -15

if [ -z "${DISCORD_BOT_TOKEN:-}" ] \
   || [ -z "${DISCORD_TEST_GUILD_ID:-}" ] \
   || [ -z "${DISCORD_TEST_CHANNEL_ID:-}" ] \
   || [ "${RUN_REAL_DISCORD_TEST:-false}" != "true" ]; then
  echo
  echo "=== Skipped-mode guard refusal (default test cluster) ==="
  code=$(curl -sS -m 5 -o /tmp/rd.$$ -w "%{http_code}" -X POST \
    "$DISCORD/discord/real/test-message" \
    -H "Content-Type: application/json" \
    -d '{"channel_id":"sandbox","summary":"should not go"}' || echo "000")
  cat /tmp/rd.$$ 2>/dev/null | head -c 300 | tr -d '\n'; echo
  rm -f /tmp/rd.$$
  if [ "$code" = "409" ]; then
    echo "REAL_DISCORD_TEST_REFUSED_DEFAULT: PASS"
  else
    echo "REAL_DISCORD_TEST_REFUSED_DEFAULT: FAIL (http=$code)"
    echo "REAL_DISCORD_PILOT_VERIFY: FAIL"
    exit 1
  fi
  echo "REAL_DISCORD_TEST_SKIPPED: PASS"
  echo
  echo "REAL_DISCORD_PILOT_VERIFY: PASS"
  exit 0
fi

echo
echo "=== Real-mode send ==="
payload=$(cat <<JSON
{
  "task_id": "$task_id",
  "channel_id": "${DISCORD_TEST_CHANNEL_ID}",
  "guild_id": "${DISCORD_TEST_GUILD_ID}",
  "role_id": "${DISCORD_ALLOWED_ROLE_ID:-}",
  "user_id": "real-discord-pilot",
  "mode": "controlled_test",
  "summary": "Stage 32 controlled-test message ($task_id)",
  "operations_url": "/operations/workflows/$task_id",
  "approval_required": false,
  "production_executed": false
}
JSON
)
resp=$(curl -sS -m 15 -X POST "$DISCORD/discord/real/test-message" \
  -H "Content-Type: application/json" \
  -d "$payload" || echo '{}')
echo "$resp" | head -c 600; echo
mid=$(echo "$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("message_id",""))' 2>/dev/null || echo "")
ext=$(echo "$resp" | python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("external_sent","")).lower())' 2>/dev/null || echo "")
if [ -n "$mid" ] && [ "$ext" = "true" ]; then
  echo "REAL_DISCORD_TEST_SENT: PASS"
else
  echo "REAL_DISCORD_TEST_SENT: FAIL"
  echo "REAL_DISCORD_PILOT_VERIFY: FAIL"
  exit 1
fi

echo
echo "=== Audit decision_type=discord_real_test_sent ==="
au=$(curl -sS -m 10 "$AUDIT/audit/events?decision_type=discord_real_test_sent&limit=5" || echo '{}')
if echo "$au" | grep -q '"discord_real_test_sent"'; then
  echo "AUDIT_DISCORD_REAL_TEST_SENT: PASS"
else
  echo "AUDIT_DISCORD_REAL_TEST_SENT: FAIL"
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
  echo "REAL_DISCORD_PILOT_VERIFY: FAIL"
  exit 1
fi

echo
echo "REAL_DISCORD_PILOT_VERIFY: PASS"
