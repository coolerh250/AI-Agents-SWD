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
| `audit-worker`    | 8006 | —                    | Consumes `stream.audit`, persists into `audit_logs` |
| `discord-gateway` | 8007 | —                    | Discord-sandbox intake + lookup proxy (default mode: `sandbox`) |
| `notification-worker` | 8008 | —                | Consumes `stream.notifications`, records delivery rows (default mode: `sandbox`) |

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

**audit-service** — endpoints `POST /audit/events`,
`GET /audit/events/{task_id}`, and `GET /audit/events`
(query by `task_id`, `agent`, `decision_type`, `limit`). The orchestrator's
`audit` node still calls `POST /audit/events` directly (it needs the
synchronous `audit_id` to record under the workflow's `audit_refs`); the
event is persisted to the PostgreSQL `audit_logs` table and republished to
the `stream.audit` Redis stream as `{"event": "audit.recorded", ...}`. The
governance columns are added by `migrations/002_governance_tables.sql`.

**audit-worker (Stage 19)** — `apps/audit-worker/` consumes `stream.audit`
with the existing `audit-group` consumer group (`XREADGROUP BLOCK` — no
busy polling), normalizes each event via `shared/sdk/audit/normalizer.py`,
and writes it through `shared/sdk/audit/store.py` (`AuditStore`) into the
same `audit_logs` table. It is the **single unified audit path** for every
service / agent that publishes to `stream.audit`:

    service / agent  --publish-->  stream.audit  --consume-->  audit-worker  -->  audit_logs

Key contracts:

* **`audit.recorded` echo filtering.** When `POST /audit/events` writes a
  row it republishes a `{"event": "audit.recorded", ...}` envelope onto
  `stream.audit`. The worker's `is_audit_recorded_echo` check skips and
  ACKs that envelope so persistence never triggers a circular write loop.
* **ACK after persist.** A successful `INSERT` is followed by an `XACK`;
  a failed `INSERT` is left un-ACKed so the consumer group redelivers.
  After `MAX_FAILURES_BEFORE_DEADLETTER = 3` failed attempts the
  envelope is routed to `stream.deadletter` as `audit.deadlettered`
  (so a poison message can't block the group's pending list) and ACKed.
* **Dedup.** Each persisted row carries `artifact_refs.source_message_id`
  (the `XADD` id); a small in-process LRU short-circuits redeliveries.
  This is runtime cache only — see Stage 19 progress notes for the
  edge-case window after a worker crash.
* **Backlog behaviour.** The `audit-group` consumer group on
  `stream.audit` was created with `$` MKSTREAM in Stage 15.5's
  `init_redis_streams.sh` but had no consumer connected until
  Stage 19. When the audit-worker first comes up, its
  `XREADGROUP >` call drains every event that arrived AFTER
  group-creation (the Pre-Step-18 measurement saw `lag≈5532`).
  The `audit.recorded` filter classifies those events
  correctly — historical POST echoes are skipped (they are
  already in `audit_logs`) and historical StreamAgent-only
  publishes become new `audit_logs` rows. After the first run
  `XINFO GROUPS stream.audit` reports `lag=0`. The drain is a
  one-time event; steady-state is one row per workflow stage,
  per agent.
* **Direct HTTP audit-write deprecation.** As of Stage 19 the three
  producers `devops-agent` (`github_pr_integration`),
  `retry-scheduler` (`workflow_failed`), and `github-automation`
  (`github_automation`) publish via `shared.sdk.audit.publisher`
  instead of calling `audit-service` over HTTP. The audit-service
  POST endpoint stays in place for orchestrator workflow audits (which
  need the synchronous `audit_id`) and for any operator-driven
  incident audits, plus as a compatibility surface — no agent or
  worker is forced through it.

The audit-worker exposes `/health`, `/status`, and `/metrics`
(`audit_worker_processed_total`, `audit_worker_failures_total`,
`audit_worker_deadlettered_total`, `audit_worker_skipped_total`,
`audit_worker_processing_seconds`). Spans:
`audit_worker.consume / .normalize / .persist / .deadletter / .skip`,
each carrying `task_id`, `agent`, `decision_type`, `redis.message_id`,
`stream=stream.audit`.

The orchestrator's `/workflow/timeline/{task_id}` carries an
`audit_timeline` list, sourced from `audit_logs`, so an operator sees the
`github_pr_integration` / `github_automation` / `workflow_failed` rows
inline with the agent timeline.

## Operations Control API (Stage 20)

Stage 20 introduces a unified read-only operator namespace under
`/operations/*` on the orchestrator (`apps/orchestrator/src/operations.py`).
It collapses status surfaces that previously required hitting half a dozen
endpoints into one place:

| Endpoint | Returns |
|----------|---------|
| `GET /operations/health` | `{"service":"operations","status":"ok"}` |
| `GET /operations/summary` | Cluster-wide totals: services / workflows / agents / incidents / DLQ / GitHub / audit / production safety |
| `GET /operations/workflows/{task_id}` | Unified workflow view: workflow + progress + agents + audit_timeline + incidents + deployment + github + dlq + notifications + trace + safety |
| `GET /operations/agents` | Pipeline overview — one row per agent with health, processed/failed counts, last task, streams, consumer group, 24h execution counts |
| `GET /operations/agents/{agent_name}` | Per-agent detail: + recent executions + recent audit events + input-stream XINFO |
| `GET /operations/streams` | XINFO for each platform stream (`stream.tasks` … `stream.deadletter.terminal`) — length / consumers / pending / lag / last-delivered-id / status |
| `GET /operations/safety` | Production safety counters + GitHub mode flags + Alertmanager receivers + safe/warning/unsafe verdict |
| `GET /operations/incidents` | Reuses `IncidentStore.list_incidents` (filters: `status`, `severity`, `task_id`, `limit`) |
| `GET /operations/dlq` | `stream.deadletter` + `stream.deadletter.terminal` snapshot (filters: `task_id`, `stream`, `terminal=true`) |
| `GET /operations/github/{task_id}` | Per-task GitHub view from `workflow_states.execution_result.github` + `deployment_records.metadata.github` + `audit_logs(github_pr_integration | github_automation)` |

**Contract:**

* **Read-only.** Nothing in `/operations/*` inserts, updates, deletes,
  ACKs, replays, or otherwise mutates platform state. A failing data
  source returns its empty shape plus a `warnings` entry rather than
  blowing up the whole view (the exception is
  `/operations/workflows/{task_id}` which returns `404` only when the
  workflow row itself doesn't exist).
* **No secrets.** `github_has_token` is exposed as a boolean only —
  the token value never leaves the env var.
* **Metrics + spans.** Every endpoint records
  `operations_requests_total{endpoint,result}`,
  `operations_request_failures_total{endpoint,reason}`,
  `operations_request_duration_seconds{endpoint}`, and emits an
  `operations.<view>` OTel span with `endpoint` / `result` / `task_id`
  / `agent` attributes.
* **`stream.notifications` known gap.** The streams view labels its
  status `not_unified_by_design` when `consumers=0` — a documented Stage
  19 follow-up, not a regression.

`/operations/safety.result` is `safe` when every production counter
is `0` and no warning fires; `warning` when counters are `0` but an
external Alertmanager receiver is configured or `GITHUB_TOKEN` is
present with `GITHUB_DRY_RUN=false`; `unsafe` only when
`deployment_records.production_executed=true OR environment=production`
or `workflow_states.execution_result->>'production_executed'='true'`
is non-zero.

## Discord Gateway Sandbox (Stage 21)

Stage 21 introduces a sandbox Discord intake service
(`apps/discord-gateway/`) on `127.0.0.1:8007`. The default mode is
`sandbox` — no real Discord API is contacted at any point unless the
opt-in pre-conditions documented below are met. The gateway turns
Discord-shaped messages into platform tasks by reusing the same
`communication-gateway /intake/mock` contract every other client uses,
so the downstream pipeline is unchanged.

| Endpoint | Purpose |
|----------|---------|
| `GET  /health` | `{"service":"discord-gateway","status":"ok","mode":"sandbox","has_token":false}` |
| `GET  /status` | Running counters (`received_count`, `dispatched_count`, `failed_count`, `last_task_id`, `last_error`) + mode + `real_test_enabled` |
| `GET  /metrics` | Prometheus surface — `discord_messages_received_total{command_type,sandbox}`, `discord_tasks_dispatched_total{command_type,result,sandbox}`, `discord_intake_failures_total{reason}`, `discord_notifications_published_total{event_type,sandbox}`, `discord_request_duration_seconds{endpoint}` |
| `POST /discord/messages` | Simplified text payload — `{content, channel_id, user_id, message_id, task_id}` |
| `POST /discord/events/mock` | Discord-like INTERACTION/MESSAGE payload with `data.options` |
| `GET  /discord/messages` | The last 20 sandbox messages the gateway has seen (in-memory ring) |
| `GET  /discord/tasks/{task_id}` | Proxies `/operations/workflows/{task_id}` and reduces it to the operator-friendly fields the Discord UX needs |
| `POST /discord/notify/test` | Publishes a `discord.notification.test` event onto `stream.notifications` + a `discord_notification_test` audit row (sandbox only) |
| `POST /discord/real/test-message` | **Opt-in only.** Sends ONE Discord message via the real API; refused with HTTP 409 unless `DISCORD_BOT_TOKEN` is set AND `RUN_REAL_DISCORD_TEST=true` |

### Command syntax

| Shape | Example |
|-------|---------|
| Slash-like | `/ai task type=dev.test description="create user management module"` |
| Natural | `ai task: create user management module` |
| Production (still goes through the approval gate) | `/ai task type=production.deploy description="deploy to production"` |
| GitHub options | `/ai task type=dev.test description="update docs" github.enabled=true github.dry_run=true` |
| Disable GitHub for one task | `/ai task type=dev.test description="test only" github.enabled=false` |

`task_id` defaults to `discord-<timestamp>-<shortid>`; the caller can
override via `task_id=…`. `request.type` defaults to `dev.test`,
`request.github.enabled` and `request.github.dry_run` default to `true`,
and `request.github.repo` defaults to `coolerh250/AI-Agents-SWD`.

### Sandbox contract

* The default mode is `sandbox` — every endpoint runs without ever
  contacting `discord.com`. Notifications are published to the existing
  `stream.notifications` Redis stream with `sandbox: true` plus one of
  `discord.task.received` / `discord.task.dispatched` /
  `discord.task.waiting_approval` / `discord.task.completed` /
  `discord.notification.test`. There is no new notification consumer
  in Stage 21; the events are observable through
  `GET /notifications` on communication-gateway.
* Audit events go through `shared/sdk/audit/publisher` (Stage 19) onto
  `stream.audit`; the audit-worker persists them with
  `decision_type=discord_intake` or `discord_notification_test`. So a
  task created from Discord is queryable via
  `GET /audit/events?decision_type=discord_intake` and via
  `audit_timeline` on `/operations/workflows/{task_id}` and
  `/workflow/timeline/{task_id}`.
* `production.deploy` still goes through the orchestrator approval
  gate — the Discord intake returns
  `stage=waiting_approval, approval_required=true,
  event_type=discord.task.waiting_approval`. No agent dispatch and no
  `production_executed` flip ever happens from this path.
* GitHub PRs remain dry-run by default. The Discord parser sets
  `request.github.dry_run=true` even for production tasks; the safety
  contract is owned by the orchestrator, not by the parser.

### Optional real Discord test guard

The single real-Discord code path is `POST /discord/real/test-message`.
It is hard-gated by **all** of:

* `DISCORD_BOT_TOKEN` is set (non-empty), and
* `RUN_REAL_DISCORD_TEST=true`, and
* a `channel_id` is supplied.

If any of these is missing the route returns HTTP 409 with a safe
detail. When the route does run, it issues exactly one `POST
/channels/{channel_id}/messages` with the body prefixed by
`[AI-Agents-SWD sandbox]`; the token never appears in the response.
No production deploy is ever executed from this path; no real GitHub
write is ever executed from this path. The default verify run
(`verify_discord_gateway.sh`) asserts the route is refused without the
opt-in flags.

### Operations integration

`/discord/tasks/{task_id}` returns:

```
{
  "task_id": "...",
  "stage": "completed",
  "execution_status": "completed",
  "completed_agents": ["intake-agent", ..., "devops-agent"],
  "github": {"pr_url": "...", "dry_run": true, "status": "success"},
  "audit_timeline_count": 7,
  "incidents_count": 0,
  "production_executed": false,
  "operations_url": "/operations/workflows/{task_id}",
  "operations_view": {...full unified view...},
  "sandbox": true
}
```

The `operations_view` field is the verbatim
`/operations/workflows/{task_id}` body the orchestrator already
serves (Stage 20).

## Notification Delivery Worker (Stage 22)

Stage 22 introduces a controlled Discord delivery surface
(`apps/notification-worker/`) on `127.0.0.1:8008`. The default mode is
`sandbox` — every event consumed from `stream.notifications` is
persisted as a row in the new `notification_deliveries` table with
`status='simulated'`, `sandbox=true`, `external_sent=false`. The real
Discord API is contacted ONLY when **all three** of the following are
true:

* `DISCORD_BOT_TOKEN` is non-empty,
* `DISCORD_TEST_CHANNEL_ID` is non-empty,
* `RUN_REAL_DISCORD_TEST=true`.

Even then the worker sends a single message to `DISCORD_TEST_CHANNEL_ID`
only, prefixed with `[AI-Agents-SWD sandbox]`, and never serializes the
token value into a response body or log line.

| Endpoint | Purpose |
|----------|---------|
| `GET  /health` | `{"service":"notification-worker","status":"ok","mode":"sandbox"\|"controlled-real","has_discord_token":bool,"real_discord_enabled":bool}` |
| `GET  /status` | Running counters (`processed_count`, `delivered_count`, `simulated_count`, `failed_count`, `skipped_count`, `last_message_id`, `last_task_id`, `last_error`) + mode + opt-in flags |
| `GET  /summary` | `/status` + aggregated `delivery_counts` from `notification_deliveries` |
| `GET  /deliveries` | List notification_deliveries (filters: `task_id`, `status`, `limit`) |
| `GET  /metrics` | `notification_worker_processed_total{event_type}`, `notification_worker_delivered_total{event_type,channel}`, `notification_worker_simulated_total{event_type,channel}`, `notification_worker_failures_total{reason}`, `notification_worker_skipped_total{reason}`, `notification_worker_processing_seconds` |
| `POST /discord/real/test-message` | **Opt-in only.** Send ONE controlled-real Discord message to `DISCORD_TEST_CHANNEL_ID`; refused with HTTP 409 unless all three env vars above are set. |

### notification_deliveries

Migration `006_notification_delivery.sql` adds one table:

```
notification_deliveries (
  id UUID PRIMARY KEY,
  task_id TEXT,
  event_type TEXT,
  channel TEXT DEFAULT 'discord',
  target TEXT,
  status TEXT,          -- pending|simulated|delivered|failed|skipped
  sandbox BOOLEAN,
  external_sent BOOLEAN,
  message_id TEXT,
  error TEXT,
  source_message_id TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ,
  delivered_at TIMESTAMPTZ
)
```

`source_message_id` carries the Redis `XADD` id of the consumed event;
a partial unique index on it gives the worker a free `ON CONFLICT DO
NOTHING` dedup check.

### discord-gateway integration

discord-gateway gained two delivery-aware endpoints on the existing
service (port `8007`):

* `GET /discord/deliveries` — list notification_deliveries (same
  filters as `notification-worker /deliveries`).
* `GET /discord/deliveries/{task_id}` — per-task delivery breakdown
  (`count`, `external_sent_count`, `simulated_count`,
  `failed_count`).

`GET /discord/tasks/{task_id}` was extended with
`notification_deliveries_count`, `latest_delivery_status`,
`latest_delivery_message_id`, `external_sent`, and a
`delivery_breakdown` block so the operator UX still gets the answer in
one round trip.

### Operations integration

* `/operations/workflows/{task_id}` adds a `notification_deliveries`
  section (`count`, `latest_status`, `external_sent_count`,
  `simulated_count`, `failed_count`, `deliveries`).
* `/operations/summary` adds a `notification_delivery_summary` block
  (`total_deliveries`, `simulated_deliveries`,
  `delivered_deliveries`, `external_sent_deliveries`,
  `failed_deliveries`, `skipped_deliveries`).
* `/operations/safety` adds Discord booleans:
  `discord_has_token`, `discord_test_channel_configured`,
  `discord_real_test_enabled`, `discord_external_send_enabled`. The
  token value is never returned. `result` stays `safe` when every
  production counter is `0`; flips to `warning` when
  `discord_external_send_enabled=true` (a Discord credential was
  loaded into the container) or one of the existing Stage-20 warnings
  fires; `unsafe` only when a production counter is non-zero.

### Audit integration

Every consumed notification produces an audit event via the Stage 19
publisher and is persisted by audit-worker:

| decision_type | When |
|---|---|
| `notification_delivery` | sandbox simulation recorded |
| `discord_real_test_sent` | controlled-real Discord delivery succeeded |
| `notification_delivery_failed` | Discord call raised |
| `discord_real_test_skipped` | `POST /discord/real/test-message` refused (opt-in env missing) |

`artifact_refs` always carries `task_id`, `event_type`, `sandbox`,
`external_sent`, `delivery_id`, `source_message_id`.

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

## GitHub Automation Service

Stage 17 ships a `github-automation` service on port `127.0.0.1:8005`
(`apps/github-automation/`). It is the platform's single in-cluster
boundary for GitHub REST calls — backed by `shared/sdk/github/`
(`GitHubClient`).

### Default contract: dry-run

The service runs **dry-run by default**. Every call to
`/github/issue`, `/github/branch`, `/github/file`,
`/github/pull-request`, `/github/checks`,
`/github/pull-request/{number}`, and the aggregate
`/github/workflow/demo-pr` returns a deterministic mock response and
contacts **no real GitHub API** unless the caller passes
`dry_run=false` *and* the container has a `GITHUB_TOKEN` env var.

`GITHUB_TOKEN` is read from the environment only — never from a file,
never from a constructor argument, never echoed in any response or log.
The Docker Compose stanza pulls it from `${GITHUB_TOKEN:-}`, so the
token is owned by the operator's shell, not the repository.

| Endpoint                            | Purpose                                  |
|-------------------------------------|------------------------------------------|
| `GET /health`                       | Service liveness (also returns `has_token`) |
| `POST /github/issue`                | Create an issue (dry-run or real)         |
| `POST /github/branch`               | Create a branch from a base ref           |
| `POST /github/file`                 | Create or update a file on a branch       |
| `POST /github/pull-request`         | Open a PR                                |
| `GET /github/pull-request/{number}` | Fetch one PR                             |
| `GET /github/checks?ref=...`        | Read check-runs on a ref                  |
| `POST /github/workflow/demo-pr`     | Aggregate: issue → branch → file → PR → checks |

### Demo-PR workflow

`POST /github/workflow/demo-pr` walks the issue → branch → file → PR →
checks sequence, builds a PR body with the five required sections
**Summary / Changed Files / Risk Assessment / Test Result /
Rollback Plan**, publishes a `github.pr.dry_run` (or
`github.pr.created` for real runs) notification on
`stream.notifications`, and writes one audit row with
`decision_type='github_automation'`. Each step also increments the
matching Prometheus counter:

```
github_issue_created_total{dry_run="true|false"}
github_branch_created_total{dry_run="true|false"}
github_pr_created_total{dry_run="true|false"}
github_checks_read_total{dry_run="true|false"}
github_automation_failures_total{operation="..."}
```

The communication-gateway exposes `POST /github/demo-pr` as an
in-cluster proxy so other services don't have to know the
`github-automation:8005` URL directly.

### PR body requirements

Every demo PR carries:

```
## Summary
## Changed Files
## Risk Assessment
## Test Result
## Rollback Plan
```

The `build_pr_body` helper enforces this layout; `tests/test_github_pr_template.py`
asserts the five sections exist and stay in that order.

### Real GitHub test — opt-in only

The `verify_github_automation.sh` script runs the dry-run flow by
default. It will only issue a real GitHub call when **both**
environment variables are set:

```
GITHUB_TOKEN=ghp_REAL_OR_FINE_GRAINED
RUN_REAL_GITHUB_TEST=true
```

Even then, the PR title is forced to begin with
`[AI-Agents-SWD Test]`, the branch is `ai-agents-swd/real-<ts>`, the
PR is left **open** (never merged), and branch protection / production
resources are never touched. See
[`docs/operations/github-automation-runbook.md`](docs/operations/github-automation-runbook.md)
for the full safety contract and rollback steps.

### Verification

```
./scripts/verify_github_automation.sh
```

Expected: `checks passed: 7 / 7` then `GITHUB_AUTOMATION_VERIFY: PASS`.

The aggregate `verify_platform_observability.sh` still passes after
this stage; `check_runtime_state.sh` gained five new smokes
(`GITHUB_AUTOMATION_HEALTH`, `GITHUB_DEMO_PR_DRY_RUN_SMOKE`,
`GITHUB_AUDIT_SMOKE`, `GITHUB_NOTIFICATION_SMOKE`,
`GITHUB_METRICS_SMOKE`).

### Agent pipeline → GitHub PR integration

Stage 18 wires `devops-agent` to call
`github-automation /github/workflow/demo-pr` after its mock dev/test
deployment. The result is folded into `deployment_records.metadata.github`
and propagated to the orchestrator on the
`devops.deployment_simulated` event so `workflow_states.execution_result.github`
ends up with: `status`, `dry_run`, `issue_url`, `branch`, `pr_url`,
`pr_number`, `checks_status`, `event_type`.

`/workflow/progress/{task_id}` surfaces `pr_url`, `github_status`,
`github_dry_run`, and the full `github` envelope.
`/workflow/timeline/{task_id}` appends one of:

* `github.demo_pr.dry_run` — successful dry-run (default path)
* `github.demo_pr.created` — successful real-mode run (opt-in)
* `github.demo_pr.failed` — github-automation HTTP/connection error
* `github.demo_pr.skipped` — `request.github.enabled = false`

To trigger the integration from `communication-gateway`:

```json
POST /intake/mock
{
  "task_id": "github-pipeline-001",
  "request": {
    "type": "dev.test",
    "description": "verify pipeline github integration",
    "github": {
      "enabled": true,
      "repo": "coolerh250/AI-Agents-SWD",
      "base_branch": "main",
      "dry_run": true
    }
  }
}
```

`request.github` is optional. When absent, the integration runs in its
default mode (enabled, dry-run). Set `enabled: false` to skip the
github-automation call entirely (devops-agent still simulates the
deployment record). Switching `dry_run: false` only takes effect when
`github-automation` has `GITHUB_TOKEN` set — without a token the SDK
raises `GitHubMissingTokenError` and `run_demo_pr` returns
`status=failed` instead of touching the network. See
[`docs/operations/github-automation-runbook.md`](docs/operations/github-automation-runbook.md)
for the full safety contract.

Two new Prometheus counters track the integration:

```
github_pipeline_integration_total{dry_run="true|false"}
github_pipeline_integration_failures_total{reason="http_error|safe_failure|disabled"}
```

Verification:

```
./scripts/verify_github_pipeline_flow.sh
```

Expected: `checks passed: 7 / 7` (or `6/7` if Tempo lags) then
`GITHUB_PIPELINE_FLOW_VERIFY: PASS`. `check_runtime_state.sh` gained
six new smokes:
`GITHUB_PIPELINE_INTEGRATION_SMOKE`,
`GITHUB_WORKFLOW_RESULT_SMOKE`, `GITHUB_TIMELINE_SMOKE`,
`GITHUB_PIPELINE_AUDIT_SMOKE`, `GITHUB_PIPELINE_NOTIFICATION_SMOKE`,
`GITHUB_PIPELINE_TRACE_SMOKE`.

**Safety contract reminder.** The integration is local/test only and
**dry-run** by default. It never merges, never modifies branch
protection, never deploys to production, and only flips to real-mode
when both `GITHUB_TOKEN` and an explicit `dry_run=false` arrive
together. The workflow_states row keeps
`execution_result.production_executed = false` regardless of
`dry_run`.

## Controlled Real GitHub Validation (Stage 23)

Stage 23 adds a strictly-guarded endpoint that lets an operator open
**one** real GitHub PR against a pinned sandbox repository — without
merging it, modifying branch protection, deleting branches, or touching
any production resource. By default the cluster runs in **sandbox-only**
mode: the endpoint returns HTTP 409 and writes an
`audit_logs.decision_type=github_real_test_blocked` row.

### Required environment (all three must be set to opt in)

```
GITHUB_TOKEN=<a sandbox-scoped fine-grained PAT, never committed>
RUN_REAL_GITHUB_TEST=true
GITHUB_TEST_REPO=coolerh250/AI-Agents-SWD   # or another sandbox repo
```

Missing any one of the three → the guard refuses every real-test request
with `safety_guard_result.reason` set to one of `missing_github_token`,
`run_real_github_test_not_true`, or `missing_github_test_repo`.

### Sandbox repo requirement

`GITHUB_TEST_REPO` pins the only repo the controlled-real flow may write
to. The guard rejects any request whose `repo` does not equal that env
var (reason `repo_mismatch`). This makes it impossible to redirect a
real PR to an unintended repository by tampering with the request body.

### Allowed actions

The controlled-real flow walks `issue → branch → file → PR → checks`.
Every step is annotated with `dry_run=false`, `real_github_test=true`,
`production_executed=false` in audit / notification / metrics / spans.

### Forbidden actions

The guard rejects, at the safe-error path before any GitHub API call:

* `branch_name` not starting with `ai-agents-test/`
* `title` not starting with `[AI-Agents-SWD Test]`
* `base_branch` in `production` / `prod` / `release/*`
* `dry_run` not exactly `false`
* `file_path` outside `docs/github-real-test/`
* `file_content` missing any of `task_id`, `workflow_id`,
  `generated_by=github-automation`, `real_github_test=true`,
  `production_executed=false`
* PR body missing any of `## Summary`, `## Changed Files`,
  `## Risk Assessment`, `## Test Result`, `## Rollback Plan`, or
  `## Safety Notes`

The endpoint never merges the PR, never modifies branch protection,
never deletes a branch, never creates a release, never triggers a
production deployment.

### How to verify SKIPPED mode (default)

```
./scripts/verify_real_github_validation.sh
```

Expected (no opt-in env set):

```
REAL_GITHUB_TEST_SKIPPED: PASS
REAL_GITHUB_VALIDATION_VERIFY: PASS
```

The script also asserts the guard refuses with HTTP 409 and that the
response carries no token-shaped substring.

### How to run the controlled real test (opt-in)

After exporting the three env vars above and restarting the
`github-automation` + `orchestrator` containers:

```
export GITHUB_TOKEN=<sandbox PAT>
export RUN_REAL_GITHUB_TEST=true
export GITHUB_TEST_REPO=coolerh250/AI-Agents-SWD
docker compose -f infra/docker-compose/docker-compose.yml up -d \
  --force-recreate github-automation orchestrator
./scripts/verify_real_github_validation.sh
```

The script then issues ONE controlled-real PR and asserts:

* the PR + issue + branch URLs come back in the response;
* `audit_logs.decision_type=github_real_test` is written;
* `event_type=github.real_test_pr.created` is published on
  `stream.notifications` with `sandbox=true`,
  `production_executed=false`;
* `/operations/github/{task_id}` carries
  `real_test.safety_guard_result.latest_success`.

The PR is **never merged**. The operator is expected to close it and
delete the head branch manually after inspection.

### How to inspect `/operations/github/{task_id}`

```
curl -sS http://localhost:8000/operations/github/<task_id> | python -m json.tool
```

Returns the existing dry-run section plus a Stage 23 `real_test` block:

```
{
  "real_test": {
    "found": true,
    "dry_run": false,
    "real_github_test": true,
    "production_executed": false,
    "issue_url": "...",
    "branch": "ai-agents-test/<task_id>",
    "pr_url": "...",
    "checks_status": "completed",
    "safety_guard_result": { "latest_success": {...}, "latest_blocked": {...} }
  }
}
```

`/operations/safety` carries four new booleans (no token value):

```
{
  "github_has_token": false,
  "real_github_test_enabled": false,
  "github_test_repo_configured": false,
  "github_external_write_enabled": false
}
```

`github_external_write_enabled = github_has_token AND
real_github_test_enabled AND github_test_repo_configured`. Whenever it
is `true`, `/operations/safety` adds a `github_external_write_enabled`
warning to the response so the platform's verdict downgrades from
`safe` to `warning`.

### Metrics

```
github_real_test_attempts_total{repo,result}
github_real_test_success_total{repo,result}
github_real_test_blocked_total{repo,reason}
github_real_test_failures_total{repo,reason}
github_real_test_duration_seconds{repo,result}
```

### Tracing

The endpoint emits one custom span per stage:

```
github.real_test.guard
github.real_test.create_issue
github.real_test.create_branch
github.real_test.create_file
github.real_test.create_pr
github.real_test.read_checks
```

Every span carries `github.dry_run=false`,
`github.real_github_test=true`, and the `task_id` / `workflow_id`.

## Staging Runtime Hardening (Stage 24)

Stage 24 ships a **staging-readiness baseline** — runtime config
validator, secrets baseline, staging compose template, backup /
restore scripts, production safety gate, and a runtime health
snapshot. Nothing in Stage 24 promotes the platform to production;
the local cluster on `10.0.1.31` keeps its existing trust-auth /
Vault-dev-mode / null-receiver posture.

### Runtime config validation

```
./scripts/validate_runtime_config.sh --mode local
./scripts/validate_runtime_config.sh --mode staging --env-file .env.staging
./scripts/validate_runtime_config.sh --mode production-check
```

Modes:

* **local** — current cluster default. Trust-auth / Vault dev-mode /
  null-receiver tolerated; opt-in real-test consistency still enforced.
* **staging** — placeholder secrets in required fields fail;
  trust-auth fails; Vault dev-mode fails unless
  `ALLOW_VAULT_DEV_MODE_FOR_STAGING=true` (downgraded to a warning).
* **production-check** — read-only audit pass. No trust-auth, no
  Vault dev-mode, no null-receiver, and (when the validator can read
  the sentinel) `production_executed=true` count must be `0`.

The validator never echoes secret values; findings reference variable
names and a `present: bool` flag only.

### Secrets baseline

[`shared/sdk/secrets/`](shared/sdk/secrets/) adds a small
`SecretProvider` abstraction:

```python
from shared.sdk.secrets import default_provider
token = default_provider().get_secret("GITHUB_TOKEN")
if token:                              # SecretRef.__bool__
    headers["Authorization"] = f"Bearer {token.reveal()}"
```

`SecretRef` redacts itself in `repr` / `str` / `model_dump`. The
`VaultPlaceholderProvider` exposes the same interface for a future
real-Vault integration without changing any call site. `redact_mapping`
strips every secret-shaped key (token / secret / password / api_key /
credential / private_key) from a dict, so audit / log / response
bodies can route through one helper.

The Discord clients in `apps/discord-gateway` and
`apps/notification-worker`, plus the GitHub-automation `/health`
endpoint, now read tokens through `SecretProvider` — `has_token`
remains a boolean and the value never lives in a plain-string
attribute on the client instance.

### Staging compose template

[`infra/docker-compose/docker-compose.staging.yml`](infra/docker-compose/docker-compose.staging.yml)
is a **template**, not a drop-in replacement for the existing
`docker-compose.yml`. It demonstrates:

* `POSTGRES_PASSWORD` required via `${VAR:?error}` substitution;
* no `POSTGRES_HOST_AUTH_METHOD=trust`;
* separate `postgres-staging-data` volume so a staging upgrade can't
  accidentally clobber the local/test data;
* no Vault dev-mode container — staging is expected to point at a
  real Vault.

To validate the template:

```
docker compose -f infra/docker-compose/docker-compose.staging.yml config
```

### Backup / restore

```
./scripts/backup_postgres.sh
./scripts/verify_backup_restore.sh
ALLOW_RESTORE=true ./scripts/restore_postgres.sh backups/aiagents-<ts>.dump
```

The backup script writes to `backups/` (gitignored). The restore
script refuses unless `ALLOW_RESTORE=true` is set AND a backup file
is passed as the first positional argument; it also refuses outright
when `APP_ENV` is `production` / `production-check`. The verify
script takes a fresh backup, asserts `pg_restore -l` parses the TOC,
confirms the live DB's table count was untouched, and asserts the
restore guard refuses without `ALLOW_RESTORE=true`.

### Production safety gate

```
./scripts/production_safety_gate.sh
```

Read-only. Inspects `deployment_records`, `workflow_states`,
`/operations/safety`, and Alertmanager receivers. Exits `0` (PASS)
when every production counter is `0` and the platform is still in
sandbox-by-default; exits `1` (FAIL) otherwise.

### Runtime health snapshot

```
./scripts/runtime_health_snapshot.sh
cat source/runtime-health.log
```

Writes a flat summary to `source/runtime-health.log` (gitignored).
The file carries `docker compose ps`, `/operations/summary`,
`/operations/safety`, Prometheus targets up/down, stream lag, open
incidents, DLQ counts, and the production-safety counters. The Stage
24 verify script greps for token-shaped substrings as a regression
guard.

### Aggregate verifier

```
./scripts/verify_staging_hardening.sh
```

Runs every Stage 24 artefact in sequence: validator (local mode),
production safety gate, backup/restore smoke, runtime health
snapshot, no-token-leak grep, staging template no-trust-auth check,
env example placeholder-only check, `production_executed=false`
SQL, and the SecretProvider redaction self-test. Ends with
`STAGING_HARDENING_VERIFY: PASS` when all 9 checks pass.

See [`docs/operations/staging-runtime-hardening.md`](docs/operations/staging-runtime-hardening.md)
for the full operator runbook, fine-grained token requirements, and
the staging readiness checklist.

## Staging Environment Bring-up (Stage 25)

Stage 25 takes the Stage 24 staging hardening baseline and actually
brings up a parallel staging cluster on the same host. The staging
project uses the docker compose project name `aiagents-staging` (not
`aiagents-test`), every host port is offset by **+10000** so it
coexists with the local/test stack, every Postgres consumer uses
**password auth** (no trust), and the staging data lives in its own
set of volumes (`postgres-staging-data`, `prometheus-staging-data`, …).

The default verify path tears the staging stack DOWN after asserting
the end-to-end flow, so the test cluster doesn't carry two 22-service
stacks at once.

### Generating the staging env file

```
./scripts/generate_staging_env.sh
```

Writes `infra/runtime/.env.staging.local` (gitignored) from the
placeholder template with a freshly-generated random `POSTGRES_PASSWORD`.
The other secret-shaped fields keep the placeholder marker so the
validator catches half-configured envs. Re-running refuses to
overwrite unless `ALLOW_OVERWRITE=true` is set.

### Bringing the staging stack up

```
./scripts/start_staging_runtime.sh [--rebuild]
```

The script validates the env via `validate_runtime_config.sh --mode
staging`, brings up `aiagents-staging` (docker compose project) on
the +10000 host ports, waits for Postgres + Redis, applies every
migration in `migrations/` against the staging DB, initialises Redis
Streams, and restarts the consumer services so they pick up the
freshly migrated tables.

| Service | Local host port | Staging host port |
|---------|-----------------|--------------------|
| postgres | 5432 | **15432** |
| redis | 6379 | **16379** |
| vault | 8200 | **18200** |
| orchestrator | 8000 | **18000** |
| policy-engine | 8001 | **18001** |
| approval-engine | 8002 | **18002** |
| audit-service | 8003 | **18003** |
| communication-gateway | 8004 | **18004** |
| github-automation | 8005 | **18005** |
| audit-worker | 8006 | **18006** |
| discord-gateway | 8007 | **18007** |
| notification-worker | 8008 | **18008** |
| intake-agent | 8010 | **18010** |
| 4 other agents | 8011-8014 | **18011-18014** |
| retry-scheduler | 8015 | **18015** |
| prometheus | 9090 | **19090** |
| grafana | 3000 | **13000** |
| alertmanager | 9093 | **19093** |
| tempo | 3200 / 4317 / 4318 | **13200 / 14317 / 14318** |

Service-to-service URLs (`http://postgres:5432`, `http://orchestrator:8000`,
…) use docker's internal DNS and stay unchanged.

### Stopping the staging stack

```
./scripts/stop_staging_runtime.sh             # keep volumes
./scripts/stop_staging_runtime.sh --volumes   # purge staging volumes too
```

### End-to-end staging verification

```
./scripts/verify_staging_runtime.sh                # default: --down after PASS
./scripts/verify_staging_runtime.sh --keep-running # leave staging running
./scripts/verify_staging_runtime.sh --no-rebuild   # skip docker build
```

Runs 12 checks: env present + placeholder-safe → validator staging
mode → start staging → health → Postgres password auth → migrations
applied → e2e workflow through discord-gateway → github dry-run on
the staging pipeline → `audit_timeline` → `notification_deliveries`
sandbox count → `/operations/safety` + `production_executed=0` →
local/test stack still healthy → tear-down (or keep-running). Ends
with `STAGING_RUNTIME_VERIFY: PASS` when all 12 pass.

### Staging DB password auth

```
docker compose -p aiagents-staging \
  -f infra/docker-compose/docker-compose.staging.yml \
  --env-file infra/runtime/.env.staging.local \
  exec postgres psql -U aiagents_app -d aiagents -c '\dt'
```

The staging Postgres image has `POSTGRES_HOST_AUTH_METHOD` deliberately
omitted; it defaults to `scram-sha-256` and refuses every connection
that doesn't carry the password. The validator's `staging` mode
asserts this contract.

### Staging backup / restore

```
./scripts/verify_staging_backup_restore.sh
```

Runs a read-only `pg_dump` against the staging Postgres, confirms
`pg_restore -l` parses the archive's TOC, asserts the staging DB's
table count is unchanged, and asserts the restore guard
(`scripts/restore_postgres.sh`) refuses without `ALLOW_RESTORE=true`.
The script samples the local/test DB before + after to assert the
staging operation never touches the `aiagents-test` data plane.

### Staging runtime health snapshot

```
./scripts/runtime_health_snapshot.sh --env staging
cat source/runtime-health-staging.log
```

Writes a flat summary to `source/runtime-health-staging.log`
(gitignored by `*.log`) with the staging `docker compose ps`,
`/operations/summary` / `/operations/safety` (booleans only), the
staging Prometheus targets up/down, the staging stream lag table,
and the staging `production_executed=true` counters (which must be
`0`). No token-shaped substring may appear in the file; the verify
script greps for one as a regression guard.

### Local/test vs staging differences

| Concern | Local/test (`aiagents-test`) | Staging (`aiagents-staging`) |
|---|---|---|
| docker compose project | `aiagents-test` | `aiagents-staging` |
| Postgres auth | `POSTGRES_HOST_AUTH_METHOD=trust` | password (`scram-sha-256` default) |
| Postgres user | `postgres` (superuser) | `aiagents_app` |
| Postgres volume | `postgres-data` | `postgres-staging-data` |
| Vault | `server -dev` | `server -dev` (documented escape hatch) |
| Alertmanager receivers | `null-receiver` only | `null-receiver` only |
| Host ports | 5432 / 6379 / 8000-8015 / 9090 / 9093 / 3000 / 3200 | +10000 offset |
| Default mode | always running | brought up + verified + torn down by `verify_staging_runtime.sh` |

### This is NOT production-ready

Staging bring-up is staging bring-up. The platform's
`production_executed=true` counter MUST stay at `0` for both stacks
throughout. The Stage 25 baseline still:

* uses Vault `server -dev` (documented escape hatch); a real Vault
  is required before production handoff;
* uses Alertmanager null-receiver; a real notifier is required;
* never opens a real Discord / GitHub call by default.

See [`docs/operations/staging-runtime-hardening.md`](docs/operations/staging-runtime-hardening.md)
for the full operator runbook + the staging readiness checklist.

## External Secrets Baseline (Stage 26)

Stage 26 wires a Vault-compatible read path behind the Stage 24 SecretRef
abstraction and adds a staging-validation mock-vault so the platform can
exercise the rotation contract without contacting a real Vault server.

### `SECRET_PROVIDER` modes

| Value         | Backend                                  | Use case                                          |
| ------------- | ---------------------------------------- | ------------------------------------------------- |
| `env`         | `os.environ`                             | Local/test default; production-check refuses this |
| `vault`       | Vault KV v2 over HTTP                    | Real staging / production secret store            |
| `mock-vault`  | Local JSON at `MOCK_VAULT_SECRETS_FILE`  | Staging validation only; production-check refuses |

`shared/sdk/secrets/provider.py` exposes the concrete classes and a
`provider_from_env()` factory that picks the right one based on
`SECRET_PROVIDER`. Every provider returns `SecretRef`, which renders as
`***REDACTED***` in any accidental log / response / audit row; the raw value
is only revealed via `SecretRef.reveal()`.

### Mock-vault staging validation

```
./scripts/bootstrap_mock_vault_secrets.sh        # writes .mock-vault-secrets.local.json (chmod 600, gitignored)
SECRET_PROVIDER=mock-vault \
  ./scripts/validate_runtime_config.sh --mode staging --env-file infra/runtime/.env.staging.local
./scripts/verify_secret_rotation_smoke.sh        # provider re-reads after the file changes
./scripts/scan_for_secret_leaks.sh               # no real-token substring in docs / scripts / runtime-health logs
./scripts/verify_staging_secrets.sh              # end-to-end: inventory + bootstrap + validator + rotation + leak scan + staging /operations/safety
```

The mock-vault file ships placeholder values for GitHub / Discord and
refuses to return any value that matches a real-token prefix
(the GitHub PAT prefixes, Slack `xoxb-`, HTTP auth `Bot ` / `Bearer `,
or `sk-` prefixes) unless the operator sets
`MOCK_VAULT_ALLOW_REAL_TOKEN_SHAPES=true`.

### `/operations/safety` secret fields

The Stage 26 safety view exposes these booleans / strings (never a value):

* `secret_provider` — `env` | `vault` | `mock-vault`
* `secret_provider_status` — provider name as reported by the SDK
* `vault_configured` — `VAULT_ADDR` + `VAULT_TOKEN` both present (boolean)
* `vault_reachable` — last Vault read succeeded
* `mock_vault_enabled`, `mock_vault_file_present`
* `missing_required_secrets` — list of names the provider could not resolve
  (name shape only, no values)

### Not production-ready

The mock-vault provider is for staging validation only. Production must
point `SECRET_PROVIDER=vault` at a real KV v2 store with `VAULT_ADDR` and
`VAULT_TOKEN` provisioned outside the repo. `validate_runtime_config.py
--mode production-check` refuses both `mock-vault` and `env`-only
configurations.

See [`docs/operations/secrets-management.md`](docs/operations/secrets-management.md)
for the full inventory, rotation, and leak-scan procedure.

## Discord-Driven Flexible Task Execution Loop (Stage 27)

Stage 27 turns Discord intake into an end-to-end task work item, with
agent discussions, an optional clarification round-trip, and a
deterministic execution-mode classifier — all without calling any LLM.

### Execution modes

| Mode | Trigger | Behaviour |
| --- | --- | --- |
| `simple_task` | Default — no dev/Scrum keyword | Lightweight bookkeeping; no Scrum fields |
| `delivery_task` | Dev keywords (`build`, `implement`, …) or `dev.*` request_type | Full agent pipeline + GitHub dry-run PR |
| `scrum_project` | Explicit Scrum vocabulary (`sprint`, `backlog`, `acceptance criteria`, `DoD`, `project kickoff`, …) | All of `delivery_task` + acceptance_criteria, DoD, scrum_metadata |

Scrum is **opt-in only**. `simple_task` / `delivery_task` never get
`acceptance_criteria`, `definition_of_done`, or `scrum_metadata`.

### Clarification flow

If the description is too short or contains a clarification signal
(`TBD`, `?`, `請再確認`, `需要釐清`, …), the requirement-agent:

1. Marks the work item `needs_clarification`.
2. Creates a `clarification_requests` row + `task.needs_clarification`
   notification + `clarification_requested` audit row.
3. **Does NOT publish to `stream.development`** — the agent pipeline
   stops at the gate.

The operator answers via:

```
curl -X POST http://localhost:8007/discord/clarifications/<id>/answer \
  -H "Content-Type: application/json" \
  -d '{"answer":"please implement a /healthz endpoint with tests","user_id":"alice"}'
```

The discord-gateway records the answer and calls
`POST /workflow/resume-after-clarification/<task_id>` which
re-classifies using ONLY the user's answers, flips to
`ready_for_development`, and republishes the intake event so the
agent pipeline runs.

### Agent discussions

Every agent appends to `agent_discussions`:

* `intake-agent` → analysis (normalized summary)
* `requirement-agent` → analysis (mode + classification reason)
* `development-agent` → execution_plan (mock code_change)
* `qa-agent` → validation_note (mock test_report)
* `devops-agent` → risk (mock deployment + github dry-run posture)

Visible via `GET /operations/tasks/work-items/<task_id>` or
`GET /operations/workflows/<task_id>.task_execution.agent_discussions`.

### Operations API

* `GET /operations/tasks/work-items` — list work items (filter by
  status / execution_mode)
* `GET /operations/tasks/work-items/<task_id>` — full work item +
  discussions + clarifications
* `GET /operations/workflows/<task_id>.task_execution` — embedded
  section on every workflow view
* `GET /operations/summary.task_execution_summary` — per-mode +
  per-status counts

See [`docs/operations/flexible-task-execution-loop.md`](docs/operations/flexible-task-execution-loop.md)
for the full operator runbook (curl examples, span names, metric
labels, Scrum opt-in rule).

### Not in this stage

* No real LLM. Classification + agent discussions are rule-based.
* No real code generation. development-agent still produces a mock
  `code_change` artifact.
* No production deploy. `production_executed=true` count stays at
  `0` for both stacks.
* No backlog UI. Scrum metadata is captured but no Kanban / sprint
  board ships with this stage.

## Controlled Code Generation Workspace (Stage 28)

Stage 28 promotes the development-agent from a pure mock to a
**deterministic, template-based** code generator that writes into a
controlled workspace, validates the output locally, and delivers a PR
draft package + a GitHub dry-run PR. No LLM, no real GitHub write,
no production deploy.

### Workspace lifecycle

```
created → generating → generated → ready_for_pr_draft
                    └─ validation_failed
                    └─ blocked
```

* **created** — row exists in `code_workspaces`, no files written yet.
* **generating** — the deterministic generator is writing files.
* **generated** / **ready_for_pr_draft** — files written + validated +
  PR draft created.
* **validation_failed** — `py_compile` or diff check failed; no PR
  draft is published.
* **blocked** — classification refused (unmatched template, denied path,
  destructive payload, secret-like content, work item not ready).

### Allowlist / denylist

Generated artifacts MUST land under one of:

* `docs/generated/`
* `apps/demo-generated/`
* `tests/generated/`
* `source/generated/`

The denylist is intentionally paranoid (`.github/`, `infra/`,
`migrations/`, `shared/sdk/secrets/`, `docker-compose*.yml`,
`*secret*`, `*.pem`, `*.key`, `*.env`, `*.env.*`,
`docs/operations/secrets-management.md`, `source/progress.md`).
A denylist hit always wins over an allowlist match, and `delete`
changes are refused outright.

### Templates

| Trigger keyword | Template | Files produced |
| --- | --- | --- |
| docs / document / readme / 文件 / 說明 | `documentation` | `docs/generated/<task_id>.md` |
| api / endpoint / service / /healthz | `demo_api` | `apps/demo-generated/<slug>_api.py` + `tests/generated/test_<slug>_api.py` |
| utility / helper / function / 工具 / 函式 | `simple_utility` | `apps/demo-generated/<slug>_utility.py` + `tests/generated/test_<slug>_utility.py` |
| (nothing matches) | `blocked` | — |

Every generated file carries `task_id`, `generated_by=development-agent`,
`generator_mode=deterministic_template`, and `production_executed=false`
in the file body.

### Local validation

The development-agent runs three checks before publishing the PR draft:

1. `py_compile` on every generated `*.py` file (no execution).
2. Diff non-empty + at least one hunk.
3. Allowlist + secret-content check on each file.

Failures flip the workspace to `validation_failed`, emit
`code.validation_failed`, and skip the PR draft.

### PR draft delivery

`pr_draft_artifacts.body` always carries the 7 sections:

```
## Summary
## Changed Files
## Generated Diff Summary
## Validation Result
## Risk Assessment
## Rollback Plan
## Safety Notes
```

The devops-agent picks up the PR draft (if present) and feeds its
`title` / `body` / `risk_assessment` / `rollback_plan` into the existing
`github-automation /github/workflow/demo-pr` dry-run endpoint. The
`github_dry_run_result` (pr_url, branch, checks_status) is written back
into `pr_draft_artifacts.github_dry_run_result`.

### Operations API

* `GET /operations/code/workspaces` — list workspaces (filter by
  `status` / `generator_mode`).
* `GET /operations/code/workspaces/<task_id>` — workspace + artifacts +
  PR draft.
* `GET /operations/code/artifacts/<task_id>` — code_change_artifacts only.
* `GET /operations/code/pr-drafts/<task_id>` — PR draft body + risk +
  rollback + github_dry_run_result.
* `GET /operations/workflows/<task_id>.code_generation` — embedded
  section on every workflow view.
* `GET /operations/summary.code_generation_summary` — per-status counts.

`GET /discord/tasks/<task_id>` also exposes `code_generation_status`,
`changed_files_count`, `pr_draft_status`, `validation_status`,
`github_dry_run_pr_url`, and `code_generation_blocked_reason`.

See [`docs/operations/controlled-code-generation.md`](docs/operations/controlled-code-generation.md)
for the full operator runbook (curl examples, scenario verifier, audit
decision types, notification event types, metric labels).

### Not in this stage

* **No LLM.** Templates are deterministic and intentionally trivial.
  A human reviewer must replace the body before merging.
* **No real GitHub write.** Every PR is dry-run; `dry_run=true` is
  enforced.
* **No auto-commit.** Generated artifacts live in
  `$DEVELOPMENT_AGENT_WORKSPACE_ROOT` (default
  `/tmp/aiagents-workspaces/<task_id>`) and are gitignored. Operators
  port the diff manually.
* **No production deploy.** `production_executed=true` count stays at
  `0` for both stacks.
* **No QA auto-fix loop.** The qa-agent still runs its mock validation
  against `development.completed`; Step 28 will tackle the QA-driven
  re-generation cycle.

## QA-Guided Validation & Auto-Fix Loop (Stage 29)

Stage 29 turns the qa-agent into a deterministic gatekeeper for the
controlled workspace. After Stage 28's development-agent produces a
workspace + artifacts + PR draft, the qa-agent loads them, runs a
fixed set of rules, and decides:

* **pass** — publish `qa.completed` to `stream.deployments`; the
  devops-agent finishes the pipeline.
* **auto-fix requested** — at least one auto-fixable blocking
  finding AND `auto_fix_attempts < max_auto_fix_attempts` →
  publish `code.auto_fix_request` to `stream.development.autofix`
  (a second consumer in the development-agent service) and a
  `qa.auto_fix_requested` event back onto `stream.qa` so the
  workflow stage flips to `qa_auto_fix`.
* **blocked for human review** — any non-auto-fixable critical
  finding (security / policy / regression), OR attempts exhausted
  → publish `qa.blocked_for_human_review`; the workflow stage
  flips to `blocked_for_human_review`. `production_executed=false`
  is preserved.

No LLM. The rules live in `shared.sdk.qa.rules`:

| Rule | What it checks |
| --- | --- |
| `validate_generated_files_exist` | every artifact path is on disk |
| `validate_python_syntax` | `py_compile` every `*.py` (no execution) |
| `validate_test_files_exist_for_api_task` | a `demo_api` app file ships its matching test |
| `validate_diff_present` | each artifact carries at least one hunk |
| `validate_no_denied_paths` | nothing under `.github/` / `infra/` / `*secret*` / `*.env*` / `source/progress.md` etc. |
| `validate_no_secret_patterns` | no GitHub / AWS / PEM literal in any generated file |
| `validate_pr_draft_sections` | PR body carries all 7 Stage 28 sections |
| `validate_destructive_diff` | no `rm -rf` / `drop database` / force-push payload |
| `validate_acceptance_alignment` | acceptance criteria mention something the workspace delivered |

### Deterministic auto-fixes (development-agent)

Only three categories are deterministic:

* **Missing PR draft sections** → append placeholder sections so
  the body carries all 7 required markers again.
* **Missing demo-API test file** → re-run the deterministic
  generator and persist the rewritten test file.
* **Python syntax error in generated file** → regenerate via the
  template (no LLM, no targeted patching).

Anything else (security / policy / acceptance / regression) is
refused and bubbles into the `blocked_for_human_review` path on
the next pass.

### Loop guard

`QA_MAX_AUTO_FIX_ATTEMPTS` (default `2`, clamped to `[1, 10]`)
caps the loop. When the qa-agent sees `auto_fix_attempts >=
max_auto_fix_attempts`, even an auto-fixable finding is treated
as blocked.

### Operations API

* `GET /operations/qa/runs` — list validation runs (filter by
  `task_id` / `status` / `final_result`).
* `GET /operations/qa/runs/<task_id>` — every run for a task with
  `latest_run` on top.
* `GET /operations/qa/findings/<task_id>` — findings, optional
  `severity` / `status` filters.
* `GET /operations/qa/auto-fix/<task_id>` — auto-fix requests.
* `GET /operations/workflows/<task_id>.qa_validation` — embedded
  section on every workflow view (`latest_run`, `findings`,
  `auto_fix_requests`, `blocked_for_human_review`, `qa_passed`).
* `GET /operations/summary.qa_summary` — aggregate counters
  (`total_validation_runs`, `passed_runs`, `failed_runs`,
  `blocked_for_human_review_count`, `auto_fix_requested_count`,
  `total_findings`).

`GET /discord/tasks/<task_id>` also exposes `qa_status`,
`qa_final_result`, `qa_findings_count`, `blocking_findings_count`,
`auto_fix_attempts`, `blocked_for_human_review`.

See [`docs/operations/qa-auto-fix-loop.md`](docs/operations/qa-auto-fix-loop.md)
for the full operator runbook (audit decision types, notification
event types, metric labels, span names, scenario verifier).

### Not in this stage

* **No LLM-driven auto-fix.** Only the three deterministic fix
  strategies above are supported.
* **No production deploy.** `production_executed=true` count
  stays at `0` on both stacks.
* **No real GitHub write.** PR drafts still flow through the
  Stage 28 dry-run path; the Stage 23 controlled-real gate
  remains untouched.
* **No `qa_findings` autoresolution UI.** Findings are
  persisted; the operator inspects via `/operations/qa/*` and
  manually marks `waived` if needed.
* **No QA-driven workflow re-classification.** The qa-agent never
  changes the work item's `execution_mode`; that stays a Stage 27
  decision.

## LLM-Assisted Development Planning Guardrails (Stage 30)

Stage 30 introduces an opt-in LLM planning layer with hard
guardrails around the existing controlled Stage 28 generator. The
LLM does **not** become a writer to the repository — it produces
proposals + safety analysis that an operator reviews. The
deterministic generator + QA gate still run.

### Provider modes

* `mock` — deterministic in-process generator (default).
* `disabled` — every call raises.
* `external_openai_placeholder` / `external_anthropic_placeholder` —
  interface guards. **No real network call** is made in Stage 30.

Toggle via `LLM_PROVIDER`. Enable the planning loop via
`ENABLE_LLM_ASSISTED_PLANNING=true` (default `false`).

### Output schemas

* `LLMDevelopmentPlan` — summary, files_to_consider, proposed_steps,
  assumptions, questions, risks, test_strategy, confidence,
  `requires_human_review=True`.
* `LLMPatchProposal` — patch_id, proposed_files, changes
  (LLMFileChange list), rationale, risk_level, safety_notes,
  test_commands, rollback_plan, confidence, `requires_human_review=True`.
* `LLMTestPlan` — unit_tests, integration_tests, manual_tests,
  acceptance_checks, risks.

`change_type=delete` is rejected outright; `confidence` is clamped to
`[0.0, 1.0]`; `requires_human_review` is forced to `True` regardless
of the upstream value.

### Safety policy

Every output runs through `apply_llm_safety_policy()`:

| Rule                    | Trigger                                                |
| ----------------------- | ------------------------------------------------------ |
| `path_blocked`          | denylist match or outside allowlist                    |
| `change_type_blocked`   | anything other than `create` / `update`                |
| `secret_like_content`   | known token / key / private-key pattern in content     |
| `destructive_content`   | `rm -rf`, `DROP TABLE`, `git push --force`, …          |
| `too_many_files`        | more than 5 changes per proposal                       |
| `content_too_large`     | more than 20 000 chars per file                        |
| `schema_invalid`        | unrecognised output type                               |

`low_confidence:*` is a **warning** (not a violation) below
`min_confidence_for_auto_proposal=0.7`.

### Prompt contract

The deterministic envelope every LLM provider receives carries
`task_summary`, `allowed_paths`, `denied_paths`, `safety_rails`,
`output_schema`. See
[`docs/operations/llm-prompt-contract.md`](docs/operations/llm-prompt-contract.md).

Prompts and responses are **hashed (SHA-256)** and a short, redacted
preview is persisted to `llm_interactions`. Full prompt / response
text never leaves the producer.

### Tables

Three additive tables (migration `010_llm_assisted_development.sql`):

* `llm_interactions` — one row per LLM call.
* `llm_proposal_artifacts` — one row per proposal (status:
  `proposed | policy_passed | blocked | accepted_for_workspace |
  rejected | superseded`).
* `llm_usage_records` — token / cost ledger (mock provider = 0).

### Operations LLM view

* `GET /operations/llm/interactions` / `…/interactions/{task_id}`
* `GET /operations/llm/proposals/{task_id}`
* `GET /operations/llm/usage`
* `GET /operations/workflows/{task_id}.llm_assistance` (provider,
  interactions, proposals, latest_safety_result, usage_summary, …)
* `GET /operations/summary.llm_summary` (aggregated counters)
* `GET /operations/safety` (`llm_provider`, `llm_real_enabled`,
  `llm_external_call_enabled`, `llm_policy_enforced`,
  `llm_requires_human_review`)

The API key value is **never** echoed to any response.

### Limitations

* **Mock LLM only by default.** Real wire-level calls are off.
* **No direct commit.** Proposals are advisory; the deterministic
  generator + QA gate still own the workspace.
* **Human review required** on every proposal.
* **No real GitHub write.** Dry-run path inherited from Stage 22-28.
* **Production deploy disabled.** `production_executed=false`
  asserted on every audit row.

See [`docs/operations/llm-assisted-development.md`](docs/operations/llm-assisted-development.md)
for the full operator runbook.

## Flexible Human Approval Policy & LLM Proposal Promotion (Stage 31)

Stage 31 introduces a policy layer that lets a human operator pick
the **granularity** of approval for an LLM proposal promotion, a
QA auto-fix, or any other audit-bearing action — without ever
overriding the hard safety rails the platform ships with.

### Approval modes

| Mode          | Authorises automatically? |
| ------------- | ------------------------- |
| `per_action`  | No. Explicit approve / reject only. (default) |
| `per_feature` | Yes, inside a per-task allowlist of actions + paths. |
| `per_stage`   | Yes, inside a per-stage allowlist of actions + paths. |
| `delegated`   | Yes, while `max_actions` / `max_files_changed` / `expires_at` hold. |

A `delegated` policy MUST set `allowed_actions`, `allowed_paths`,
`denied_paths`, `max_actions`, `max_files_changed`,
`max_auto_fix_attempts`, and `expires_at`. The orchestrator returns
`400 delegated_missing:<field>` otherwise.

### Hard safety policy (always wins)

Even an `active` delegated policy that lists one of these actions
is refused:

* `production_deploy`, `real_github_write`, `real_github_pr_merge`,
  `branch_protection_modification`, `force_push`, `delete_file`,
  `secret_write`, `destructive_command`, `real_llm_network_call`,
  `denylist_path_mutation`.

The same applies content-wise: a proposal carrying a token / key /
private-key literal, a destructive command, or a denylisted path
gets a `hard_policy_block` regardless of any policy authorising it.

### Approval vs promotion

* **Approval** records the operator's decision on a proposal
  (`llm_proposal_approvals`).
* **Promotion** materialises the proposal into
  `code_change_artifacts` (`llm_proposal_promotions`).

A `per_action` proposal must have an `approved` approval row before
`/llm/proposals/{id}/promote` accepts it. `per_feature`, `per_stage`,
`delegated` modes can authorise via an active policy instead — the
promotion records `decision_source=policy_allows` and the policy's
`actions_used` counter bumps.

### Tables

Four additive tables (migration `011_human_approval_policy_and_llm_promotion.sql`):

* `human_approval_policies` — per-action / per-feature / per-stage /
  delegated policies. Status: `pending | active | expired | revoked | rejected`.
* `human_approval_decisions` — every approve / reject / revoke /
  delegated decision row.
* `llm_proposal_approvals` — per-proposal approval lifecycle.
* `llm_proposal_promotions` — promotion attempts with status:
  `requested | promoted | validation_failed | qa_passed | qa_blocked |
  blocked_by_policy | failed | canceled`.

### Operations + Discord surfaces

* `GET /operations/approval-policies` / `…/approval-policies/{task_id}` /
  `…/approval-decisions/{task_id}`.
* `GET /operations/workflows/{task_id}.approval_policy` (active
  policies, decisions, delegated usage, hard policy blocks).
* `GET /operations/summary.approval_policy_summary` (aggregated
  counters).
* `GET /operations/safety` adds `delegated_agent_enabled`,
  `active_delegated_policies`, `hard_policy_enforced=true`,
  `production_delegation_allowed=false`,
  `real_github_delegation_allowed=false`.
* `GET /discord/tasks/{task_id}` adds `approval_mode`,
  `active_approval_policy`, `delegated_actions_used`,
  `delegated_actions_remaining`, `latest_approval_decision`,
  `llm_promotion_status`.
* Discord proxies: `/discord/approval-policies`,
  `/discord/approval-policies/{task_id}`,
  `/discord/approval-policies/{policy_id}/revoke`,
  `/discord/llm/proposals/{proposal_id}/approve`,
  `/discord/llm/proposals/{proposal_id}/reject`,
  `/discord/llm/proposals/{proposal_id}/promote`.

### Limitations

* **No production delegation.** `production_executed=false` asserted
  on every audit row.
* **No real GitHub delegation.** Stage 23 controlled-real gate
  untouched.
* **No PR merge.** Promotion writes `code_change_artifacts`; the
  dry-run demo-PR path inherited from Stage 28 is the only emitter.
* **No file deletion.** Stage 28 forbade `delete` at the workspace
  policy level; Stage 31 reaffirms it at the approval level.
* **No silent override.** Every promotion writes audit +
  notification + decision rows; revoke is one POST away.

See [`docs/operations/human-approval-policy.md`](docs/operations/human-approval-policy.md)
and [`docs/operations/llm-proposal-promotion.md`](docs/operations/llm-proposal-promotion.md)
for the full operator runbooks.

## Real Integration Sandbox Pilot (Stage 32)

Stage 32 wires the platform's real Discord and real GitHub adapters
behind an opt-in allowlist. The default posture is SANDBOX-ONLY and
every real endpoint refuses with HTTP 409 until the operator
explicitly sets the env vars listed below.

### Scope (in)

| Adapter | What is allowed |
|---|---|
| Real Discord test channel | One pinned test guild + test channel + optional role + bot token (Vault-stored). One controlled-test message per call. |
| Real GitHub sandbox repo | One pinned sandbox repo + fine-grained PAT. Files only under `docs/github-real-test/`. PR opened, never merged. |

### Scope (out)

- Real LLM calls (`real_llm_network_call` remains a hard-safety action).
- Production GitHub repo writes — the sandbox guard refuses
  `coolerh250/AI-Agents-SWD` unless suffixed `-sandbox` / `_sandbox`.
- PR merges, branch-protection changes, releases, deployments,
  branch deletes, workflow file mutation, writes to `.github/` /
  `infra/` / `migrations/` / `apps/` / `shared/` / `scripts/` /
  `tests/`.
- Production deploys (`production_executed=true` counters must stay
  at 0).

### Required operator inputs

Discord: `DISCORD_BOT_TOKEN`, `DISCORD_TEST_GUILD_ID`,
`DISCORD_TEST_CHANNEL_ID`, `RUN_REAL_DISCORD_TEST=true`,
optionally `DISCORD_ALLOWED_ROLE_ID`.

GitHub: `GITHUB_TOKEN`, `GITHUB_TEST_REPO`,
`RUN_REAL_GITHUB_TEST=true`.

### Skipped mode (default test cluster)

```bash
./scripts/check_real_integration_inputs.sh         # PRESENT/ABSENT + length only
./scripts/verify_real_integration_pilot.sh         # SKIPPED: PASS without env
```

### Real mode (opt-in shell)

```bash
export DISCORD_BOT_TOKEN=... DISCORD_TEST_GUILD_ID=... DISCORD_TEST_CHANNEL_ID=... RUN_REAL_DISCORD_TEST=true
./scripts/verify_real_discord_pilot.sh
unset DISCORD_BOT_TOKEN DISCORD_TEST_GUILD_ID DISCORD_TEST_CHANNEL_ID RUN_REAL_DISCORD_TEST
```

### Surfaces

- Operations: `/operations/real-integrations`,
  `/operations/real-integrations/discord`,
  `/operations/real-integrations/github`, plus the existing
  `/operations/safety` extended with `real_discord_*` / `real_github_*`
  booleans.
- Audit decision_types: `discord_real_test_sent`,
  `discord_real_test_blocked`, `discord_real_task_received`,
  `discord_real_task_blocked`, `github_sandbox_pr_created`,
  `github_sandbox_guard_failed`.
- Notification events: `discord.real_test_sent`,
  `discord.real_task_received`, `github.sandbox_pr.created`.
- Metrics: `real_discord_tests_total`, `real_discord_tasks_total`,
  `real_discord_guard_blocks_total`, `real_github_sandbox_prs_total`,
  `real_github_guard_blocks_total`, `real_integration_failures_total`.

### No-Go items

- Pointing `GITHUB_TEST_REPO` at the canonical production repo.
- Setting `ENABLE_REAL_LLM_NETWORK_CALL=true`.
- Manually merging a sandbox PR.
- Re-using the test bot token in any production-bound bot.
- Storing any of these env vars in repo / logs / progress.md /
  README / API response.

See [`docs/operations/real-integration-pilot.md`](docs/operations/real-integration-pilot.md)
for the full operator runbook.

## Identity Inventory & Auth Boundary Model (Stage 54A / Step 52.1)

First sub-stage of **Step 52 — Production Identity & OIDC Foundation**: an
evidence-backed inventory + boundary model of the current identity stack, with
**no real OIDC, no production auth, and no external IdP**. Under
[infra/identity/](infra/identity/): authentication / session / CSRF / RBAC /
operator-action-authorization inventories, an identity trust boundary model, a
test-vs-production auth boundary, identity-to-audit mapping, human-acceptance &
verification-rerun boundaries, production OIDC prerequisites (all
**unconfigured**), a risk register and a machine-readable policy catalog —
derived from the real `shared/sdk/operator_actions/*` code (auth/session/rbac/
csrf/action_catalog/verification_runner). Key boundaries: test-local signed
session is **non-production** (dev/test only); production auth is **disabled and
fail-closed**; the session stores only `sha256(token)` (no raw token, no
localStorage/URL token); `platform_admin` has the **operator action set only**
(no Kubernetes/ArgoCD/GitHub/deploy authority); **human acceptance is not
deployment**; verification rerun is **allowlist-only**. Verify with
`python scripts/verify_identity_boundary_inventory.py`
(`IDENTITY_BOUNDARY_INVENTORY_VERIFY`),
`verify_auth_rbac_boundary.py` (`AUTH_RBAC_BOUNDARY_VERIFY`),
`verify_identity_audit_boundary.py` (`IDENTITY_AUDIT_BOUNDARY_VERIFY`), and the
combined `scripts/verify_identity_auth_boundary_baseline.sh`
(`IDENTITY_AUTH_BOUNDARY_BASELINE_VERIFY`). Docs under
[docs/security/](docs/security/). No production identity readiness is declared;
OIDC provider abstraction (52.2), session hardening + role mapping (52.3), and
identity visibility (52.4) follow.

## OIDC Provider Abstraction & Disabled Production Config (Stage 54B / Step 52.2)

Second sub-stage of **Step 52**: a **model-only** OIDC provider abstraction that
connects to **no** IdP, fetches **no** discovery document or JWKS, exchanges
**no** authorization code, validates **no** real token, and creates **no**
session. New SDK [shared/sdk/identity/](shared/sdk/identity/) (`oidc_models`,
`oidc_provider`, `oidc_config`, `oidc_policy`, `oidc_redaction`) — the
abstraction imports no HTTP client and every live provider operation raises
`OidcDisabledError`. Ten contracts under [infra/identity/](infra/identity/):
provider catalog, disabled production config, discovery contract, JWKS reference
model, claim contract, role-mapping contract, callback boundary, state/nonce/PKCE
contract, token-validation boundary, and safety-policy catalog. The committed
production provider is `enabled: false` / `productionAllowed: false` /
`status: disabled_unconfigured` (no real issuer / client ID / client-secret ref /
redirect URI; discovery & JWKS fetch off). The fail-closed loader/validator
forces `invalid` on production-enabled, test-local fallback, enabled-but-
incomplete, unknown-user≠deny, a privileged default role, discovery/JWKS/callback
enabled, or a secret-shaped literal; the committed config reports
`disabled_unconfigured`. A token's `role`/`is_admin`/`platform_admin` claim is
**never** authoritative and `platform_admin` is **never** auto-granted. Verify
with `python scripts/verify_oidc_provider_abstraction.py`
(`OIDC_PROVIDER_ABSTRACTION_VERIFY`), `verify_oidc_fail_closed_config.py`
(`OIDC_FAIL_CLOSED_CONFIG_VERIFY`), `verify_oidc_no_secret_leak.py`
(`OIDC_NO_SECRET_LEAK_VERIFY`), and the combined
`scripts/verify_oidc_disabled_production_baseline.sh`
(`OIDC_DISABLED_PRODUCTION_BASELINE_VERIFY`). Docs under
[docs/security/](docs/security/) (`oidc-*`). Production OIDC remains disabled and
**not production-ready**; session hardening + role mapping (52.3) and identity
visibility (52.4) follow.

## Session Hardening & Role Mapping (Stage 54C / Step 52.3)

Third sub-stage of **Step 52**: session hardening + a safe local role mapping
engine, with **no real IdP, no production auth, and break-glass disabled**. New
SDK modules under [shared/sdk/identity/](shared/sdk/identity/): `session_cleanup`
(non-destructive — dry-run default, never deletes, marks only active-past-expiry
sessions `expired`, references `session_hash`/`status`/`expires_at` only, no raw
token; the Step 50 `admin_console_sessions` schema already supports it, so **no
migration**), `role_mapping`/`role_mapping_models` (explicit-rule-only engine
that denies missing/unverified/unmapped claims; `IdentityClaims` has no
`role`/`is_admin` field so a token role claim is structurally non-authoritative),
and `identity_runtime_config` (fail-closed validator over 11 unsafe production
conditions). Models under [infra/identity/](infra/identity/): session hardening
catalog, concurrency policy, forced-logout, key-rotation (model-only; production
secret store deferred to Step 53), role-mapping policy, a SAFE placeholder-group
fixture, unknown-user policy, break-glass model (disabled, depends on Step 60),
and an authorization-decision model (role mapping ≠ RBAC ≠ policy approval;
confirmation ≠ permission; human acceptance ≠ deployment; `platform_admin` ≠
infrastructure admin). Default role is `none`, unknown users are denied,
`platform_admin` requires an explicit mapping, wildcard groups are rejected, and
no real group IDs are committed. Verify with
`python scripts/verify_session_hardening.py` (`SESSION_HARDENING_VERIFY`),
`verify_role_mapping_policy.py` (`ROLE_MAPPING_POLICY_VERIFY`),
`verify_unknown_user_policy.py` (`UNKNOWN_USER_POLICY_VERIFY`),
`verify_break_glass_model.py` (`BREAK_GLASS_MODEL_VERIFY`),
`verify_identity_authorization_model.py` (`IDENTITY_AUTHORIZATION_MODEL_VERIFY`),
`verify_identity_audit_enrichment.py` (`IDENTITY_AUDIT_ENRICHMENT_VERIFY`), and
the combined `scripts/verify_session_role_mapping_baseline.sh`
(`SESSION_ROLE_MAPPING_BASELINE_VERIFY`). Docs under
[docs/security/](docs/security/). Production identity remains disabled and **not
production-ready**; Admin Console identity visibility + integrated Step 52
verification (52.4) follow.

## SBOM / Image Digest / Container Security Baseline (Stage 56C / Step 54.3)

Adds a **local, offline** SBOM + container security baseline on top of Step 54.1/54.2 —
**modeled and locally verifiable, NOT production-enforced**. No registry login, no
image pull/push, no image signing, no production attestation, no external upload, no
production gate. Under [infra/security/](infra/security/): SBOM capability inventory /
generation boundary / artifact schema, a container image inventory (27 images; no digest
pinned, no `:latest`), image digest + tag policies, a Dockerfile security inventory (20
Dockerfiles, all root), container runtime security alignment (maps Step 51
securityContext vs the root-image reality), an image vulnerability scan capability +
result schema (policy-only, no CVE verdict), a signing/attestation model (disabled), a
registry credential boundary (Step 53 secret store only), and a container security
evidence model. New SDK [shared/sdk/container_security/](shared/sdk/container_security/)
exposes read-only posture loaders + safety fields. Local runners
(`scripts/run_local_sbom_baseline.py`, `scripts/run_local_image_policy_scan.py`) write
redacted reports to `.runtime/security/` (gitignored — **never committed**). 13 GET-only
`/operations/security/{sbom,images}/*` endpoints + container/SBOM `/operations/safety`
fields (`security_container_production_ready=false`, `security_image_digest_pinning_complete=false`,
`security_dockerfile_non_root_complete=false`, `security_image_vulnerability_cve_scan_performed=false`,
registry-login / image-push / signing all false) surface it, plus an Admin Console
read-only SBOM / container security section. A missing/unavailable CVE scan is never
clean; missing digests are never production-safe. Verify with `python
scripts/verify_sbom_capability_inventory.py`, `verify_sbom_generation_boundary.py`,
`verify_local_sbom_baseline.py`, `verify_container_image_inventory.py`,
`verify_image_digest_policy.py`, `verify_dockerfile_security_inventory.py`,
`verify_container_runtime_security_alignment.py`, `verify_local_image_policy_baseline.py`,
`verify_image_signing_attestation_model.py`,
`verify_container_security_operations_visibility.py`,
`verify_admin_console_container_security.py`, `verify_container_security_safety_fields.py`,
and the combined `scripts/verify_sbom_container_security_baseline.sh`
(`SBOM_CONTAINER_SECURITY_BASELINE_VERIFY`, which chains Step 51 + 52 + 53 + 54.1 + 54.2).
Docs under [docs/security/](docs/security/) + [docs/operations/](docs/operations/). **No
registry login, no image push/sign/attest, no production SBOM/image gate declared.**
Next: Step 54.4 (threat model / release risk summary / integrated verification), Step 55
(non-production cluster smoke).

## Threat Model / Release Risk / Integrated Verification (Stage 56D / Step 54.4)

Integrates Steps 54.1–54.3 into a **threat model**, **release risk summary**, **security
evidence package** and **security readiness report** — **modeled, locally verifiable, NOT
production-enforced**. Under [infra/security/](infra/security/): threat-model baseline +
category taxonomy + agent / supply-chain / runtime-gitops threat models + release-risk
summary model + scoring policy + evidence-package schema + committed integrated summary.
The `security_integrated` SDK + three generators (evidence package / release risk summary /
readiness report) write to gitignored `.runtime/security/` (never committed). 9 GET
`/operations/security/{threat-model,release-risk,evidence,readiness,step54}/*` endpoints +
14 `/operations/safety` integrated fields back the Admin Console **Threat Model / Release
Risk / Evidence** section (no generate-evidence / approve-release / enable-gate / deploy /
create-PR / sync-ArgoCD control). 11 verifiers + combined
`APPLICATION_SECURITY_SUPPLY_CHAIN_BASELINE_VERIFY` (chains Step 51 + 52 + 53 + 54.1 + 54.2
+ 54.3, deduped via `scripts/lib/baseline_run_guard.sh`) + 17 tests + full regression.
**A release risk summary is NOT an approval; no production release gate; Step 54 is closed
as a local, modeled baseline (NOT production security gate / release approval / deployment
ready / all-risks-remediated).** Step 55 (cluster smoke) and Step 56 (ArgoCD sync) remain.

## Non-production Kubernetes Runtime Smoke (Stage 57A / Step 55)

Takes the Step 51 static Kubernetes/Helm baseline toward a **real non-production cluster**
runtime smoke — **framework ready, NOT production-enforced**. Under
[infra/kubernetes/](infra/kubernetes/): a cluster smoke plan, namespace plan, runtime smoke
report schema, and `values-nonprod-smoke.yaml`. A Helm smoke runner
(`scripts/run_nonproduction_helm_smoke.sh`, `--dry-run-only` + guardrails: refuses
production/default/`*prod*` namespaces + production values, no Ingress/LoadBalancer/
ClusterRole/CRD, no ArgoCD sync), the `runtime_smoke` SDK, 14 verifiers (cluster-dependent
ones honestly emit `BLOCKED_NO_SAFE_CLUSTER`), a combined
`NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY` (chains Step 51/52/53/54, deduped), 12 GET
`/operations/runtime/nonprod-smoke/*` endpoints + 17 `/operations/safety` smoke fields, an
Admin Console **Non-production Runtime Smoke** section (no deploy/helm-install/cleanup/exec/
sync), and 10 tests. **Step 55.1 (Stage 57B) bootstrapped a safe local kind cluster and the
smoke now PASSes for real (scoped)** — see below. `nonprod_runtime_smoke_production_
ready=false`, no production deploy / ArgoCD sync, `production_executed_true_count=0`.

## Safe Non-production Cluster Bootstrap (Stage 57B / Step 55.1)

Closes the Step 55 `BLOCKED_NO_SAFE_CLUSTER` gap: a **safe, local-only kind cluster**
(`kind-aiagents-smoke`, namespace `aiagents-smoke-dev`) is bootstrapped on the test host and
the Step 55 runtime smoke runs **for real → PASS (scoped)**. Tooling from official sources
(kubectl v1.36.2, helm v3.16.4, kind v0.25.0; recorded in
[infra/kubernetes/nonproduction-tooling-inventory.yaml](infra/kubernetes/nonproduction-tooling-inventory.yaml)).
[scripts/bootstrap_nonproduction_kind_cluster.sh](scripts/bootstrap_nonproduction_kind_cluster.sh)
creates the cluster, `kind load`s locally-built images (no registry login/push), and creates
a non-secret in-cluster runtime secret (never committed). A scoped control-plane subset
(orchestrator + policy-engine + approval-engine + audit-service + in-cluster postgres + redis)
is installed via `values-nonprod-smoke-local.yaml`; **6/6 pods Ready + migration Job Complete**.
[scripts/run_nonproduction_runtime_smoke.py](scripts/run_nonproduction_runtime_smoke.py) runs
real `kubectl` checks + an in-cluster connectivity probe and writes a redacted
gitignored runtime report the verifiers consume (PASS reflects the live cluster; absent
report → BLOCKED — never faked). 4 new verifiers + combined
`NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY`, 5 tests, 5 docs. Known gaps (honest):
scoped subset only; kindnet does not enforce NetworkPolicy; chart migration execution is
fail-closed. No production cluster/namespace, no registry login/push, no public
ingress/LoadBalancer/NodePort, no ArgoCD sync, `production_executed_true_count=0`. **Step 56
(real ArgoCD manual sync) remains out of scope and must not begin from automation.**

## Local Security Scan Toolchain Baseline (Stage 56B / Step 54.2)

Makes the Step 54.1 scan policies **partially executable** with a **local, offline**
toolchain — **modeled and locally executable, NOT production-enforced**. No external
scanner, no source upload, no token, no network call, no GitHub write/PR, no image
push, no production release gate. Under [infra/security/](infra/security/): a local
scanner capability inventory (custom baselines bundled; gitleaks/bandit/semgrep/
pip-audit/osv runtime-detected), a scanner execution boundary, scan target catalog,
scan exclusion policy, scan result artifact schema, and scan status summary model. New
SDK [shared/sdk/security_findings/](shared/sdk/security_findings/) provides a normalized
`SecurityFinding` / `ScanResult` (evidence redacted, no secret value), a result
normalizer, and read-only scan posture loaders. Local runners
(`scripts/run_local_secret_scan.py`, `run_local_sast_scan.py`,
`run_local_dependency_scan.py`, `normalize_security_scan_results.py`) write redacted
reports to `.runtime/security/` (gitignored — **never committed**). Nine GET-only
`/operations/security/scans/*` endpoints + 16 `/operations/safety` scan fields
(`security_scan_production_ready=false`, external upload / network / token / run-endpoint
/ reports-committed / production-gate all false; last-status degrades to `not_run` in the
image) surface it, plus an Admin Console read-only scan posture section. A
`tool_unavailable` scan is never a PASS; a missing scan is never clean; the dependency
scan performs **no CVE lookup**. Verify with `python
scripts/verify_local_scanner_capabilities.py`, `verify_scanner_execution_boundary.py`,
`verify_scan_target_catalog.py`, `verify_local_secret_scan_baseline.py`,
`verify_local_sast_baseline.py`, `verify_local_dependency_scan_baseline.py`,
`verify_security_scan_result_normalization.py`,
`verify_security_scan_operations_visibility.py`, `verify_admin_console_scan_posture.py`,
`verify_security_scan_safety_fields.py`, and the combined
`scripts/verify_security_scan_toolchain_baseline.sh`
(`SECURITY_SCAN_TOOLCHAIN_BASELINE_VERIFY`, which chains Step 51 + 52 + 53 + 54.1). Docs
under [docs/security/](docs/security/) + [docs/operations/](docs/operations/). **No
external scan, no SBOM, no production scan gate declared.** Next: Step 54.3 (SBOM / image
digest / container security), Step 54.4 (threat model / release risk / integrated
verification).

## Application Security & Supply Chain Baseline (Stage 56A / Step 54.1)

Establishes a **modeled, NOT-enforced-for-production** application security &
supply chain baseline — no scanner run, no SBOM generated, no image push, no
registry/scanner connection, no GitHub write, no production release gate. Under
[infra/security/](infra/security/): application security asset inventory (26
assets), supply chain inventory, dependency surface inventory, a scan policy
catalog, SAST / dependency / secret / SBOM / container-image policy models, threat
model & release risk input catalogs, an evidence model, a finding severity
taxonomy, a fail-closed gate policy, and a committed anti-drift posture summary
([security-foundation-summary.yaml](infra/security/security-foundation-summary.yaml)).
New read-only SDK [shared/sdk/security_foundation/](shared/sdk/security_foundation/)
aggregates them (reusing the Step 53 redaction; never runs a scanner or touches
the network). Seventeen GET-only `/operations/security/*` endpoints + 20
`/operations/safety` fields (`security_foundation_status=modeled_not_enforced`,
`security_production_ready=false`, all scanner-configured / github-write /
pr-creation / image-push / registry-login / external-scanner-upload flags
`false`) surface it, plus an Admin Console read-only **Security / Supply Chain**
view with no run-scan / upload-source / connect-scanner / configure-scanner /
create-PR / push-image / production-gate control. Recorded blockers (modeled, not
fixed): images not digest-pinned, Dockerfiles run as root, Python deps unpinned
(no lockfile), no cluster runtime smoke. Verify with `python
scripts/verify_security_asset_inventory.py`, `verify_supply_chain_inventory.py`,
`verify_security_scan_policy_baseline.py`, `verify_security_evidence_model.py`,
`verify_security_gate_policy.py`, `verify_security_operations_visibility.py`,
`verify_admin_console_security_posture.py`, `verify_security_safety_fields.py`,
and the combined `scripts/verify_security_supply_chain_policy_baseline.sh`
(`SECURITY_SUPPLY_CHAIN_POLICY_BASELINE_VERIFY`, which chains the Step 51 + Step
52 + Step 53 baselines). Docs under [docs/security/](docs/security/) +
[docs/operations/](docs/operations/). **No scans run, no SBOM, no image supply
chain, no release gate declared production-ready.** Next: Step 54.2 (scan
toolchain), Step 54.3 (SBOM / image digest / container security), Step 54.4
(threat model / release risk / integrated verification).

## Production Secret Management Foundation (Stage 55A / Step 53)

Establishes a **modeled, fail-closed, NOT-configured** secret management
foundation — no real secret value, no secret store connection, no production
auth/deploy. Under [infra/secrets/](infra/secrets/): a secret inventory (15
categories), classification (secret vs public-config), ownership (roles only),
lifecycle / rotation / access-boundary / audit / redaction models, a disabled
production secret-store config, and four reference catalogs (identity / runtime /
backup / gitops) where every reference is `store=disabled`, `configured=false`,
`productionReady=false`. New SDK [shared/sdk/secrets_foundation/](shared/sdk/secrets_foundation/)
(distinct from the runtime value-holding `shared/sdk/secrets`) provides a
**reference-only** `SecretRef` (carries no value; rejects inline secrets), a
disabled `SecretStoreProvider` whose `read_secret_value` raises
`SecretValueAccessDisabledError`, a redaction helper, and a read-only posture
collector + committed anti-drift summary
([secret-foundation-summary.yaml](infra/secrets/secret-foundation-summary.yaml)).
Thirteen GET-only `/operations/secrets/*` endpoints + 21 `/operations/safety`
fields (`secrets_foundation_status=modeled_fail_closed_not_configured`,
`secrets_production_ready=false`, `secrets_read_value_enabled=false`, every
`secrets_*_committed=false`) surface it, plus an Admin Console read-only **Secret
Posture** view with no reveal / copy / upload / rotate / configure control.
Verify with `python scripts/verify_secret_inventory.py`,
`verify_secret_reference_schema.py`, `verify_secret_store_abstraction.py`,
`verify_secret_no_inline_values.py`, `verify_secret_rotation_model.py`,
`verify_secret_redaction_policy.py`, `verify_secret_operations_visibility.py`,
`verify_admin_console_secret_posture.py`, `verify_secret_safety_fields.py`, and
the combined `scripts/verify_secret_management_foundation_baseline.sh`
(`SECRET_MANAGEMENT_FOUNDATION_BASELINE_VERIFY`, which chains the Step 51 + Step
52 baselines). Docs under [docs/security/](docs/security/) +
[docs/operations/](docs/operations/). **No production secrets configured, no
production secret store connected, no production readiness declared.** Next:
Step 54 (Application Security & Supply Chain Baseline).

## Identity Visibility & Integrated Verification (Stage 54D / Step 52.4 — closes Step 52)

Final sub-stage of **Step 52**: a **read-only** identity posture surface +
integrated Step 52 verification — production identity **modeled, fail-closed,
NOT enabled** (no real IdP, no production auth, no production login). New SDK
[shared/sdk/identity_posture/](shared/sdk/identity_posture/) aggregates the
committed Step 52.1/52.2/52.3 identity models into a redacted summary
([identity-posture-summary.yaml](infra/identity/identity-posture-summary.yaml),
anti-drift tested; status `modeled_fail_closed_not_enabled`, never
`production_identity_ready`). Thirteen GET-only `/operations/identity/*`
endpoints expose it (no POST/PUT/PATCH/DELETE, no login/callback/authorize/token/
logout/connect, no role-mapping mutation, no break-glass activation; `unknown`
when the summary is absent — never a fake PASS), and `/operations/safety` gains
35 identity fields (`identity_production_ready=false`, `identity_oidc_enabled=false`,
`identity_unknown_user_behavior=deny`, `identity_default_role=none`,
`identity_break_glass_enabled=false`, `production_executed_true_count=0`). The
Admin Console adds a read-only **Identity Posture** view (static fallback + React)
with NO OIDC login / connect / configure button, no production auth toggle, no
role-mapping editor, no break-glass button, and no token/secret display. Verify
with `python scripts/verify_identity_operations_visibility.py`
(`IDENTITY_OPERATIONS_VISIBILITY_VERIFY`),
`verify_admin_console_identity_posture.py` (`ADMIN_CONSOLE_IDENTITY_POSTURE_VERIFY`),
`verify_identity_safety_fields.py` (`IDENTITY_SAFETY_FIELDS_VERIFY`), and the
combined `scripts/verify_identity_foundation_baseline.sh`
(`IDENTITY_FOUNDATION_BASELINE_VERIFY`, which chains the Step 52.1/52.2/52.3
baselines). Docs under [docs/security/](docs/security/) +
[docs/operations/](docs/operations/). **Step 52 closes as: production identity
and OIDC foundation modeled, fail-closed, not enabled** — never production
identity ready. Production secret store (Step 53), production OIDC + real role
mapping, and a production approval identity chain (Step 60) remain out of scope.

## Runtime Visibility & Integrated Verification (Stage 53G / Step 51.4)

Closes Step 51 with a **read-only** runtime visibility surface + integrated
verification — **validated, not deployed** (no cluster, no Helm install, no
ArgoCD sync, no production readiness). A new `shared/sdk/runtime_baseline`
aggregates the committed Step 51 baseline into a redacted summary
([runtime-baseline-summary.yaml](infra/kubernetes/runtime-baseline-summary.yaml),
anti-drift tested; status `validated_not_deployed`, never `production_ready`).
Twelve GET-only `/operations/runtime/*` endpoints expose it (no
POST/PUT/PATCH/DELETE, no deploy/sync/apply/install, `unknown` when absent — never
a fake PASS), and `/operations/safety` gains Kubernetes/Helm/GitOps fields
(`kubernetes_cluster_connected=false`, `argocd_auto_sync_enabled=false`,
`runtime_production_ready=false`, `runtime_validated_not_deployed=true`, per-area
`*_status=passed`). The Admin Console adds a read-only **Runtime Baseline** view
(static fallback + React) with **no** deploy/sync/apply/install control, no
cluster-credential/kubeconfig/token input, and no mutation client method. The
combined `scripts/verify_kubernetes_helm_argocd_baseline.sh` chains all 23 prior
markers + the 3 runtime verifiers (`KUBERNETES_HELM_ARGOCD_BASELINE_VERIFY`,
`RUNTIME_OPERATIONS_VISIBILITY_VERIFY`, `RUNTIME_SAFETY_FIELDS_VERIFY`,
`ADMIN_CONSOLE_RUNTIME_BASELINE_VERIFY`). See
[`docs/platform/runtime-baseline-visibility.md`](docs/platform/runtime-baseline-visibility.md),
[`kubernetes-helm-argocd-integrated-baseline.md`](docs/platform/kubernetes-helm-argocd-integrated-baseline.md),
[`docs/operations/runtime-baseline-verification.md`](docs/operations/runtime-baseline-verification.md),
and [`kubernetes-non-production-limitations.md`](docs/operations/kubernetes-non-production-limitations.md).
**Step 51 overall: closed — Kubernetes / Helm / ArgoCD static runtime baseline
validated, not deployed** (NOT a production-readiness declaration).

## ArgoCD & Environment GitOps Baseline (Stage 53F / Step 51.3)

Adds a GitOps baseline under [infra/gitops/](infra/gitops/) — **manifests +
static validation only, never applied**: no ArgoCD installed, no `argocd app
sync`, no `kubectl`, no cluster connection. An ArgoCD `AppProject` restricts the
source to this repo, denies all cluster-scoped resources (empty
`clusterResourceWhitelist`) and `Secret`, and whitelists only the namespaced
kinds the chart renders. Four `Application` manifests (dev, test,
staging-placeholder, production-placeholder) are each pinned to their Helm values
file; a non-production app-of-apps references **dev + test only**. **Auto-sync is
disabled everywhere** (no `syncPolicy.automated`, no prune/selfHeal/allowEmpty,
no CreateNamespace, no finalizers, no hooks, no image-updater/notifications);
destinations are placeholders (`kubernetes.default.svc` marked placeholder;
`*.invalid` for staging/prod); no credentials, no Secret resource, no real
cluster endpoint. The **production placeholder is disabled** (`do-not-sync` +
`disabled-placeholder` + future-requirement annotations), excluded from the
app-of-apps, and its merged values stay fail-closed (no deploy/PVC/batch/egress/
operator actions). An environment catalog
([gitops-environments.yaml](infra/gitops/gitops-environments.yaml)) maps
environments → values → Applications and the mapping verifier asserts they agree.
Verify with `python scripts/verify_argocd_manifests.py`
(`ARGOCD_MANIFESTS_VERIFY: PASS`),
`verify_gitops_environment_mapping.py` (`GITOPS_ENVIRONMENT_MAPPING_VERIFY:
PASS`), `verify_gitops_production_isolation.py`
(`GITOPS_PRODUCTION_ISOLATION_VERIFY: PASS`), and
`scripts/verify_gitops_argocd_baseline.sh` (`GITOPS_ARGOCD_BASELINE_VERIFY:
PASS`). See [`docs/platform/argocd-gitops-baseline.md`](docs/platform/argocd-gitops-baseline.md),
[`gitops-environment-model.md`](docs/platform/gitops-environment-model.md),
[`argocd-production-isolation.md`](docs/platform/argocd-production-isolation.md),
and [`argocd-sync-safety.md`](docs/platform/argocd-sync-safety.md). Runtime
visibility (51.4) is deferred; real GitOps rollout / production readiness remain
out of scope.

## Migration, Backup & Restore Job Baseline (Stage 53E / Step 51.2C2)

Adds controlled Kubernetes batch manifests — a migration Job, a disabled +
suspended backup CronJob, and a disabled restore Job scaffold — **validated, not
executed** (no cluster, no kubectl, no helm install, no migration/backup/restore
run). Every batch command is **fixed and shell-free**, catalogued in
[batch-command-catalog.yaml](infra/kubernetes/batch-command-catalog.yaml) and
mirrored into `values.batchCommands` (no command/args/shell from free-form
values; verified equal). The migration wrapper uses a Postgres **advisory lock**
(`pg_advisory_lock`, the repo's existing idiom) and is forward-only; backup +
restore use **`secretKeyRef`-only** credentials (encryption key never inline);
the restore scaffold is isolated to the fixed `aiagents_restore_drill_` prefix
with source ≠ target and separate source/target Secret references. Batch pods get
restricted SecurityContext (runAsNonRoot, RuntimeDefault, no privesc, drop ALL,
read-only root, `/tmp` only), dedicated ServiceAccounts with
`automountServiceAccountToken: false` and **no Kubernetes RBAC**, and a minimal
DB-only NetworkPolicy. All operations are **disabled-by-default**
(`executionEnabled`/`scheduleEnabled=false`, CronJob `suspend=true`,
`concurrencyPolicy: Forbid`, `backoffLimit: 0`, deadline + TTL) and **fail-closed
in staging/production** (no batch resource renders; the 51.2A workload-security
verifier was extended to also cover CronJob pods). The backup artifact target is
a disabled placeholder, never an active datastore PVC; no Helm/ArgoCD hooks.
Verify with `python scripts/verify_kubernetes_batch_operation_inventory.py`
(`KUBERNETES_BATCH_OPERATION_INVENTORY_VERIFY: PASS`),
`verify_kubernetes_migration_job.py` (`KUBERNETES_MIGRATION_JOB_VERIFY: PASS`),
`verify_kubernetes_backup_cronjob.py` (`KUBERNETES_BACKUP_CRONJOB_VERIFY: PASS`),
`verify_kubernetes_restore_job.py` (`KUBERNETES_RESTORE_JOB_VERIFY: PASS`),
`verify_kubernetes_batch_job_policy.py` (`KUBERNETES_BATCH_JOB_POLICY_VERIFY:
PASS`), and `scripts/verify_kubernetes_batch_jobs_baseline.sh`
(`KUBERNETES_BATCH_JOBS_BASELINE_VERIFY: PASS`). See
[`docs/platform/kubernetes-batch-job-policy.md`](docs/platform/kubernetes-batch-job-policy.md),
[`kubernetes-migration-job-baseline.md`](docs/platform/kubernetes-migration-job-baseline.md),
[`kubernetes-backup-cronjob-baseline.md`](docs/platform/kubernetes-backup-cronjob-baseline.md),
and [`kubernetes-restore-job-safety.md`](docs/platform/kubernetes-restore-job-safety.md).
GitOps (51.3) is deferred; production migration/backup/restore execution remains out of scope.

## Storage Ownership & Data Lifecycle Baseline (Stage 53D / Step 51.2C1)

Adds an evidence-backed storage ownership + data-lifecycle baseline and a
fail-closed, environment-safe PVC layer. Every filesystem/storage consumer in
the real runtime is inventoried
([storage-consumer-inventory.yaml](infra/kubernetes/storage-consumer-inventory.yaml))
and normalized into typed stores with owner/writers/readers, lifecycle,
durability, rebuildability, confidentiality and integrity, plus a per-environment
strategy ([storage-ownership-catalog.yaml](infra/kubernetes/storage-ownership-catalog.yaml)).
In-cluster Postgres (`/var/lib/postgresql/data`) and Redis (`/data`) get
**generated RWO PVCs in dev/test only**, mounted in the Deployment template;
staging/production disable the internal datastores and use `externalService`.
Workspace stays **ephemeral per-pod** (not shared, no RWX); reports / audit
forensic exports stay `unresolved` (writers are deferred one-shot jobs); backup
is **separate** and deferred to Step 51.2C2. No `StorageClass`/`PersistentVolume`
resource, no hostPath/NFS/CSI, no real storage class or claim name, no
`ReadWriteOncePod`; generated PVCs are RWO single-writer; forbidden mount paths
rejected; production placeholders stay `productionConfigured=false` (fail
closed). Verify with `python scripts/verify_kubernetes_storage_inventory.py`
(`KUBERNETES_STORAGE_INVENTORY_VERIFY: PASS`),
`python scripts/verify_kubernetes_data_lifecycle.py`
(`KUBERNETES_DATA_LIFECYCLE_VERIFY: PASS`),
`python scripts/verify_kubernetes_storage_manifest.py`
(`KUBERNETES_STORAGE_MANIFEST_VERIFY: PASS`), and
`scripts/verify_kubernetes_storage_baseline.sh`
(`KUBERNETES_STORAGE_BASELINE_VERIFY: PASS`). Static manifest baseline only (no
cluster, no kubectl, no helm install). See
[`docs/platform/kubernetes-storage-baseline.md`](docs/platform/kubernetes-storage-baseline.md),
[`docs/platform/kubernetes-data-lifecycle.md`](docs/platform/kubernetes-data-lifecycle.md),
[`docs/platform/kubernetes-workspace-storage-model.md`](docs/platform/kubernetes-workspace-storage-model.md),
and [`docs/platform/kubernetes-datastore-persistence.md`](docs/platform/kubernetes-datastore-persistence.md).
Migration/Backup Jobs (51.2C2) and GitOps (51.3) are deferred.

## NetworkPolicy & Service Connectivity Baseline (Stage 53C / Step 51.2B)

Adds a default-deny Kubernetes NetworkPolicy baseline generated from the
evidence-backed connectivity model. The dependency matrix was revalidated (one
correction: OTLP→tempo now lists all 20 services → **75** edges = 49 internal +
26 observability-deferred), normalized into a
[connectivity catalog](infra/kubernetes/network-connectivity-catalog.yaml) and
mirrored into `networkPolicy.internalEdges`. Each environment renders
default-deny ingress + egress (the only empty pod selectors), a scoped DNS
egress (kube-dns, TCP/UDP 53 only), and per-target ingress / per-source egress
allows for all 49 internal edges — every required edge covered in both
directions (verifier requires `missing=0`, `unexpected=0`). Postgres (18
sources) and Redis (19 sources) are ClusterIP, dev/test-only, never exposed.
External egress is disabled for GitHub/LLM/Discord/Slack/Telegram/cloud/OIDC and
OTLP/Prometheus (observability deferred); no `0.0.0.0/0`/`::/0`, no IPBlock, no
NodePort/LoadBalancer/Ingress. `validate-values.yaml` is fail-closed (staging/
prod cannot disable NetworkPolicy or enable external egress / ingress-controller
/ external datastores). Verify with
`python scripts/verify_kubernetes_network_topology.py`
(`KUBERNETES_NETWORK_TOPOLOGY_VERIFY: PASS`),
`python scripts/verify_kubernetes_network_policy.py`
(`KUBERNETES_NETWORK_POLICY_VERIFY: PASS`),
`python scripts/verify_kubernetes_service_connectivity.py`
(`KUBERNETES_SERVICE_CONNECTIVITY_VERIFY: PASS`), and
`scripts/verify_kubernetes_network_baseline.sh`
(`KUBERNETES_NETWORK_BASELINE_VERIFY: PASS`). Static manifest baseline only (no
cluster, no kubectl, no helm install); CNI enforcement is a deferred cluster
concern. See
[`docs/platform/kubernetes-network-policy-baseline.md`](docs/platform/kubernetes-network-policy-baseline.md),
[`docs/platform/kubernetes-service-connectivity.md`](docs/platform/kubernetes-service-connectivity.md),
and [`docs/platform/kubernetes-external-egress-model.md`](docs/platform/kubernetes-external-egress-model.md).
Storage/Jobs (51.2C) and GitOps (51.3) are deferred.

## Workload Security & RBAC Safety Baseline (Stage 53B / Step 51.2A)

Applies a restricted, values-driven SecurityContext baseline to every workload
in the foundation chart and proves the RBAC posture is zero-privilege. The
[workload-security inventory](infra/kubernetes/workload-security-inventory.yaml)
records each of the 23 components' real runtime needs (first-party images are
`python:3.12-slim` with no USER directive; only `/tmp` is written). The chart's
`global.workloadSecurity` enforces runAsNonRoot, non-zero UID, RuntimeDefault
seccomp, `allowPrivilegeEscalation=false`, `privileged=false`, drop ALL
capabilities (no add), read-only root filesystem (first-party), size-limited
`emptyDir` writable paths, and `automountServiceAccountToken=false` on both the
ServiceAccount and pod spec. `validate-values.yaml` is fail-closed (staging/prod
cannot disable security; no root UID, privilege escalation, cap-add, hostPath,
docker socket, or writable `/`,`/app`,`/etc`). The
[RBAC safety catalog](infra/kubernetes/rbac-safety-catalog.yaml) records that no
Role/ClusterRole is created and no component needs the Kubernetes API; the Step
50 operator/platform_admin roles get no Kubernetes permission. Verify with
`python scripts/verify_kubernetes_workload_security.py`
(`KUBERNETES_WORKLOAD_SECURITY_VERIFY: PASS`),
`python scripts/verify_kubernetes_rbac_safety.py`
(`KUBERNETES_RBAC_SAFETY_VERIFY: PASS`), and
`scripts/verify_kubernetes_security_rbac_baseline.sh`
(`KUBERNETES_SECURITY_RBAC_BASELINE_VERIFY: PASS`). Static manifest baseline only
(no cluster, no kubectl, no helm install); non-root/read-only-root runtime start
is flagged `requires_cluster_smoke`. See
[`docs/platform/kubernetes-workload-security-baseline.md`](docs/platform/kubernetes-workload-security-baseline.md),
[`docs/platform/kubernetes-rbac-safety-baseline.md`](docs/platform/kubernetes-rbac-safety-baseline.md),
and [`docs/platform/kubernetes-writable-path-model.md`](docs/platform/kubernetes-writable-path-model.md).
NetworkPolicy (51.2B), storage/Jobs (51.2C) and GitOps (51.3) are deferred.

## Runtime Inventory & Helm Foundation (Stage 53A / Step 51.1)

Turns the actual Docker Compose runtime into an evidence-backed inventory and a
lint-able, render-able **Helm foundation** — the base for Kubernetes work in
Step 51.2+. The [runtime inventory](infra/kubernetes/runtime-inventory.yaml) +
[dependency matrix](infra/kubernetes/runtime-dependency-matrix.yaml) classify
all 27 Compose services (20 first-party long-running Deployment targets,
optional dev/test Postgres/Redis, test-only Vault, deferred observability) and
record one-shot jobs (migrations, backup) so they are never turned into
Deployments. The [`ai-agents-platform`](infra/kubernetes/charts/ai-agents-platform)
chart (v0.1.0) renders generic Deployment/Service/ConfigMap/ServiceAccount
manifests from a values-driven component loop across **dev / test /
staging-placeholder / production-placeholder**. It is a **foundation only**: no
cluster connection, no `helm install`; `realDeployEnabled` is false everywhere;
the production placeholder is **fail-closed and non-deployable**
(`validate-values.yaml` rejects test/production auth, operator actions, GitHub
write, deployment, in-cluster datastores, `:latest`, and inline secrets — the
chart never creates a Secret). Verify with
`python scripts/verify_kubernetes_runtime_inventory.py`
(`KUBERNETES_RUNTIME_INVENTORY_VERIFY: PASS`) and
`scripts/verify_helm_foundation.sh` (`HELM_FOUNDATION_VERIFY: PASS`). See
[`docs/platform/runtime-service-inventory.md`](docs/platform/runtime-service-inventory.md),
[`docs/platform/helm-foundation.md`](docs/platform/helm-foundation.md), and
[`docs/platform/environment-values-foundation.md`](docs/platform/environment-values-foundation.md).
Security hardening, NetworkPolicy, RBAC, storage, Jobs and GitOps are deferred
to later Step 51 sub-stages.

## Admin Console v1 — Operator Actions (Stage 52)

Upgrades the Admin Console from read-only visibility to a **controlled Operator
Console** (`/operator`). Enabled actions — add review note, request changes,
accept, reject, and **allowlisted** verification rerun — are each gated by
test-local signed-session **authentication**, **RBAC**
(viewer/reviewer/operator/platform_admin), **CSRF**, the platform
**policy-engine**, a one-time **confirmation** nonce, **idempotency**, and
**audit**. Delivery acceptance is a **human-review acceptance only** — it never
triggers GitHub, PR, merge, deploy, external delivery, or production. High-risk
actions (deploy, GitHub write/PR, workflow pause/resume, work-item mutation,
production backup/restore, policy/budget edits, arbitrary shell) are
**disabled-only** catalog entries returning `403 policy_blocked` /
`409 action_disabled`. Auth fails closed (production auth / OIDC disabled,
unknown modes denied); the session token is an HttpOnly/SameSite=Strict cookie,
never in localStorage; no raw token/secret is persisted. Verify with
`scripts/verify_admin_console_v1_operator_actions.sh`
(`ADMIN_CONSOLE_V1_OPERATOR_ACTIONS_VERIFY: PASS`). See
[`docs/product/admin-console-v1-operator-actions.md`](docs/product/admin-console-v1-operator-actions.md),
[`docs/product/operator-rbac-model.md`](docs/product/operator-rbac-model.md),
[`docs/product/operator-action-policy-model.md`](docs/product/operator-action-policy-model.md),
[`docs/product/operator-confirmation-idempotency.md`](docs/product/operator-confirmation-idempotency.md),
[`docs/operations/admin-console-auth-session.md`](docs/operations/admin-console-auth-session.md),
[`docs/operations/verification-rerun-runbook.md`](docs/operations/verification-rerun-runbook.md),
and
[`docs/operations/operator-action-audit.md`](docs/operations/operator-action-audit.md).

## Backup / DR Gap Closure (Stage 51)

Closes the four long-standing Backup / DR documented gaps — `encryption_no_key`,
`storage_not_off_host`, `schedule_dry_run_only`, `migration_down_gaps` — at a
**controlled test baseline**, advancing backup readiness from `PASS_WITH_GAPS` to
`passed_with_non_production_limitations`. Extends the Stage 36 backup design
(`shared/sdk/backup`) with `shared/sdk/backup_dr/`: a test-only encrypted backup
(key file chmod 600, gitignored; manifest carries a `key_id` label, never the raw
key), a mock off-host transfer with readback-checksum verification, an isolated
restore drill (`aiagents_restore_drill_*` only — never production), dry-run
validated cron/systemd/k8s schedule specs, a dry-run retention policy
(`actual_delete_count=0`), and a complete migration rollback catalog (every
migration classified, zero `unknown`). Read-only `/operations/backup-dr/*`
endpoints + 24 new `/operations/safety` fields. **Not** production backup/restore,
**not** real cloud write, **not** a real production schedule; no raw key
persisted; `production_executed_true_count` stays 0; `backup_dr.*` / `restore.*` /
`dr.*` notifications default-denied. Verify with
`scripts/verify_backup_dr_gap_closure.sh`
(`BACKUP_DR_GAP_CLOSURE_VERIFY: PASS`). See
[`docs/operations/backup-dr-gap-closure.md`](docs/operations/backup-dr-gap-closure.md),
[`docs/operations/encrypted-backup-runbook.md`](docs/operations/encrypted-backup-runbook.md),
[`docs/operations/restore-drill-runbook.md`](docs/operations/restore-drill-runbook.md),
[`docs/operations/offhost-backup-target.md`](docs/operations/offhost-backup-target.md),
[`docs/operations/backup-schedule-and-retention.md`](docs/operations/backup-schedule-and-retention.md),
and
[`docs/operations/migration-rollback-catalog.md`](docs/operations/migration-rollback-catalog.md).

## Admin Console v0 — Read-only Visibility (Stage 50)

The first browser UI: a **read-only** project-delivery management console served
by the orchestrator at **`/admin`**. It surfaces platform safety, projects,
task graph, design review, workspace execution, mini delivery pilot, delivery
package + acceptance gate, human acceptance (pending), regression status, backup
readiness gaps, incidents, and LLM / cost governance — backed by six read-only
aggregate endpoints under `/operations/admin-console/*`. It does **not** replace
Grafana (which stays for metrics / tracing / infra). Strictly read-only: GET-only
API client, no operator actions, no write API, no deploy / PR / approval; secret
and chain-of-thought redaction on every rendered value;
`admin_console_read_only=true`, `admin_console_write_api_enabled=false`,
`admin_console_operator_actions_enabled=false`. Served via a committed zero-build
static fallback (so `/admin` responds without a Node toolchain) or an optional
React + Vite + TypeScript bundle. See
[`docs/product/admin-console-v0.md`](docs/product/admin-console-v0.md),
[`docs/product/admin-console-information-architecture.md`](docs/product/admin-console-information-architecture.md),
[`docs/product/admin-console-read-only-safety.md`](docs/product/admin-console-read-only-safety.md),
[`docs/product/admin-console-page-map.md`](docs/product/admin-console-page-map.md),
and
[`docs/operations/admin-console-operations.md`](docs/operations/admin-console-operations.md).

## Delivery Package & Acceptance Gate (Stage 49)

On top of the Stage 48 mini delivery pilot, the platform assembles a completed
pilot into a formal, human-reviewable **Delivery Package**: 14 sections, linked
source artifacts (refs + hashes only), an operator-readable acceptance
checklist, an 18-check **Acceptance Gate**, business / technical / operator
handoff summaries, a delivery readiness snapshot, and a pending operator-review
placeholder. The gate resolves to `ready_for_operator_review` —
`human_acceptance_status` stays `pending` and operator accept / reject /
request-changes endpoints are **disabled by default**. Controlled-only — no real
PR, no merge, no deploy, no real LLM, no external delivery, no auto-accept;
`production_executed` stays `false`. `delivery_package.*` / `acceptance_gate.*` /
`handoff.*` notifications are default-denied. See
[`docs/product/delivery-package-acceptance-gate.md`](docs/product/delivery-package-acceptance-gate.md),
[`docs/product/fastapi-todo-delivery-package.md`](docs/product/fastapi-todo-delivery-package.md),
[`docs/product/operator-acceptance-review.md`](docs/product/operator-acceptance-review.md),
[`docs/product/delivery-readiness-model.md`](docs/product/delivery-readiness-model.md),
and
[`docs/operations/delivery-package-operations.md`](docs/operations/delivery-package-operations.md).

## Mini Project Delivery Pilot (Stage 48)

The first verifiable controlled end-to-end delivery path: one pilot run chains
project planning → design review → controlled workspace execution → test/static
evidence → evidence-based acceptance evaluation → QA summary → safety summary →
a mini delivery pilot report, recording pilot-level steps, evidence, and
artifact links. Controlled-only — no real PR, no merge, no deploy, no real LLM,
no external delivery; `production_executed` stays `false`. `delivery_pilot.*` /
`acceptance.*` / `qa_evidence.*` notifications are default-denied. See
[`docs/product/mini-project-delivery-pilot.md`](docs/product/mini-project-delivery-pilot.md),
[`docs/product/fastapi-todo-mini-pilot.md`](docs/product/fastapi-todo-mini-pilot.md),
[`docs/product/acceptance-evidence-evaluation.md`](docs/product/acceptance-evidence-evaluation.md),
[`docs/product/qa-safety-evidence.md`](docs/product/qa-safety-evidence.md),
and
[`docs/operations/mini-delivery-pilot-operations.md`](docs/operations/mini-delivery-pilot-operations.md).

## Real Repo Workspace Operator v1 (Stage 47)

On top of the Stage 45 graph + Stage 46 design review, the platform can run a
**controlled workspace execution**: after a non-blocked design review it
generates a deterministic FastAPI Todo project under an allowlisted workspace
root, runs `pytest` + static checks (`ruff`/`compileall`), and records a diff
summary, artifacts (implementation summary / generated-code manifest / test
result / diff), and work-item execution links. Controlled-only — no repo-root
write, no GitHub, no PR, no merge, no deploy, no real LLM; `production_executed`
stays `false`. Generated workspaces are gitignored and never committed. See
[`docs/product/real-repo-workspace-operator.md`](docs/product/real-repo-workspace-operator.md),
[`docs/product/controlled-workspace-safety.md`](docs/product/controlled-workspace-safety.md),
[`docs/product/fastapi-todo-workspace-template.md`](docs/product/fastapi-todo-workspace-template.md),
and
[`docs/operations/workspace-operator-operations.md`](docs/operations/workspace-operator-operations.md).

## Agent Discussion & Design Review Protocol (Stage 46)

On top of the Stage 45 project graph, the platform runs a structured multi-role
design review (requirement / architecture / implementation / QA / security /
delivery + acceptance coverage), evaluates review gates, and records a go/no-go
decision — all review-only, deterministic, with no chain-of-thought persistence.
No real LLM, no repo write, no PR, no deploy, no work-item dispatch. See
[`docs/product/agent-discussion-design-review.md`](docs/product/agent-discussion-design-review.md),
[`docs/product/design-review-gates.md`](docs/product/design-review-gates.md),
and
[`docs/operations/design-review-operations.md`](docs/operations/design-review-operations.md).

## Project Planner & Task Graph (Stage 45)

Moves the platform from a linear workflow pipeline toward a project-delivery
platform. A software request becomes a project plan: brief, user stories,
acceptance criteria, milestones, and a validated work-item task graph with
dependencies and suggested agent roles. Planning-only — no LLM, no GitHub write,
no deploy, no work-item dispatch. See
[`docs/product/project-planner-agent.md`](docs/product/project-planner-agent.md),
[`docs/product/project-task-graph.md`](docs/product/project-task-graph.md),
[`docs/product/mini-project-delivery-path.md`](docs/product/mini-project-delivery-path.md),
and
[`docs/operations/project-planning-operations.md`](docs/operations/project-planning-operations.md).

## Audit Integrity Remediation — HMAC Keyring & Direct POST Closure (Stage 39)

Stage 39 closes the two audit-integrity carry-forward gaps recorded
under Stages 34-36:

* **HMAC key rotation / key map loader** -- a new
  [`shared/sdk/audit_integrity/keyring.py`](shared/sdk/audit_integrity/keyring.py)
  reads `AUDIT_HMAC_KEYRING_JSON` (multi-key, preferred) or
  `AUDIT_HMAC_KEY` (legacy single-key fallback). The signer signs new
  rows with the keyring's active key; the verifier looks up the
  per-row `signing_key_id` so a row signed with an older key keeps
  verifying after rotation. Keyring modes: `none` /
  `legacy_single_key` / `multi_keyring` / `invalid`. A malformed
  config refuses to sign so a wrong key never enters the chain. The
  key value is never returned, logged, or persisted -- only the
  opaque `signing_key_id` and metadata.
* **audit-service `POST /audit/events` direct-write integrity gap** --
  the handler now inserts `audit_logs` and `audit_integrity_records`
  in the **same Postgres transaction**, holding
  `pg_advisory_xact_lock(hashtext('audit_integrity_chain_v1'))` to
  serialise the sequence assignment. On any integrity failure the
  transaction rolls back and the service responds **`503`** -- no
  orphan audit row ever lands.

New verification modes (`AUDIT_VERIFY_SIGNATURE_MODE`):

* `permissive` -- hash chain mandatory; key-missing downgrades the
  run to `partial`. Default.
* `strict` -- hash chain mandatory; signed rows must verify and the
  key must be in the keyring; unsigned rows fail unless
  `AUDIT_VERIFY_ALLOW_UNSIGNED_LEGACY=1`. Recommended for production.
* `chain_only` -- hash chain only; HMAC ignored. Emergency
  diagnostic.

New endpoints + safety fields (orchestrator):

* `GET /operations/audit/keyring` -- read-only view of the loaded
  keyring + `audit_hmac_key_metadata` rows. Never returns key bytes.
* `GET /operations/audit/integrity` -- now carries
  `hmac_keyring_*`, `active_signing_key_id`, `signed_records`,
  `unsigned_records`, `key_missing_records`,
  `signature_failed_records`, `latest_verification_mode`,
  `direct_post_integrity_enabled`,
  `direct_post_missing_integrity_records`, and
  `audit_integrity_writer_locking_enabled`.
* `GET /operations/audit/receipt/{audit_log_id}` -- new
  `signing_key_id`, `signature_status`, `signature_verification_status`
  (`ok` / `key_missing` / `signature_failed` / `no_keyring` / `n/a`),
  `key_available`, `keyring_mode`.
* `POST /operations/audit/verify-chain?mode=<mode>` -- accept a
  verification mode (also supports a JSON body).
* `GET /operations/safety` -- new flags:
  `audit_hmac_keyring_configured`, `audit_hmac_keyring_valid`,
  `audit_hmac_keyring_mode`, `audit_hmac_active_signing_key_id`,
  `audit_hmac_rotation_supported`,
  `audit_direct_post_integrity_enabled`,
  `audit_direct_post_integrity_gap_closed`,
  `audit_integrity_concurrency_lock_enabled`,
  `audit_integrity_strict_verify_ready`,
  `audit_signature_key_missing_count`.

New verify scripts: `verify_audit_hmac_key_rotation.sh`,
`verify_audit_direct_post_integrity.sh`,
`verify_audit_integrity_remediation.sh` (markers
`AUDIT_HMAC_KEY_ROTATION_VERIFY: PASS`,
`AUDIT_DIRECT_POST_INTEGRITY_VERIFY: PASS`,
`AUDIT_INTEGRITY_REMEDIATION_VERIFY: PASS`). 12 new runtime smokes in
`scripts/check_runtime_state.sh`.

The full operator runbook lives in
[`docs/operations/tamper-evident-audit.md`](docs/operations/tamper-evident-audit.md)
under "Stage 39 -- HMAC keyring rotation + direct POST integrity
closure".

Stage 39 does **not** roll out a production secret store, real
off-host backup target, Kubernetes baseline, or external alert
receiver -- those remain carry-forward items.

## LLM Model Routing & Agent Model Policy (Stage 38)

Stage 38 centralises every "which model do we use for this LLM call?"
decision. Agents no longer pick models. Agents submit a standardised
`LLMCapabilityRequest` describing what capability they need, plus risk
level, schema, and estimated tokens. A central `ModelRouter` consults
`agent_model_policies`, `llm_model_registry`, the Stage 35 budget
gate, and the existing Stage 30 / 35 safety rails to return a
`LLMRoutingDecision`.

- New SDK: [`shared/sdk/llm_routing/`](shared/sdk/llm_routing/) -- models,
  registry, policy, router, evaluator, async store.
- New migration: [`migrations/014_llm_model_routing_policy.sql`](migrations/014_llm_model_routing_policy.sql)
  adds `llm_model_registry`, `agent_model_policies`, `llm_routing_decisions`.
- Default seed: mock-only + plan-only real provider entries are
  seeded `inactive`; agent policies block real LLM, patch generation,
  and workspace write by default.
- Hard rails (router-enforced regardless of registry / policy state):
  patch generation hard-disabled; workspace write hard-disabled;
  unauthorised `requested_model_alias` -> `direct_model_rejected`.
- New endpoints: `GET /operations/llm/models`,
  `GET /operations/llm/model-policies`,
  `GET /operations/llm/routing-decisions`,
  `GET /operations/llm/routing-decisions/{task_id}`,
  `POST /operations/llm/routing/preview`,
  `POST /operations/llm/routing/seed-defaults`.
- `GET /operations/safety` gains `llm_model_router_enabled`,
  `agent_direct_model_selection_allowed=false`,
  `llm_routing_policy_enforced=true`,
  `llm_model_registry_active_count`,
  `llm_routing_budget_enforced=true`,
  `llm_routing_human_review_enforced=true`,
  `llm_model_routing_active_policies`.
- `GET /operations/summary` gets an `llm_model_routing_summary`
  block.
- `GET /discord/tasks/{task_id}` gains `llm_model_router_enabled`,
  `agent_direct_model_selection_allowed=false`,
  `selected_model_alias`, `selected_provider`, `selected_model_tier`,
  `routing_decision`, `routing_requires_human_review`,
  `routing_fallback_used`.

Verification:

```bash
./scripts/verify_llm_model_routing.sh
```

See [`docs/operations/llm-model-routing.md`](docs/operations/llm-model-routing.md).

## Backup / Restore / DR Drill (Stage 36)

Stage 36 brings PostgreSQL backup + restore up to production-readiness
baseline. The platform itself is NOT a production deploy; the tooling
described here exposes which gaps still block the production gate.

- New SDK: [`shared/sdk/backup/`](shared/sdk/backup/) (manifest,
  checksum, encryption metadata, pluggable storage interface, isolated
  restore-DB rules).
- New scripts:
  - [`scripts/backup_postgres_encrypted.sh`](scripts/backup_postgres_encrypted.sh)
    -- pg_dump + openssl AES-256-CBC + manifest + sha256 (never prints
    the key value).
  - [`scripts/decrypt_backup_for_restore.sh`](scripts/decrypt_backup_for_restore.sh).
  - [`scripts/upload_backup_artifact.sh`](scripts/upload_backup_artifact.sh)
    / [`scripts/download_backup_artifact.sh`](scripts/download_backup_artifact.sh)
    -- local-filesystem (real) + s3-compatible-placeholder (wired but
    not implemented) + disabled.
  - [`scripts/run_restore_drill.sh`](scripts/run_restore_drill.sh) --
    encrypted backup + isolated `aiagents_restore_drill_<ts>` restore
    + row count + audit integrity walk + cleanup +
    `source/dr-reports/dr_report_<ts>.json`.
  - [`scripts/measure_backup_rto_rpo.sh`](scripts/measure_backup_rto_rpo.sh).
  - [`scripts/install_backup_cron.sh`](scripts/install_backup_cron.sh)
    (dry-run by default) / [`scripts/uninstall_backup_cron.sh`](scripts/uninstall_backup_cron.sh).
  - [`scripts/check_migration_down_scripts.sh`](scripts/check_migration_down_scripts.sh).
  - [`scripts/verify_backup_drill.sh`](scripts/verify_backup_drill.sh)
    and [`scripts/verify_backup_production_readiness.sh`](scripts/verify_backup_production_readiness.sh).
- New endpoints: `GET /operations/backup/status`,
  `GET /operations/backup/reports`,
  `GET /operations/backup/reports/latest`.
- `GET /operations/safety` gains `backup_encryption_enabled`,
  `backup_encryption_production_ready`, `backup_off_host_enabled`,
  `backup_storage_mode`, `latest_restore_drill_status`,
  `backup_production_ready`, `backup_gaps`,
  `migration_down_scripts_complete`, `dr_runbook_present`.
- `GET /operations/summary` carries a `backup_summary` block with
  `latest_backup_at`, `latest_backup_id`,
  `latest_restore_drill_status`, `rto_seconds`, `rpo_seconds`,
  `off_host_uploaded`, `encryption_enabled`, `storage_mode`,
  `production_executed`.

Verification:

```bash
./scripts/verify_backup_drill.sh
./scripts/verify_backup_production_readiness.sh
```

`verify_backup_production_readiness.sh` is expected to return
`PASS_WITH_GAPS` on the test cluster: off-host S3 is wired-but-not-
implemented, the cron entry is dry-run-only, and migration down scripts
are not yet shipped. The remediation roadmap is owned by future steps.

See [`docs/operations/backup-restore-dr.md`](docs/operations/backup-restore-dr.md),
[`docs/operations/restore-drill-runbook.md`](docs/operations/restore-drill-runbook.md),
and [`docs/operations/backup-schedule.md`](docs/operations/backup-schedule.md).

## LLM Cost Governance + Real LLM Plan-Only Pilot (Stage 35)

Stage 35 adds an enforceable budget for every real LLM call and
opens a narrow plan-only pilot path. Two new tables
(`llm_budget_policies` + `llm_budget_events`) carry per-scope cost /
token caps and a row per preflight / recorded-usage / budget-exceeded
decision. The mock provider is exempt; every real LLM call MUST
clear an active policy before touching the wire.

- New providers: `external_openai`, `external_anthropic` (plan-only).
- Both providers REFUSE `generate_patch_proposal` /
  `generate_test_plan` -- only `generate_development_plan` is
  implemented.
- Endpoints: `GET /operations/llm/budget`,
  `GET /operations/llm/budget/policies`,
  `POST /operations/llm/budget/policies`,
  `GET /operations/llm/budget/usage`,
  `GET /operations/llm/budget/events`,
  `GET /operations/llm/plan-only/{task_id}`.
- `GET /operations/safety` gains `real_llm_enabled_pilot`,
  `llm_real_plan_only_enabled`,
  `llm_patch_generation_enabled` (**always false**),
  `llm_workspace_write_enabled` (**always false**),
  `llm_cost_governance_enabled`, `llm_budget_policy_active`,
  `llm_budget_enforcement_mode`, `llm_daily_budget_remaining`,
  `llm_monthly_budget_remaining`, `llm_budget_exceeded`.

Verification:

```bash
./scripts/check_llm_runtime_inputs.sh
./scripts/verify_llm_cost_governance.sh
./scripts/verify_real_llm_plan_only_pilot.sh
```

Without the real-LLM env, the pilot script emits
`REAL_LLM_PLAN_ONLY_SKIPPED: PASS` and exits 0. See
[`docs/operations/llm-cost-governance.md`](docs/operations/llm-cost-governance.md)
and [`docs/operations/real-llm-plan-only-pilot.md`](docs/operations/real-llm-plan-only-pilot.md).

## Tamper-Evident Audit Chain (Stage 34)

Stage 34 adds a hash-chain integrity record next to every
`audit_logs` row. The audit-worker computes `canonical_payload_hash`
+ `row_hash` (SHA-256) and (optionally) an HMAC signature for each
new audit row, and writes it into `audit_integrity_records`. A
sibling table `audit_chain_verification_runs` records every
verify-chain pass. Stage 34 does **not** modify the existing
`audit_logs` table.

- `POST /operations/audit/verify-chain` runs the verifier on demand
  and records the run.
- `GET /operations/audit/receipt/{audit_log_id}` returns a
  per-row receipt with `row_hash`, `canonical_payload_hash`,
  `hmac_signature_present` (boolean) + an 8-char preview. The full
  HMAC signature is never returned by this endpoint.
- HMAC is optional. Without `AUDIT_HMAC_KEY` the chain still
  detects payload mutation, row-hash mutation, prev-hash mutation,
  reordering, and missing rows; `signature_status` is recorded as
  `signing_key_not_configured`. The key value is never logged or
  returned by any operations endpoint.

Verification:

```bash
./scripts/backfill_audit_integrity.sh
./scripts/verify_audit_integrity.sh
./scripts/simulate_audit_tamper_detection.sh
./scripts/verify_tamper_evident_audit.sh
```

See [`docs/operations/tamper-evident-audit.md`](docs/operations/tamper-evident-audit.md)
for the full threat model + verification runbook.

## Real Discord Delivery Policy (Stage 33)

Step 31R surfaced an "autospam" blocker: with real Discord env live in
the `notification-worker` container, the stream consumer routed every
internal platform event (workflow / qa / code / github / …) to the test
channel. Stage 33 adds a per-event policy on the stream-consumer path
that mirrors the Stage 32 endpoint guard:

- Default **deny** for `workflow.*`, `qa.*`, `code.*`, `github.*`,
  `task.*`, `llm.*`, `approval.*`, `audit.*`, `incident.*`, `retry.*`.
- Default **allow** for `discord.real_test_sent`,
  `discord.real_task_received` only.
- Per-event opt-in via `metadata.real_delivery=true` (denylist still
  wins).
- `production_executed=true` and wrong-channel payloads are always
  blocked.
- Blocked events produce one `discord_real_delivery_blocked` audit row
  and **never** republish onto `stream.notifications` (no notification
  loop).

Knobs: `REAL_DISCORD_ALLOWLIST`, `REAL_DISCORD_DENYLIST`,
`REAL_DISCORD_ALLOW_MARKER`. None of these widens the Stage 32 endpoint
guard or the `HARD_SAFETY_ACTIONS` rail. See
[`docs/operations/real-discord-delivery-policy.md`](docs/operations/real-discord-delivery-policy.md).

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
