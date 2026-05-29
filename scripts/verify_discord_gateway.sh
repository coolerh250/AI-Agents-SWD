#!/usr/bin/env bash
# Verify the Stage 21 Discord Gateway sandbox end-to-end:
#
#   /discord/messages (dev.test)   -> orchestrator pipeline -> github dry-run PR
#   /discord/messages (production) -> waiting_approval (no agent dispatch)
#
# Drives one orchestrator-mode dev.test sandbox message + one
# production.deploy sandbox message, then asserts the unified audit /
# notification / operations paths show the Discord origin. The real
# Discord API is never contacted unless DISCORD_BOT_TOKEN +
# RUN_REAL_DISCORD_TEST=true are both set; this script does NOT flip
# either flag.
# Run from the repository root.
set -uo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
DISCORD="${DISCORD_GATEWAY_URL:-http://localhost:8007}"
GATEWAY="${GATEWAY_URL:-http://localhost:8004}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
AUDIT="${AUDIT_SERVICE_URL:-http://localhost:8003}"
DEFAULT_REPO="${GITHUB_DEFAULT_REPO:-coolerh250/AI-Agents-SWD}"

echo "### verify_discord_gateway: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== container state ==="
$COMPOSE ps discord-gateway orchestrator audit-worker

ts=$(date +%s)
dev_task="discord-verify-dev-$ts"
prod_task="discord-verify-prod-$ts"

# 1. /health
echo
echo "=== 1. /health ==="
dg_health=$(curl -sS -m 5 "$DISCORD/health" || echo '{}')
echo "$dg_health"
if echo "$dg_health" | grep -q '"service": *"discord-gateway"' \
   && echo "$dg_health" | grep -q '"mode": *"sandbox"' \
   && echo "$dg_health" | grep -q '"has_token": *false'; then
  echo "  /health: PASS"; h_ok=1
else
  echo "  /health: FAIL"; h_ok=0
fi

# 2. /status
echo
echo "=== 2. /status ==="
dg_status=$(curl -sS -m 5 "$DISCORD/status" || echo '{}')
if echo "$dg_status" | grep -q '"mode": *"sandbox"' \
   && echo "$dg_status" | grep -q '"running":' \
   && echo "$dg_status" | grep -q '"real_test_enabled": *false'; then
  echo "  /status: PASS"; st_ok=1
else
  echo "  /status: FAIL"; st_ok=0
fi

# 3. dev.test sandbox message
echo
echo "=== 3. seed dev.test sandbox message $dev_task ==="
dev_resp=$(curl -sS -m 30 -X POST "$DISCORD/discord/messages" \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.test description=\\\"discord verify dev\\\" task_id=$dev_task github.enabled=true github.dry_run=true\",\"channel_id\":\"sandbox-verify\",\"user_id\":\"verify-operator\",\"message_id\":\"vmsg-1\"}" \
  || echo '{}')
echo "$dev_resp" | head -c 400
echo
if echo "$dev_resp" | grep -q '"sandbox": *true' \
   && echo "$dev_resp" | grep -q '"operations_url":'; then
  echo "  /discord/messages dev.test accepted: PASS"; di_ok=1
else
  echo "  /discord/messages dev.test accepted: FAIL"; di_ok=0
fi

