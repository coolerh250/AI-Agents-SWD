# AI Agents SWD — Manual Verification Guide

Copy-paste manual verification for a human operator on the `10.0.1.31`
test server. **Local/test only — no production action.**

> Safety contract: nothing below contacts a real cloud / GitHub / Slack
> / Kubernetes / LLM API, sends a real alert, or modifies a production
> resource. Alertmanager stays on the null receiver; the platform never
> sets `production_executed = true`.

---

## 0. Prerequisites

* SSH access to the test server (profile `aiagent-swd`,
  static IP `10.0.1.31`).
* Repository checked out at `/home/itadmin/AI-Agents-SWD`.
* Docker engine + Compose v2 installed.
* No real secrets in the environment — Vault runs in dev mode.

---

## 1. Connect & sync

```
ssh aiagent-swd
cd /home/itadmin/AI-Agents-SWD
git pull --ff-only
git log -1 --oneline
```

The latest commit hash should match what was just pushed to `main`.

---

## 2. Bring runtime up

```
docker compose -f infra/docker-compose/docker-compose.yml ps
docker compose -f infra/docker-compose/docker-compose.yml build
docker compose -f infra/docker-compose/docker-compose.yml up -d
docker compose -f infra/docker-compose/docker-compose.yml \
  up -d --force-recreate prometheus grafana alertmanager tempo
```

Wait ~20 seconds for healthchecks to settle, then re-run
`docker compose ... ps` and confirm every service is `running (healthy)`.

---

## 3. Run the test suite

```
source .venv/bin/activate
pip install -r requirements.txt
./scripts/run_tests.sh
```

Expected: `pytest` all green; `ruff`, `black --check`, and `mypy` clean.

---

## 4. Run the runtime smoke battery

```
./scripts/check_runtime_state.sh
```

Expected: every `*_SMOKE` line ends in `PASS` and the script prints
`CHECK_RUNTIME_STATE_DONE`.

---

## 5. Verify tracing backend

```
./scripts/verify_tracing_backend.sh
```

Expected: `TEMPO_READY: PASS`, `OTLP_HTTP_ENDPOINT: PASS`,
`GRAFANA_TEMPO_DATASOURCE: PASS`, `VERIFY_TRACING_BACKEND_DONE`.

---

## 6. Verify end-to-end trace flow

```
./scripts/verify_trace_flow.sh
```

Expected: `TRACE_FLOW_SMOKE: PASS (trace_id=... covers all 7 services)`
and `VERIFY_TRACE_FLOW_DONE`.

---

## 7. Verify alerting

```
./scripts/verify_alerting.sh
```

Expected: `ALERTMANAGER_HEALTHY: PASS`,
`PROMETHEUS_RULES_LOADED: PASS`, `PROMETHEUS_RULES_NAMES: PASS`,
`ALERTMANAGER_OFFHOST_RECEIVER: PASS (null receiver only)`,
`VERIFY_ALERTING_DONE`.

---

## 8. Verify incident flow

```
./scripts/verify_incident_flow.sh
```

Expected: `INCIDENT_FLOW_SMOKE: PASS` and `VERIFY_INCIDENT_FLOW_DONE`.

---

## 9. Run the full platform observability verification

```
./scripts/verify_platform_observability.sh
```

Expected last lines:

```
CHECK_RUNTIME_STATE: PASS
VERIFY_TRACING_BACKEND: PASS
VERIFY_TRACE_FLOW: PASS
VERIFY_ALERTING: PASS
VERIFY_INCIDENT_FLOW: PASS
PLATFORM_OBSERVABILITY_VERIFY: PASS
VERIFY_PLATFORM_OBSERVABILITY_DONE
```

---

## 10. Spot-check health endpoints

```
for p in 8000 8001 8002 8003 8004 8010 8011 8012 8013 8014 8015; do
  printf "  :%s -> %s\n" "$p" "$(curl -sS -o /dev/null -w '%{http_code}' -m 5 http://localhost:$p/health)"
done
```

Every line should print `200`.

---

## 11. Build a workflow and watch it complete

```
ts=$(date +%s)
task_id="manual-verify-$ts"
curl -sS -m 30 -X POST http://localhost:8004/intake/mock \
  -H 'Content-Type: application/json' \
  -d "{\"task_id\":\"$task_id\",\"request\":{\"type\":\"dev.test\",\"description\":\"manual verify\"}}"

# Watch progress until completed
for i in $(seq 1 20); do
  curl -sS "http://localhost:8000/workflow/progress/$task_id" \
    | python3 -m json.tool | head -n 30
  sleep 2
done
```

The final progress payload must show `"current_stage":"completed"` and
a non-empty `completed_agents` array containing all five agents.

---

## 12. Inspect the workflow timeline

```
curl -sS "http://localhost:8000/workflow/timeline/$task_id" \
  | python3 -m json.tool | head -n 60
```

Expected keys: `agent_timeline`, `traces`, `workflow_id`, `task_id`.

---

## 13. Open Grafana

* URL: `http://10.0.1.31:3000`
* Dashboards → `AI Agents SWD Platform`.
* Confirm: workflow / agent / retry panels populated, Active alerts
  (firing) stat panel visible, Service health (up per job) table
  visible, Active alerts over time timeseries visible.

