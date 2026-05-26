#!/usr/bin/env bash
# Verify the Alertmanager + Prometheus alert pipeline. Local/test only —
# no real off-host notifier is contacted. Run from the repository root.
#
# Pre-condition: docker compose up has been run and the
# prometheus / alertmanager containers are reachable on 127.0.0.1.
set -uo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"

echo "### verify_alerting: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== alertmanager container state ==="
$COMPOSE ps alertmanager

echo
echo "=== alertmanager /-/healthy ==="
am_health=$(curl -sS -o /dev/null -w '%{http_code}' -m 5 "$ALERTMANAGER_URL/-/healthy" || echo 000)
echo "  HTTP $am_health"
if [ "$am_health" = "200" ]; then
  echo "ALERTMANAGER_HEALTHY: PASS"
else
  echo "ALERTMANAGER_HEALTHY: FAIL"
fi

echo
echo "=== alertmanager /api/v2/status ==="
am_status=$(curl -sS -m 5 "$ALERTMANAGER_URL/api/v2/status" || echo '{}')
echo "$am_status" | head -c 600 || true
echo
if echo "$am_status" | grep -q '"versionInfo"'; then
  echo "ALERTMANAGER_STATUS_API: PASS"
else
  echo "ALERTMANAGER_STATUS_API: CHECK"
fi

echo
echo "=== prometheus /api/v1/rules (AIAgents groups loaded) ==="
rules=$(curl -sS -m 10 "$PROMETHEUS_URL/api/v1/rules" || echo '{}')
echo "$rules" | head -c 600 || true
echo
group_count=$(echo "$rules" | grep -o '"name":"aiagents\.[a-z]*"' | sort -u | wc -l)
echo "aiagents.* rule groups found: $group_count"
if [ "${group_count:-0}" -ge 4 ]; then
  echo "PROMETHEUS_RULES_LOADED: PASS"
else
  echo "PROMETHEUS_RULES_LOADED: CHECK"
fi

# Each required alert must appear by name in /api/v1/rules
echo
echo "=== required alert names present ==="
missing=()
for name in \
  AIWorkflowFailuresHigh \
  AIWorkflowLatencyP95High \
  AIAgentExecutionFailuresHigh \
  AIDeadletterIncreasing \
  AIRetrySpike \
  AIServiceDown \
  AIPrometheusTargetDown \
  AIApprovalPendingTooLong
do
  if echo "$rules" | grep -q "\"name\":\"$name\""; then
    echo "  $name: PRESENT"
  else
    echo "  $name: MISSING"
    missing+=("$name")
  fi
done
if [ "${#missing[@]}" -eq 0 ]; then
  echo "PROMETHEUS_RULES_NAMES: PASS"
else
  echo "PROMETHEUS_RULES_NAMES: CHECK (missing: ${missing[*]})"
fi

echo
echo "=== prometheus /api/v1/alerts (active alerts) ==="
alerts=$(curl -sS -m 10 "$PROMETHEUS_URL/api/v1/alerts" || echo '{}')
echo "$alerts" | head -c 600 || true
echo
if echo "$alerts" | grep -q '"status":"success"'; then
  echo "PROMETHEUS_ALERTS_API: PASS"
else
  echo "PROMETHEUS_ALERTS_API: CHECK"
fi

echo
echo "=== prometheus targets (every job up) ==="
targets=$(curl -sS -m 10 "$PROMETHEUS_URL/api/v1/targets" || echo '{}')
up_count=$(echo "$targets" | grep -o '"health":"up"' | wc -l)
down_count=$(echo "$targets" | grep -o '"health":"down"' | wc -l)
echo "targets up=$up_count down=$down_count"
if [ "${up_count:-0}" -ge 11 ] && [ "${down_count:-0}" -eq 0 ]; then
  echo "PROMETHEUS_TARGETS_ALL_UP: PASS"
else
  echo "PROMETHEUS_TARGETS_ALL_UP: CHECK"
fi

echo
echo "=== alertmanager /api/v2/receivers (no real off-host notifier) ==="
recv=$(curl -sS -m 5 "$ALERTMANAGER_URL/api/v2/receivers" || echo '[]')
echo "$recv" | head -c 400 || true
echo
if echo "$recv" | grep -q 'slack\|discord\|telegram\|pagerduty\|opsgenie\|webhook'; then
  echo "ALERTMANAGER_OFFHOST_RECEIVER: FAIL (an external receiver is configured!)"
else
  echo "ALERTMANAGER_OFFHOST_RECEIVER: PASS (null receiver only)"
fi

echo
echo "VERIFY_ALERTING_DONE"
