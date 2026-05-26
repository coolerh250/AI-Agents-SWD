# AI Agents SWD — Observability Runbook

Local / test runbook for the platform observability stack on `10.0.1.31`.
Everything below assumes the operator is on the test server with the
repository checked out at `/home/itadmin/AI-Agents-SWD` and Docker Compose
up. **No production action is performed by any command in this document.**

> Safety contract: the platform never deploys to production, never calls
> a real cloud / GitHub / Slack / Kubernetes / LLM API, never sends a
> real Slack / Discord / Telegram / PagerDuty alert, and stores no real
> secrets. Alertmanager uses a null receiver; the incident API is the
> in-platform record of operator response.

---

## 1. Platform service map

| Component               | Port  | Purpose                                          |
|-------------------------|-------|--------------------------------------------------|
| orchestrator            | 8000  | Workflow API + `/incidents`                      |
| policy-engine           | 8001  | Risk classification                              |
| approval-engine         | 8002  | Approval request / decision                      |
| audit-service           | 8003  | Append-only decision log                         |
| communication-gateway   | 8004  | Inbound `/intake/mock`, `/notifications` proxy   |
| intake-agent            | 8010  | Stage 1 agent                                    |
| requirement-agent       | 8011  | Stage 2 agent                                    |
| development-agent       | 8012  | Stage 3 agent                                    |
| qa-agent                | 8013  | Stage 4 agent                                    |
| devops-agent            | 8014  | Stage 5 mock dev/test deployment                 |
| retry-scheduler         | 8015  | DLQ + retry + terminal-failure → incident        |
| postgres                | 5432  | Workflow / agent / audit / incident state        |
| redis                   | 6379  | Streams (events, deadletter, notifications)      |
| vault                   | 8200  | Dev-mode KV (no real secrets)                    |
| prometheus              | 9090  | Metrics scrape + rules + alerts                  |
| grafana                 | 3000  | Dashboards (provisioned: Prometheus/Tempo/AM)    |
| tempo                   | 3200  | Trace store (HTTP + OTLP gRPC :4317 / HTTP :4318) |
| alertmanager            | 9093  | Null receiver only                               |

All ports are bound to `127.0.0.1` on `10.0.1.31`.

---

## 2. Quick health pass

```
cd /home/itadmin/AI-Agents-SWD
./scripts/verify_platform_observability.sh
```

A green run ends with `PLATFORM_OBSERVABILITY_VERIFY: PASS`. The script
also reports `CHECK_RUNTIME_STATE: PASS`, `VERIFY_TRACING_BACKEND: PASS`,
`VERIFY_TRACE_FLOW: PASS`, `VERIFY_ALERTING: PASS`, and
`VERIFY_INCIDENT_FLOW: PASS`. If any line says `FAIL`, jump to the
matching section below.

---

## 3. Check Docker containers

```
docker compose -f infra/docker-compose/docker-compose.yml ps
```

All 18 services should be `running (healthy)` (or `running` for
short-lived ones). To restart a single component without rebuilding the
world:

```
docker compose -f infra/docker-compose/docker-compose.yml \
  up -d --force-recreate <service>
```

---

## 4. Check service health

```
for p in 8000 8001 8002 8003 8004 8010 8011 8012 8013 8014 8015; do
  printf "  :%s -> %s\n" "$p" "$(curl -sS -o /dev/null -w '%{http_code}' -m 5 http://localhost:$p/health)"
done
```

Each line should print `200`.

---

## 5. Prometheus

* Healthcheck: `curl http://localhost:9090/-/healthy`
* Targets: `curl http://localhost:9090/api/v1/targets` — every entry
  must be `"health":"up"`.
* Rules: `curl http://localhost:9090/api/v1/rules` — must list the
  five `aiagents.*` rule groups loaded from
  `infra/observability/prometheus/rules/aiagents.rules.yml`.
* Active alerts: `curl http://localhost:9090/api/v1/alerts`.

---

## 6. Alertmanager

* Healthcheck: `curl http://localhost:9093/-/healthy`
* Status: `curl http://localhost:9093/api/v2/status`
* **Receiver contract** — the receivers endpoint must NOT mention
  `slack`, `discord`, `telegram`, `pagerduty`, `opsgenie`, `webhook` or
  `email`. Verify:

```
curl -s http://localhost:9093/api/v2/receivers \
  | grep -E 'slack|discord|telegram|pagerduty|opsgenie|webhook|email' \
  && echo "REGRESSION: external receiver detected" \
  || echo "null receiver only: OK"
```

