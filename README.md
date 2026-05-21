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

## Production Restriction

**No production deployment is performed without explicit human approval.**
Automation must not create, modify, or deploy production resources.

## Secrets

**No secrets are stored in this repository.** API keys, tokens, passwords, and
other credentials must be supplied via environment variables or a secrets
manager — never committed. See `.gitignore`.
