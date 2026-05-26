#!/usr/bin/env bash
# Full platform observability + operational-readiness verification.
#
# Runs the per-area checks (Docker, health, metrics, Prometheus, Grafana,
# Tempo, Alertmanager, workflow + trace, incident, SLO, safety) and then
# reuses the existing verify_*.sh scripts as sub-steps so a single command
# is enough to declare the platform observably healthy on 10.0.1.31.
#
# Local/test only — contacts no cloud SaaS, sends no real notifications,
# performs no production deploy. Run from the repository root.
set -uo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
GATEWAY="${GATEWAY_URL:-http://localhost:8004}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
AUDIT="${AUDIT_SERVICE_URL:-http://localhost:8003}"
POLICY="${POLICY_ENGINE_URL:-http://localhost:8001}"
APPROVAL="${APPROVAL_ENGINE_URL:-http://localhost:8002}"
PROM="${PROMETHEUS_URL:-http://localhost:9090}"
GRAFANA="${GRAFANA_URL:-http://localhost:3000}"
TEMPO="${TEMPO_URL:-http://localhost:3200}"
ALERTMANAGER="${ALERTMANAGER_URL:-http://localhost:9093}"

PASS=0
FAIL=0
RESULTS=()

record() {
  local name="$1" status="$2" detail="${3:-}"
  if [ "$status" = "PASS" ]; then
    PASS=$((PASS+1))
    echo "  $name: PASS${detail:+  ($detail)}"
  else
    FAIL=$((FAIL+1))
    echo "  $name: FAIL${detail:+  ($detail)}"
  fi
  RESULTS+=("$name $status")
}

echo "### verify_platform_observability: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "============================================================"
echo "1. Docker / Runtime"
echo "============================================================"
$COMPOSE ps

services_required=(
  postgres redis vault
  policy-engine approval-engine audit-service
  orchestrator communication-gateway
  intake-agent requirement-agent development-agent qa-agent devops-agent
  retry-scheduler
  prometheus grafana tempo alertmanager
)
ps_text=$($COMPOSE ps --format '{{.Service}} {{.State}} {{.Status}}' 2>/dev/null || $COMPOSE ps)
for svc in "${services_required[@]}"; do
  line=$(echo "$ps_text" | grep -E "(^| )${svc}( |$)" | head -n1)
  if echo "$line" | grep -qiE 'running|up'; then
    record "container.${svc}" PASS "$line"
  else
    record "container.${svc}" FAIL "$line"
  fi
done

echo
echo "============================================================"
echo "2. Health endpoints"
echo "============================================================"
health_targets=(
  "orchestrator:$ORCH/health"
  "communication-gateway:$GATEWAY/health"
  "policy-engine:$POLICY/health"
  "approval-engine:$APPROVAL/health"
  "audit-service:$AUDIT/health"
  "retry-scheduler:http://localhost:8015/health"
  "intake-agent:http://localhost:8010/health"
  "requirement-agent:http://localhost:8011/health"
  "development-agent:http://localhost:8012/health"
  "qa-agent:http://localhost:8013/health"
  "devops-agent:http://localhost:8014/health"
)
for entry in "${health_targets[@]}"; do
  name="${entry%%:*}"
  url="${entry#*:}"
  code=$(curl -sS -o /dev/null -w '%{http_code}' -m 8 "$url" || echo 000)
  if [ "$code" = "200" ]; then
    record "health.${name}" PASS "HTTP $code"
  else
    record "health.${name}" FAIL "HTTP $code at $url"
  fi
done

echo
echo "============================================================"
echo "3. Metrics endpoints"
echo "============================================================"
orch_metrics=$(curl -sS -m 10 "$ORCH/metrics" || echo '')
if echo "$orch_metrics" | grep -q '^workflow_total'; then
  record "metrics.orchestrator.workflow_total" PASS
else
  record "metrics.orchestrator.workflow_total" FAIL
fi