The local/test runtime must stay on the null receiver. When wiring a
real notifier later, do it through Vault + an entrypoint that renders
`alertmanager.yml` at container start — never commit a webhook URL or
token to git.

---

## 7. Grafana

* URL: `http://10.0.1.31:3000` (anonymous viewer enabled by default).
* Datasources: `curl http://localhost:3000/api/datasources` — must
  include `type: prometheus`, `type: tempo`, `type: alertmanager`.
* Dashboard: search `AI Agents SWD Platform` — covers workflow / agent
  / retry panels plus the post-15.3 active-alerts and service-health
  panels.

If a dashboard or datasource change doesn't show up after a `git pull`,
force-recreate Grafana so provisioning re-runs:

```
docker compose -f infra/docker-compose/docker-compose.yml \
  up -d --force-recreate grafana
```

---

## 8. Tempo (traces)

* Ready: `curl http://localhost:3200/ready` → `ready`
* Version: `curl http://localhost:3200/status/version`
* Trace lookup by ID:

```
curl -s http://localhost:3200/api/traces/<trace_id> | head -c 1500
```

If a workflow `trace_id` doesn't appear in Tempo:

1. Check the orchestrator OTEL env vars: `docker compose exec
   orchestrator env | grep ^OTEL_`. `OTEL_EXPORTER_OTLP_ENDPOINT` must
   point at `http://tempo:4317` and `OTEL_SERVICE_NAME` must be set.
2. Confirm port `4317`/`4318` are listening:
   `verify_tracing_backend.sh` covers both.
3. Wait ~10s — Tempo has a small ingestion lag.

---

## 9. Find a workflow by `task_id`

```
curl -s http://localhost:8000/workflow/<task_id>            # raw state
curl -s http://localhost:8000/workflow/progress/<task_id>   # progress + trace_id
curl -s http://localhost:8000/workflow/timeline/<task_id>   # agent timeline + traces
```

The `trace_id` field on the progress payload is the canonical handle
for Tempo lookups.

---

## 10. Find a full trace by `trace_id`

Workflow progress → `trace_id` → Tempo:

```
trace_id=$(curl -s http://localhost:8000/workflow/progress/<task_id> \
  | python3 -c "import json,sys;print(json.load(sys.stdin).get('trace_id',''))")
curl -s "http://localhost:3200/api/traces/$trace_id"
```

For a healthy `dev.test` workflow you should see seven `service.name`
values: `communication-gateway`, `orchestrator`, `intake-agent`,
`requirement-agent`, `development-agent`, `qa-agent`, `devops-agent`.

---

## 11. Dead-letter queue (DLQ)

* List recent dead-lettered events:
  `curl http://localhost:8015/deadletter?count=20`
* Inspect a single entry by message_id (returned in the list above).
* Manually replay one to its original stream:
  `curl -X POST http://localhost:8015/deadletter/replay/<message_id>`

A replay must publish back to the `original_stream` recorded in the
dead-letter payload. `scripts/check_runtime_state.sh` covers both list
and replay (`DLQ_LIST_SMOKE`, `DLQ_REPLAY_SMOKE`).

---

## 12. Incidents

```
curl -s http://localhost:8000/incidents
curl -s "http://localhost:8000/incidents?status=open"
curl -s "http://localhost:8000/incidents?task_id=<task_id>"
curl -s http://localhost:8000/incidents/<incident_id>

# Acknowledge / resolve
curl -X POST http://localhost:8000/incidents/<incident_id>/ack
curl -X POST http://localhost:8000/incidents/<incident_id>/resolve

# Operator-created incident (sev3 by default)
curl -X POST http://localhost:8000/incidents \
  -H 'Content-Type: application/json' \
  -d '{"summary":"manual smoke","severity":"sev3","source":"operator"}'
```

Each create/ack/resolve also publishes on `stream.notifications` and
writes an audit event via the audit-service; nothing leaves the host.

---

## 13. Confirm terminal failure was turned into an incident

When the retry-scheduler exhausts retries on a dead-letter event:

1. `incident_records` gets a new row (`source: retry-scheduler`,
   `severity: sev2`, details carry `original_stream`, `retry_count`,
   `max_retries`, `failure_reason`).
2. `workflow_states.stage` is flipped to `failed`,
   `execution_result.{status,failure_reason,production_executed,failed_at}`
   are set.
3. A `workflow.failed` notification is published on
   `stream.notifications` keyed by `task_id`.
4. An audit event `decision_type = workflow_failed` is written.

Verify end-to-end:

