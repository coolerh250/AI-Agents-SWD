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
Vault (dev mode), and the `orchestrator` placeholder service.

Validate the compose configuration:

```
docker compose -f infra/docker-compose/docker-compose.yml config
```

Start the runtime (on the test server `10.0.1.31`):

```
docker compose -f infra/docker-compose/docker-compose.yml up -d postgres redis vault orchestrator
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

The `orchestrator` service runs a LangGraph workflow skeleton
(`apps/orchestrator/src/workflow.py`) with six nodes:
`intake → requirement → policy → approval → audit → final`. It wires in the
shared SDK's `PolicyClient`, `AuditClient`, and `RedisStreamEventBus`.

API endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Liveness check |
| POST | `/workflow/test` | Run the mock workflow for a request |
| POST | `/workflow/policy-test` | Evaluate an action against the policy |
| GET  | `/workflow/schema` | Describe the `WorkflowState` fields |

Run the mock workflow:

```
curl -X POST http://localhost:8000/workflow/test \
  -H "Content-Type: application/json" \
  -d '{"task_id":"mock-1","source":"manual","request":{"type":"dev.test"}}'
```

A non-production request runs through to `stage: completed`. A
`production.deploy` request is flagged by the policy node and ends at
`stage: waiting_approval` — **the workflow never executes a production
action**; it only records that human approval is required.

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
