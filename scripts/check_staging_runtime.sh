#!/usr/bin/env bash
# Stage 25 staging health summary. Read-only.
#
# Prints docker compose ps + each service /health for the
# aiagents-staging project. Exits 0 when every required service is
# reachable; exits 1 otherwise. Never echoes a password.
#
# Run from the repository root.
set -uo pipefail

COMPOSE_FILE="${STAGING_COMPOSE_FILE:-infra/docker-compose/docker-compose.staging.yml}"
PROJECT="${STAGING_COMPOSE_PROJECT:-aiagents-staging}"
ENV_FILE="${STAGING_ENV_FILE:-infra/runtime/.env.staging.local}"
COMPOSE="docker compose -p ${PROJECT} -f ${COMPOSE_FILE}"

# Same env-file fallback as stop_staging_runtime.sh — compose parse
# needs POSTGRES_PASSWORD to exist, but `ps` doesn't actually use it.
if [ -f "$ENV_FILE" ]; then
  ENV_FLAG="--env-file $ENV_FILE"
else
  export POSTGRES_PASSWORD="check-noop"
  ENV_FLAG=""
fi

echo "### check_staging_runtime start: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== docker compose ps ==="
$COMPOSE $ENV_FLAG ps --format "table {{.Service}}\t{{.Status}}" 2>&1 | head -40

# Iterate over staging host ports. We hit /health on every service. Exit
# code stays 0 if at least the four critical surfaces respond.
declare -A PORTS=(
  [orchestrator]=18000
  [policy-engine]=18001
  [approval-engine]=18002
  [audit-service]=18003
  [communication-gateway]=18004
  [github-automation]=18005
  [audit-worker]=18006
  [discord-gateway]=18007
  [notification-worker]=18008
  [intake-agent]=18010
  [requirement-agent]=18011
  [development-agent]=18012
  [qa-agent]=18013
  [devops-agent]=18014
  [retry-scheduler]=18015
)

echo
echo "=== /health summary (staging ports) ==="
ok=0
total=0
critical_ok=1
for svc in orchestrator audit-service communication-gateway audit-worker; do
  port=${PORTS[$svc]:-}
  if [ -z "$port" ]; then continue; fi
  if curl -sS -m 5 "http://localhost:${port}/health" >/dev/null 2>&1; then
    echo "  ${svc}:${port}  OK"
  else
    echo "  ${svc}:${port}  FAIL"
    critical_ok=0
  fi
done

echo
for svc in policy-engine approval-engine github-automation discord-gateway \
           notification-worker intake-agent requirement-agent development-agent \
           qa-agent devops-agent retry-scheduler; do
  port=${PORTS[$svc]:-}
  if [ -z "$port" ]; then continue; fi
  total=$((total+1))
  if curl -sS -m 5 "http://localhost:${port}/health" >/dev/null 2>&1; then
    echo "  ${svc}:${port}  OK"
    ok=$((ok+1))
  else
    echo "  ${svc}:${port}  FAIL"
  fi
done

# Prometheus / Grafana / Tempo / Alertmanager
echo
for svc in prometheus:19090:/-/ready grafana:13000:/api/health tempo:13200:/ready alertmanager:19093:/-/healthy; do
  IFS=: read -r name port path <<< "$svc"
  if curl -sS -m 5 "http://localhost:${port}${path}" >/dev/null 2>&1; then
    echo "  ${name}:${port}  OK"
  else
    echo "  ${name}:${port}  CHECK"
  fi
done

echo
echo "  ok_count=$ok / $total (additional services)"
if [ "$critical_ok" = "1" ] && [ "$ok" -ge "$((total - 2))" ]; then
  echo "CHECK_STAGING_RUNTIME: PASS"
  exit 0
fi
echo "CHECK_STAGING_RUNTIME: CHECK"
exit 1
