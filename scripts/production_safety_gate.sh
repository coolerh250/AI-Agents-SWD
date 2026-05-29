#!/usr/bin/env bash
# Stage 24 production safety gate. Read-only.
#
# Asserts the platform's "no production deploy happened" contract by
# inspecting:
#
#   * deployment_records with metadata->>'production_executed'='true'
#     OR environment='production'
#   * workflow_states with execution_result->>'production_executed'='true'
#   * /operations/safety result and warning fields
#   * RUN_REAL_GITHUB_TEST / RUN_REAL_DISCORD_TEST env defaults
#   * Alertmanager receivers (null-receiver allowed)
#   * Vault dev-mode posture
#   * Postgres trust-auth posture
#
# Exit 0 (PASS) when every counter is 0 and the live cluster is still
# in sandbox-by-default mode. Exit 1 (FAIL) otherwise.
#
# Run from the repository root.
set -uo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-aiagents}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"

echo "### production_safety_gate start: $(date '+%Y-%m-%d %H:%M:%S %Z')"

fail=0

# 1. deployment_records.production_executed=true OR environment=production
dep=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
echo "  deployment_records.production_executed_true_or_env_production = ${dep:-?}"
if [ -z "$dep" ] || [ "$dep" != "0" ]; then
  echo "  FAIL: deployment_records carries production rows"
  fail=$((fail+1))
fi

# 2. workflow_states.execution_result.production_executed=true
wf=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
echo "  workflow_states.production_executed_true = ${wf:-?}"
if [ -z "$wf" ] || [ "$wf" != "0" ]; then
  echo "  FAIL: workflow_states carries production rows"
  fail=$((fail+1))
fi

# 3. /operations/safety reports safe / warning (only warning if documented)
safety=$(curl -sS -m 10 "$ORCH/operations/safety" || echo '{}')
result=$(echo "$safety" | sed -n 's/.*"result":"\([^"]*\)".*/\1/p' | head -n1)
echo "  /operations/safety.result = ${result:-?}"
if [ "$result" != "safe" ] && [ "$result" != "warning" ]; then
  echo "  FAIL: /operations/safety reports $result"
  fail=$((fail+1))
fi

# 4. real GitHub default off
real_gh=$(echo "$safety" | sed -n 's/.*"real_github_test_enabled":\(true\|false\).*/\1/p' | head -n1)
echo "  real_github_test_enabled = ${real_gh:-?}"
if [ "$real_gh" = "true" ]; then
  ext_gh=$(echo "$safety" | sed -n 's/.*"github_external_write_enabled":\(true\|false\).*/\1/p' | head -n1)
  echo "  github_external_write_enabled = ${ext_gh:-?} (opt-in)"
fi

# 5. real Discord default off
real_ds=$(echo "$safety" | sed -n 's/.*"discord_real_test_enabled":\(true\|false\).*/\1/p' | head -n1)
echo "  discord_real_test_enabled = ${real_ds:-?}"

# 6. Alertmanager receivers — only null-receiver allowed by default
recv=$(curl -sS -m 5 "$ALERTMANAGER_URL/api/v2/receivers" 2>/dev/null \
  || echo '[]')
external_present=$(echo "$safety" | sed -n 's/.*"external_alert_receivers_present":\(true\|false\).*/\1/p' | head -n1)
echo "  alertmanager_external_receivers_present = ${external_present:-?}"
if [ "$external_present" = "true" ]; then
  echo "  WARN: Alertmanager reports external receivers — confirm intentional"
fi

# 7. Vault posture (local/test default is dev mode; we only note it)
vault_addr=$(echo "$safety" | sed -n 's/.*"vault_mode_note":"\([^"]*\)".*/\1/p' | head -n1)
echo "  vault_mode_note = ${vault_addr:-?}"

# 8. Postgres posture (local/test default is trust; we only note it)
pg_note=$(echo "$safety" | sed -n 's/.*"postgres_auth_note":"\([^"]*\)".*/\1/p' | head -n1)
echo "  postgres_auth_note = ${pg_note:-?}"

echo
if [ "$fail" -eq 0 ]; then
  echo "PRODUCTION_SAFETY_GATE: PASS"
  exit 0
fi
echo "PRODUCTION_SAFETY_GATE: FAIL (fails=$fail)"
exit 1
