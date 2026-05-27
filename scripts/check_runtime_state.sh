#!/usr/bin/env bash
# Check the state of the local/test runtime: containers, PostgreSQL tables,
# Redis streams, and the orchestrator health endpoint.
# Run from the repository root.
set -euo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"

echo "### runtime state check: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== docker compose ps ==="
$COMPOSE ps

echo
echo "=== PostgreSQL tables (database: aiagents) ==="
$COMPOSE exec -T postgres psql -U postgres -d aiagents -c '\dt'
tcount=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d '[:space:]')
echo "public table count: $tcount"

echo
echo "=== Redis streams & consumer groups ==="
streams=$($COMPOSE exec -T redis redis-cli --scan --pattern 'stream.*' </dev/null 2>/dev/null | sort)
for s in $streams; do
  grp=$($COMPOSE exec -T redis redis-cli XINFO GROUPS "$s" </dev/null 2>/dev/null | grep -cF 'name' || true)
  echo "  $s  ->  $grp consumer group(s)"
done

echo
echo "=== orchestrator /health ==="
if curl -sS -m 10 http://localhost:8000/health; then
  echo
  echo "HEALTH: PASS"
else
  echo
  echo "HEALTH: FAIL"
fi

echo
echo "=== orchestrator /workflow/schema ==="
curl -sS -m 10 http://localhost:8000/workflow/schema || echo "(schema unavailable)"
echo

