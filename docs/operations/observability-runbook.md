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
| `scripts/check_runtime_state.sh`             | 50+ runtime smokes covering every service             | per-smoke `PASS` lines               |
| `scripts/verify_tracing_backend.sh`          | Tempo ready + OTLP ports + Grafana datasource         | `TEMPO_READY: PASS`                  |
| `scripts/verify_trace_flow.sh`               | End-to-end trace with all 7 service spans             | `TRACE_FLOW_SMOKE: PASS`             |
| `scripts/verify_alerting.sh`                 | Alertmanager + Prometheus rules + null receiver       | `ALERTMANAGER_HEALTHY: PASS`         |
| `scripts/verify_incident_flow.sh`            | Terminal failure → incident → workflow.failed → ack/resolve | `INCIDENT_FLOW_SMOKE: PASS`    |
| `scripts/verify_github_automation.sh`        | github-automation dry-run (+ opt-in real GitHub test) | `GITHUB_AUTOMATION_VERIFY: PASS`     |
| `scripts/verify_github_pipeline_flow.sh`     | Agent pipeline → github-automation → workflow result  | `GITHUB_PIPELINE_FLOW_VERIFY: PASS`  |
| `scripts/verify_unified_audit.sh`            | Unified `stream.audit → audit-worker → audit_logs`    | `UNIFIED_AUDIT_VERIFY: PASS`         |
| `scripts/verify_operations_view.sh`          | Stage 20 Operations Control API end-to-end            | `OPERATIONS_VIEW_VERIFY: PASS`       |
| `scripts/verify_discord_gateway.sh`          | Stage 21 Discord Gateway sandbox end-to-end           | `DISCORD_GATEWAY_VERIFY: PASS`       |
| `scripts/verify_notification_delivery.sh`    | Stage 22 controlled Discord notification delivery     | `NOTIFICATION_DELIVERY_VERIFY: PASS` |
| `scripts/verify_platform_observability.sh`   | Aggregates all of the above + safety + SLO            | `PLATFORM_OBSERVABILITY_VERIFY: PASS` |

### 17a. audit-worker (Stage 19)

* **Health.** `curl http://localhost:8006/health` returns
  `{"service":"audit-worker","status":"ok"}`.
* **Status.** `curl http://localhost:8006/status` shows
  `running`, `input_stream=stream.audit`, `group=audit-group`,
  `consumer=audit-worker-1`, and the running counters
  (`processed_count` / `failed_count` / `deadlettered_count` /
  `skipped_count`).
* **Metrics.** `curl http://localhost:8006/metrics | grep audit_worker_`
  exposes `audit_worker_processed_total{decision_type=...}`,
  `audit_worker_failures_total{reason=...}`,
  `audit_worker_deadlettered_total`,
  `audit_worker_skipped_total{reason=...}`,
  `audit_worker_processing_seconds`.
* **Consumer group.** `redis-cli XINFO GROUPS stream.audit` must
  show `audit-group` with `consumers >= 1`. The worker uses
  `XREADGROUP BLOCK` so there is no busy-polling — the consumer
  name is `audit-worker-1`.
* **`audit.recorded` skip.** Every `POST /audit/events` echoes
  `{"event": "audit.recorded", ...}` back onto `stream.audit`. The
  worker's `is_audit_recorded_echo` check skips and ACKs the
  envelope; the echo never lands in `audit_logs`. Look for
  `audit_worker_skipped_total{reason="audit_recorded_echo"}`
  ticking up over time.
* **Deadletter.** A poison message that keeps failing is routed
  onto `stream.deadletter` as `audit.deadlettered` after
  `MAX_FAILURES_BEFORE_DEADLETTER = 3` attempts; the original
  message is then ACKed so the group's pending list doesn't grow
  unbounded. The retry-scheduler will not re-queue it (the
  deadletter envelope carries no `original_stream`).