agent_hit=0
for entry in intake-agent:8010 requirement-agent:8011 development-agent:8012 qa-agent:8013 devops-agent:8014; do
  name="${entry%%:*}"
  port="${entry##*:}"
  body=$(curl -sS -m 10 "http://localhost:${port}/metrics" || echo '')
  if echo "$body" | grep -q '^agent_execution_total'; then
    agent_hit=$((agent_hit+1))
  fi
done
if [ "$agent_hit" -ge 1 ]; then
  record "metrics.agents.agent_execution_total" PASS "$agent_hit/5 agents emit metric"
else
  record "metrics.agents.agent_execution_total" FAIL "0/5 agents emit agent_execution_total"
fi

retry_metrics=$(curl -sS -m 10 "http://localhost:8015/metrics" || echo '')
if echo "$retry_metrics" | grep -qE '^(retry_total|deadletter_total)'; then
  record "metrics.retry-scheduler.retry_or_deadletter" PASS
else
  record "metrics.retry-scheduler.retry_or_deadletter" FAIL
fi

echo
echo "============================================================"
echo "4. Prometheus"
echo "============================================================"
if curl -sS -m 10 "$PROM/-/healthy" >/dev/null 2>&1; then
  record "prometheus.healthy" PASS
else
  record "prometheus.healthy" FAIL
fi

prom_targets=$(curl -sS -m 10 "$PROM/api/v1/targets" || echo '{}')
up_count=$(echo "$prom_targets" | grep -o '"health":"up"' | wc -l)
down_count=$(echo "$prom_targets" | grep -o '"health":"down"' | wc -l)
if [ "${up_count:-0}" -ge 1 ] && [ "${down_count:-0}" -eq 0 ]; then
  record "prometheus.targets.all_up" PASS "up=$up_count down=$down_count"
else
  record "prometheus.targets.all_up" FAIL "up=$up_count down=$down_count"
fi

prom_rules=$(curl -sS -m 10 "$PROM/api/v1/rules" || echo '{}')
group_count=$(echo "$prom_rules" | grep -o '"name":"aiagents\.[a-z]*"' | sort -u | wc -l)
if [ "${group_count:-0}" -ge 4 ]; then
  record "prometheus.rules.aiagents_groups" PASS "$group_count groups"
else
  record "prometheus.rules.aiagents_groups" FAIL "$group_count groups (expected ≥4)"
fi

prom_alerts=$(curl -sS -m 10 "$PROM/api/v1/alerts" || echo '{}')
if echo "$prom_alerts" | grep -q '"status":"success"'; then
  record "prometheus.alerts.api_success" PASS
else
  record "prometheus.alerts.api_success" FAIL
fi

echo
echo "============================================================"
echo "5. Grafana"
echo "============================================================"
gh=$(curl -sS -m 10 "$GRAFANA/api/health" || echo '{}')
if echo "$gh" | grep -qE '"database"[[:space:]]*:[[:space:]]*"ok"'; then
  record "grafana.api.health" PASS
else
  record "grafana.api.health" FAIL
fi

ds=$(curl -sS -m 10 "$GRAFANA/api/datasources" || echo '[]')
for ds_type in prometheus tempo alertmanager; do
  if echo "$ds" | grep -q "\"type\":\"${ds_type}\""; then
    record "grafana.datasource.${ds_type}" PASS
  else
    record "grafana.datasource.${ds_type}" FAIL
  fi
done

dashboards=$(curl -sS -m 10 "$GRAFANA/api/search?query=AI%20Agents" || echo '[]')
if echo "$dashboards" | grep -q '"title":"AI Agents SWD Platform"'; then
  record "grafana.dashboard.aiagents" PASS
else
  record "grafana.dashboard.aiagents" FAIL
fi

echo
echo "============================================================"
echo "6. Tempo"
echo "============================================================"
tready=$(curl -sS -m 10 "$TEMPO/ready" || echo '')
if [ "$tready" = "ready" ] || echo "$tready" | grep -qi ready; then
  record "tempo.ready" PASS
else
  record "tempo.ready" FAIL