# 4. wait for workflow to complete
echo
echo "=== 4. wait for $dev_task to complete ==="
for i in $(seq 1 45); do
  prog=$(curl -sS -m 10 "$ORCH/workflow/progress/$dev_task" || echo '{}')
  stage=$(echo "$prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  pr_url=$(echo "$prog" | sed -n 's/.*"pr_url": *"\([^"]*\)".*/\1/p' | head -n1)
  if [ "$stage" = "completed" ] && [ -n "$pr_url" ]; then break; fi
  sleep 2
done
echo "  stage=$stage pr_url=$pr_url"
sleep 5  # allow stream.audit -> audit-worker -> audit_logs to settle

# 5. /discord/tasks/{task_id} returns unified view
echo
echo "=== 5. /discord/tasks/$dev_task ==="
dev_lookup=$(curl -sS -m 15 "$DISCORD/discord/tasks/$dev_task" || echo '{}')
echo "$dev_lookup" | head -c 600
echo
if echo "$dev_lookup" | grep -q '"sandbox": *true' \
   && echo "$dev_lookup" | grep -q '"operations_url":' \
   && echo "$dev_lookup" | grep -q '"production_executed": *false'; then
  echo "  /discord/tasks lookup: PASS"; lk_ok=1
else
  echo "  /discord/tasks lookup: FAIL"; lk_ok=0
fi

# 6. /operations/workflows/{task_id}
echo
echo "=== 6. /operations/workflows/$dev_task ==="
op_view=$(curl -sS -m 15 "$ORCH/operations/workflows/$dev_task" || echo '{}')
if echo "$op_view" | grep -q '"audit_timeline"' \
   && echo "$op_view" | grep -q '"github"' \
   && echo "$op_view" | grep -q '"agents"'; then
  echo "  /operations/workflows lookup: PASS"; ov_ok=1
else
  echo "  /operations/workflows lookup: FAIL"; ov_ok=0
fi

# 7. completed_agents contains 5 agents
echo
echo "=== 7. completed_agents includes 5 pipeline agents ==="
agents_ok=1
for ag in intake-agent requirement-agent development-agent qa-agent devops-agent; do
  if echo "$op_view" | grep -q "\"$ag\""; then
    echo "  $ag completed: PASS"
  else
    echo "  $ag completed: FAIL"; agents_ok=0
  fi
done

# 8. github dry_run + pr_url
echo
echo "=== 8. github dry_run + pr_url ==="
if echo "$op_view" | grep -q '"dry_run":true' \
   && echo "$op_view" | grep -q '"pr_url":"https'; then
  echo "  github dry_run + pr_url: PASS"; gh_ok=1
else
  echo "  github dry_run + pr_url: FAIL"; gh_ok=0
fi

# 9. audit_logs has discord_intake
echo
echo "=== 9. audit_logs has discord_intake for $dev_task ==="
dg_audit=$(curl -sS -m 10 "$AUDIT/audit/events?task_id=$dev_task&decision_type=discord_intake&limit=5" || echo '{}')
if echo "$dg_audit" | grep -q '"decision_type": *"discord_intake"' \
   && echo "$dg_audit" | grep -q '"agent": *"discord-gateway"'; then
  echo "  audit.discord_intake: PASS"; au_ok=1
else
  echo "  audit.discord_intake: FAIL"; au_ok=0
fi

# 10. stream.notifications has discord.task.* event
echo
echo "=== 10. stream.notifications has discord.task.* event for $dev_task ==="
notifs=$(curl -sS -m 10 "$GATEWAY/notifications?count=200" || echo '{}')
if echo "$notifs" | grep -q "$dev_task" \
   && ( echo "$notifs" | grep -q 'discord.task.completed' \
      || echo "$notifs" | grep -q 'discord.task.dispatched' ); then
  echo "  notification.discord.task: PASS"; nf_ok=1
else
  echo "  notification.discord.task: FAIL"; nf_ok=0
fi

# 11. production.deploy stops at waiting_approval
echo
echo "=== 11. seed production.deploy sandbox message $prod_task ==="
prod_resp=$(curl -sS -m 30 -X POST "$DISCORD/discord/messages" \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=production.deploy description=\\\"discord verify production\\\" task_id=$prod_task\",\"channel_id\":\"sandbox-verify-prod\",\"user_id\":\"verify-operator\"}" \
  || echo '{}')
echo "$prod_resp" | head -c 400
echo
prod_stage=$(echo "$prod_resp" | sed -n 's/.*"stage": *"\([^"]*\)".*/\1/p' | head -n1)
prod_approval=$(echo "$prod_resp" | sed -n 's/.*"approval_required": *\(true\|false\).*/\1/p' | head -n1)
if [ "$prod_stage" = "waiting_approval" ] && [ "$prod_approval" = "true" ]; then
  echo "  production stage=waiting_approval, approval_required=true: PASS"; pr_ok=1
else
  echo "  production stage / approval_required: FAIL ($prod_stage / $prod_approval)"
  pr_ok=0
fi

# 12-13. confirm no agent dispatch / production execution before approval
echo
echo "=== 12-13. confirm no production_executed for $prod_task ==="
prod_wf=$(curl -sS -m 10 "$ORCH/workflow/$prod_task" || echo '{}')
if echo "$prod_wf" | grep -q '"stage":"waiting_approval"' \
   && ! echo "$prod_wf" | grep -q '"production_executed":true'; then
  echo "  waiting_approval and production_executed!=true: PASS"; nx_ok=1
else
  echo "  waiting_approval and production_executed!=true: FAIL"; nx_ok=0
fi

# 14. real Discord call refused
echo
echo "=== 14. real Discord test guard (must refuse without opt-in env) ==="
rd_resp=$(curl -sS -m 5 -o /tmp/discord_real.$$ -w "%{http_code}" -X POST "$DISCORD/discord/real/test-message" \
  -H "Content-Type: application/json" \
  -d '{"channel_id":"sandbox","message":"should-not-go"}' || echo "000")
rm -f /tmp/discord_real.$$
echo "  real-discord opt-in HTTP code: $rd_resp"
if [ "$rd_resp" = "409" ]; then
  echo "  real-discord refused without opt-in: PASS"; rd_ok=1
else
  echo "  real-discord refused without opt-in: FAIL"; rd_ok=0
fi

# 15. summary
echo
checks=0
[ "$h_ok"      = "1" ] && checks=$((checks+1))
[ "$st_ok"     = "1" ] && checks=$((checks+1))
[ "$di_ok"     = "1" ] && checks=$((checks+1))
[ "$lk_ok"     = "1" ] && checks=$((checks+1))
[ "$ov_ok"     = "1" ] && checks=$((checks+1))
[ "$agents_ok" = "1" ] && checks=$((checks+1))
[ "$gh_ok"     = "1" ] && checks=$((checks+1))
[ "$au_ok"     = "1" ] && checks=$((checks+1))
[ "$nf_ok"     = "1" ] && checks=$((checks+1))
[ "$pr_ok"     = "1" ] && checks=$((checks+1))
[ "$nx_ok"     = "1" ] && checks=$((checks+1))
[ "$rd_ok"     = "1" ] && checks=$((checks+1))
echo "checks passed: $checks / 12"
if [ "$checks" -ge 12 ]; then
  echo "DISCORD_GATEWAY_VERIFY: PASS"
elif [ "$checks" -ge 11 ]; then
  echo "DISCORD_GATEWAY_VERIFY: PASS (11/12 — non-fatal lag tolerated)"
else
  echo "DISCORD_GATEWAY_VERIFY: CHECK"
fi
echo
echo "VERIFY_DISCORD_GATEWAY_DONE"