```
./scripts/verify_incident_flow.sh
```

Expected: `INCIDENT_FLOW_SMOKE: PASS`.

---

## 14. Confirm workflow failed state

```
psql_cmd="docker compose -f infra/docker-compose/docker-compose.yml \
  exec -T postgres psql -U postgres -d aiagents -tAc"
$psql_cmd "SELECT task_id, stage, execution_result->>'status' \
           FROM workflow_states WHERE stage='failed' ORDER BY updated_at DESC LIMIT 10;"
```

Cross-check with the matching incident:

```
$psql_cmd "SELECT task_id, status, severity, source \
           FROM incident_records ORDER BY created_at DESC LIMIT 10;"
```

---

## 15. Confirm `production_executed = false`

Mock devops deployments record `production_executed: false` in
`deployment_records.metadata`. To assert no row ever flipped to `true`:

```
docker compose -f infra/docker-compose/docker-compose.yml \
  exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT COUNT(*) FROM deployment_records
    WHERE metadata->>'production_executed'='true' OR environment='production';"
```

The query must return `0`. `verify_platform_observability.sh`
section 12 runs this query automatically.

---

## 16. Common issues

### Grafana dashboard / datasource changes don't show up after `git pull`
Provisioning is mounted read-only and re-read on container start.
Force-recreate Grafana:

```
docker compose -f infra/docker-compose/docker-compose.yml \
  up -d --force-recreate grafana
```

### Tempo: trace not found
- Confirm the workflow actually emitted spans:
  `docker compose logs --tail=200 orchestrator | grep -i otel`.
- Confirm the OTEL endpoint env var inside the container is reachable:
  `docker compose exec orchestrator sh -c 'env | grep ^OTEL_'`.
- Tempo has a small ingestion delay; wait ~10s and retry.
- Verify the trace_id you used really came from the orchestrator-side
  OTel SDK (via `/workflow/progress/<task_id>` → `trace_id` field),
  not a random hex string.

### Prometheus target down
- `curl http://localhost:9090/api/v1/targets` — find the down job.
- Check the service container:
  `docker compose ps <service>` and `docker compose logs --tail=200 <service>`.
- Confirm the `/metrics` endpoint responds locally:
  `curl http://localhost:<port>/metrics`.

### DLQ replay race / flake
Use the deterministic per-event-type filter rather than “newest entry on
target stream”. Stage 15.4 fixed the integration test by switching to
`xrange(target_stream, '-', '+', count=50)` and filtering for
`event == retry.manual_replay` — apply the same pattern in ad-hoc
scripts.

### Postgres trust auth / Vault dev mode reminder
The compose stack uses Postgres trust auth and Vault dev mode on
purpose — this is local/test only. Never repurpose this configuration
for production; production must use real auth + a real KMS.

---

## 17. Verification scripts (cheat sheet)

| Script                                       | Verifies                                              | Pass marker                          |
|----------------------------------------------|-------------------------------------------------------|--------------------------------------|
| `scripts/check_runtime_state.sh`             | 40+ runtime smokes covering every service             | per-smoke `PASS` lines               |
| `scripts/verify_tracing_backend.sh`          | Tempo ready + OTLP ports + Grafana datasource         | `TEMPO_READY: PASS`                  |
| `scripts/verify_trace_flow.sh`               | End-to-end trace with all 7 service spans             | `TRACE_FLOW_SMOKE: PASS`             |
| `scripts/verify_alerting.sh`                 | Alertmanager + Prometheus rules + null receiver       | `ALERTMANAGER_HEALTHY: PASS`         |
| `scripts/verify_incident_flow.sh`            | Terminal failure → incident → workflow.failed → ack/resolve | `INCIDENT_FLOW_SMOKE: PASS`    |
| `scripts/verify_platform_observability.sh`   | Aggregates all of the above + safety + SLO            | `PLATFORM_OBSERVABILITY_VERIFY: PASS` |

---

## 18. What to do when something is FAIL

1. Find the failing line in `verify_platform_observability.sh` output.
2. Open the matching sub-script and re-run it in isolation — its output
   shows the exact HTTP body / smoke that failed.
3. Use the corresponding section above (3 through 16) to diagnose.
4. **Never** restart, drop, or “fix” a production resource — there is
   no production in scope here. The platform is local/test only.

---

## 19. References

* `README.md` — top-level platform overview.
* `docs/operations/manual-verification.md` — copy-paste command list
  for a human operator on `10.0.1.31`.
* `source/progress.md` — per-stage delivery log.