---

## 14. Inspect Prometheus

```
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | head -n 40
curl -s http://localhost:9090/api/v1/rules   | python3 -m json.tool | head -n 60
curl -s http://localhost:9090/api/v1/alerts  | python3 -m json.tool | head -n 40
```

Every target must be `"health":"up"` and at least four `aiagents.*`
rule groups must be loaded.

---

## 15. Query Tempo for the manual trace

```
trace_id=$(curl -s "http://localhost:8000/workflow/progress/$task_id" \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('trace_id',''))")
echo "trace_id=$trace_id"
sleep 6
curl -s "http://localhost:3200/api/traces/$trace_id" | head -c 1500
```

The response must include `service.name` entries for the seven services
(`communication-gateway`, `orchestrator`, `intake-agent`,
`requirement-agent`, `development-agent`, `qa-agent`, `devops-agent`).

---

## 16. Drive an incident

```
fail_task="manual-incident-$(date +%s)"
curl -sS -m 30 -X POST http://localhost:8004/intake/mock \
  -H 'Content-Type: application/json' \
  -d "{\"task_id\":\"$fail_task\",\"request\":{\"type\":\"dev.test\",\"simulate_failure\":true}}"

# Poll until the incident exists
for i in $(seq 1 30); do
  curl -sS "http://localhost:8000/incidents?task_id=$fail_task" \
    | python3 -m json.tool | head -n 25
  sleep 2
done
```

Then:

```
inc_id=$(curl -sS "http://localhost:8000/incidents?task_id=$fail_task" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['incidents'][0]['incident_id'])")
echo "inc_id=$inc_id"
curl -sS -X POST "http://localhost:8000/incidents/$inc_id/ack"     | python3 -m json.tool
curl -sS -X POST "http://localhost:8000/incidents/$inc_id/resolve" | python3 -m json.tool
```

And confirm the workflow flipped to `failed`:

```
curl -sS "http://localhost:8000/workflow/$fail_task" \
  | python3 -m json.tool | grep -E '"stage"|"status"|"production_executed"'
```

`stage` must be `failed`, `status` must be `failed`, and
`production_executed` must be `false`.

---

## 17. Confirm `production_executed = false` across all deployments

```
docker compose -f infra/docker-compose/docker-compose.yml \
  exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT COUNT(*) FROM deployment_records
    WHERE metadata->>'production_executed'='true' OR environment='production';"
```

Expected output: `0`.

---

## 17a. Verify the unified audit path (Stage 19)

The audit-worker consumes `stream.audit` and writes `audit_logs`:

```
curl -sS http://localhost:8006/health
curl -sS http://localhost:8006/status | python3 -m json.tool
curl -sS http://localhost:8006/metrics | grep audit_worker_
docker compose -f infra/docker-compose/docker-compose.yml \
  exec -T redis redis-cli XINFO GROUPS stream.audit
./scripts/verify_unified_audit.sh
```

`/health` returns `{"service":"audit-worker","status":"ok"}`.
`/status` shows `"running":true`, `"group":"audit-group"`, and the
processed counter incrementing as workflows run. `XINFO GROUPS` lists
`audit-group` with `consumers >= 1`. `verify_unified_audit.sh` ends
with `UNIFIED_AUDIT_VERIFY: PASS`.

Query the unified audit DB directly:

```
curl -sS "http://localhost:8003/audit/events?limit=5" | python3 -m json.tool
curl -sS "http://localhost:8003/audit/events?agent=qa-agent&limit=5" \
  | python3 -m json.tool
curl -sS "http://localhost:8003/audit/events?decision_type=github_pr_integration&limit=5" \
  | python3 -m json.tool
```

A pipeline-triggered workflow with `github.enabled=true` produces
`github_pr_integration` (devops-agent) and `github_automation`
(github-automation) rows in `audit_logs`.

`/workflow/timeline/{task_id}` carries `audit_timeline` next to
`agent_timeline` / `retry_timeline`:

```
curl -sS "http://localhost:8000/workflow/timeline/$task" \
  | python3 -m json.tool | grep -A2 audit_timeline | head -30
```

---

## 18. Sign-off checklist

* [ ] `git log -1` matches the commit the team agreed to ship.
* [ ] All 19 services + audit-worker reported `running (healthy)`.
* [ ] `./scripts/run_tests.sh` ended green.
* [ ] `./scripts/verify_unified_audit.sh` ended `UNIFIED_AUDIT_VERIFY: PASS`.
* [ ] `./scripts/verify_platform_observability.sh` ended
      `PLATFORM_OBSERVABILITY_VERIFY: PASS`.
* [ ] Manual workflow reached `completed`, trace covered all 7
      services, incident lifecycle (create → ack → resolve) worked.
* [ ] `deployment_records` shows zero rows with
      `production_executed = true` or `environment = production`.
* [ ] `workflow_states.execution_result->>'production_executed'='true'`
      count is `0`.
* [ ] Alertmanager `/api/v2/receivers` mentions no external
      Slack / Discord / Telegram / PagerDuty / webhook / email
      receiver.

If every box is ticked, the platform is ready for the next iteration.
Nothing on this checklist authorizes a production deploy.