fi

if curl -sS -m 5 "$TEMPO/status/version" >/dev/null 2>&1; then
  record "tempo.status.version" PASS
else
  record "tempo.status.version" FAIL
fi

echo
echo "============================================================"
echo "7. Alertmanager"
echo "============================================================"
am_health=$(curl -sS -o /dev/null -w '%{http_code}' -m 5 "$ALERTMANAGER/-/healthy" || echo 000)
if [ "$am_health" = "200" ]; then
  record "alertmanager.healthy" PASS "HTTP $am_health"
else
  record "alertmanager.healthy" FAIL "HTTP $am_health"
fi

am_status=$(curl -sS -m 5 "$ALERTMANAGER/api/v2/status" || echo '{}')
if echo "$am_status" | grep -q '"versionInfo"'; then
  record "alertmanager.status.api" PASS
else
  record "alertmanager.status.api" FAIL
fi

recv=$(curl -sS -m 5 "$ALERTMANAGER/api/v2/receivers" || echo '[]')
if echo "$recv" | grep -qE 'slack|discord|telegram|pagerduty|opsgenie|webhook|email'; then
  record "alertmanager.receivers.no_offhost" FAIL "external receiver detected"
else
  record "alertmanager.receivers.no_offhost" PASS "null receiver only"
fi

echo
echo "============================================================"
echo "8. Workflow end-to-end"
echo "============================================================"
ts=$(date +%s)
wf_task="observability-verify-$ts"
seed=$(curl -sS -m 30 -X POST "$GATEWAY/intake/mock" -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$wf_task\",\"request\":{\"type\":\"dev.test\",\"description\":\"platform observability verify\"}}" \
  || echo '{}')
echo "  seed response: $(echo "$seed" | head -c 200)"