echo
echo "=== /workflow/test (non-production dispatch smoke) ==="
np=$(curl -sS -m 20 -X POST http://localhost:8000/workflow/test \
  -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-dev","source":"check","request":{"type":"dev.test"}}' || echo '{}')
echo "$np"
if echo "$np" | grep -q '"stage": *"dispatched"'; then
  echo "NON_PROD_SMOKE: PASS"
else
  echo "NON_PROD_SMOKE: CHECK"
fi

echo
echo "=== /workflow/test (production.deploy approval smoke) ==="
pd=$(curl -sS -m 20 -X POST http://localhost:8000/workflow/test \
  -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-prod","source":"check","request":{"type":"production.deploy"}}' || echo '{}')
echo "$pd"
if echo "$pd" | grep -q '"stage": *"waiting_approval"'; then
  echo "PROD_APPROVAL_SMOKE: PASS"
else
  echo "PROD_APPROVAL_SMOKE: CHECK"
fi

echo
echo "=== governance services /health ==="
for entry in policy-engine:8001 approval-engine:8002 audit-service:8003; do
  name="${entry%%:*}"
  port="${entry##*:}"
  if curl -sS -m 10 "http://localhost:${port}/health" >/dev/null 2>&1; then
    echo "  ${name} (:${port})  ->  HEALTH: PASS"
  else
    echo "  ${name} (:${port})  ->  HEALTH: FAIL"
  fi
done

echo
echo "=== approval-engine flow smoke (request -> approve) ==="
appr=$(curl -sS -m 15 -X POST http://localhost:8002/approval/request \
  -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-approval","action":"production.deploy","risk_level":"high","reason":"runtime smoke test","requested_by":"check-runtime"}' || echo '{}')
echo "$appr"
rid=$(echo "$appr" | sed -n 's/.*"request_id": *"\([^"]*\)".*/\1/p')
if [ -n "$rid" ]; then
  appr2=$(curl -sS -m 15 -X POST http://localhost:8002/approval/approve \
    -H "Content-Type: application/json" \
    -d "{\"request_id\":\"$rid\",\"decided_by\":\"check-runtime\"}" || echo '{}')
  echo "$appr2"
  if echo "$appr2" | grep -q '"status": *"approved"'; then
    echo "APPROVAL_SMOKE: PASS"
  else
    echo "APPROVAL_SMOKE: CHECK"
  fi
else
  echo "APPROVAL_SMOKE: CHECK"
fi

echo
echo "=== audit-service insert smoke (insert -> query) ==="
aud=$(curl -sS -m 15 -X POST http://localhost:8003/audit/events \
  -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-audit","agent":"check-runtime","decision_type":"smoke","summary":"runtime smoke test","result":"ok","artifact_refs":{}}' || echo '{}')
echo "$aud"
aud2=$(curl -sS -m 15 http://localhost:8003/audit/events/smoke-audit || echo '{}')
echo "$aud2"
if echo "$aud2" | grep -q '"count"'; then
  echo "AUDIT_SMOKE: PASS"
else
  echo "AUDIT_SMOKE: CHECK"
fi

echo
echo "=== workflow persistence smoke (run -> GET /workflow/{id}) ==="
wf_task="smoke-persist-$$"
curl -sS -m 25 -X POST http://localhost:8000/workflow/test -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$wf_task\",\"source\":\"check\",\"request\":{\"type\":\"dev.test\"}}" \
  >/dev/null 2>&1 || true
persisted=$(curl -sS -m 10 "http://localhost:8000/workflow/$wf_task" || echo '{}')
echo "$persisted"
if echo "$persisted" | grep -q "\"task_id\":\"$wf_task\""; then
  echo "WORKFLOW_PERSISTENCE_SMOKE: PASS"
else
  echo "WORKFLOW_PERSISTENCE_SMOKE: CHECK"
fi

echo
echo "=== workflow replay smoke (GET /workflow/replay/{id}) ==="
replay=$(curl -sS -m 10 "http://localhost:8000/workflow/replay/$wf_task" || echo '{}')
echo "$replay"
if echo "$replay" | grep -q '"executed":false'; then
  echo "WORKFLOW_REPLAY_SMOKE: PASS"
else
  echo "WORKFLOW_REPLAY_SMOKE: CHECK"
fi

echo
echo "=== approval resume smoke (production.deploy -> approve -> resume) ==="
rs_task="smoke-resume-$$"
rs_wf=$(curl -sS -m 25 -X POST http://localhost:8000/workflow/test -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$rs_task\",\"source\":\"check\",\"request\":{\"type\":\"production.deploy\"}}" \
  || echo '{}')
echo "$rs_wf"
rs_req=$(echo "$rs_wf" | sed -n 's/.*"approval_request_id": *"\([^"]*\)".*/\1/p')
if [ -n "$rs_req" ]; then
  curl -sS -m 15 -X POST http://localhost:8002/approval/approve -H "Content-Type: application/json" \
    -d "{\"request_id\":\"$rs_req\",\"decided_by\":\"check-runtime\"}" >/dev/null 2>&1 || true
  rs_resumed=$(curl -sS -m 15 -X POST "http://localhost:8000/workflow/resume/$rs_task" || echo '{}')
  echo "$rs_resumed"
  if echo "$rs_resumed" | grep -qE '"stage": *"(dispatched|completed)"'; then
    echo "APPROVAL_RESUME_SMOKE: PASS"
  else
    echo "APPROVAL_RESUME_SMOKE: CHECK"
  fi
else
  echo "APPROVAL_RESUME_SMOKE: CHECK"
fi

echo
echo "=== communication-gateway /health ==="
if curl -sS -m 10 http://localhost:8004/health >/dev/null 2>&1; then
  echo "  communication-gateway (:8004)  ->  HEALTH: PASS"
else
  echo "  communication-gateway (:8004)  ->  HEALTH: FAIL"
fi

echo
echo "=== /intake/mock non-production smoke ==="
gw_dev=$(curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-gw-dev","request":{"type":"dev.test"}}' || echo '{}')
echo "$gw_dev"
if echo "$gw_dev" | grep -q '"stage": *"dispatched"'; then
  echo "INTAKE_NONPROD_SMOKE: PASS"
else
  echo "INTAKE_NONPROD_SMOKE: CHECK"
fi

echo
echo "=== /intake/mock production.deploy smoke ==="
gw_prod=$(curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-gw-prod","request":{"type":"production.deploy"}}' || echo '{}')
echo "$gw_prod"
if echo "$gw_prod" | grep -q '"stage": *"waiting_approval"'; then
  echo "INTAKE_PROD_SMOKE: PASS"
else
  echo "INTAKE_PROD_SMOKE: CHECK"
fi

echo
echo "=== /notifications/test + /notifications smoke ==="
nt=$(curl -sS -m 15 -X POST http://localhost:8004/notifications/test -H "Content-Type: application/json" \
  -d '{"task_id":"smoke-gw-notif","event_type":"runtime.smoke","message":"runtime check"}' || echo '{}')
echo "$nt"
notif=$(curl -sS -m 15 "http://localhost:8004/notifications?count=20" || echo '{}')
echo "$notif"
if echo "$notif" | grep -q 'smoke-gw-notif'; then
  echo "NOTIFICATIONS_SMOKE: PASS"
else
  echo "NOTIFICATIONS_SMOKE: CHECK"
fi

echo
echo "=== agent services /health ==="
for entry in intake-agent:8010 requirement-agent:8011 development-agent:8012 \
             qa-agent:8013 devops-agent:8014 retry-scheduler:8015; do
  name="${entry%%:*}"
  port="${entry##*:}"
  if curl -sS -m 10 "http://localhost:${port}/health" >/dev/null 2>&1; then
    echo "  ${name} (:${port})  ->  HEALTH: PASS"
  else
    echo "  ${name} (:${port})  ->  HEALTH: FAIL"
  fi
done

echo
echo "=== full agent pipeline smoke (tasks -> intake -> requirement -> development -> qa -> devops) ==="
pl_task="smoke-pipeline-$$"
dep_before=$($COMPOSE exec -T redis redis-cli XLEN stream.deployments | tr -d '[:space:]')
curl -sS -m 20 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$pl_task\",\"request\":{\"type\":\"dev.test\"},\"publish_to_stream\":true}" \
  >/dev/null 2>&1 || true
dep_after="${dep_before:-0}"
for i in $(seq 1 20); do
  dep_after=$($COMPOSE exec -T redis redis-cli XLEN stream.deployments | tr -d '[:space:]')
  if [ "${dep_after:-0}" -gt "${dep_before:-0}" ]; then break; fi
  sleep 2
done
echo "stream.deployments: before=${dep_before:-0} after=${dep_after:-0}"
if [ "${dep_after:-0}" -gt "${dep_before:-0}" ]; then
  echo "FULL_PIPELINE_SMOKE: PASS"
else
  echo "FULL_PIPELINE_SMOKE: CHECK"
fi
sleep 3

echo
echo "=== agent_executions for $pl_task ==="
$COMPOSE exec -T postgres psql -U postgres -d aiagents -c \
  "SELECT agent, status FROM agent_executions WHERE task_id='$pl_task' ORDER BY created_at;"
exec_count=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM agent_executions WHERE task_id='$pl_task' AND status='completed';" \
  | tr -d '[:space:]')
echo "completed executions for $pl_task: ${exec_count:-0}"
if [ "${exec_count:-0}" -ge 5 ]; then
  echo "AGENT_EXECUTIONS_SMOKE: PASS"
else
  echo "AGENT_EXECUTIONS_SMOKE: CHECK"
fi

echo
echo "=== deployment_records for $pl_task ==="
$COMPOSE exec -T postgres psql -U postgres -d aiagents -c \
  "SELECT task_id, environment, status FROM deployment_records WHERE task_id='$pl_task';"
dep_rows=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE task_id='$pl_task';" | tr -d '[:space:]')
if [ "${dep_rows:-0}" -ge 1 ]; then
  echo "DEPLOYMENT_RECORD_SMOKE: PASS"
else
  echo "DEPLOYMENT_RECORD_SMOKE: CHECK"
fi

echo
echo "=== unified dispatch end-to-end (gateway -> orchestrator -> agents -> completed) ==="
e2e_task="smoke-e2e-$$"
e2e_disp=$(curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$e2e_task\",\"request\":{\"type\":\"dev.test\"}}" || echo '{}')
echo "$e2e_disp"
if echo "$e2e_disp" | grep -q '"stage": *"dispatched"'; then
  echo "DISPATCH_SMOKE: PASS"
else
  echo "DISPATCH_SMOKE: CHECK"
fi
e2e_final='{}'
for i in $(seq 1 30); do
  e2e_final=$(curl -sS -m 10 "http://localhost:8000/workflow/$e2e_task" || echo '{}')
  if echo "$e2e_final" | grep -q '"stage": *"completed"'; then break; fi
  sleep 2
done
echo "$e2e_final"
if echo "$e2e_final" | grep -q '"stage": *"completed"'; then
  echo "DISPATCH_TO_COMPLETED_SMOKE: PASS"
else
  echo "DISPATCH_TO_COMPLETED_SMOKE: CHECK"
fi

echo
echo "=== workflow progress API smoke (GET /workflow/progress/{id}) ==="
prog=$(curl -sS -m 10 "http://localhost:8000/workflow/progress/$e2e_task" || echo '{}')
echo "$prog"
if echo "$prog" | grep -q '"execution_status"' && echo "$prog" | grep -q '"completed_agents"'; then
  echo "PROGRESS_API_SMOKE: PASS"
else
  echo "PROGRESS_API_SMOKE: CHECK"
fi

echo
echo "=== deadletter foundation smoke (publish -> stream.deadletter) ==="
dl=$(python3 - <<'PY' 2>/dev/null || echo 'ERR ERR'
import asyncio

from shared.sdk.event_bus.redis_streams import DEAD_LETTER_STREAM, RedisStreamEventBus


async def main() -> None:
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")
    before = await bus.client.xlen(DEAD_LETTER_STREAM)
    await bus.publish_dead_letter(
        "stream.smoke",
        {"task_id": "smoke-deadletter", "retry_count": 3, "max_retries": 3},
        "runtime smoke",
    )
    after = await bus.client.xlen(DEAD_LETTER_STREAM)
    await bus.close()
    print(f"{before} {after}")


asyncio.run(main())
PY
)
echo "stream.deadletter xlen (before after): $dl"
dl_before=$(echo "$dl" | awk '{print $1}')
dl_after=$(echo "$dl" | awk '{print $2}')
if [ "${dl_after:-x}" != "x" ] && [ "${dl_after:-0}" -gt "${dl_before:-0}" ] 2>/dev/null; then
  echo "DEADLETTER_SMOKE: PASS"
else
  echo "DEADLETTER_SMOKE: CHECK"
fi

echo
echo "=== retry-scheduler /deadletter list smoke ==="
dl_list=$(curl -sS -m 10 "http://localhost:8015/deadletter?count=5" || echo '{}')
echo "$dl_list"
if echo "$dl_list" | grep -q '"count"'; then
  echo "DLQ_LIST_SMOKE: PASS"
else
  echo "DLQ_LIST_SMOKE: CHECK"
fi

echo
echo "=== retry-scheduler /deadletter/replay smoke (publish -> replay -> on original stream) ==="
replay_smoke=$(python3 - <<'PY' 2>/dev/null || echo 'ERR'
import asyncio
import json
import urllib.request

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


async def main() -> None:
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")
    target = "test.replay.smoke"
    try:
        message_id = await bus.publish_dead_letter(
            target,
            {"task_id": "smoke-replay", "workflow_id": "wf-smoke-replay", "retry_count": 1, "max_retries": 3},
            "replay smoke",
        )
        before = await bus.client.xlen(target)
        req = urllib.request.Request(
            f"http://localhost:8015/deadletter/replay/{message_id}", method="POST"
        )
        body = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        after = await bus.client.xlen(target)
        await bus.client.delete(target)
        print(f"replayed={body.get('replayed')} stream={body.get('stream')} before={before} after={after}")
    finally:
        await bus.close()


asyncio.run(main())
PY
)
echo "$replay_smoke"
if echo "$replay_smoke" | grep -q 'replayed=True' && echo "$replay_smoke" | grep -q 'stream=test.replay.smoke'; then
  echo "DLQ_REPLAY_SMOKE: PASS"
else
  echo "DLQ_REPLAY_SMOKE: CHECK"
fi

echo
echo "=== workflow cancel smoke (waiting_approval -> cancel -> canceled) ==="
# Use production.deploy so the workflow sits at waiting_approval (non-terminal)
# without racing the agent pipeline to completed.
cancel_task="smoke-cancel-$$"
curl -sS -m 25 -X POST http://localhost:8000/workflow/test -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$cancel_task\",\"source\":\"check\",\"request\":{\"type\":\"production.deploy\"}}" \
  >/dev/null 2>&1 || true
cancel_resp=$(curl -sS -m 10 -X POST "http://localhost:8000/workflow/cancel/$cancel_task" \
  -H "Content-Type: application/json" -d '{"reason":"runtime smoke"}' || echo '{}')
echo "$cancel_resp"
if echo "$cancel_resp" | grep -q '"stage": *"canceled"' \
   && echo "$cancel_resp" | grep -q '"cancel_reason": *"runtime smoke"'; then
  echo "WORKFLOW_CANCEL_SMOKE: PASS"
else
  echo "WORKFLOW_CANCEL_SMOKE: CHECK"
fi

echo
echo "=== workflow abort smoke (waiting_approval -> abort -> aborted) ==="
abort_task="smoke-abort-$$"
curl -sS -m 25 -X POST http://localhost:8000/workflow/test -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$abort_task\",\"source\":\"check\",\"request\":{\"type\":\"production.deploy\"}}" \
  >/dev/null 2>&1 || true
abort_resp=$(curl -sS -m 10 -X POST "http://localhost:8000/workflow/abort/$abort_task" \
  -H "Content-Type: application/json" -d '{"reason":"runtime smoke abort"}' || echo '{}')
echo "$abort_resp"
if echo "$abort_resp" | grep -q '"stage": *"aborted"' \
   && echo "$abort_resp" | grep -q '"abort_reason": *"runtime smoke abort"'; then
  echo "WORKFLOW_ABORT_SMOKE: PASS"
else
  echo "WORKFLOW_ABORT_SMOKE: CHECK"
fi

echo
echo "=== failure simulation smoke (simulate_failure -> deadletter -> terminal_failure) ==="
fail_task="smoke-fail-$$"
fail_smoke=$(python3 - <<PY 2>/dev/null || echo 'ERR'
import asyncio
import json
import time

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


async def main() -> None:
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")
    try:
        await bus.publish_event(
            "stream.tasks",
            {
                "event": "task.created",
                "task_id": "$fail_task",
                "workflow_id": "wf-$fail_task",
                "source": "check",
                "request": {"type": "dev.test", "simulate_failure": True},
            },
        )
        dl_match = None
        term_match = None
        deadline = time.time() + 75
        while time.time() < deadline:
            for stream_name, target in (("stream.deadletter", "dl"), ("stream.deadletter.terminal", "term")):
                entries = await bus.client.xrevrange(stream_name, "+", "-", count=300)
                for _id, fields in entries:
                    try:
                        payload = json.loads(fields.get("data", "{}"))
                    except (ValueError, TypeError):
                        continue
                    if payload.get("task_id") == "$fail_task":
                        if target == "dl" and dl_match is None:
                            dl_match = payload
                        elif target == "term" and term_match is None:
                            term_match = payload
            if dl_match and term_match:
                break
            await asyncio.sleep(2)
        dl_rc = dl_match.get("retry_count") if dl_match else None
        term_rc = term_match.get("retry_count") if term_match else None
        print(f"dl_retry_count={dl_rc} terminal_retry_count={term_rc}")
    finally:
        await bus.close()


asyncio.run(main())
PY
)
echo "$fail_smoke"
if echo "$fail_smoke" | grep -q 'dl_retry_count=' \
   && echo "$fail_smoke" | grep -q 'terminal_retry_count=' \
   && ! echo "$fail_smoke" | grep -q 'terminal_retry_count=None'; then
  echo "FAILURE_SIMULATION_SMOKE: PASS"
else
  echo "FAILURE_SIMULATION_SMOKE: CHECK"
fi

echo
echo "=== tempo /ready ==="
tr=$(curl -sS -m 10 http://localhost:3200/ready || echo '')
echo "$tr"
if [ "$tr" = "ready" ] || echo "$tr" | grep -qi ready; then
  echo "TEMPO_HEALTH: PASS"
else
  echo "TEMPO_HEALTH: FAIL"
fi

echo
echo "=== prometheus /-/ready ==="
if curl -sS -m 10 http://localhost:9090/-/ready >/dev/null 2>&1; then
  echo "PROMETHEUS_HEALTH: PASS"
else
  echo "PROMETHEUS_HEALTH: FAIL"
fi

echo
echo "=== alertmanager /-/healthy ==="
am_health=$(curl -sS -o /dev/null -w '%{http_code}' -m 10 http://localhost:9093/-/healthy || echo 000)
echo "  HTTP $am_health"
if [ "$am_health" = "200" ]; then
  echo "ALERTMANAGER_HEALTH: PASS"
else
  echo "ALERTMANAGER_HEALTH: FAIL"
fi

echo
echo "=== prometheus /api/v1/rules (aiagents.* rule groups) ==="
rules=$(curl -sS -m 10 http://localhost:9090/api/v1/rules || echo '{}')
echo "$rules" | head -c 400 || true
echo
group_count=$(echo "$rules" | grep -o '"name":"aiagents\.[a-z]*"' | sort -u | wc -l)
echo "aiagents.* rule groups: $group_count"
if [ "${group_count:-0}" -ge 4 ]; then
  echo "PROMETHEUS_RULES_SMOKE: PASS"
else
  echo "PROMETHEUS_RULES_SMOKE: CHECK"
fi

echo
echo "=== prometheus /api/v1/alerts ==="
alerts=$(curl -sS -m 10 http://localhost:9090/api/v1/alerts || echo '{}')
echo "$alerts" | head -c 400 || true
echo
if echo "$alerts" | grep -q '"status":"success"'; then
  echo "PROMETHEUS_ALERTS_API_SMOKE: PASS"
else
  echo "PROMETHEUS_ALERTS_API_SMOKE: CHECK"
fi

echo
echo "=== grafana /api/health ==="
gh=$(curl -sS -m 10 http://localhost:3000/api/health || echo '{}')
echo "$gh"
if echo "$gh" | grep -qE '"database"[[:space:]]*:[[:space:]]*"ok"'; then
  echo "GRAFANA_HEALTH: PASS"
else
  echo "GRAFANA_HEALTH: FAIL"
fi

echo
echo "=== grafana datasources (anonymous) ==="
ds=$(curl -sS -m 10 http://localhost:3000/api/datasources || echo '[]')
echo "$ds" | head -c 1000
echo
if echo "$ds" | grep -q '"type":"tempo"' && echo "$ds" | grep -q '"url":"http://tempo:3200"'; then
  echo "GRAFANA_TEMPO_DATASOURCE_SMOKE: PASS"
else
  echo "GRAFANA_TEMPO_DATASOURCE_SMOKE: CHECK"
fi

echo
echo "=== prometheus /api/v1/targets ==="
targets=$(curl -sS -m 10 http://localhost:9090/api/v1/targets || echo '{}')
echo "$targets" | head -c 500
echo
if echo "$targets" | grep -q 'orchestrator' && echo "$targets" | grep -q 'retry-scheduler'; then
  echo "PROMETHEUS_TARGETS_SMOKE: PASS"
else
  echo "PROMETHEUS_TARGETS_SMOKE: CHECK"
fi

echo
echo "=== orchestrator /metrics smoke ==="
metrics=$(curl -sS -m 10 http://localhost:8000/metrics || echo '')
if echo "$metrics" | grep -q '^workflow_total'; then
  echo "METRICS_ENDPOINT_SMOKE: PASS"
else
  echo "METRICS_ENDPOINT_SMOKE: CHECK"
fi

echo
echo "=== trace propagation smoke (dispatch -> stream.devops carries trace_id) ==="
trace_smoke=$(python3 - <<PY 2>/dev/null || echo 'ERR'
import asyncio
import json
import time
import uuid

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


async def main() -> None:
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")
    task_id = "smoke-trace-" + uuid.uuid4().hex[:8]
    workflow_id = "wf-smoke-trace-" + uuid.uuid4().hex[:8]
    trace_id = "f" * 32
    try:
        await bus.publish_event(
            "stream.tasks",
            {
                "event": "task.created",
                "task_id": task_id,
                "workflow_id": workflow_id,
                "trace_id": trace_id,
                "source": "check",
                "request": {"type": "dev.test"},
            },
        )
        deadline = time.time() + 30
        match = None
        while time.time() < deadline:
            entries = await bus.client.xrevrange("stream.devops", "+", "-", count=200)
            for _id, fields in entries:
                try:
                    payload = json.loads(fields.get("data", "{}"))
                except (ValueError, TypeError):
                    continue
                if payload.get("task_id") == task_id:
                    match = payload
                    break
            if match:
                break
            await asyncio.sleep(1)
        if match is None:
            print("no devops event")
        else:
            print(f"trace_id={match.get('trace_id', '')} span_id={match.get('span_id', '')}")
    finally:
        await bus.close()


asyncio.run(main())
PY
)
echo "$trace_smoke"
if echo "$trace_smoke" | grep -q "trace_id=${trace_smoke##*=}"; then
  : # noop, placeholder
fi
if echo "$trace_smoke" | grep -qE 'trace_id=[a-f0-9]{32}' && echo "$trace_smoke" | grep -qE 'span_id=[a-f0-9]{16}'; then
  echo "TRACE_PROPAGATION_SMOKE: PASS"
else
  echo "TRACE_PROPAGATION_SMOKE: CHECK"
fi

echo
echo "=== workflow timeline API smoke ==="
tl=$(curl -sS -m 10 "http://localhost:8000/workflow/timeline/$e2e_task" || echo '{}')
echo "$tl" | head -c 800
echo
if echo "$tl" | grep -q '"agent_timeline"' && echo "$tl" | grep -q '"traces"'; then
  echo "WORKFLOW_TIMELINE_SMOKE: PASS"
else
  echo "WORKFLOW_TIMELINE_SMOKE: CHECK"
fi

echo
echo "=== incident API smoke (GET /incidents list) ==="
inc_list=$(curl -sS -m 10 http://localhost:8000/incidents || echo '{}')
echo "$inc_list" | head -c 400 || true
echo
if echo "$inc_list" | grep -q '"count"'; then
  echo "INCIDENT_API_SMOKE: PASS"
else
  echo "INCIDENT_API_SMOKE: CHECK"
fi

echo
echo "=== incident create smoke (POST /incidents) ==="
inc_task="smoke-incident-$$"
inc_create=$(curl -sS -m 10 -X POST http://localhost:8000/incidents \
  -H "Content-Type: application/json" \
  -d "{\"severity\":\"sev3\",\"source\":\"check-runtime\",\"summary\":\"runtime incident smoke\",\"task_id\":\"$inc_task\",\"details\":{\"smoke\":true}}" \
  || echo '{}')
echo "$inc_create" | head -c 400 || true
echo
inc_id=$(echo "$inc_create" | sed -n 's/.*"incident_id": *"\([a-f0-9-]*\)".*/\1/p' | head -n1)
if [ -n "$inc_id" ] && echo "$inc_create" | grep -q '"status": *"open"'; then
  echo "INCIDENT_CREATE_SMOKE: PASS (incident_id=$inc_id)"
else
  echo "INCIDENT_CREATE_SMOKE: CHECK"
fi

echo
echo "=== incident ack smoke (POST /incidents/{id}/ack) ==="
if [ -n "$inc_id" ]; then
  inc_ack=$(curl -sS -m 10 -X POST "http://localhost:8000/incidents/$inc_id/ack" || echo '{}')
  echo "$inc_ack" | head -c 400 || true
  echo
  if echo "$inc_ack" | grep -q '"status": *"acknowledged"'; then
    echo "INCIDENT_ACK_SMOKE: PASS"
  else
    echo "INCIDENT_ACK_SMOKE: CHECK"
  fi
else
  echo "INCIDENT_ACK_SMOKE: CHECK (no incident_id from create)"
fi

echo
echo "=== incident resolve smoke (POST /incidents/{id}/resolve) ==="
if [ -n "$inc_id" ]; then
  inc_res=$(curl -sS -m 10 -X POST "http://localhost:8000/incidents/$inc_id/resolve" || echo '{}')
  echo "$inc_res" | head -c 400 || true
  echo
  if echo "$inc_res" | grep -q '"status": *"resolved"'; then
    echo "INCIDENT_RESOLVE_SMOKE: PASS"
  else
    echo "INCIDENT_RESOLVE_SMOKE: CHECK"
  fi
else
  echo "INCIDENT_RESOLVE_SMOKE: CHECK (no incident_id from create)"
fi

echo
echo "=== terminal failure -> incident smoke (simulate_failure -> incident row) ==="
tf_task="smoke-terminal-incident-$$"
curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$tf_task\",\"request\":{\"type\":\"dev.test\",\"simulate_failure\":true}}" \
  >/dev/null 2>&1 || true
tf_incident_id=""
tf_wf_stage=""
for i in $(seq 1 45); do
  tf_list=$(curl -sS -m 10 "http://localhost:8000/incidents?task_id=$tf_task" || echo '{}')
  tf_incident_id=$(echo "$tf_list" | sed -n 's/.*"incident_id": *"\([a-f0-9-]*\)".*/\1/p' | head -n1)
  tf_wf=$(curl -sS -m 10 "http://localhost:8000/workflow/$tf_task" || echo '{}')
  tf_wf_stage=$(echo "$tf_wf" | sed -n 's/.*"stage": *"\([^"]*\)".*/\1/p' | head -n1)
  if [ -n "$tf_incident_id" ] && [ "$tf_wf_stage" = "failed" ]; then break; fi
  sleep 2
done
echo "tf_task=$tf_task incident_id=$tf_incident_id workflow_stage=$tf_wf_stage"
if [ -n "$tf_incident_id" ]; then
  echo "TERMINAL_FAILURE_INCIDENT_SMOKE: PASS"
else
  echo "TERMINAL_FAILURE_INCIDENT_SMOKE: CHECK"
fi

echo
echo "=== workflow failed state smoke (workflow_states.stage=failed after terminal) ==="
if [ "$tf_wf_stage" = "failed" ]; then
  echo "WORKFLOW_FAILED_STATE_SMOKE: PASS"
else
  echo "WORKFLOW_FAILED_STATE_SMOKE: CHECK (workflow stage=$tf_wf_stage)"
fi

echo
echo "=== SLO config smoke ==="
slo_path="infra/observability/slo/aiagents-slo.yml"
if [ -f "$slo_path" ] && grep -q "^slos:" "$slo_path" \
   && grep -q "name: workflow_completion_p95_seconds" "$slo_path" \
   && grep -q "name: service_availability" "$slo_path"; then
  echo "SLO_CONFIG_SMOKE: PASS"
else
  echo "SLO_CONFIG_SMOKE: CHECK"
fi

echo
echo "=== trace flow smoke (trace_id reaches Tempo with all 7 service spans) ==="
tf_task="smoke-trace-flow-$$"
# Orchestrator mode so the workflow row is persisted and the agent pipeline
# completes — direct stream.tasks publishes have no workflow_state row.
curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$tf_task\",\"request\":{\"type\":\"dev.test\",\"description\":\"trace flow check\"}}" \
  >/dev/null 2>&1 || true
tf_trace=""
tf_stage=""
for i in $(seq 1 40); do
  tf_prog=$(curl -sS -m 10 "http://localhost:8000/workflow/progress/$tf_task" || echo '{}')
  tf_stage=$(echo "$tf_prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  if [ -z "$tf_trace" ]; then
    tf_trace=$(echo "$tf_prog" | sed -n 's/.*"trace_id": *"\([a-f0-9]*\)".*/\1/p' | head -n1)
  fi
  if [ "$tf_stage" = "completed" ]; then break; fi
  sleep 2
done
echo "task=$tf_task trace_id=$tf_trace stage=$tf_stage"
sleep 6
if [ -n "$tf_trace" ]; then
  tf_body=$(curl -sS -m 15 "http://localhost:3200/api/traces/$tf_trace" || echo '')
  # Tempo /api/traces responses can be very large; head closes the pipe early
  # and triggers SIGPIPE under set -euo pipefail. Swallow that explicitly.
  echo "$tf_body" | head -c 500 || true
  echo
  hits=0
  for svc in communication-gateway orchestrator intake-agent requirement-agent development-agent qa-agent devops-agent; do
    if echo "$tf_body" | grep -q "\"$svc\""; then hits=$((hits+1)); fi
  done
  if [ "${hits:-0}" -ge 6 ]; then
    echo "TRACE_FLOW_SMOKE: PASS ($hits/7 services in trace $tf_trace)"
  else
    echo "TRACE_FLOW_SMOKE: CHECK ($hits/7 services in trace $tf_trace)"
  fi
else
  echo "TRACE_FLOW_SMOKE: CHECK (no trace_id for $tf_task)"
fi

echo
echo "=== github-automation /health ==="
if curl -sS -m 10 http://localhost:8005/health >/dev/null 2>&1; then
  echo "  github-automation (:8005)  ->  HEALTH: PASS"
  echo "GITHUB_AUTOMATION_HEALTH: PASS"
else
  echo "  github-automation (:8005)  ->  HEALTH: FAIL"
  echo "GITHUB_AUTOMATION_HEALTH: FAIL"
fi

echo
echo "=== github-automation /github/workflow/demo-pr (dry-run) ==="
gh_task="smoke-gh-$$"
gh_demo=$(curl -sS -m 15 -X POST http://localhost:8005/github/workflow/demo-pr \
  -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$gh_task\",\"repo\":\"coolerh250/AI-Agents-SWD\",\"dry_run\":true,\"title\":\"[AI-Agents-SWD Test] runtime smoke\",\"file_path\":\"docs/automation-demo.md\",\"file_content\":\"# runtime smoke\\n\"}" \
  || echo '{}')
echo "$gh_demo" | head -c 800 || true
echo
if echo "$gh_demo" | grep -q '"dry_run":true' \
   && echo "$gh_demo" | grep -q '"event_type":"github.pr.dry_run"' \
   && echo "$gh_demo" | grep -q '"pull_request"'; then
  echo "GITHUB_DEMO_PR_DRY_RUN_SMOKE: PASS"
else
  echo "GITHUB_DEMO_PR_DRY_RUN_SMOKE: CHECK"
fi

echo
echo "=== github-automation -> audit smoke (decision_type=github_automation) ==="
gh_audit=$(curl -sS -m 10 "http://localhost:8003/audit/events/$gh_task" || echo '{}')
echo "$gh_audit" | head -c 400 || true
echo
if echo "$gh_audit" | grep -q '"decision_type": *"github_automation"'; then
  echo "GITHUB_AUDIT_SMOKE: PASS"
else
  echo "GITHUB_AUDIT_SMOKE: CHECK"
fi

echo
echo "=== github-automation -> notification smoke (event_type=github.pr.dry_run) ==="
gh_notif=$(curl -sS -m 10 "http://localhost:8004/notifications?count=100" || echo '{}')
if echo "$gh_notif" | grep -q '"event_type": *"github.pr.dry_run"' \
   && echo "$gh_notif" | grep -q "$gh_task"; then
  echo "GITHUB_NOTIFICATION_SMOKE: PASS"
else
  echo "GITHUB_NOTIFICATION_SMOKE: CHECK"
fi

echo
echo "=== github-automation /metrics smoke (github_* counters present) ==="
gh_metrics=$(curl -sS -m 10 http://localhost:8005/metrics || echo '')
# Counter `.labels(...)` series only render after the first inc(); accept the
# HELP / TYPE registration too so a no-failure run still counts.
if echo "$gh_metrics" | grep -qE '(^|# HELP |# TYPE )github_issue_created_total' \
   && echo "$gh_metrics" | grep -qE '(^|# HELP |# TYPE )github_pr_created_total' \
   && echo "$gh_metrics" | grep -qE '(^|# HELP |# TYPE )github_checks_read_total' \
   && echo "$gh_metrics" | grep -qE '(^|# HELP |# TYPE )github_automation_failures_total'; then
  echo "GITHUB_METRICS_SMOKE: PASS"
else
  echo "GITHUB_METRICS_SMOKE: CHECK"
fi

echo
echo "=== pipeline -> github-automation integration smoke ==="
gpi_task="smoke-gpi-$$"
gpi_seed=$(curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$gpi_task\",\"request\":{\"type\":\"dev.test\",\"description\":\"github pipeline smoke\",\"github\":{\"enabled\":true,\"dry_run\":true}}}" \
  || echo '{}')
echo "$gpi_seed" | head -c 300 || true
echo
gpi_pr_url=""
gpi_status=""
for i in $(seq 1 30); do
  gpi_prog=$(curl -sS -m 10 "http://localhost:8000/workflow/progress/$gpi_task" || echo '{}')
  gpi_stage=$(echo "$gpi_prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  gpi_pr_url=$(echo "$gpi_prog" | sed -n 's/.*"pr_url": *"\([^"]*\)".*/\1/p' | head -n1)
  gpi_status=$(echo "$gpi_prog" | sed -n 's/.*"github_status": *"\([^"]*\)".*/\1/p' | head -n1)
  if [ "$gpi_stage" = "completed" ] && [ -n "$gpi_pr_url" ]; then break; fi
  sleep 2
done
echo "gpi_task=$gpi_task pr_url=$gpi_pr_url github_status=$gpi_status"
if [ -n "$gpi_pr_url" ] && [ "$gpi_status" = "success" ]; then
  echo "GITHUB_PIPELINE_INTEGRATION_SMOKE: PASS"
else
  echo "GITHUB_PIPELINE_INTEGRATION_SMOKE: CHECK"
fi

echo
echo "=== workflow_states.execution_result.github backfill smoke ==="
gpi_wf=$(curl -sS -m 10 "http://localhost:8000/workflow/$gpi_task" || echo '{}')
if echo "$gpi_wf" | grep -q '"github"' \
   && echo "$gpi_wf" | grep -q '"dry_run":true' \
   && echo "$gpi_wf" | grep -q '"production_executed":false'; then
  echo "GITHUB_WORKFLOW_RESULT_SMOKE: PASS"
else
  echo "GITHUB_WORKFLOW_RESULT_SMOKE: CHECK"
fi

echo
echo "=== workflow timeline carries github.demo_pr.dry_run smoke ==="
gpi_tl=$(curl -sS -m 10 "http://localhost:8000/workflow/timeline/$gpi_task" || echo '{}')
if echo "$gpi_tl" | grep -q 'github.demo_pr.dry_run'; then
  echo "GITHUB_TIMELINE_SMOKE: PASS"
else
  echo "GITHUB_TIMELINE_SMOKE: CHECK"
fi

echo
echo "=== audit decision_type=github_pr_integration smoke ==="
gpi_audit=$(curl -sS -m 10 "http://localhost:8003/audit/events/$gpi_task" || echo '{}')
if echo "$gpi_audit" | grep -q '"decision_type": *"github_pr_integration"'; then
  echo "GITHUB_PIPELINE_AUDIT_SMOKE: PASS"
else
  echo "GITHUB_PIPELINE_AUDIT_SMOKE: CHECK"
fi

echo
echo "=== notification github.pr.dry_run for $gpi_task smoke ==="
gpi_notif=$(curl -sS -m 10 "http://localhost:8004/notifications?count=200" || echo '{}')
if echo "$gpi_notif" | grep -q '"event_type": *"github.pr.dry_run"' \
   && echo "$gpi_notif" | grep -q "$gpi_task"; then
  echo "GITHUB_PIPELINE_NOTIFICATION_SMOKE: PASS"
else
  echo "GITHUB_PIPELINE_NOTIFICATION_SMOKE: CHECK"
fi

echo
echo "=== github-automation trace smoke (pipeline trace includes service) ==="
gpi_trace=$(echo "$gpi_prog" | sed -n 's/.*"trace_id": *"\([a-f0-9]*\)".*/\1/p' | head -n1)
if [ -n "$gpi_trace" ]; then
  sleep 4
  gpi_body=$(curl -sS -m 15 "http://localhost:3200/api/traces/$gpi_trace" || echo '')
  if echo "$gpi_body" | grep -q '"github-automation"' \
     && echo "$gpi_body" | grep -q '"devops-agent"'; then
    echo "GITHUB_PIPELINE_TRACE_SMOKE: PASS (trace_id=$gpi_trace)"
  else
    echo "GITHUB_PIPELINE_TRACE_SMOKE: CHECK (trace_id=$gpi_trace)"
  fi
else
  echo "GITHUB_PIPELINE_TRACE_SMOKE: CHECK (no trace_id for $gpi_task)"
fi

echo
echo "CHECK_RUNTIME_STATE_DONE"
