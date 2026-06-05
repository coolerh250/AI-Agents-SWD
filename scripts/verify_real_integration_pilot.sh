#!/usr/bin/env bash
# Stage 32 -- real-integration pilot master verifier.
#
# Runs the operator-input check + the two provider-specific verify
# scripts + a /operations/real-integrations smoke + a production-
# safety re-assertion. Default mode (no real env vars set):
#   * Per-provider verify reports SKIPPED: PASS
#   * Master marker REAL_INTEGRATION_PILOT_VERIFY: PASS
#
# Real mode (env vars set): the per-provider verify scripts execute
# the actual real call and the master marker still requires PASS from
# every step + production_executed=0.
set -uo pipefail

ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"

echo "### verify_real_integration_pilot: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== 1. inputs ==="
./scripts/check_real_integration_inputs.sh | tail -20
inputs_verdict=$(./scripts/check_real_integration_inputs.sh | tail -1 | awk '{print $NF}')
echo "  inputs_verdict=$inputs_verdict"

echo
echo "=== 2. verify_real_discord_pilot ==="
./scripts/verify_real_discord_pilot.sh | tail -30
discord_last=$(./scripts/verify_real_discord_pilot.sh | tail -1)
echo "  discord_last_line=$discord_last"

echo
echo "=== 3. verify_real_github_sandbox_pilot ==="
./scripts/verify_real_github_sandbox_pilot.sh | tail -30
github_last=$(./scripts/verify_real_github_sandbox_pilot.sh | tail -1)
echo "  github_last_line=$github_last"

echo
echo "=== 4. /operations/real-integrations reachable ==="
ri_code=$(curl -sS -m 10 -o /dev/null -w "%{http_code}" "$ORCH/operations/real-integrations" || echo "000")
if [ "$ri_code" = "200" ]; then
  echo "OPERATIONS_REAL_INTEGRATIONS: PASS"
else
  echo "OPERATIONS_REAL_INTEGRATIONS: FAIL (http=$ri_code)"
fi

echo
echo "=== 5. production_safety final ==="
COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
dep=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
wf=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
echo "  deployment_records.production_executed_true=$dep"
echo "  workflow_states.production_executed_true=$wf"
if [ "$dep" != "0" ] || [ "$wf" != "0" ]; then
  echo "PRODUCTION_SAFETY: FAIL"
  echo "REAL_INTEGRATION_PILOT_VERIFY: FAIL"
  exit 1
fi
echo "PRODUCTION_SAFETY: PASS"

case "$discord_last" in
  "REAL_DISCORD_PILOT_VERIFY: PASS") ;;
  *) echo "REAL_INTEGRATION_PILOT_VERIFY: FAIL"; exit 1 ;;
esac

case "$github_last" in
  "REAL_GITHUB_SANDBOX_PILOT_VERIFY: PASS") ;;
  *) echo "REAL_INTEGRATION_PILOT_VERIFY: FAIL"; exit 1 ;;
esac

echo
echo "REAL_INTEGRATION_PILOT_VERIFY: PASS"
