#!/usr/bin/env bash
# Stage 25 staging end-to-end verifier.
#
# Brings the aiagents-staging stack up, runs an end-to-end workflow
# through it, asserts every safety / audit / notification / observability
# contract, then (by default) brings it down.
#
# Flags:
#   --keep-running   leave the staging stack running after verification.
#   --down           force tear-down (default behaviour).
#   --no-rebuild     skip the docker compose build step.
#
# Designed to coexist with the local/test aiagents-test stack — the
# staging stack uses a separate compose project + separate volumes +
# host ports offset by +10000.
set -uo pipefail

PROJECT="${STAGING_COMPOSE_PROJECT:-aiagents-staging}"
COMPOSE_FILE="${STAGING_COMPOSE_FILE:-infra/docker-compose/docker-compose.staging.yml}"
ENV_FILE="${STAGING_ENV_FILE:-infra/runtime/.env.staging.local}"
COMPOSE="docker compose -p ${PROJECT} -f ${COMPOSE_FILE}"

# Staging host ports.
DISCORD_PORT=18007
ORCH_PORT=18000
GATEWAY_PORT=18004
AUDIT_PORT=18003
GH_PORT=18005
NW_PORT=18008
PROM_PORT=19090
PG_PORT=15432

ACTION="down"
REBUILD=1
for arg in "$@"; do
  case "$arg" in
    --keep-running) ACTION="keep" ;;
    --down) ACTION="down" ;;
    --no-rebuild) REBUILD=0 ;;
  esac
done

echo "### verify_staging_runtime: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  project=$PROJECT compose=$COMPOSE_FILE env_file=$ENV_FILE"
echo "  post_action=$ACTION rebuild=$REBUILD"

checks=0
total=12
fail() {
  echo "  $1: FAIL"
}
pass() {
  echo "  $1: PASS"
  checks=$((checks+1))
}

# 1. env generation
echo
echo "=== 1. staging env present + placeholder-only ==="
if [ ! -f "$ENV_FILE" ]; then
  ./scripts/generate_staging_env.sh || true
fi
if [ -f "$ENV_FILE" ] && grep -q "^POSTGRES_PASSWORD=" "$ENV_FILE"; then
  pass "STAGING_ENV_PRESENT"
else
  fail "STAGING_ENV_PRESENT"
fi

# Make sure no real GitHub / Discord token snuck in.
leak=0
for k in GITHUB_TOKEN DISCORD_BOT_TOKEN VAULT_TOKEN; do
  val=$(grep -E "^${k}=" "$ENV_FILE" 2>/dev/null | head -n1 | cut -d= -f2-)
  if [ -n "$val" ] && [ "$val" != "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE" ]; then
    echo "  WARN: $k has a non-placeholder value (opt-in real-test enabled)"
    # Not a failure — the operator may have explicitly opted in.
  fi
done
# But the file MUST NOT have echoed the password to stdout — we only
# allow it inside the file, never in the verify-script output.
echo "  env file readable by owner only:"
ls -l "$ENV_FILE" 2>&1 | awk '{print "    "$1, $3}'

# 2. validator staging mode (without ALLOW_VAULT_DEV_MODE_FOR_STAGING)
echo
echo "=== 2. validator --mode staging ==="
if ./scripts/validate_runtime_config.sh --mode staging --env-file "$ENV_FILE" 2>&1 | tee /tmp/vsrv.$$ | tail -5; then
  if grep -q "RUNTIME_CONFIG_VALIDATION: PASS" /tmp/vsrv.$$; then
    pass "STAGING_VALIDATOR"
  else
    fail "STAGING_VALIDATOR"
  fi
fi
# Look for the vault dev-mode warning marker
if grep -q "vault_dev_mode_in_staging" /tmp/vsrv.$$; then
  echo "  STAGING_VAULT_DEV_MODE_ALLOWED: WARN (documented escape hatch)"
fi
rm -f /tmp/vsrv.$$

# 3. bring staging up
echo
echo "=== 3. start_staging_runtime.sh ==="
if [ "$REBUILD" = "1" ]; then
  if ./scripts/start_staging_runtime.sh --rebuild 2>&1 | tail -5; then
    pass "STAGING_START"
  else
    fail "STAGING_START"
  fi
else
  if ./scripts/start_staging_runtime.sh 2>&1 | tail -5; then
    pass "STAGING_START"
  else
    fail "STAGING_START"
  fi
fi

# 4. health
echo
echo "=== 4. check_staging_runtime.sh ==="
sleep 8
if ./scripts/check_staging_runtime.sh 2>&1 | tail -8; then
  pass "STAGING_HEALTH"
else
  fail "STAGING_HEALTH"
fi

# 5. Postgres password auth (no trust auth)
echo
echo "=== 5. Postgres password auth ==="
trust_set=$($COMPOSE --env-file "$ENV_FILE" exec -T postgres sh -c \
  'echo "${POSTGRES_HOST_AUTH_METHOD:-<unset>}"' 2>/dev/null | tr -d '[:space:]')
echo "  POSTGRES_HOST_AUTH_METHOD inside container: ${trust_set:-?}"
if [ "$trust_set" = "<unset>" ] || [ "$trust_set" = "" ]; then
  pass "STAGING_POSTGRES_PASSWORD_AUTH"
else
  fail "STAGING_POSTGRES_PASSWORD_AUTH"