* **Backlog behaviour.** `audit-group` was created with `$`
  MKSTREAM in Stage 15.5 but had no consumer until Stage 19.
  On audit-worker startup the first `XREADGROUP >` call drains
  every event that arrived after group-creation
  (Pre-Step-18 saw `lag≈5532`). The `audit.recorded` filter
  classifies them: historical POST echoes are skipped
  (already in `audit_logs`), historical StreamAgent-only
  publishes become new rows. After the drain
  `XINFO GROUPS stream.audit` shows `lag=0`; steady-state is
  one row per workflow stage per agent. If you ever need to
  re-drain from the beginning of the stream (e.g. after a
  retention reset): `XGROUP SETID stream.audit audit-group
  0-0` and restart audit-worker; the `audit.recorded` filter
  and the `source_message_id` dedup cache still apply.

### 17b. /audit/events query API

* `curl "http://localhost:8003/audit/events?limit=5"` — newest 5
  audit rows across all tasks.
* `curl "http://localhost:8003/audit/events?agent=qa-agent&limit=5"`
  — newest qa-agent rows.
* `curl "http://localhost:8003/audit/events?decision_type=github_pr_integration&limit=5"`
  — newest pipeline-triggered PR rows.
* `GET /audit/events/{task_id}` still returns every row for a
  single task, ordered ascending.

### 17n. Notification delivery worker (Stage 22)

The notification-worker (`apps/notification-worker/`, port `8008`) is
sandbox-by-default. Operator checks:

* **Health.** `curl http://localhost:8008/health` returns
  `{"service":"notification-worker","status":"ok","mode":"sandbox","has_discord_token":false,"real_discord_enabled":false}`.
* **Status.** `curl http://localhost:8008/status` shows
  `running=true`, `mode=sandbox`, `input_stream=stream.notifications`,
  `group=notification-worker-group`, plus counters
  (`processed_count`, `delivered_count`, `simulated_count`,
  `failed_count`, `skipped_count`).
* **Metrics.** `curl http://localhost:8008/metrics | grep ^notification_worker_`
  exposes the new `notification_worker_*` series.
* **Confirm sandbox delivery.**
  ```
  curl "http://localhost:8007/discord/deliveries/$task" | python3 -m json.tool
  ```
  Expect `external_sent_count = 0`, `simulated_count >= 2`
  (`discord.task.received` + `discord.task.completed`).
* **Confirm external_sent=false.**
  ```
  curl "http://localhost:8000/operations/safety" \
    | python3 -m json.tool | grep -E 'discord_(has_token|test_channel|real_test_enabled|external_send)'
  ```
  `discord_external_send_enabled` must be `false` unless the opt-in
  env vars are deliberately loaded into the container.
* **Real-Discord guard.**
  ```
  curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
    http://localhost:8008/discord/real/test-message \
    -H 'Content-Type: application/json' \
    -d '{"content":"sandbox guard verification"}'
  ```
  Expected: `409`. The audit row `decision_type=discord_real_test_skipped`
  documents the refusal:
  ```
  curl "http://localhost:8003/audit/events?decision_type=discord_real_test_skipped&limit=3" \
    | python3 -m json.tool
  ```
* **Notification delivery audit.**
  ```
  curl "http://localhost:8003/audit/events?decision_type=notification_delivery&limit=5" \
    | python3 -m json.tool
  ```
  Each row's `artifact_refs` carries `sandbox=true`,
  `external_sent=false`, `delivery_id`, `source_message_id`,
  `event_type`.

### Backlog policy

`notification-worker` uses the existing `notification-group`
consumer group, which the Stage 15.5 `init_redis_streams.sh`
created with `MKSTREAM $`. On first startup the worker drains every
event the group has yet to deliver. Older entries that arrived before
`notification-worker` came online still hit the
`source_message_id` partial unique index, so a duplicate replay (e.g.
after `XGROUP SETID`) is safe — duplicate inserts return `None` and
the worker counts them as `skipped_total{reason="duplicate"}`.

### 17d. Discord Gateway sandbox (Stage 21)

