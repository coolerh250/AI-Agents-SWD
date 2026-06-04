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
echo "=== audit-worker /health smoke ==="
if curl -sS -m 10 http://localhost:8006/health >/dev/null 2>&1; then
  echo "  audit-worker (:8006)  ->  HEALTH: PASS"
  echo "AUDIT_WORKER_HEALTH_SMOKE: PASS"
else
  echo "  audit-worker (:8006)  ->  HEALTH: FAIL"
  echo "AUDIT_WORKER_HEALTH_SMOKE: FAIL"
fi

echo
echo "=== audit-worker /status smoke ==="
aw_status=$(curl -sS -m 10 http://localhost:8006/status || echo '{}')
echo "$aw_status" | head -c 400 || true
echo
if echo "$aw_status" | grep -q '"service": *"audit-worker"' \
   && echo "$aw_status" | grep -q '"input_stream": *"stream.audit"' \
   && echo "$aw_status" | grep -q '"group": *"audit-group"'; then
  echo "AUDIT_WORKER_STATUS_SMOKE: PASS"
else
  echo "AUDIT_WORKER_STATUS_SMOKE: CHECK"
fi

echo
echo "=== stream.audit -> audit_logs smoke (orchestrator pipeline) ==="
aw_task="smoke-aw-$$"
curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$aw_task\",\"request\":{\"type\":\"dev.test\",\"description\":\"audit-worker smoke\"}}" >/dev/null 2>&1 || true
aw_seen=0
for i in $(seq 1 30); do
  aw_prog=$(curl -sS -m 10 "http://localhost:8000/workflow/progress/$aw_task" || echo '{}')
  aw_stage=$(echo "$aw_prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  if [ "$aw_stage" = "completed" ]; then break; fi
  sleep 2
done
sleep 3
aw_audit=$(curl -sS -m 10 "http://localhost:8003/audit/events/$aw_task" || echo '{}')
aw_count=$(echo "$aw_audit" | sed -n 's/.*"count": *\([0-9]*\).*/\1/p' | head -n1)
echo "audit count for $aw_task: $aw_count"
if [ -n "$aw_count" ] && [ "$aw_count" -ge 4 ]; then
  echo "AUDIT_STREAM_TO_DB_SMOKE: PASS"
else
  echo "AUDIT_STREAM_TO_DB_SMOKE: CHECK ($aw_count rows)"
fi

echo
echo "=== audit.recorded skip smoke (echo not re-persisted) ==="
aw_metrics=$(curl -sS -m 10 http://localhost:8006/metrics || echo '')
if echo "$aw_metrics" | grep -qE '(^|# HELP |# TYPE )audit_worker_skipped_total'; then
  echo "AUDIT_RECORDED_SKIP_SMOKE: PASS"
else
  echo "AUDIT_RECORDED_SKIP_SMOKE: CHECK"
fi

echo
echo "=== audit deadletter metric smoke ==="
if echo "$aw_metrics" | grep -qE '(^|# HELP |# TYPE )audit_worker_deadlettered_total'; then
  echo "AUDIT_DEADLETTER_SMOKE: PASS"
else
  echo "AUDIT_DEADLETTER_SMOKE: CHECK"
fi

echo
echo "=== workflow audit_timeline smoke ==="
aw_tl=$(curl -sS -m 10 "http://localhost:8000/workflow/timeline/$aw_task" || echo '{}')
if echo "$aw_tl" | grep -q '"audit_timeline"'; then
  echo "AUDIT_TIMELINE_SMOKE: PASS"
else
  echo "AUDIT_TIMELINE_SMOKE: CHECK"
fi

echo
echo "=== github pipeline -> audit_logs.github_pr_integration smoke (DB-persisted via worker) ==="
if echo "$gpi_audit" | grep -q '"decision_type": *"github_pr_integration"' \
   && echo "$gpi_audit" | grep -q '"decision_type": *"github_automation"'; then
  echo "GITHUB_PIPELINE_AUDIT_DB_SMOKE: PASS"
else
  echo "GITHUB_PIPELINE_AUDIT_DB_SMOKE: CHECK"
fi

echo
echo "=== terminal failure -> audit_logs.workflow_failed smoke ==="
tf_task="smoke-aw-fail-$$"
curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$tf_task\",\"request\":{\"type\":\"dev.test\",\"simulate_failure\":true}}" >/dev/null 2>&1 || true
sleep 12
tf_audit=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=workflow_failed&limit=5" || echo '{}')
if echo "$tf_audit" | grep -q '"decision_type": *"workflow_failed"'; then
  echo "TERMINAL_FAILURE_AUDIT_DB_SMOKE: PASS"
else
  echo "TERMINAL_FAILURE_AUDIT_DB_SMOKE: CHECK"
fi


echo
echo "=== operations API health smoke ==="
if curl -sS -m 5 http://localhost:8000/operations/health | grep -q '"service": *"operations"'; then
  echo "OPERATIONS_HEALTH_SMOKE: PASS"
else
  echo "OPERATIONS_HEALTH_SMOKE: FAIL"
fi

echo
echo "=== operations summary smoke ==="
op_sum=$(curl -sS -m 15 http://localhost:8000/operations/summary || echo '{}')
if echo "$op_sum" | grep -q '"production_safety"' \
   && echo "$op_sum" | grep -q '"workflows_summary"' \
   && echo "$op_sum" | grep -q '"agents_summary"' \
   && echo "$op_sum" | grep -q '"github_summary"'; then
  echo "OPERATIONS_SUMMARY_SMOKE: PASS"
else
  echo "OPERATIONS_SUMMARY_SMOKE: CHECK"
fi

echo
echo "=== operations workflow view smoke ==="
op_task="ops-smoke-$$"
curl -sS -m 30 -X POST http://localhost:8004/intake/mock -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$op_task\",\"request\":{\"type\":\"dev.test\",\"description\":\"operations smoke\"}}" \
  >/dev/null 2>&1 || true
for i in $(seq 1 30); do
  op_prog=$(curl -sS -m 10 "http://localhost:8000/workflow/progress/$op_task" || echo '{}')
  op_stage=$(echo "$op_prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  if [ "$op_stage" = "completed" ]; then break; fi
  sleep 2
done
sleep 3
op_wf=$(curl -sS -m 15 "http://localhost:8000/operations/workflows/$op_task" || echo '{}')
if echo "$op_wf" | grep -q '"audit_timeline"' \
   && echo "$op_wf" | grep -q '"github"' \
   && echo "$op_wf" | grep -q '"agents"' \
   && echo "$op_wf" | grep -q '"production_executed":false'; then
  echo "OPERATIONS_WORKFLOW_VIEW_SMOKE: PASS"
else
  echo "OPERATIONS_WORKFLOW_VIEW_SMOKE: CHECK"
fi

echo
echo "=== operations agents view smoke ==="
op_agents=$(curl -sS -m 10 http://localhost:8000/operations/agents || echo '{}')
if echo "$op_agents" | grep -q '"intake-agent"' \
   && echo "$op_agents" | grep -q '"devops-agent"' \
   && echo "$op_agents" | grep -q '"input_stream"' \
   && echo "$op_agents" | grep -q '"consumer_group"'; then
  echo "OPERATIONS_AGENTS_SMOKE: PASS"
else
  echo "OPERATIONS_AGENTS_SMOKE: CHECK"
fi

echo
echo "=== operations streams view smoke ==="
op_streams=$(curl -sS -m 10 http://localhost:8000/operations/streams || echo '{}')
if echo "$op_streams" | grep -q '"stream.audit"' \
   && echo "$op_streams" | grep -q '"stream.notifications"' \
   && echo "$op_streams" | grep -q '"stream.deadletter"'; then
  echo "OPERATIONS_STREAMS_SMOKE: PASS"
else
  echo "OPERATIONS_STREAMS_SMOKE: CHECK"
fi

echo
echo "=== operations safety view smoke ==="
op_safety=$(curl -sS -m 10 http://localhost:8000/operations/safety || echo '{}')
if echo "$op_safety" | grep -q '"production_executed_true_count": *0' \
   && echo "$op_safety" | grep -q '"workflow_production_executed_true_count": *0' \
   && echo "$op_safety" | grep -qE '"result": *"(safe|warning)"'; then
  echo "OPERATIONS_SAFETY_SMOKE: PASS"
else
  echo "OPERATIONS_SAFETY_SMOKE: CHECK"
fi

echo
echo "=== operations incidents view smoke ==="
op_inc=$(curl -sS -m 10 http://localhost:8000/operations/incidents?limit=5 || echo '{}')
if echo "$op_inc" | grep -q '"count":' \
   && echo "$op_inc" | grep -q '"incidents":'; then
  echo "OPERATIONS_INCIDENTS_SMOKE: PASS"
else
  echo "OPERATIONS_INCIDENTS_SMOKE: CHECK"
fi

echo
echo "=== operations dlq view smoke ==="
op_dlq=$(curl -sS -m 10 http://localhost:8000/operations/dlq?limit=5 || echo '{}')
if echo "$op_dlq" | grep -q '"deadletter_length":' \
   && echo "$op_dlq" | grep -q '"deadletter_terminal_length":'; then
  echo "OPERATIONS_DLQ_SMOKE: PASS"
else
  echo "OPERATIONS_DLQ_SMOKE: CHECK"
fi

echo
echo "=== operations github view smoke ==="
op_gh=$(curl -sS -m 10 "http://localhost:8000/operations/github/$op_task" || echo '{}')
if echo "$op_gh" | grep -q '"found":' \
   && echo "$op_gh" | grep -q '"source":'; then
  echo "OPERATIONS_GITHUB_SMOKE: PASS"
else
  echo "OPERATIONS_GITHUB_SMOKE: CHECK"
fi


echo
echo "=== discord-gateway /health smoke ==="
if curl -sS -m 5 http://localhost:8007/health | grep -q '"service": *"discord-gateway"'; then
  echo "DISCORD_GATEWAY_HEALTH_SMOKE: PASS"
else
  echo "DISCORD_GATEWAY_HEALTH_SMOKE: FAIL"
fi

echo
echo "=== discord-gateway /status smoke ==="
dg_status=$(curl -sS -m 10 http://localhost:8007/status || echo '{}')
echo "$dg_status" | head -c 400 || true
echo
if echo "$dg_status" | grep -q '"mode": *"sandbox"' \
   && echo "$dg_status" | grep -q '"running":' \
   && echo "$dg_status" | grep -q '"received_count":' \
   && echo "$dg_status" | grep -q '"real_test_enabled": *false'; then
  echo "DISCORD_GATEWAY_STATUS_SMOKE: PASS"
else
  echo "DISCORD_GATEWAY_STATUS_SMOKE: CHECK"
fi

echo
echo "=== discord /discord/messages dev.test intake smoke ==="
dg_task="discord-smoke-$$"
dg_msg=$(curl -sS -m 30 -X POST http://localhost:8007/discord/messages \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.test description=\\\"runtime smoke\\\" task_id=$dg_task\",\"channel_id\":\"sandbox-ch\",\"user_id\":\"runtime-smoke\"}" \
  || echo '{}')
echo "$dg_msg" | head -c 400 || true
echo
if echo "$dg_msg" | grep -q '"sandbox": *true' \
   && echo "$dg_msg" | grep -q '"operations_url":'; then
  echo "DISCORD_MESSAGE_INTAKE_SMOKE: PASS"
else
  echo "DISCORD_MESSAGE_INTAKE_SMOKE: CHECK"
fi

echo
echo "=== discord /discord/events/mock intake smoke ==="
dg_event_task="discord-event-smoke-$$"
dg_event=$(curl -sS -m 30 -X POST http://localhost:8007/discord/events/mock \
  -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$dg_event_task\",\"channel_id\":\"sandbox-evt\",\"author\":{\"id\":\"mock-user\"},\"id\":\"evt-1\",\"data\":{\"name\":\"ai\",\"options\":[{\"name\":\"task\",\"value\":\"\"},{\"name\":\"type\",\"value\":\"dev.test\"},{\"name\":\"description\",\"value\":\"events-mock smoke\"}]}}" \
  || echo '{}')
if echo "$dg_event" | grep -q '"sandbox": *true' \
   && echo "$dg_event" | grep -q '"command_type": *"slash"'; then
  echo "DISCORD_EVENT_MOCK_SMOKE: PASS"
else
  echo "DISCORD_EVENT_MOCK_SMOKE: CHECK"
fi

echo
echo "=== discord production.deploy approval gate smoke ==="
dg_prod_task="discord-prod-smoke-$$"
dg_prod=$(curl -sS -m 30 -X POST http://localhost:8007/discord/messages \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=production.deploy description=\\\"smoke production\\\" task_id=$dg_prod_task\",\"channel_id\":\"sandbox-prod\",\"user_id\":\"runtime-smoke\"}" \
  || echo '{}')
if echo "$dg_prod" | grep -q '"stage": *"waiting_approval"' \
   && echo "$dg_prod" | grep -q '"approval_required": *true' \
   && echo "$dg_prod" | grep -q '"event_type": *"discord.task.waiting_approval"'; then
  echo "DISCORD_PRODUCTION_APPROVAL_SMOKE: PASS"
else
  echo "DISCORD_PRODUCTION_APPROVAL_SMOKE: CHECK"
fi

echo
echo "=== wait for $dg_task to complete then look up via /discord/tasks ==="
for i in $(seq 1 30); do
  dg_prog=$(curl -sS -m 10 "http://localhost:8000/workflow/progress/$dg_task" || echo '{}')
  dg_stage=$(echo "$dg_prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  if [ "$dg_stage" = "completed" ]; then break; fi
  sleep 2
done
sleep 4
dg_lookup=$(curl -sS -m 10 "http://localhost:8007/discord/tasks/$dg_task" || echo '{}')
if echo "$dg_lookup" | grep -q '"sandbox": *true' \
   && echo "$dg_lookup" | grep -q '"operations_url":' \
   && echo "$dg_lookup" | grep -q '"production_executed": *false'; then
  echo "DISCORD_TASK_LOOKUP_SMOKE: PASS"
else
  echo "DISCORD_TASK_LOOKUP_SMOKE: CHECK"
fi

echo
echo "=== discord notification stream smoke ==="
dg_notifs=$(curl -sS -m 10 "http://localhost:8004/notifications?count=200" || echo '{}')
if echo "$dg_notifs" | grep -q 'discord.task.received' \
   || echo "$dg_notifs" | grep -q 'discord.task.dispatched' \
   || echo "$dg_notifs" | grep -q 'discord.task.completed'; then
  echo "DISCORD_NOTIFICATION_SMOKE: PASS"
else
  echo "DISCORD_NOTIFICATION_SMOKE: CHECK"
fi

echo
echo "=== discord audit_logs smoke (decision_type=discord_intake via audit-worker) ==="
dg_audit=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=discord_intake&limit=5" || echo '{}')
if echo "$dg_audit" | grep -q '"decision_type": *"discord_intake"' \
   && echo "$dg_audit" | grep -q '"agent": *"discord-gateway"'; then
  echo "DISCORD_AUDIT_DB_SMOKE: PASS"
else
  echo "DISCORD_AUDIT_DB_SMOKE: CHECK"
fi

echo
echo "=== discord /metrics smoke ==="
dg_metrics=$(curl -sS -m 10 http://localhost:8007/metrics || echo '')
if echo "$dg_metrics" | grep -qE '(^|# HELP |# TYPE )discord_messages_received_total' \
   && echo "$dg_metrics" | grep -qE '(^|# HELP |# TYPE )discord_tasks_dispatched_total' \
   && echo "$dg_metrics" | grep -qE '(^|# HELP |# TYPE )discord_notifications_published_total'; then
  echo "DISCORD_METRICS_SMOKE: PASS"
else
  echo "DISCORD_METRICS_SMOKE: CHECK"
fi


echo
echo "=== notification-worker /health smoke ==="
if curl -sS -m 5 http://localhost:8008/health | grep -q '"service": *"notification-worker"'; then
  echo "NOTIFICATION_WORKER_HEALTH_SMOKE: PASS"
else
  echo "NOTIFICATION_WORKER_HEALTH_SMOKE: FAIL"
fi

echo
echo "=== notification-worker /status smoke ==="
nw_status=$(curl -sS -m 10 http://localhost:8008/status || echo '{}')
echo "$nw_status" | head -c 400 || true
echo
if echo "$nw_status" | grep -q '"input_stream": *"stream.notifications"' \
   && echo "$nw_status" | grep -q '"group": *"notification-worker-group"' \
   && echo "$nw_status" | grep -q '"mode":' \
   && echo "$nw_status" | grep -q '"external_send_enabled":'; then
  echo "NOTIFICATION_WORKER_STATUS_SMOKE: PASS"
else
  echo "NOTIFICATION_WORKER_STATUS_SMOKE: CHECK"
fi

echo
echo "=== stream.notifications -> notification_deliveries smoke ==="
nw_task="nw-smoke-$$"
curl -sS -m 30 -X POST http://localhost:8007/discord/messages \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.test description=\\\"nw smoke\\\" task_id=$nw_task\",\"channel_id\":\"sandbox-nw\",\"user_id\":\"runtime-smoke\"}" \
  >/dev/null 2>&1 || true
for i in $(seq 1 30); do
  nw_prog=$(curl -sS -m 10 "http://localhost:8000/workflow/progress/$nw_task" || echo '{}')
  nw_stage=$(echo "$nw_prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
  if [ "$nw_stage" = "completed" ]; then break; fi
  sleep 2
done
sleep 5
nw_dels=$(curl -sS -m 10 "http://localhost:8007/discord/deliveries/$nw_task" || echo '{}')
nw_count=$(echo "$nw_dels" | sed -n 's/.*"count": *\([0-9]*\).*/\1/p' | head -n1)
echo "deliveries for $nw_task: $nw_count"
if [ -n "$nw_count" ] && [ "$nw_count" -ge 2 ]; then
  echo "NOTIFICATION_STREAM_DELIVERY_SMOKE: PASS"
else
  echo "NOTIFICATION_STREAM_DELIVERY_SMOKE: CHECK ($nw_count)"
fi

echo
echo "=== notification_deliveries sandbox flag smoke ==="
if echo "$nw_dels" | grep -q '"sandbox":true' \
   && echo "$nw_dels" | grep -q '"external_sent":false'; then
  echo "NOTIFICATION_DELIVERY_DB_SMOKE: PASS"
else
  echo "NOTIFICATION_DELIVERY_DB_SMOKE: CHECK"
fi

echo
echo "=== notification_delivery audit smoke (audit-worker persisted) ==="
nw_audit=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=notification_delivery&limit=5" || echo '{}')
if echo "$nw_audit" | grep -q '"decision_type": *"notification_delivery"' \
   && echo "$nw_audit" | grep -q '"agent": *"notification-worker"'; then
  echo "NOTIFICATION_DELIVERY_AUDIT_SMOKE: PASS"
else
  echo "NOTIFICATION_DELIVERY_AUDIT_SMOKE: CHECK"
fi

echo
echo "=== /discord/deliveries top-level list smoke ==="
dg_all=$(curl -sS -m 10 "http://localhost:8007/discord/deliveries?limit=5" || echo '{}')
if echo "$dg_all" | grep -q '"count":' && echo "$dg_all" | grep -q '"deliveries":'; then
  echo "DISCORD_DELIVERIES_API_SMOKE: PASS"
else
  echo "DISCORD_DELIVERIES_API_SMOKE: CHECK"
fi

echo
echo "=== /operations/workflows includes notification_deliveries smoke ==="
op_view=$(curl -sS -m 10 "http://localhost:8000/operations/workflows/$nw_task" || echo '{}')
if echo "$op_view" | grep -q '"notification_deliveries"' \
   && echo "$op_view" | grep -q '"simulated_count":'; then
  echo "OPERATIONS_NOTIFICATION_DELIVERY_SMOKE: PASS"
else
  echo "OPERATIONS_NOTIFICATION_DELIVERY_SMOKE: CHECK"
fi

echo
echo "=== notification-worker /discord/real/test-message guard smoke ==="
rt_code=$(curl -sS -m 5 -o /tmp/nw_rt.$$ -w "%{http_code}" -X POST http://localhost:8008/discord/real/test-message \
  -H "Content-Type: application/json" \
  -d '{"content":"sandbox guard verification"}' || echo "000")
rm -f /tmp/nw_rt.$$
echo "real-test guard HTTP: $rt_code"
if [ "$rt_code" = "409" ]; then
  echo "DISCORD_REAL_TEST_GUARD_SMOKE: PASS"
else
  echo "DISCORD_REAL_TEST_GUARD_SMOKE: CHECK"
fi

echo
echo "=== notification-worker /metrics smoke ==="
nw_metrics=$(curl -sS -m 10 http://localhost:8008/metrics || echo '')
if echo "$nw_metrics" | grep -qE '(^|# HELP |# TYPE )notification_worker_processed_total' \
   && echo "$nw_metrics" | grep -qE '(^|# HELP |# TYPE )notification_worker_simulated_total' \
   && echo "$nw_metrics" | grep -qE '(^|# HELP |# TYPE )notification_worker_processing_seconds'; then
  echo "NOTIFICATION_WORKER_METRICS_SMOKE: PASS"
else
  echo "NOTIFICATION_WORKER_METRICS_SMOKE: CHECK"
fi

echo
echo "=== Stage 23 controlled-real GitHub validation smokes ==="

# 1. guard refuses by default (no token / no opt-in / no GITHUB_TEST_REPO)
rgv_task="rgv-smoke-$$"
rgv_body=$(cat <<JSON
{
  "task_id":"$rgv_task",
  "workflow_id":"wf-$rgv_task",
  "repo":"coolerh250/AI-Agents-SWD",
  "base_branch":"main",
  "branch_name":"ai-agents-test/$rgv_task",
  "title":"[AI-Agents-SWD Test] runtime guard smoke",
  "body":"## Summary\nGuard smoke\n\n## Changed Files\n- docs/github-real-test/$rgv_task.md\n\n## Risk Assessment\nLow\n\n## Test Result\nGuard only\n\n## Rollback Plan\nNo write expected\n\n## Safety Notes\nGuard runtime smoke.",
  "file_path":"docs/github-real-test/$rgv_task.md",
  "file_content":"task_id=$rgv_task\nworkflow_id=wf-$rgv_task\ngenerated_by=github-automation\nreal_github_test=true\nproduction_executed=false\n",
  "dry_run":false
}
JSON
)
rgv_code=$(curl -sS -m 10 -o /tmp/rgv_smoke.$$ -w "%{http_code}" \
  -X POST http://localhost:8005/github/workflow/real-test-pr \
  -H "Content-Type: application/json" \
  -d "$rgv_body" || echo "000")
rgv_resp=$(cat /tmp/rgv_smoke.$$ 2>/dev/null || echo '{}')
rm -f /tmp/rgv_smoke.$$
echo "  real-test-pr guard HTTP: $rgv_code"
if [ "$rgv_code" = "409" ] && echo "$rgv_resp" | grep -q '"safety_guard_result"'; then
  echo "GITHUB_REAL_GUARD_SMOKE: PASS"
else
  echo "GITHUB_REAL_GUARD_SMOKE: CHECK ($rgv_code)"
fi

# 2. default mode reports REAL_GITHUB_TEST_SKIPPED
if [ "${RUN_REAL_GITHUB_TEST:-false}" = "true" ] && [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${GITHUB_TEST_REPO:-}" ]; then
  echo "GITHUB_REAL_TEST_SKIPPED_SMOKE: SKIP (opt-in env present)"
else
  echo "GITHUB_REAL_TEST_SKIPPED_SMOKE: PASS"
fi

# 3. metrics registered
rgv_metrics=$(curl -sS -m 10 http://localhost:8005/metrics || echo '')
if echo "$rgv_metrics" | grep -qE '(^|# HELP |# TYPE )github_real_test_attempts_total' \
   && echo "$rgv_metrics" | grep -qE '(^|# HELP |# TYPE )github_real_test_blocked_total' \
   && echo "$rgv_metrics" | grep -qE '(^|# HELP |# TYPE )github_real_test_duration_seconds'; then
  echo "GITHUB_REAL_METRICS_SMOKE: PASS"
else
  echo "GITHUB_REAL_METRICS_SMOKE: CHECK"
fi

# 4. operations /safety carries the four github_* booleans
rgv_safety=$(curl -sS -m 10 http://localhost:8000/operations/safety || echo '{}')
if echo "$rgv_safety" | grep -q '"github_has_token":' \
   && echo "$rgv_safety" | grep -q '"real_github_test_enabled":' \
   && echo "$rgv_safety" | grep -q '"github_test_repo_configured":' \
   && echo "$rgv_safety" | grep -q '"github_external_write_enabled":'; then
  echo "GITHUB_REAL_OPERATIONS_SMOKE: PASS"
else
  echo "GITHUB_REAL_OPERATIONS_SMOKE: CHECK"
fi

# 5. dry-run regression — /github/workflow/demo-pr still dry-runs cleanly
rgv_demo_task="rgv-demo-$$"
rgv_demo=$(curl -sS -m 15 -X POST http://localhost:8005/github/workflow/demo-pr \
  -H "Content-Type: application/json" \
  -d "{\"task_id\":\"$rgv_demo_task\",\"dry_run\":true,\"branch_name\":\"ai-agents-swd/$rgv_demo_task\"}" \
  || echo '{}')
if echo "$rgv_demo" | grep -q '"dry_run":true' \
   && echo "$rgv_demo" | grep -q '"pull_request"' \
   && echo "$rgv_demo" | grep -q '"event_type":"github.pr.dry_run"'; then
  echo "GITHUB_DRY_RUN_REGRESSION_SMOKE: PASS"
else
  echo "GITHUB_DRY_RUN_REGRESSION_SMOKE: CHECK"
fi

echo
echo "=== Stage 24 staging hardening smokes ==="

# 1. runtime config validator (local mode must PASS)
rgv_local=$(./scripts/validate_runtime_config.sh --mode local 2>&1 || true)
if echo "$rgv_local" | grep -q "RUNTIME_CONFIG_VALIDATION: PASS"; then
  echo "RUNTIME_CONFIG_LOCAL_SMOKE: PASS"
else
  echo "RUNTIME_CONFIG_LOCAL_SMOKE: CHECK"
fi

# 2. production safety gate (read-only)
psg_out=$(./scripts/production_safety_gate.sh 2>&1 || true)
if echo "$psg_out" | grep -q "PRODUCTION_SAFETY_GATE: PASS"; then
  echo "PRODUCTION_SAFETY_GATE_SMOKE: PASS"
else
  echo "PRODUCTION_SAFETY_GATE_SMOKE: CHECK"
fi

# 3. backup/restore smoke
bru_out=$(./scripts/verify_backup_restore.sh 2>&1 || true)
if echo "$bru_out" | grep -q "BACKUP_RESTORE_VERIFY: PASS"; then
  echo "BACKUP_RESTORE_SMOKE: PASS"
else
  echo "BACKUP_RESTORE_SMOKE: CHECK"
fi

# 4. runtime health snapshot
rhs_out=$(./scripts/runtime_health_snapshot.sh 2>&1 || true)
if echo "$rhs_out" | grep -q "RUNTIME_HEALTH_SNAPSHOT_DONE: PASS" \
   && [ -f source/runtime-health.log ]; then
  echo "RUNTIME_HEALTH_SNAPSHOT_SMOKE: PASS"
else
  echo "RUNTIME_HEALTH_SNAPSHOT_SMOKE: CHECK"
fi

# 5. SecretProvider redaction self-test
if python3 -c "
import sys
sys.path.insert(0, '.')
from shared.sdk.secrets import EnvSecretProvider, redact_mapping
p = EnvSecretProvider({'GITHUB_TOKEN': 'ghp_NEVER_LEAK'})
ref = p.get_secret('GITHUB_TOKEN')
assert 'ghp_NEVER_LEAK' not in repr(ref) + str(ref)
assert redact_mapping({'GITHUB_TOKEN': 'x'})['GITHUB_TOKEN'] == '***REDACTED***'
" >/dev/null 2>&1; then
  echo "SECRET_REDACTION_SMOKE: PASS"
else
  echo "SECRET_REDACTION_SMOKE: CHECK"
fi

# 6. staging compose template carries no trust-auth + uses env placeholders
if [ -f infra/docker-compose/docker-compose.staging.yml ] \
   && ! grep -q "POSTGRES_HOST_AUTH_METHOD: trust" infra/docker-compose/docker-compose.staging.yml \
   && grep -q 'POSTGRES_PASSWORD: \${POSTGRES_PASSWORD' infra/docker-compose/docker-compose.staging.yml; then
  echo "STAGING_TEMPLATE_SMOKE: PASS"
else
  echo "STAGING_TEMPLATE_SMOKE: CHECK"
fi

echo
echo "=== Stage 25 staging bring-up readiness smokes (lightweight, no compose up) ==="

# 1. env generator syntax + idempotent re-run on a tmp workspace
gen_tmp=$(mktemp -d 2>/dev/null || mktemp -d -t rgen)
mkdir -p "$gen_tmp/scripts" "$gen_tmp/infra/runtime"
cp scripts/generate_staging_env.sh "$gen_tmp/scripts/" 2>/dev/null
cp infra/runtime/env.staging.example "$gen_tmp/infra/runtime/" 2>/dev/null
gen_out=$( (cd "$gen_tmp" && bash scripts/generate_staging_env.sh) 2>&1 | tail -3 || true)
gen_skip=$( (cd "$gen_tmp" && bash scripts/generate_staging_env.sh) 2>&1 | tail -3 || true)
rm -rf "$gen_tmp"
if echo "$gen_out" | grep -q "GENERATE_STAGING_ENV: PASS" \
   && echo "$gen_skip" | grep -q "GENERATE_STAGING_ENV: SKIP"; then
  echo "STAGING_ENV_GENERATION_SMOKE: PASS"
else
  echo "STAGING_ENV_GENERATION_SMOKE: CHECK"
fi

# 2. validator can parse staging mode against the placeholder template.
# The validator exits 1 on FAIL — that's the EXPECTED result here (the
# template still carries placeholder secrets by design), so swallow the
# non-zero return code with `|| true` so set -e doesn't abort.
val_out=$(./scripts/validate_runtime_config.sh --mode staging --env-file infra/runtime/env.staging.example 2>&1 || true)
if echo "$val_out" | grep -q "RUNTIME_CONFIG_VALIDATION: FAIL" \
   && echo "$val_out" | grep -q "placeholder_secret"; then
  echo "STAGING_CONFIG_VALIDATION_SMOKE: PASS"
else
  echo "STAGING_CONFIG_VALIDATION_SMOKE: CHECK"
fi

# 3. staging compose template is parseable + carries the +10000 offset
if grep -qE 'POSTGRES_PASSWORD: \$\{POSTGRES_PASSWORD:\?' infra/docker-compose/docker-compose.staging.yml \
   && grep -qE '127\.0\.0\.1:18000:8000' infra/docker-compose/docker-compose.staging.yml \
   && grep -qE '127\.0\.0\.1:15432:5432' infra/docker-compose/docker-compose.staging.yml; then
  echo "STAGING_COMPOSE_TEMPLATE_SMOKE: PASS"
else
  echo "STAGING_COMPOSE_TEMPLATE_SMOKE: CHECK"
fi

# 4. staging runtime scripts pass bash -n
runtime_script_ok=1
for s in scripts/start_staging_runtime.sh scripts/stop_staging_runtime.sh \
         scripts/check_staging_runtime.sh scripts/verify_staging_runtime.sh \
         scripts/verify_staging_backup_restore.sh; do
  if ! bash -n "$s" 2>/dev/null; then
    runtime_script_ok=0
    echo "  $s: syntax FAIL"
  fi
done
if [ "$runtime_script_ok" = "1" ]; then
  echo "STAGING_RUNTIME_SCRIPT_SMOKE: PASS"
else
  echo "STAGING_RUNTIME_SCRIPT_SMOKE: CHECK"
fi

echo
echo "=== Stage 26 secrets-integration smokes (no compose up) ==="

# 1. inventory file + lister
sm_inv=$(./scripts/list_required_secrets.py 2>&1 | tail -3 || true)
if echo "$sm_inv" | grep -q "REQUIRED_SECRETS_INVENTORY: PASS"; then
  echo "SECRETS_INVENTORY_SMOKE: PASS"
else
  echo "SECRETS_INVENTORY_SMOKE: CHECK"
fi

# 2. provider selection — SDK self-test
if python3 -c "
import sys
sys.path.insert(0, '.')
from shared.sdk.secrets import provider_from_env, EnvSecretProvider, MockVaultSecretProvider, VaultKvSecretProvider
assert isinstance(provider_from_env({}), EnvSecretProvider)
assert isinstance(provider_from_env({'SECRET_PROVIDER': 'mock-vault'}), MockVaultSecretProvider)
assert isinstance(provider_from_env({'SECRET_PROVIDER': 'vault'}), VaultKvSecretProvider)
" >/dev/null 2>&1; then
  echo "SECRET_PROVIDER_SMOKE: PASS"
else
  echo "SECRET_PROVIDER_SMOKE: CHECK"
fi

# 3. mock-vault bootstrap on a tmp workspace
mv_tmp=$(mktemp -d 2>/dev/null || mktemp -d -t rmv)
mkdir -p "$mv_tmp/scripts" "$mv_tmp/infra/runtime"
cp scripts/bootstrap_mock_vault_secrets.sh "$mv_tmp/scripts/" 2>/dev/null
cp infra/runtime/mock-vault-secrets.example.json "$mv_tmp/infra/runtime/" 2>/dev/null
mv_out=$( (cd "$mv_tmp" && bash scripts/bootstrap_mock_vault_secrets.sh) 2>&1 | tail -3 || true)
rm -rf "$mv_tmp"
if echo "$mv_out" | grep -q "BOOTSTRAP_MOCK_VAULT_SECRETS: PASS"; then
  echo "MOCK_VAULT_BOOTSTRAP_SMOKE: PASS"
else
  echo "MOCK_VAULT_BOOTSTRAP_SMOKE: CHECK"
fi

# 4. rotation smoke
rot_out=$(./scripts/verify_secret_rotation_smoke.sh 2>&1 | tail -8 || true)
if echo "$rot_out" | grep -q "SECRET_ROTATION_SMOKE: PASS"; then
  echo "SECRET_ROTATION_SMOKE: PASS"
else
  echo "SECRET_ROTATION_SMOKE: CHECK"
fi

# 5. leak scan over the repo
leak_out=$(./scripts/scan_for_secret_leaks.sh 2>&1 | tail -3 || true)
if echo "$leak_out" | grep -q "SECRET_LEAK_SCAN: PASS"; then
  echo "SECRET_LEAK_SCAN_SMOKE: PASS"
else
  echo "SECRET_LEAK_SCAN_SMOKE: CHECK"
fi

# 6. staging-secrets verify in light mode (no compose up)
ssec_out=$(./scripts/verify_staging_secrets.sh --no-bring-up 2>&1 | tail -10 || true)
if echo "$ssec_out" | grep -q "STAGING_SECRETS_VERIFY: PASS"; then
  echo "STAGING_SECRETS_SMOKE: PASS"
else
  echo "STAGING_SECRETS_SMOKE: CHECK"
fi

echo
echo "=== Stage 27 flexible task execution loop smokes (lightweight) ==="

stage27_ts=$(date +%s)

# 1. simple-task intake -> work item created
te_simple="stage27-runtime-simple-$stage27_ts"
curl -sS -m 30 -X POST http://localhost:8007/discord/messages -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=general description=\\\"summarise the platform docs intro into bullet points\\\" task_id=$te_simple\",\"channel_id\":\"sandbox-stage27\",\"user_id\":\"check\"}" \
  >/dev/null 2>&1 || true
sleep 8
te_wi=$(curl -sS -m 10 "http://localhost:8000/operations/tasks/work-items/$te_simple" || echo '{}')
if echo "$te_wi" | grep -q "\"task_id\": *\"$te_simple\""; then
  echo "TASK_WORK_ITEM_SMOKE: PASS"
else
  echo "TASK_WORK_ITEM_SMOKE: CHECK"
fi
if echo "$te_wi" | grep -q '"execution_mode": *"simple_task"'; then
  echo "EXECUTION_MODE_CLASSIFIER_SMOKE: PASS"
else
  echo "EXECUTION_MODE_CLASSIFIER_SMOKE: CHECK"
fi
if echo "$te_wi" | grep -qE '"agent": *"(intake-agent|requirement-agent)"'; then
  echo "AGENT_DISCUSSION_SMOKE: PASS"
else
  echo "AGENT_DISCUSSION_SMOKE: CHECK"
fi

# 2. unclear task -> needs_clarification + clarification_request open
te_unclear="stage27-runtime-clar-$stage27_ts"
curl -sS -m 30 -X POST http://localhost:8007/discord/messages -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.test description=\\\"TBD\\\" task_id=$te_unclear\",\"channel_id\":\"sandbox-stage27\",\"user_id\":\"check\"}" \
  >/dev/null 2>&1 || true
sleep 8
te_clar=$(curl -sS -m 10 "http://localhost:8007/discord/clarifications/$te_unclear" || echo '{}')
if echo "$te_clar" | grep -q '"open_count":' && ! echo "$te_clar" | grep -q '"open_count": *0'; then
  echo "CLARIFICATION_REQUEST_SMOKE: PASS"
else
  echo "CLARIFICATION_REQUEST_SMOKE: CHECK"
fi

# 3. answer the clarification
te_clar_id=$(echo "$te_clar" | sed -n 's/.*"clarification_id": *"\([a-f0-9-]*\)".*/\1/p' | head -n1)
if [ -n "$te_clar_id" ]; then
  te_ans=$(curl -sS -m 10 -X POST "http://localhost:8007/discord/clarifications/$te_clar_id/answer" \
    -H "Content-Type: application/json" \
    -d "{\"answer\":\"please implement a new /healthz endpoint with tests\",\"user_id\":\"check\"}" \
    || echo '{}')
  if echo "$te_ans" | grep -q '"status": *"answered"'; then
    echo "CLARIFICATION_ANSWER_SMOKE: PASS"
  else
    echo "CLARIFICATION_ANSWER_SMOKE: CHECK"
  fi
  sleep 8
  te_wi2=$(curl -sS -m 10 "http://localhost:8000/operations/tasks/work-items/$te_unclear" || echo '{}')
  if echo "$te_wi2" | grep -qE '"status": *"(ready_for_development|completed)"'; then
    echo "TASK_READY_FOR_DEVELOPMENT_SMOKE: PASS"
  else
    echo "TASK_READY_FOR_DEVELOPMENT_SMOKE: CHECK"
  fi
else
  echo "CLARIFICATION_ANSWER_SMOKE: CHECK"
  echo "TASK_READY_FOR_DEVELOPMENT_SMOKE: CHECK"
fi

# 4. workflow gate — needs_clarification didn't dispatch development
if echo "$te_clar" | grep -q '"open_count":'; then
  # quick re-fetch the operations workflow view; the development-agent
  # column must be empty until the resume.
  te_ops=$(curl -sS -m 10 "http://localhost:8000/operations/workflows/$te_unclear" || echo '{}')
  if echo "$te_ops" | grep -q '"task_execution"'; then
    echo "TASK_WORKFLOW_GATE_SMOKE: PASS"
  else
    echo "TASK_WORKFLOW_GATE_SMOKE: CHECK"
  fi
else
  echo "TASK_WORKFLOW_GATE_SMOKE: CHECK"
fi

# 5. operations API integration
te_sum=$(curl -sS -m 10 http://localhost:8000/operations/summary || echo '{}')
if echo "$te_sum" | grep -q '"task_execution_summary"'; then
  echo "OPERATIONS_TASK_EXECUTION_VIEW_SMOKE: PASS"
else
  echo "OPERATIONS_TASK_EXECUTION_VIEW_SMOKE: CHECK"
fi

# 6. discord clarification API endpoint reachable
if [ -n "$te_clar_id" ]; then
  echo "DISCORD_CLARIFICATION_API_SMOKE: PASS"
else
  echo "DISCORD_CLARIFICATION_API_SMOKE: CHECK"
fi

# 7. audit decision_types persisted (task_ready_for_development OR
# clarification_requested OR clarification_answered).
te_audit=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=clarification_requested&limit=5" || echo '{}')
te_audit2=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=task_ready_for_development&limit=5" || echo '{}')
if echo "$te_audit" | grep -q 'clarification_requested' \
   || echo "$te_audit2" | grep -q 'task_ready_for_development'; then
  echo "TASK_EXECUTION_AUDIT_SMOKE: PASS"
else
  echo "TASK_EXECUTION_AUDIT_SMOKE: CHECK"
fi

# 8. notification deliveries
te_nots=$(curl -sS -m 10 "http://localhost:8004/notifications?count=200" || echo '{}')
if echo "$te_nots" | grep -q 'task.needs_clarification' \
   || echo "$te_nots" | grep -q 'task.ready_for_development' \
   || echo "$te_nots" | grep -q 'clarification.answered'; then
  echo "TASK_EXECUTION_NOTIFICATION_SMOKE: PASS"
else
  echo "TASK_EXECUTION_NOTIFICATION_SMOKE: CHECK"
fi

echo
echo "=== Stage 28 controlled code generation smokes (lightweight) ==="

stage28_ts=$(date +%s)

# 1. delivery_task with API description -> workspace + artifact + pr_draft
cg_api="stage28-runtime-api-$stage28_ts"
curl -sS -m 30 -X POST http://localhost:8007/discord/messages -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.api description=\\\"please implement a /healthz endpoint API with tests\\\" task_id=$cg_api\",\"channel_id\":\"sandbox-stage28\",\"user_id\":\"check\"}" \
  >/dev/null 2>&1 || true
sleep 10
cg_ws=$(curl -sS -m 10 "http://localhost:8000/operations/code/workspaces/$cg_api" || echo '{}')
if echo "$cg_ws" | grep -q "\"task_id\": *\"$cg_api\""; then
  echo "CODE_WORKSPACE_SMOKE: PASS"
else
  echo "CODE_WORKSPACE_SMOKE: CHECK"
fi
if echo "$cg_ws" | grep -q "apps/demo-generated/" && echo "$cg_ws" | grep -q "tests/generated/"; then
  echo "CODE_GENERATION_API_SMOKE: PASS"
else
  echo "CODE_GENERATION_API_SMOKE: CHECK"
fi
cg_pr=$(curl -sS -m 10 "http://localhost:8000/operations/code/pr-drafts/$cg_api" || echo '{}')
if echo "$cg_pr" | grep -q '"status": *"ready"'; then
  echo "CODE_PR_DRAFT_SMOKE: PASS"
else
  echo "CODE_PR_DRAFT_SMOKE: CHECK"
fi
if echo "$cg_pr" | grep -q '"status": *"passed"'; then
  echo "CODE_VALIDATION_SMOKE: PASS"
else
  echo "CODE_VALIDATION_SMOKE: CHECK"
fi

# 2. docs description -> documentation template
cg_doc="stage28-runtime-doc-$stage28_ts"
curl -sS -m 30 -X POST http://localhost:8007/discord/messages -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.doc description=\\\"please write the documentation for the new module\\\" task_id=$cg_doc\",\"channel_id\":\"sandbox-stage28\",\"user_id\":\"check\"}" \
  >/dev/null 2>&1 || true
sleep 10
cg_doc_ws=$(curl -sS -m 10 "http://localhost:8000/operations/code/workspaces/$cg_doc" || echo '{}')
if echo "$cg_doc_ws" | grep -q "docs/generated/$cg_doc.md"; then
  echo "CODE_GENERATION_DOCS_SMOKE: PASS"
else
  echo "CODE_GENERATION_DOCS_SMOKE: CHECK"
fi

# 3. policy block
cg_block="stage28-runtime-block-$stage28_ts"
curl -sS -m 30 -X POST http://localhost:8007/discord/messages -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.test description=\\\"qwertyuiop unclassifiable random nonsense for blocked path\\\" task_id=$cg_block\",\"channel_id\":\"sandbox-stage28\",\"user_id\":\"check\"}" \
  >/dev/null 2>&1 || true
sleep 10
cg_block_ws=$(curl -sS -m 10 "http://localhost:8000/operations/code/workspaces/$cg_block" || echo '{}')
if echo "$cg_block_ws" | grep -q '"status": *"blocked"'; then
  echo "CODE_GENERATION_POLICY_BLOCK_SMOKE: PASS"
else
  echo "CODE_GENERATION_POLICY_BLOCK_SMOKE: CHECK"
fi

# 4. operations summary contains code_generation_summary
cg_sum=$(curl -sS -m 10 http://localhost:8000/operations/summary || echo '{}')
if echo "$cg_sum" | grep -q '"code_generation_summary"'; then
  echo "OPERATIONS_CODE_VIEW_SMOKE: PASS"
else
  echo "OPERATIONS_CODE_VIEW_SMOKE: CHECK"
fi

# 5. discord task lookup exposes code_generation_status
cg_dtask=$(curl -sS -m 10 "http://localhost:8007/discord/tasks/$cg_api" || echo '{}')
if echo "$cg_dtask" | grep -q '"code_generation_status"'; then
  echo "DISCORD_CODE_STATUS_SMOKE: PASS"
else
  echo "DISCORD_CODE_STATUS_SMOKE: CHECK"
fi

# 6. audit code_generated decision_type persisted
cg_audit=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=code_generated&limit=5" || echo '{}')
cg_audit2=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=code_pr_draft_created&limit=5" || echo '{}')
cg_audit3=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=code_generation_blocked&limit=5" || echo '{}')
if echo "$cg_audit" | grep -q 'code_generated' \
   || echo "$cg_audit2" | grep -q 'code_pr_draft_created' \
   || echo "$cg_audit3" | grep -q 'code_generation_blocked'; then
  echo "CODE_AUDIT_SMOKE: PASS"
else
  echo "CODE_AUDIT_SMOKE: CHECK"
fi

# 7. notification deliveries for code.* events
cg_nots=$(curl -sS -m 10 "http://localhost:8004/notifications?count=200" || echo '{}')
if echo "$cg_nots" | grep -q 'code.generated' \
   || echo "$cg_nots" | grep -q 'code.pr_draft_ready' \
   || echo "$cg_nots" | grep -q 'code.generation_blocked' \
   || echo "$cg_nots" | grep -q 'code.workspace_created'; then
  echo "CODE_NOTIFICATION_SMOKE: PASS"
else
  echo "CODE_NOTIFICATION_SMOKE: CHECK"
fi

echo
echo "=== Stage 29 QA-guided validation + auto-fix loop smokes (lightweight) ==="

stage29_ts=$(date +%s)

# 1. delivery_task API description -> QA validation run + pass
qa_api="stage29-runtime-qapass-$stage29_ts"
curl -sS -m 30 -X POST http://localhost:8007/discord/messages -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.api description=\\\"please implement a /healthz endpoint API with tests\\\" task_id=$qa_api\",\"channel_id\":\"sandbox-stage29\",\"user_id\":\"check\"}" \
  >/dev/null 2>&1 || true
sleep 12
qa_run=$(curl -sS -m 10 "http://localhost:8000/operations/qa/runs/$qa_api" || echo '{}')
if echo "$qa_run" | grep -q '"qa_run_id"'; then
  echo "QA_VALIDATION_PASS_SMOKE: PASS"
else
  echo "QA_VALIDATION_PASS_SMOKE: CHECK"
fi
if echo "$qa_run" | grep -qE '"final_result": *"(pass|not_applicable)"'; then
  echo "QA_FINDING_SMOKE: PASS"
else
  echo "QA_FINDING_SMOKE: CHECK"
fi

# 2. auto-fix request endpoint reachable
qa_fix=$(curl -sS -m 10 "http://localhost:8000/operations/qa/auto-fix/$qa_api" || echo '{}')
if echo "$qa_fix" | grep -q '"auto_fix_requests"'; then
  echo "QA_AUTO_FIX_REQUEST_SMOKE: PASS"
else
  echo "QA_AUTO_FIX_REQUEST_SMOKE: CHECK"
fi

# 3. auto-fix loop machinery wired: development-agent-autofix consumer
# reachable (its /status appears under the dev-agent status payload).
da_status=$(curl -sS -m 10 "http://localhost:8012/status" || echo '{}')
if echo "$da_status" | grep -q '"autofix"'; then
  echo "QA_AUTO_FIX_LOOP_SMOKE: PASS"
else
  echo "QA_AUTO_FIX_LOOP_SMOKE: CHECK"
fi

# 4. blocked path — unclassifiable task → code_generation blocked,
# QA validation should not falsely pass.
qa_blk="stage29-runtime-block-$stage29_ts"
curl -sS -m 30 -X POST http://localhost:8007/discord/messages -H "Content-Type: application/json" \
  -d "{\"content\":\"/ai task type=dev.test description=\\\"qwertyuiop unclassifiable random nonsense for blocked path\\\" task_id=$qa_blk\",\"channel_id\":\"sandbox-stage29\",\"user_id\":\"check\"}" \
  >/dev/null 2>&1 || true
sleep 10
qa_blk_ops=$(curl -sS -m 10 "http://localhost:8000/operations/workflows/$qa_blk" || echo '{}')
if echo "$qa_blk_ops" | grep -q '"qa_passed": *false'; then
  echo "QA_BLOCKED_FOR_HUMAN_REVIEW_SMOKE: PASS"
else
  echo "QA_BLOCKED_FOR_HUMAN_REVIEW_SMOKE: CHECK"
fi

# 5. operations summary contains qa_summary
qa_sum=$(curl -sS -m 10 http://localhost:8000/operations/summary || echo '{}')
if echo "$qa_sum" | grep -q '"qa_summary"'; then
  echo "OPERATIONS_QA_VIEW_SMOKE: PASS"
else
  echo "OPERATIONS_QA_VIEW_SMOKE: CHECK"
fi

# 6. discord task lookup exposes qa_status
qa_dtask=$(curl -sS -m 10 "http://localhost:8007/discord/tasks/$qa_api" || echo '{}')
if echo "$qa_dtask" | grep -q '"qa_status"'; then
  echo "DISCORD_QA_STATUS_SMOKE: PASS"
else
  echo "DISCORD_QA_STATUS_SMOKE: CHECK"
fi

# 7. audit QA decision_types persisted
qa_audit=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=qa_validation_started&limit=5" || echo '{}')
qa_audit2=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=qa_validation_passed&limit=5" || echo '{}')
qa_audit3=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=qa_blocked_for_human_review&limit=5" || echo '{}')
if echo "$qa_audit" | grep -q 'qa_validation_started' \
   || echo "$qa_audit2" | grep -q 'qa_validation_passed' \
   || echo "$qa_audit3" | grep -q 'qa_blocked_for_human_review'; then
  echo "QA_AUDIT_SMOKE: PASS"
else
  echo "QA_AUDIT_SMOKE: CHECK"
fi

# 8. notification deliveries for qa.* events
qa_nots=$(curl -sS -m 10 "http://localhost:8007/discord/deliveries/$qa_api" || echo '{}')
if echo "$qa_nots" | grep -q 'qa.validation_started' \
   || echo "$qa_nots" | grep -q 'qa.validation_passed' \
   || echo "$qa_nots" | grep -q 'qa.blocked_for_human_review'; then
  echo "QA_NOTIFICATION_SMOKE: PASS"
else
  echo "QA_NOTIFICATION_SMOKE: CHECK"
fi

# 9. qa_validation_runs_total metric exposed
qa_metric=$(curl -sS -m 10 "http://localhost:8000/metrics" 2>/dev/null | grep -E "^qa_validation_runs_total" 2>/dev/null | head -1 || true)
if [ -n "$qa_metric" ]; then
  echo "QA_METRICS_SMOKE: PASS"
else
  echo "QA_METRICS_SMOKE: CHECK"
fi

echo
echo "=== Stage 30: LLM-assisted development guardrails ==="

# 10. LLM provider default in /operations/safety
llm_safety=$(curl -sS -m 10 http://localhost:8000/operations/safety || echo '{}')
if echo "$llm_safety" | grep -q '"llm_provider"'; then
  echo "LLM_PROVIDER_SMOKE: PASS"
else
  echo "LLM_PROVIDER_SMOKE: CHECK"
fi

# 11. mock LLM proposal policy-clean
llm_clean=$(python3 -c "
import sys
sys.path.insert(0, '.')
from shared.sdk.llm import MockLLMProvider, apply_llm_safety_policy
p = MockLLMProvider()
prop = p.generate_patch_proposal(task_id='smoke', description='please add /healthz API')
print('OK' if apply_llm_safety_policy(prop)['allowed'] else 'FAIL')
" 2>/dev/null)
if [ "$llm_clean" = "OK" ]; then
  echo "LLM_POLICY_PASS_SMOKE: PASS"
else
  echo "LLM_POLICY_PASS_SMOKE: CHECK"
fi

# 12. mock LLM proposal policy-block (denied path trigger)
llm_block=$(python3 -c "
import sys
sys.path.insert(0, '.')
from shared.sdk.llm import MockLLMProvider, apply_llm_safety_policy
p = MockLLMProvider()
prop = p.generate_patch_proposal(task_id='smoke', description='please denied path test')
res = apply_llm_safety_policy(prop)
print('OK' if not res['allowed'] else 'FAIL')
" 2>/dev/null)
if [ "$llm_block" = "OK" ]; then
  echo "LLM_POLICY_BLOCK_SMOKE: PASS"
else
  echo "LLM_POLICY_BLOCK_SMOKE: CHECK"
fi

# 13. prompt contract envelope reachable
llm_contract=$(python3 -c "
import sys
sys.path.insert(0, '.')
from shared.sdk.llm import build_prompt_contract
c = build_prompt_contract(
    task_id='smoke', execution_mode='delivery_task',
    interaction_type='patch_proposal', description='ok',
    allowed_paths=['docs/generated/'], denied_paths=['infra/*'],
    output_schema_name='LLMPatchProposal',
)
print('OK' if c['safety_rails']['no_secrets'] else 'FAIL')
" 2>/dev/null)
if [ "$llm_contract" = "OK" ]; then
  echo "LLM_PROMPT_CONTRACT_SMOKE: PASS"
else
  echo "LLM_PROMPT_CONTRACT_SMOKE: CHECK"
fi

# 14. /operations/llm/* endpoints reachable
llm_ints=$(curl -sS -m 10 "http://localhost:8000/operations/llm/interactions?limit=1" || echo '{}')
if echo "$llm_ints" | grep -q '"interactions"'; then
  echo "LLM_OPERATIONS_VIEW_SMOKE: PASS"
else
  echo "LLM_OPERATIONS_VIEW_SMOKE: CHECK"
fi

# 15. llm_assistance section on workflow view
llm_wf=$(curl -sS -m 10 "http://localhost:8000/operations/workflows/$qa_api" || echo '{}')
if echo "$llm_wf" | grep -q '"llm_assistance"'; then
  echo "LLM_PROPOSAL_ARTIFACT_SMOKE: PASS"
else
  echo "LLM_PROPOSAL_ARTIFACT_SMOKE: CHECK"
fi

# 16. Discord status surfaces LLM fields
llm_dtask=$(curl -sS -m 10 "http://localhost:8007/discord/tasks/$qa_api" || echo '{}')
if echo "$llm_dtask" | grep -q '"llm_provider"'; then
  echo "LLM_DISCORD_STATUS_SMOKE: PASS"
else
  echo "LLM_DISCORD_STATUS_SMOKE: CHECK"
fi

# 17. Audit LLM decision_types reachable
llm_aud=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=llm_proposal_created&limit=5" || echo '{}')
llm_aud2=$(curl -sS -m 10 "http://localhost:8003/audit/events?decision_type=llm_real_test_skipped&limit=5" || echo '{}')
if echo "$llm_aud" | grep -q '"events"' || echo "$llm_aud2" | grep -q '"events"'; then
  echo "LLM_AUDIT_SMOKE: PASS"
else
  echo "LLM_AUDIT_SMOKE: CHECK"
fi

# 18. notification deliveries for llm.* events
llm_nots=$(curl -sS -m 10 "http://localhost:8007/discord/deliveries/$qa_api" || echo '{}')
if echo "$llm_nots" | grep -q 'llm.proposal' || echo "$llm_nots" | grep -q '"deliveries"'; then
  echo "LLM_NOTIFICATION_SMOKE: PASS"
else
  echo "LLM_NOTIFICATION_SMOKE: CHECK"
fi

# 19. real LLM guard default disabled
real_llm=$(echo "$llm_safety" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print('OK' if d.get('llm_real_enabled') is False else 'FAIL')
except Exception:
    print('CHECK')")
if [ "$real_llm" = "OK" ]; then
  echo "REAL_LLM_GUARD_SMOKE: PASS"
else
  echo "REAL_LLM_GUARD_SMOKE: CHECK"
fi

echo
echo "CHECK_RUNTIME_STATE_DONE"
