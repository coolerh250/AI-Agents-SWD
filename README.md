# AI Agents SWD Platform

## Project Name

AI Agents SWD Platform

## Purpose

A monorepo for an AI-agent-driven software-development platform. It hosts the
orchestration services, the individual AI agents, shared libraries, and the
infrastructure definitions used to build, test, and govern the platform.

## Repository Structure

```
apps/                      Core platform services
  orchestrator/              Coordinates agents and workflows
  communication-gateway/     Internal/external communication entry point
  approval-engine/           Human-in-the-loop approval handling
  policy-engine/             Policy evaluation and enforcement
  audit-service/             Audit logging and traceability
agents/                    Individual AI agents
  intake-agent/              Intake and triage of incoming requests
  requirement-agent/         Requirement analysis
  frontend-agent/            Frontend implementation
  backend-agent/             Backend implementation
  qa-agent/                  Testing and quality assurance
  devops-agent/              Build, deployment, and operations
shared/                    Shared libraries and assets
  sdk/                       Common SDK
  models/                    Shared data models
  prompts/                   Prompt templates
  utils/                     Utility helpers
  observability/             Logging, metrics, and tracing helpers
  governance/                Governance and compliance helpers
infra/                     Infrastructure definitions
  docker-compose/            Local/test Docker Compose definitions
  kubernetes/                Kubernetes manifests
  helm/                      Helm charts
  argocd/                    Argo CD application definitions
  vault/                     Vault configuration (no secret values committed)
migrations/                Database migrations
scripts/                   Operational and helper scripts
tests/                     Cross-cutting / integration tests
source/                    Project progress log and source notes
```

## Local / Test Deployment Principle

- All build, test, and deployment activity runs **only on the test server `10.0.1.31`**.
- The test server pulls the latest code from GitHub (`git clone` / `git pull`)
  before any deployment.
- No automated deployment to Production is performed.

## Test Server

- Host: `10.0.1.31`
- Access: SSH with key-based authentication.

## Local / Test Runtime

A Docker Compose runtime for local/test use is defined in
`infra/docker-compose/docker-compose.yml`. It provides PostgreSQL 16, Redis 7,
Vault (dev mode), the platform services (`orchestrator`, `policy-engine`,
`approval-engine`, `audit-service`, `communication-gateway`), and the agent
pipeline (`intake-agent`, `requirement-agent`, `development-agent`, `qa-agent`,
`devops-agent`).

Validate the compose configuration:

```
docker compose -f infra/docker-compose/docker-compose.yml config
```

Start the runtime (on the test server `10.0.1.31`):

```
docker compose -f infra/docker-compose/docker-compose.yml up -d
docker compose -f infra/docker-compose/docker-compose.yml ps
```

Check the orchestrator health endpoint:

```
curl http://localhost:8000/health
# {"service":"orchestrator","status":"ok"}
```

Stop the runtime:

```
docker compose -f infra/docker-compose/docker-compose.yml down
```

Notes:

- Vault runs in **dev mode** (in-memory, ephemeral) — for local/test only, never production.
- PostgreSQL uses `POSTGRES_HOST_AUTH_METHOD=trust` for this local/test runtime
  only, so no credentials are stored in the repository.
- All service ports bind to `127.0.0.1` on the host.

## Database & Streams Initialization

After the runtime is up, initialize the PostgreSQL schema and Redis Streams.
All commands run from the repository root on the test server.

One-shot setup (start runtime + apply migration + initialize streams):

```
./scripts/init_local_runtime.sh
```

Apply the PostgreSQL migration only:

```
docker compose -f infra/docker-compose/docker-compose.yml exec -T postgres \
  psql -U postgres -d aiagents -v ON_ERROR_STOP=1 < migrations/001_init_core_tables.sql
```

Initialize the Redis Streams consumer groups only:

```
./scripts/init_redis_streams.sh
```

Check runtime state (containers, tables, streams, orchestrator health):

```
./scripts/check_runtime_state.sh
```

The PostgreSQL migration and the Redis Streams initialization are both
idempotent — safe to run repeatedly.

## Shared SDK

`shared/` provides libraries used by both apps and agents:

```
shared/sdk/base_agent/    BaseAgent abstract class
shared/sdk/event_bus/     RedisStreamEventBus (async Redis Streams)
shared/sdk/audit/         AuditClient
shared/sdk/policy/        PolicyClient
shared/models/            Pydantic models (WorkflowState, AgentEvent,
                          TaskCreatedEvent, AuditEvent)
```

- **BaseAgent** (`abc.ABC`) — concrete agents implement `receive_task`,
  `analyze`, and `execute`; the base class provides `request_approval`,
  `write_audit`, and `report`. It performs no LLM calls, no production
  operations, and reads/writes no secrets.