The Discord Gateway (`apps/discord-gateway/`, port `8007`) is
**sandbox-only** by default — every endpoint runs without
contacting `discord.com`. Operator checks:

* **Health.** `curl http://localhost:8007/health` returns
  `{"service":"discord-gateway","status":"ok","mode":"sandbox","has_token":false}`.
  If `has_token` is `true` the bot token env var is set; this is the
  only place the token's presence is observed.
* **Status.** `curl http://localhost:8007/status` shows
  `running`, `mode=sandbox`, `received_count`,
  `dispatched_count`, `failed_count`, `last_task_id`,
  `last_error`, plus `real_test_enabled` (must be `false` unless
  `RUN_REAL_DISCORD_TEST=true`).
* **Metrics.** `curl http://localhost:8007/metrics | grep ^discord_`
  exposes `discord_messages_received_total{command_type,sandbox}`,
  `discord_tasks_dispatched_total{command_type,result,sandbox}`,
  `discord_intake_failures_total{reason}`,
  `discord_notifications_published_total{event_type,sandbox}`,
  `discord_request_duration_seconds{endpoint}`.
* **Create a sandbox task.**
  ```
  curl -sS -X POST http://localhost:8007/discord/messages \
    -H 'Content-Type: application/json' \
    -d '{"content":"/ai task type=dev.test description=\"verify discord\"","channel_id":"sandbox-ops","user_id":"operator"}'
  ```
  The response carries the new `task_id`, the workflow `stage`, and
  `operations_url=/operations/workflows/{task_id}`.
* **Follow the task end-to-end.**
  `curl http://localhost:8007/discord/tasks/$task | python3 -m json.tool`
  proxies the unified workflow view and surfaces
  `completed_agents`, `github.pr_url`, `audit_timeline_count`,
  `incidents_count`, `production_executed`. The verbatim
  `/operations/workflows/{task_id}` body is also inlined under
  `operations_view` for one-shot inspection.
* **Confirm discord audit event landed.**
  ```
  curl "http://localhost:8003/audit/events?decision_type=discord_intake&limit=5" \
    | python3 -m json.tool
  ```
  Each row's `artifact_refs` carries `channel_id`, `user_id`,
  `message_id`, `sandbox: true`, `operations_url`.
* **Confirm discord notifications landed.**
  ```
  curl "http://localhost:8004/notifications?count=200" \
    | python3 -m json.tool | grep discord.task
  ```
  Expect `discord.task.received` + one of
  `discord.task.dispatched / .waiting_approval / .completed`.
* **No real Discord API call.** The runtime smoke checks the
  refusal: `curl -sS -X POST http://localhost:8007/discord/real/test-message`
  returns HTTP 409 with detail
  `real Discord test is not enabled — set DISCORD_BOT_TOKEN and
  RUN_REAL_DISCORD_TEST=true to opt in` whenever either flag is
  missing. The runbook's optional real-test recipe is the only
  documented way to lift the gate; the default verify run never
  flips it.

### 17ops. Operations Control API (Stage 20)

The orchestrator serves a unified `/operations/*` namespace
(`apps/orchestrator/src/operations.py`). Every endpoint is read-only
and degrades safely on a missing data source.

* **Health.** `curl http://localhost:8000/operations/health` returns
  `{"service":"operations","status":"ok"}`. The other operations
  endpoints don't require any extra service — they query the same
  Postgres / Redis / sibling HTTP services this runbook already
  documents.
* **Workflow status, all in one place.**
  `curl http://localhost:8000/operations/workflows/$task | python3 -m json.tool`
  carries `workflow`, `progress`, `agents`, `audit_timeline`,
  `incidents`, `deployment`, `github`, `dlq`, `notifications`,
  `trace`, `safety` plus a top-level `production_executed` boolean.
  Section 5 of `docs/operations/manual-verification.md` shows the
  curl recipe.