wf_trace=""
wf_stage=""
for i in $(seq 1 40); do
  prog=$(curl -sS -m 10 "$ORCH/workflow/progress/$wf_task" || echo '{}')
  wf_stage=$(echo "$prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  if [ -z "$wf_trace" ]; then
    wf_trace=$(echo "$prog" | sed -n 's/.*"trace_id": *"\([a-f0-9]*\)".*/\1/p' | head -n1)
  fi
  if [ "$wf_stage" = "completed" ]; then break; fi
  sleep 2
done

if [ "$wf_stage" = "completed" ]; then
  record "workflow.reaches_completed" PASS "task=$wf_task"
else
  record "workflow.reaches_completed" FAIL "stage=$wf_stage task=$wf_task"
fi

progress=$(curl -sS -m 10 "$ORCH/workflow/progress/$wf_task" || echo '{}')
if echo "$progress" | grep -q '"completed_agents"'; then
  record "workflow.progress.completed_agents" PASS
else
  record "workflow.progress.completed_agents" FAIL
fi
for agent in intake-agent requirement-agent development-agent qa-agent devops-agent; do
  if echo "$progress" | grep -q "\"$agent\""; then
    record "workflow.progress.$agent" PASS
  else
    record "workflow.progress.$agent" FAIL
  fi
done

timeline=$(curl -sS -m 10 "$ORCH/workflow/timeline/$wf_task" || echo '{}')
if echo "$timeline" | grep -q '"agent_timeline"' && echo "$timeline" | grep -q '"traces"'; then
  record "workflow.timeline.api" PASS
else
  record "workflow.timeline.api" FAIL
fi

echo
echo "============================================================"
echo "9. Trace propagation (trace_id reaches Tempo with all 7 services)"
echo "============================================================"
if [ -n "$wf_trace" ]; then
  sleep 6
  tbody=$(curl -sS -m 15 "$TEMPO/api/traces/$wf_trace" || echo '')
  echo "  trace_id=$wf_trace; body head:"
  echo "$tbody" | head -c 400 || true
  echo
  if [ -z "$tbody" ] || echo "$tbody" | grep -qi 'trace not found'; then
    record "trace.tempo.lookup" FAIL "trace $wf_trace not found"
  else
    record "trace.tempo.lookup" PASS
    for svc in communication-gateway orchestrator intake-agent requirement-agent development-agent qa-agent devops-agent; do
      if echo "$tbody" | grep -q "\"$svc\""; then
        record "trace.span.$svc" PASS
      else
        record "trace.span.$svc" FAIL
      fi
    done
  fi
else
  record "trace.tempo.lookup" FAIL "no trace_id from workflow progress"
fi

echo
echo "============================================================"
echo "10. Incident lifecycle (terminal failure -> incident -> ack -> resolve)"
echo "============================================================"
inc_task="observability-incident-$ts"
curl -sS -m 30 -X POST "$GATEWAY/intake/mock" -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$inc_task\",\"request\":{\"type\":\"dev.test\",\"simulate_failure\":true}}" \
  >/dev/null 2>&1 || true

inc_id=""
inc_stage=""
for i in $(seq 1 60); do
  ilist=$(curl -sS -m 10 "$ORCH/incidents?task_id=$inc_task" || echo '{}')
  inc_id=$(echo "$ilist" | sed -n 's/.*"incident_id": *"\([a-f0-9-]*\)".*/\1/p' | head -n1)
  iwf=$(curl -sS -m 10 "$ORCH/workflow/$inc_task" || echo '{}')
  inc_stage=$(echo "$iwf" | sed -n 's/.*"stage": *"\([^"]*\)".*/\1/p' | head -n1)
  if [ -n "$inc_id" ] && [ "$inc_stage" = "failed" ]; then break; fi
  sleep 2
done

if [ -n "$inc_id" ]; then
  record "incident.created_from_terminal" PASS "incident_id=$inc_id"
else
  record "incident.created_from_terminal" FAIL "no incident for task $inc_task"
fi
if [ "$inc_stage" = "failed" ]; then
  record "incident.workflow_state_failed" PASS
else
  record "incident.workflow_state_failed" FAIL "stage=$inc_stage"
fi
if [ -n "$inc_id" ]; then
  ack=$(curl -sS -m 10 -X POST "$ORCH/incidents/$inc_id/ack" || echo '{}')
  if echo "$ack" | grep -q '"status": *"acknowledged"'; then
    record "incident.ack" PASS
  else
    record "incident.ack" FAIL
  fi
  res=$(curl -sS -m 10 -X POST "$ORCH/incidents/$inc_id/resolve" || echo '{}')
  if echo "$res" | grep -q '"status": *"resolved"'; then
    record "incident.resolve" PASS
  else
    record "incident.resolve" FAIL
  fi
else
  record "incident.ack" FAIL "no incident_id"
  record "incident.resolve" FAIL "no incident_id"
fi

echo
echo "============================================================"
echo "11. SLO configuration"
echo "============================================================"
slo_path="infra/observability/slo/aiagents-slo.yml"
if [ -f "$slo_path" ]; then
  if python3 -c "import yaml; yaml.safe_load(open('$slo_path'))" 2>/dev/null; then
    record "slo.yaml.valid" PASS
  else
    record "slo.yaml.valid" FAIL
  fi
  for req in workflow_completion_p95_seconds workflow_success_rate agent_failure_rate dlq_growth_rate approval_pending_duration_seconds service_availability; do
    if grep -q "name: $req" "$slo_path"; then
      record "slo.entry.$req" PASS
    else
      record "slo.entry.$req" FAIL
    fi
  done
  if grep -q 'status: planned' "$slo_path" && grep -q 'todo:' "$slo_path"; then
    record "slo.planned.has_todo" PASS
  else
    record "slo.planned.has_todo" FAIL
  fi
else
  record "slo.file" FAIL "missing $slo_path"
fi

echo
echo "============================================================"
echo "12. Safety — no production_executed=true in recent deployments"
echo "============================================================"
dep_query=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT COALESCE(SUM(CASE WHEN metadata->>'production_executed'='true' THEN 1 ELSE 0 END),0) AS prod_true,
          COALESCE(SUM(CASE WHEN environment='production' THEN 1 ELSE 0 END),0) AS env_prod,
          COUNT(*) AS total
     FROM deployment_records;" 2>/dev/null | tr -d '[:space:]')
echo "  deployment_records summary (prod_true|env_prod|total): $dep_query"
prod_true=$(echo "$dep_query" | awk -F'|' '{print $1}')
env_prod=$(echo "$dep_query" | awk -F'|' '{print $2}')
if [ "${prod_true:-0}" = "0" ] && [ "${env_prod:-0}" = "0" ]; then
  record "safety.no_production_executed" PASS "prod_true=$prod_true env_prod=$env_prod"
else
  record "safety.no_production_executed" FAIL "prod_true=$prod_true env_prod=$env_prod"
fi

wf_exec=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT COALESCE(SUM(CASE WHEN execution_result->>'production_executed'='true' THEN 1 ELSE 0 END),0)
     FROM workflow_states;" 2>/dev/null | tr -d '[:space:]')
echo "  workflow_states execution_result.production_executed=true count: ${wf_exec:-0}"
if [ "${wf_exec:-0}" = "0" ]; then
  record "safety.workflow.production_executed_false" PASS
else
  record "safety.workflow.production_executed_false" FAIL "$wf_exec rows have production_executed=true"
fi

echo
echo "============================================================"
echo "13. Sub-scripts"
echo "============================================================"

run_subscript() {
  local label="$1" script="$2" marker="$3"
  echo
  echo "------------------------------------------------------------"
  echo ">>> $label  ($script)"
  echo "------------------------------------------------------------"
  local out
  if [ -x "$script" ]; then
    out=$("$script" 2>&1 || true)
  else
    out=$(bash "$script" 2>&1 || true)
  fi
  echo "$out"
  if echo "$out" | grep -q "$marker: PASS"; then
    record "subscript.$label" PASS
  else
    record "subscript.$label" FAIL "$marker not PASS"
  fi
}

run_subscript CHECK_RUNTIME_STATE     ./scripts/check_runtime_state.sh  TRACE_FLOW_SMOKE
run_subscript VERIFY_TRACING_BACKEND  ./scripts/verify_tracing_backend.sh TEMPO_READY
run_subscript VERIFY_TRACE_FLOW       ./scripts/verify_trace_flow.sh     TRACE_FLOW_SMOKE
run_subscript VERIFY_ALERTING         ./scripts/verify_alerting.sh       ALERTMANAGER_HEALTHY
run_subscript VERIFY_INCIDENT_FLOW    ./scripts/verify_incident_flow.sh  INCIDENT_FLOW_SMOKE

echo
echo "============================================================"
echo "Summary"
echo "============================================================"
echo "  PASS=$PASS  FAIL=$FAIL  total=$((PASS+FAIL))"
for r in "${RESULTS[@]}"; do
  echo "  $r"
done | grep ' FAIL$' || true
echo
if [ "$FAIL" -eq 0 ]; then
  echo "CHECK_RUNTIME_STATE: PASS"
  echo "VERIFY_TRACING_BACKEND: PASS"
  echo "VERIFY_TRACE_FLOW: PASS"
  echo "VERIFY_ALERTING: PASS"
  echo "VERIFY_INCIDENT_FLOW: PASS"
  echo "PLATFORM_OBSERVABILITY_VERIFY: PASS"
else
  for sub in CHECK_RUNTIME_STATE VERIFY_TRACING_BACKEND VERIFY_TRACE_FLOW VERIFY_ALERTING VERIFY_INCIDENT_FLOW; do
    if printf '%s\n' "${RESULTS[@]}" | grep -q "^subscript.${sub} PASS$"; then
      echo "${sub}: PASS"
    else
      echo "${sub}: FAIL"
    fi
  done
  echo "PLATFORM_OBSERVABILITY_VERIFY: FAIL"
fi

echo
echo "VERIFY_PLATFORM_OBSERVABILITY_DONE"