- **RedisStreamEventBus** — async event bus over Redis Streams:
  `publish_event`, `consume_events`, `ack_event`, and `ensure_group`
  (idempotent BUSYGROUP handling). The Redis URL is read from the `REDIS_URL`
  environment variable, defaulting to `redis://localhost:6379`.
- **PolicyClient** — `evaluate_policy(action)` returns `allowed` and
  `approval_required`. Restricted actions (e.g. `production.deploy`,
  `secret.rotation`) require human approval.
- **AuditClient** — `build_audit_event()` / `write_audit_event()`; audit
  events are published to the `stream.audit` Redis stream.

## Orchestrator Workflow

The `orchestrator` service runs a LangGraph workflow
(`apps/orchestrator/src/workflow.py`) with six nodes:
`intake → requirement → policy → approval → audit → dispatch`. The `policy`,
`approval`, and `audit` nodes call the dedicated governance services over HTTP
via the shared SDK's `PolicyHttpClient`, `ApprovalHttpClient`, and
`AuditHttpClient`. The `dispatch` node hands the task to the agent pipeline —
the orchestrator no longer simulates the work in-process (see
[Unified Workflow Dispatch](#unified-workflow-dispatch)).

API endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Liveness check |
| POST | `/workflow/test` | Run the workflow for a request (dispatches to the agents) |
| POST | `/workflow/policy-test` | Evaluate an action against the policy |
| GET  | `/workflow/schema` | Describe the `WorkflowState` fields |
| GET  | `/workflow` | List persisted workflows (optional `?status=`) |
| GET  | `/workflow/{task_id}` | Get one persisted workflow state |
| GET  | `/workflow/progress/{task_id}` | Get a workflow's agent-pipeline progress |
| GET  | `/workflow/replay/{task_id}` | Replay a persisted workflow state (no execution) |
| POST | `/workflow/resume/{task_id}` | Resume an approved workflow |
| POST | `/workflow/cancel/{task_id}` | Cancel a non-terminal workflow |
| POST | `/workflow/abort/{task_id}` | Abort a non-terminal workflow (ignore future agent events) |

Run the workflow:

```
curl -X POST http://localhost:8000/workflow/test \
  -H "Content-Type: application/json" \
  -d '{"task_id":"mock-1","source":"manual","request":{"type":"dev.test"}}'
```

A non-production request is dispatched to the agent pipeline
(`stage: dispatched`); when the pipeline finishes, the orchestrator's workflow
event consumer drives it to `stage: completed`. A `production.deploy` request is
flagged by the policy node and ends at `stage: waiting_approval` — it is **not**
dispatched until it is approved, and **the workflow never executes a production
action**.

## Governance Services

Governance is split into three standalone FastAPI services. The orchestrator
calls them over HTTP; each service URL is read from an environment variable
(with a `localhost` fallback for tests).

| Service | Port | Env variable | Responsibility |
|---------|------|--------------|----------------|
| `orchestrator`    | 8000 | —                    | Runs the LangGraph workflow |
| `policy-engine`   | 8001 | `POLICY_ENGINE_URL`  | Evaluates actions against policy |
| `approval-engine` | 8002 | `APPROVAL_ENGINE_URL`| Creates / decides approval requests |
| `audit-service`   | 8003 | `AUDIT_SERVICE_URL`  | Persists and serves audit events |

All service ports bind to `127.0.0.1` on the host.

**policy-engine** — `POST /policy/evaluate` takes `{"action": "..."}` and returns
`allowed`, `approval_required`, `risk_level`, and `reason`. Restricted actions
(e.g. `production.deploy`, `secret.rotation`) return `approval_required: true`.

**approval-engine** — endpoints `POST /approval/request`, `POST /approval/approve`,
`POST /approval/reject`, and `GET /approval/{request_id}`. Approval flow:

1. The orchestrator's `approval` node calls `POST /approval/request` for a
   restricted action.
2. The request is persisted to the PostgreSQL `approval_requests` table with
   `status: pending` and published to the `stream.approvals` Redis stream.
3. `POST /approval/approve` / `POST /approval/reject` update the row and publish
   an `approval.approved` / `approval.rejected` event. **No production action is
   executed** — `production.deploy` stays at `waiting_approval`.

**audit-service** — endpoints `POST /audit/events` and
`GET /audit/events/{task_id}`. Audit flow: the orchestrator's `audit` node calls
`POST /audit/events`; the event is persisted to the PostgreSQL `audit_logs`
table and published to the `stream.audit` Redis stream. `GET /audit/events/{task_id}`
returns all audit events recorded for a task.

The governance columns are added by `migrations/002_governance_tables.sql`.

## Workflow Persistence & Resume

The orchestrator persists every workflow so it survives a restart and can be
resumed after an approval decision.

**Persistence** — `shared/sdk/workflow_store/store.py` (`WorkflowStore`, asyncpg)
writes one row per workflow into the PostgreSQL `workflow_states` table
(`migrations/003_workflow_persistence.sql`). The workflow `create`s the row at
start and `update`s it after every node transition; the full LangGraph state is
stored in the `state` JSONB column, with the governance fields mirrored into
dedicated columns for listing and filtering. The `DATABASE_URL` environment
variable selects the database.

**Resume engine** — `apps/orchestrator/src/resume_engine.py` (`ResumeEngine`):

- `resume_workflow(task_id)` — resume a workflow once its approval is granted.
- `resume_approved_workflows()` — startup recovery: reconcile every
  `waiting_approval` workflow against the approval-engine.
- `replay_workflow_state(task_id)` — return the persisted state without
  executing anything.

Resuming is **mock-safe**: it only updates workflow bookkeeping (stage,
`execution_result`, audit trail). It never executes a production action — a
resumed `production.deploy` reaches `completed` with `production_executed: false`.

**Approval resume flow** — on startup the orchestrator opens a Redis consumer
group on `stream.approvals` (`XREADGROUP BLOCK` — no polling). When the
approval-engine publishes `approval.approved`, the workflow is resumed to
`completed`; `approval.rejected` moves it to `rejected`. Workflows approved while
the orchestrator was down are recovered by the startup scan.

**Restart survivability** — because workflow state lives in PostgreSQL, restarting
the orchestrator container loses nothing: `GET /workflow/{task_id}` and
`GET /workflow/replay/{task_id}` keep returning the persisted state.

## Communication Gateway

`communication-gateway` (port `8004`) is the entry point for mock user requests
and notifications — the foundation for future Slack / Discord / Telegram
integrations. It makes **no real external calls**.

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Liveness check |
| POST | `/intake/mock` | Submit a mock request; runs it through the orchestrator |
| GET  | `/tasks/{task_id}` | Get a persisted workflow state via the orchestrator |
| POST | `/notifications/test` | Publish a test notification |
| GET  | `/notifications` | Read recent notifications |

**Mock intake flow** — `POST /intake/mock` takes a mock request, calls the
orchestrator `POST /workflow/test`, and returns `task_id`, `stage`,
`approval_required`, and the full `workflow_result`. A `production.deploy`
request still stops at `waiting_approval` — no production action is executed.

**Notification flow** — notifications are published to the `stream.notifications`
Redis stream by `shared/sdk/notifications/client.py` (`NotificationClient`). The
orchestrator publishes a notification when a workflow reaches `completed` or
`waiting_approval`, and the resume engine publishes one when a workflow is
`resumed` or `rejected`. `GET /notifications` reads recent entries with
`XREVRANGE`; `POST /notifications/test` publishes a test notification. Each
notification carries `task_id`, `event_type`, `message`, and `created_at`.

The `communication-gateway` reads `ORCHESTRATOR_URL` and `REDIS_URL` from the
environment.

## Agent Services

Concrete agents are standalone services under `agents/`. Each subclasses the
shared `StreamAgent` (itself a `BaseAgent`), runs a Redis Streams consumer
group, and exposes `GET /health` and `GET /status`. They make no LLM / GitHub /
Slack / Kubernetes / cloud calls and execute no production actions.

| Agent | Port | Consumes | Produces |
|-------|------|----------|----------|
| `intake-agent` | 8010 | `stream.tasks` | `stream.requirements` |
| `requirement-agent` | 8011 | `stream.requirements` | `stream.development` |
| `development-agent` | 8012 | `stream.development` | `stream.qa` |
| `qa-agent` | 8013 | `stream.qa` | `stream.deployments` |
| `devops-agent` | 8014 | `stream.deployments` | `stream.devops` (+ `deployment_records`) |

**Agent pipeline** — a task placed on `stream.tasks` flows through the full
pipeline:

```
stream.tasks → intake-agent → stream.requirements → requirement-agent →
stream.development → development-agent → stream.qa → qa-agent →
stream.deployments → devops-agent → deployment_records
```

- `intake-agent` normalizes the raw task; `requirement-agent` produces a mock
  `requirement_spec`; `development-agent` produces a mock `code_change`;
  `qa-agent` produces a mock `test_report`; `devops-agent` produces a mock
  `deployment_record` (`environment: test`, `status: simulated`,
  `production_executed: false`) — **no production deployment is performed**.
- Every agent records an `agent_executions` row (`started` → `completed` /
  `failed`), writes an audit event to `stream.audit`, and publishes a
  notification to `stream.notifications`.

**Agent execution persistence** — `shared/sdk/agent_execution/store.py`
(`AgentExecutionStore`, asyncpg) persists every message an agent processes to the
`agent_executions` table (`migrations/004_agent_execution_persistence.sql`).
Query executions through the communication-gateway:

```
curl "http://localhost:8004/executions?task_id=demo-1"
curl "http://localhost:8004/executions?agent=devops-agent&status=completed"
```

Place a task on `stream.tasks` through the communication-gateway:

```
curl -X POST http://localhost:8004/intake/mock \
  -H "Content-Type: application/json" \
  -d '{"task_id":"demo-1","request":{"type":"dev.test"},"publish_to_stream":true}'
```

With `publish_to_stream: true` the gateway writes to `stream.tasks` for the
agents to process; the default (`false`) runs the workflow directly through the
orchestrator. `scripts/check_runtime_state.sh` runs an end-to-end agent pipeline
smoke test and checks `agent_executions` and `deployment_records`.

## Unified Workflow Dispatch

The orchestrator workflow and the agent pipeline are one flow: the orchestrator
no longer simulates the work in-process — it **dispatches** the task to the
agents and tracks their progress.

```
communication-gateway → orchestrator workflow → stream.tasks → intake-agent →
requirement-agent → development-agent → qa-agent → devops-agent →
stream.devops → orchestrator → workflow state completed
```

**Dispatch** — the workflow's `dispatch` node publishes a `task.created` event
(`task_id`, `workflow_id`, `request`, `source`, `requested_at`) to `stream.tasks`
and sets `stage: dispatched`, `execution_result.status: awaiting_agents`.
`apps/orchestrator/src/dispatch.py` owns the dispatch helper. A
`production.deploy` request still passes policy/approval first — it is **not**
dispatched until it is approved; the resume engine dispatches an approved
restricted action, which the agents only ever *simulate*.

**Workflow event consumer** — on startup the orchestrator opens a Redis consumer
group (`orchestrator-workflow-group`) on the agent pipeline streams
(`stream.development`, `stream.qa`, `stream.deployments`, `stream.devops`).
`requirement.completed` / `development.completed` / `qa.completed` move the
workflow to `in_progress`; `devops.deployment_simulated` moves it to `completed`
and records `deployment_record_id` in `execution_result`
(`apps/orchestrator/src/workflow_events.py`).

**Progress tracking** — `GET /workflow/progress/{task_id}` returns
`current_stage`, `completed_agents`, `pending_agents`, `execution_status`
(`waiting_approval` / `dispatched` / `in_progress` / `completed` / `failed`),
`approval_status`, and timestamps. It combines the persisted workflow state with
the `agent_executions` rows (`apps/orchestrator/src/progress.py`).

**Event correlation** — every task / agent event carries `task_id` **and**
`workflow_id`; each agent forwards both ids to the next stage
(`StreamAgent.correlation_ids`). The devops-agent's `deployment_records` row
also carries the `workflow_id`.

**Retry & dead-letter foundation** — events carry `retry_count` / `max_retries`
metadata. When an agent fails to process a message it is re-published to the
input stream with an incremented `retry_count`; once `retry_count` reaches
`max_retries` (default 3) it is routed to the `stream.deadletter` stream — the
dead-letter event includes `original_stream`, `retry_count`, `max_retries`,
`retry_after_seconds`, `failed_at`, and `failure_reason`
(`shared/sdk/event_bus/redis_streams.py`).

## Retry Scheduler, DLQ Replay & Workflow Cancelation

The `retry-scheduler` (port `8015`) is the operator-recovery side of the
unified workflow dispatch.

**Retry scheduler** — `apps/retry-scheduler/` opens a Redis consumer group on
`stream.deadletter`. For each event it sleeps `retry_after_seconds` (capped at
60s) and re-publishes the original event back to `original_stream` with
`event: retry.requeued`. The agent's consumer group then re-processes it. When
the dead-letter event's `retry_count` has already passed `max_retries`, the
scheduler skips the requeue and publishes a `retry.terminal_failure` event on
`stream.deadletter.terminal` instead — the task is bounded, not retried
forever. The consume loop uses `XREADGROUP BLOCK` and each scheduled requeue
uses `asyncio.sleep`; there is no busy polling.

**DLQ replay API**:

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Liveness check |
| GET  | `/status` | Scheduler counters (`requeued_count`, `terminal_failure_count`) |
| GET  | `/deadletter` | List recent dead-letter entries (`?count=N`) |
| POST | `/deadletter/replay/{message_id}` | Replay one entry back to its original stream |

`POST /deadletter/replay/{message_id}` re-publishes the entry as
`event: retry.manual_replay` to its `original_stream`, regardless of
`retry_count`. It is the operator's manual recovery path.

**Workflow cancelation** — `POST /workflow/cancel/{task_id}` moves a
non-terminal workflow to `stage: canceled`, sets `canceled_at` and
`cancel_reason` in the persisted state, and publishes a
`workflow.canceled` notification. `POST /workflow/abort/{task_id}` does the
same for `stage: aborted` (with `aborted_at` and `abort_reason`). Both refuse
to act on a workflow that is already `completed`, `canceled`, `aborted`, or
`rejected`. The body is optional: `{"reason": "..."}`.

**Event ignore after abort** — the orchestrator's workflow-event consumer
checks the persisted stage before applying an agent event. If the workflow is
already `aborted` or `canceled`, the event is ignored: the consumer records an
`audit_logs` row (`decision_type: workflow_event_ignored`) and publishes a
`workflow.event_ignored` notification, and the workflow stays at its
terminated stage.

**Controlled failure** — the development-agent supports
`request.simulate_failure: true`; when set, `handle()` raises a
`SimulatedFailure` so the retry / dead-letter foundation can be exercised
end-to-end. The failure only raises within `handle`; the consumer loop never
crashes.

## Observability — Tracing, Metrics, Grafana

Every service initializes OpenTelemetry tracing (`setup_tracing(service_name)`)
and exposes a Prometheus `/metrics` endpoint
(`shared/sdk/observability/{tracing.py,metrics.py,correlation.py}`).
**No real cloud observability SaaS is contacted** — tracing exports only when
`OTEL_EXPORTER_OTLP_ENDPOINT` is set; metrics are scraped over the local
network by the bundled Prometheus.

**Distributed trace propagation** — every Redis event in the pipeline carries
the same `{task_id, workflow_id, trace_id, span_id}` correlation block. The
orchestrator generates a `trace_id` when it dispatches a workflow; every agent
forwards it to the next stage and generates a fresh `span_id` per hop so a
trace viewer can build the per-stage span graph
(`StreamAgent.correlation_ids`).

**Metrics exposed by `/metrics`** — `workflow_total`,
`workflow_completed_total`, `workflow_failed_total{reason}`,
`workflow_duration_seconds`, `agent_execution_total{agent,status}`,
`agent_execution_failures_total{agent}`, `agent_latency_seconds{agent}`,
`deadletter_total{original_stream}`, `retry_total{kind}`,
`notification_total{event_type}`.

**Stack**:

| Component | Port | Purpose |
|-----------|------|---------|
| `prometheus` | `9090` | Scrapes every service's `/metrics` every 15s |
| `grafana`    | `3000` | Renders the bundled AI Agents SWD Platform dashboard (anonymous Admin in the local/test runtime); Prometheus + Tempo datasources auto-provisioned |
| `tempo`      | `3200` (query), `4317` (OTLP gRPC), `4318` (OTLP HTTP) | Local filesystem trace backend; configured but no real cloud observability SaaS is contacted |
| `alertmanager` | `9093` | Routes Prometheus alerts to a local null receiver; no real Slack / Discord / Telegram / PagerDuty / webhook is contacted |

All bind to `127.0.0.1` only. Configuration lives under
[infra/observability/](infra/observability/):

```
infra/observability/
  prometheus.yml                                          # scrape config + rule_files + alerting
  prometheus/rules/aiagents.rules.yml                     # AI Agents SWD alert rules
  alertmanager/alertmanager.yml                           # Alertmanager (null receiver only)
  tempo/tempo.yml                                         # tempo trace backend (OTLP gRPC + HTTP, local FS)
  grafana/provisioning/datasources/prometheus.yml        # Prometheus datasource
  grafana/provisioning/datasources/tempo.yml             # Tempo datasource (service map links to Prometheus)
  grafana/provisioning/datasources/alertmanager.yml      # Alertmanager datasource (Prometheus implementation)
  grafana/provisioning/dashboards/dashboards.yml         # dashboard provider
  grafana/dashboards/aiagents.json                       # workflow + agent + alerts dashboard
```

**Trace backend (Tempo)** — every service container sets
`OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317`,
`OTEL_EXPORTER_OTLP_PROTOCOL=grpc`, and
`OTEL_SERVICE_NAME=<service-name>`. Tempo's OTLP receivers listen on
`4317` (gRPC) / `4318` (HTTP) and persist traces to `/var/tempo` (a Docker
volume). `usage_report.reporting_enabled: false` keeps Tempo offline. Grafana
auto-provisions a Tempo datasource; the dashboard `serviceMap.datasourceUid`
references the Prometheus datasource (`uid: prometheus`) so the trace
service-map can correlate spans with the agent / workflow metrics.
`scripts/verify_tracing_backend.sh` validates the Tempo container, OTLP port
listeners, and the Grafana Tempo datasource.

**OpenTelemetry auto-instrumentation** — every service calls
`setup_tracing(service_name)` then installs the OpenTelemetry SDK
instrumentations relevant to its stack
(`shared/sdk/observability/tracing.py`):

- `instrument_fastapi(app, name)` produces an HTTP span per incoming request
- `instrument_httpx()` produces a client span for every outbound
  service-to-service call (orchestrator → policy / approval / audit,
  communication-gateway → orchestrator)
- `instrument_redis()` produces a span per Redis command, on top of the
  per-publish / per-consume / per-ack custom spans emitted by
  `RedisStreamEventBus`
- `instrument_asyncpg()` produces a span per SQL statement, on top of the
  per-operation custom spans wrapped around `WorkflowStore`,
  `AgentExecutionStore`, and `deployment_records`

**Custom span hierarchy** — on top of auto-instrumentation each workflow,
agent, and retry step emits a named custom span (`shared/sdk/observability/
tracing.py::start_span`):

| Layer | Span names |
|-------|-----------|
| Orchestrator workflow | `workflow.run`, `workflow.policy_check`, `workflow.approval_request`, `workflow.audit`, `workflow.dispatch`, `workflow.event_update`, `workflow.completed`, `workflow.failed` |
| Agent (`StreamAgent`)   | `agent.receive`, `agent.analyze`, `agent.execute`, `agent.publish_next`, `agent.write_audit`, `agent.publish_notification` |
| Retry scheduler        | `retry.consume_deadletter`, `retry.requeue`, `retry.terminal_failure`, `retry.manual_replay` |
| Redis event bus        | `redis.publish`, `redis.consume`, `redis.consume_multi`, `redis.ack` |
| HTTP clients           | `policy.evaluate`, `approval.request`, `approval.approve`, `approval.reject`, `approval.get`, `audit.record_event`, `audit.get_events` |
| asyncpg (custom)       | `workflow_store.{create,update,get}`, `agent_execution.{create,complete,fail}`, `deployment_records.insert` |

Every custom span carries the `{service.name, task_id, workflow_id, agent,
event_type, stream}` attribute set so Tempo's service-map and Grafana's
TraceQL search can group spans by task / workflow.

**Querying traces in Grafana** — open http://localhost:3000 → Explore →
data source `Tempo`. Pick `TraceQL` and try `{ service.name = "orchestrator"
}` or `{ name = "workflow.dispatch" }`. Each Redis event in the pipeline still
carries the `{task_id, workflow_id, trace_id, span_id}` correlation block, so
`/workflow/progress/{task_id}` and `/workflow/timeline/{task_id}` both expose
the `trace_id` for direct pivoting into Tempo.

**End-to-end verification** — `scripts/verify_trace_flow.sh` seeds one task
through `/intake/mock`, polls `/workflow/progress/{task_id}` until the
workflow reaches `completed`, then queries
`GET http://tempo:3200/api/traces/<trace_id>` and asserts that all seven
service names (`communication-gateway`, `orchestrator`, `intake-agent`,
`requirement-agent`, `development-agent`, `qa-agent`, `devops-agent`) appear
in the same trace.

Open the dashboard at http://localhost:3000 (folder "AI Agents SWD"; the
dashboard `AI Agents SWD Platform`). The Tempo datasource is available
under Connections → Data sources → Tempo.

**Workflow timeline** — `GET /workflow/progress/{task_id}` now also returns
`traces` (`trace_id`, `workflow_id`), `agent_timeline` (chronological per-agent
status + `duration_ms`), and `retry_timeline` (DLQ entries observed for the
task). `GET /workflow/timeline/{task_id}` returns the same timelines as a
condensed, dashboard-friendly view
(`apps/orchestrator/src/progress.py`).

### Alertmanager + Prometheus alert rules

Prometheus loads `infra/observability/prometheus/rules/aiagents.rules.yml`
and forwards firing alerts to the bundled `alertmanager` container at
`http://alertmanager:9093`. Alertmanager routes every alert to a **null
receiver**: no Slack, Discord, Telegram, PagerDuty, OpsGenie, email, or
webhook is contacted from the local/test environment, and no notifier
secret is stored in the repo. Any real off-host notifier must be wired
through Vault and added behind a feature flag.

The rule file ships eight alerts grouped into four families:

| Alert                          | Family            | Severity | Trigger expression |
|--------------------------------|-------------------|----------|--------------------|
| `AIWorkflowFailuresHigh`       | `aiagents.workflow` | warning  | `increase(workflow_failed_total[5m]) > 0` |
| `AIWorkflowLatencyP95High`     | `aiagents.workflow` | warning  | `histogram_quantile(0.95, sum by (le) (rate(workflow_duration_seconds_bucket[5m]))) > 30` |
| `AIAgentExecutionFailuresHigh` | `aiagents.agent`    | warning  | `increase(agent_execution_failures_total[5m]) > 0` |
| `AIDeadletterIncreasing`       | `aiagents.retry`    | warning  | `increase(deadletter_total[5m]) > 0` |
| `AIRetrySpike`                 | `aiagents.retry`    | warning  | `increase(retry_total[5m]) > 5` |
| `AIServiceDown`                | `aiagents.platform` | critical | `up == 0` for 2m |
| `AIPrometheusTargetDown`       | `aiagents.platform` | critical | `up == 0` for 10m |
| `AIApprovalPendingTooLong`     | `aiagents.approval` | warning  | placeholder (`vector(0) > 1`) until an `approval_pending_seconds` metric exists |

Every alert carries `{severity, component}` labels and `{summary,
description, runbook_url}` annotations. The runbook URLs point at this
README anchor until a dedicated runbook ships.

**Verifying alerts** — `scripts/verify_alerting.sh` checks:

- `GET http://localhost:9093/-/healthy` → `ALERTMANAGER_HEALTHY: PASS`
- `GET http://localhost:9093/api/v2/status` returns Alertmanager
  `versionInfo` + `cluster`
- `GET http://localhost:9090/api/v1/rules` exposes ≥ 4 `aiagents.*`
  rule groups and every required `AI*` alert by name
- `GET http://localhost:9090/api/v1/alerts` returns `status: success`
- `GET http://localhost:9090/api/v1/targets` reports every job `up`
- `GET http://localhost:9093/api/v2/receivers` does NOT contain
  `slack` / `discord` / `telegram` / `pagerduty` / `opsgenie` / `webhook`

`scripts/check_runtime_state.sh` calls the same endpoints and emits
`ALERTMANAGER_HEALTH / PROMETHEUS_RULES_SMOKE / PROMETHEUS_ALERTS_API_SMOKE`
markers.

In Grafana Explore the **Alertmanager** datasource is preconfigured with
`implementation: prometheus`, so the **AI Agents SWD Platform** dashboard
gains an *Active alerts (firing)* stat, an *Active alerts over time*
timeseries, and a *Service health (up per job)* table on top of the
existing workflow / agent / retry panels.

**Wiring a real notifier later** — when production notifiers are added,
do not commit the receiver block to git: read the webhook URL / token
from Vault via an entrypoint script, render `alertmanager.yml` from a
template at container start, and gate the rollout behind an explicit
operator switch. The local/test runtime must keep using the null
receiver.

### Incident API + IncidentStore

The orchestrator exposes a `/incidents` API backed by
`shared/sdk/incidents/IncidentStore` and the `incident_records`
PostgreSQL table (migration `005_incident_management.sql` extends the
table with `task_id`, `workflow_id`, `source`, `details`,
`acknowledged_at`, `resolved_at` columns and the matching indexes;
strictly additive and idempotent).

| Endpoint                                  | Purpose                                                                 |
|-------------------------------------------|-------------------------------------------------------------------------|
| `GET /incidents`                          | List incidents; supports `?status=`, `?severity=`, `?task_id=`, `?workflow_id=` |
| `GET /incidents/{incident_id}`            | Fetch one incident                                                       |
| `POST /incidents`                         | Create an operator incident (`summary` required; `severity` defaults to `sev3`; `source` defaults to `operator`) |
| `POST /incidents/{incident_id}/ack`       | Mark as `acknowledged`, set `acknowledged_at`, publish `incident.acknowledged` notification + audit |
| `POST /incidents/{incident_id}/resolve`   | Mark as `resolved`, set `resolved_at`, publish `incident.resolved` notification + audit |

Severities follow the standard four-tier SEV ladder
(`sev1 / sev2 / sev3 / sev4`); statuses are
`open / acknowledged / resolved`. Every create / ack / resolve also
publishes a notification on `stream.notifications` and writes an audit
event via the audit-service. The Alertmanager still routes alerts to a
**null receiver** — no off-host notifier is contacted; the incident API
is the in-platform record of what an operator did about a firing alert.

### Terminal failure → incident → workflow.failed

When the retry-scheduler observes a dead-letter event whose
`retry_count` has already exceeded `max_retries`, it:

1. Publishes the terminal event on `stream.deadletter.terminal` (as
   before).
2. Creates an incident_records row (`severity: sev2`,
   `source: retry-scheduler`, summary including
   *terminal failure / max retries exceeded*, `details` carrying
   `original_stream`, `retry_count`, `max_retries`, `failure_reason`,
   `failed_at`, `original_event`, `original_message_id`).
3. Flips the matching workflow_states row to `stage = failed` and sets
   `execution_result.{status, failure_reason, production_executed,
   failed_at}`. If no workflow row exists, the incident still lands and
   `details.workflow_not_found = true` is recorded; the scheduler does
   not crash.
4. Publishes a `workflow.failed` notification keyed by `task_id`.
5. Writes an audit event `decision_type = workflow_failed` via the
   audit-service.

`scripts/verify_incident_flow.sh` drives this end-to-end: it seeds a
`simulate_failure: true` workflow, polls `/incidents?task_id=...` until
the incident appears, asserts `workflow.stage = failed`, the
`workflow.failed` notification, the audit event, then exercises
`/incidents/{id}/ack` and `/incidents/{id}/resolve`. The aggregate
result is printed as `INCIDENT_FLOW_SMOKE: PASS / FAIL / CHECK`.

`scripts/check_runtime_state.sh` covers the same surface with seven new
inline smokes: `INCIDENT_API_SMOKE`, `INCIDENT_CREATE_SMOKE`,
`INCIDENT_ACK_SMOKE`, `INCIDENT_RESOLVE_SMOKE`,
`TERMINAL_FAILURE_INCIDENT_SMOKE`, `WORKFLOW_FAILED_STATE_SMOKE`,
`SLO_CONFIG_SMOKE`.

### SLO configuration

`infra/observability/slo/aiagents-slo.yml` declares the platform's
service-level objectives. Each SLO carries `name`, `description`,
`target`, `window`, `query`, `severity`, `owner`, `runbook_url`, and a
`status` field (`active` when the underlying metric exists today;
`planned` when the SLO is documented for transparency but its query is
a placeholder pending a metric).

| SLO                                  | Target  | Window | Status   | Query base |
|--------------------------------------|---------|--------|----------|-----------|
| `workflow_completion_p95_seconds`    | ≤ 30s   | 5m     | active   | `histogram_quantile(0.95, … workflow_duration_seconds_bucket …)` |
| `workflow_success_rate`              | ≥ 95%   | 15m    | active   | `workflow_completed_total / (workflow_completed_total + workflow_failed_total)` |
| `agent_failure_rate`                 | ≤ 5%    | 5m     | active   | `agent_execution_failures_total / agent_execution_total` |
| `dlq_growth_rate`                    | ≤ 5/5m  | 5m     | active   | `increase(deadletter_total[5m])` |
| `approval_pending_duration_seconds`  | ≤ 3600s | 1h     | planned  | `vector(0)` (TODO: emit `approval_pending_seconds`) |
| `service_availability`               | ≥ 99%   | 5m     | active   | `avg_over_time(up[5m])` |

The `approval_pending_duration_seconds` SLO is intentionally
`status: planned` and mirrors the placeholder `AIApprovalPendingTooLong`
Prometheus alert: once the approval-engine ships
`approval_pending_seconds`, both will be flipped to real
`histogram_quantile` expressions together. No SLO references a metric
that does not exist without an explicit `status: planned` + `todo:`
field.

## Operational Readiness

The Step 15.5 verification battery covers everything the Step 15.1–15.4
observability stack ships: Docker / runtime, service health, metrics,
Prometheus, Grafana, Tempo, Alertmanager, end-to-end workflow + trace,
incident lifecycle, SLO config, and the safety contract
(`production_executed = false`, no external alert receiver). Run from
the repository root:

```
./scripts/verify_platform_observability.sh
```

A green run ends with:

```
CHECK_RUNTIME_STATE: PASS
VERIFY_TRACING_BACKEND: PASS
VERIFY_TRACE_FLOW: PASS
VERIFY_ALERTING: PASS
VERIFY_INCIDENT_FLOW: PASS
PLATFORM_OBSERVABILITY_VERIFY: PASS
```

The script aggregates the existing
`check_runtime_state.sh / verify_tracing_backend.sh /
verify_trace_flow.sh / verify_alerting.sh / verify_incident_flow.sh`
scripts and adds Docker / health / metrics / Grafana / safety probes on
top, so one command is enough to declare the platform observably
healthy on `10.0.1.31`.

For a human operator walking through the same checks step-by-step,
follow [`docs/operations/manual-verification.md`](docs/operations/manual-verification.md).
For troubleshooting and how-do-I questions (find a workflow by
`task_id`, query a trace, replay the DLQ, ack/resolve an incident),
read [`docs/operations/observability-runbook.md`](docs/operations/observability-runbook.md).

**Current local/test limitation** — the platform is local/test only on
`10.0.1.31`. Alertmanager runs with a **null receiver**: no Slack,
Discord, Telegram, PagerDuty, OpsGenie, webhook, or email destination
is configured, and the verification script enforces that contract.
Mock dev/test deployments always record
`metadata.production_executed = false`; the safety probe in
`verify_platform_observability.sh` fails if any `deployment_records`
row ever flips to `true` or sets `environment = 'production'`. No
production resource is created, modified, or deployed by anything in
this repository.

## Testing

Python dependencies are listed in `requirements.txt`; pytest configuration is
in `pyproject.toml`. Run the test suite from the repository root:

```
./scripts/run_tests.sh
```

This runs `pytest` and, when installed, `ruff`, `black --check`, and `mypy`.
Redis Streams integration tests use a local/test Redis (`REDIS_URL`, default
`redis://localhost:6379`) and are skipped automatically when no Redis is
reachable.

## Production Restriction

**No production deployment is performed without explicit human approval.**
Automation must not create, modify, or deploy production resources.

## Secrets

**No secrets are stored in this repository.** API keys, tokens, passwords, and
other credentials must be supplied via environment variables or a secrets
manager — never committed. See `.gitignore`.