* **Agent status.**
  `curl http://localhost:8000/operations/agents` lists each pipeline
  agent's `health_status`, `processed_count`, `failed_count`,
  `recent_executions_count`, `recent_failures_count`, plus the
  `input_stream` / `output_stream` / `consumer_group` topology so
  you can cross-reference with the streams view.
  `curl http://localhost:8000/operations/agents/$name` adds the
  recent `agent_executions`, recent `audit_logs` rows, and the
  matching XINFO snapshot.
* **Stream lag / pending.**
  `curl http://localhost:8000/operations/streams` returns one row per
  platform stream with length / consumers / pending / lag /
  last-delivered-id and a derived `status`
  (`ok` / `warning` / `informational` / `not_unified_by_design` / `unknown`).
  `stream.notifications` is labelled `not_unified_by_design` until a
  notification consumer ships — that is the documented Stage 19
  follow-up, not a regression.
* **Production safety.**
  `curl http://localhost:8000/operations/safety` is the
  one-shot operator check. Every production counter must be `0`;
  `github_has_token` exposes the boolean (never the value);
  `alertmanager_receivers` lists the configured receivers and
  `external_alert_receivers_present` flips `true` if Slack / Discord
  / Telegram / PagerDuty / webhook receivers are wired. `result`:
  `safe` (clean) / `warning` (counters clean + a non-fatal warning)
  / `unsafe` (any production counter > 0).
* **GitHub dry-run PR for a task.**
  `curl http://localhost:8000/operations/github/$task` aggregates
  the github result from `workflow_states.execution_result.github`,
  `deployment_records.metadata.github`, and the
  `github_pr_integration` / `github_automation` rows in `audit_logs`.
  `found=false` when the task has no github result; `source`
  enumerates which of the three data sources contributed.
* **DLQ without replay.**
  `curl "http://localhost:8000/operations/dlq?limit=20"` returns the
  most-recent `stream.deadletter` + `stream.deadletter.terminal`
  events. `?task_id=…` and `?stream=…` filter; `?terminal=true`
  surfaces only the terminal stream. The endpoint does NOT ACK,
  replay, or delete anything — operator-driven replay still lives
  on `POST /deadletter/replay/{message_id}` against the
  retry-scheduler.

`/operations/summary` rolls the cluster-wide counters up into one
JSON body — that is the natural starting point for a status check
("anything red anywhere?"). The per-task / per-agent / per-stream
endpoints are the drill-down.

Metrics: every call increments
`operations_requests_total{endpoint,result}` and records a
`operations_request_duration_seconds{endpoint}` sample, so a Grafana
panel of "operations API healthiness" is a single PromQL away.
Each request emits an `operations.<view>` OTel span; the
unified-workflow view in particular carries the workflow's
`task_id` so a Tempo TraceQL can pivot from `/operations/workflows/$t`
straight to the workflow's distributed trace.

### 17c. Workflow audit_timeline

`/workflow/timeline/{task_id}` carries an `audit_timeline` list
sourced from `audit_logs`. Each entry has `decision_type`, `agent`,
`created_at`, `summary`, `result`, and `artifact_refs`. A healthy
github-pipeline workflow shows entries for `intake / requirement /
development / qa / deployment / github_pr_integration /
github_automation` ordered by `created_at`.

### 17d. Tamper-evident audit chain (Stage 34)

`audit_logs` is now mirrored by `audit_integrity_records` (per-row
hash-chain) and `audit_chain_verification_runs` (per-verify summary).
Run on demand:

```bash
./scripts/backfill_audit_integrity.sh
./scripts/verify_audit_integrity.sh
./scripts/simulate_audit_tamper_detection.sh
./scripts/verify_tamper_evident_audit.sh
```

Operator surfaces: `GET /operations/audit/integrity`,
`POST /operations/audit/verify-chain`,
`GET /operations/audit/verify-chain/latest`,
`GET /operations/audit/receipt/{audit_log_id}`. The receipt endpoint
exposes `hmac_signature_present` + an 8-char preview only -- the full
signature and the HMAC key value are never returned. See
[`tamper-evident-audit.md`](./tamper-evident-audit.md).

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