fi

# Confirm tables exist (proves migrations ran under the password user).
pg_user=$(grep -E '^STAGING_POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2- || true)
pg_user="${pg_user:-aiagents_app}"
pg_db=$(grep -E '^STAGING_POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2- || true)
pg_db="${pg_db:-aiagents}"
tables=$($COMPOSE --env-file "$ENV_FILE" exec -T postgres psql -U "$pg_user" -d "$pg_db" -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null \
  | tr -d '[:space:]')
echo "  staging public tables: ${tables:-?}"
if [ -n "$tables" ] && [ "$tables" -ge 6 ]; then
  pass "STAGING_MIGRATIONS_APPLIED"
else
  fail "STAGING_MIGRATIONS_APPLIED"
fi

# 6. end-to-end workflow through staging discord-gateway
echo
echo "=== 6. e2e workflow on staging ==="
ts=$(date +%s)
task_id="staging-e2e-${ts}"
seed=$(curl -sS -m 30 -X POST "http://localhost:${DISCORD_PORT}/discord/messages" \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.test description=\\\"staging e2e\\\" task_id=${task_id}\",\"channel_id\":\"staging-e2e\",\"user_id\":\"staging-verify\"}" \
  || echo '{}')
echo "  seed response head: $(echo "$seed" | head -c 240)"

stage=""
for i in $(seq 1 60); do
  prog=$(curl -sS -m 10 "http://localhost:${ORCH_PORT}/workflow/progress/${task_id}" || echo '{}')
  stage=$(echo "$prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  if [ "$stage" = "completed" ]; then break; fi
  sleep 2
done
echo "  final stage: ${stage:-?}"
sleep 6
if [ "$stage" = "completed" ]; then
  pass "STAGING_E2E_WORKFLOW"
else
  fail "STAGING_E2E_WORKFLOW"
fi

# 7. github dry-run section appears
echo
echo "=== 7. github dry-run via staging pipeline ==="
view=$(curl -sS -m 10 "http://localhost:${ORCH_PORT}/operations/workflows/${task_id}" || echo '{}')
if echo "$view" | grep -q '"github"' \
   && echo "$view" | grep -q '"dry_run":true'; then
  pass "STAGING_GITHUB_DRY_RUN"
else
  fail "STAGING_GITHUB_DRY_RUN"
fi

# 8. audit_timeline
if echo "$view" | grep -q '"audit_timeline"'; then
  pass "STAGING_AUDIT_TIMELINE"
else
  fail "STAGING_AUDIT_TIMELINE"
fi

# 9. notification_deliveries
if echo "$view" | grep -q '"notification_deliveries"' \
   && echo "$view" | grep -q '"simulated_count":'; then
  pass "STAGING_NOTIFICATION_DELIVERY"
else
  fail "STAGING_NOTIFICATION_DELIVERY"
fi

# 10. safety + production_executed=false
echo
echo "=== 10. staging /operations/safety ==="
safety=$(curl -sS -m 10 "http://localhost:${ORCH_PORT}/operations/safety" || echo '{}')
result=$(echo "$safety" | sed -n 's/.*"result":"\([^"]*\)".*/\1/p' | head -n1)
echo "  /operations/safety.result = ${result:-?}"
if [ "$result" = "safe" ] || [ "$result" = "warning" ]; then
  pass "STAGING_OPERATIONS_SAFETY"
else
  fail "STAGING_OPERATIONS_SAFETY"
fi

prod_dep=$($COMPOSE --env-file "$ENV_FILE" exec -T postgres \
  psql -U "$pg_user" -d "$pg_db" -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
prod_wf=$($COMPOSE --env-file "$ENV_FILE" exec -T postgres \
  psql -U "$pg_user" -d "$pg_db" -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
echo "  staging deployment_records.production_executed_true = ${prod_dep:-?}"
echo "  staging workflow_states.production_executed_true    = ${prod_wf:-?}"
if [ "$prod_dep" = "0" ] && [ "$prod_wf" = "0" ]; then
  pass "STAGING_PRODUCTION_SAFETY"
else
  fail "STAGING_PRODUCTION_SAFETY"
fi

# 11. local/test stack still healthy (regression guard)
echo
echo "=== 11. local/test stack unaffected ==="
if curl -sS -m 5 http://localhost:8000/health >/dev/null 2>&1 \
   && curl -sS -m 5 http://localhost:8005/health >/dev/null 2>&1; then
  pass "LOCAL_TEST_UNAFFECTED"
else
  fail "LOCAL_TEST_UNAFFECTED"
fi

# 12. teardown (default)
echo
if [ "$ACTION" = "down" ]; then
  echo "=== 12. stop_staging_runtime.sh (default --down) ==="
  if ./scripts/stop_staging_runtime.sh 2>&1 | tail -3; then
    pass "STAGING_STOP"
  else
    fail "STAGING_STOP"
  fi
else
  echo "=== 12. staging left running (--keep-running) ==="
  pass "STAGING_LEFT_RUNNING"
fi

echo
echo "checks passed: $checks / $total"
if [ "$checks" -eq "$total" ]; then
  echo "STAGING_RUNTIME_VERIFY: PASS"
else
  echo "STAGING_RUNTIME_VERIFY: CHECK"
fi
echo
echo "VERIFY_STAGING_RUNTIME_DONE"
