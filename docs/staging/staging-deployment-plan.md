# Staging Deployment Plan (Step 64A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Plan for deploying the staging stack in **Step 64B** (this Step 64A document does NOT deploy
anything; no `docker compose up`, no `kubectl apply`, no `helm install`).

## Staging target
- **Staging target host:** `10.0.1.32` · **Access method:** SSH
- **Credential handling:** interactive only — requested at connect time, never stored, never
  committed, never printed.
- **Deployment source:** GitHub `origin/main` (or sync from `10.0.1.31`), cloned to
  `10.0.1.32` in Step 64B.

## Deployment approach (Option A — Docker Compose)
Reuse the committed `infra/docker-compose/docker-compose.staging.yml` (project
`aiagents-staging`, 22 services, `+10000` host-port offset) plus `scripts/start_staging_runtime.sh`
/ `stop_staging_runtime.sh` / `check_staging_runtime.sh`. **Execution is deferred to Step 64B.**

## Pre-checks (read-only, Step 64B)
- Host reachable over SSH; user can run Docker (group or sudo — operator to confirm).
- Docker + Docker Compose v2 present (else recorded as a prerequisite gap; no auto-install).
- Disk / memory / CPU sufficient for 22 containers.
- `POSTGRES_PASSWORD` + staging env generated locally via `scripts/generate_staging_env.sh`
  into a gitignored `.env.staging.local` — never committed.

## Required host capabilities
Docker Engine, Docker Compose v2, ≥ ~4 vCPU / ~8 GB RAM / ~20 GB free disk (estimate),
loopback + optional LAN port exposure for `18000`.

## Expected ports (host, `+10000` offset)
| Service | Host port |
|---|---|
| orchestrator (Admin Console `/admin`) | 18000 |
| policy-engine | 18001 |
| approval-engine | 18002 |
| audit-service | 18003 |
| communication-gateway | 18004 |
| postgres | 15432 |
| redis | 16379 |
| vault (dev) | 18200 |

## Configuration model
Environment via gitignored `.env.staging.local` (shape from `.env.example` /
`generate_staging_env.sh`). No secret value is committed or printed. Live GitHub / Slack /
LLM integrations remain **disabled** by default.

## Database migration approach
28 idempotent SQL migrations in `migrations/` applied by `start_staging_runtime.sh` against
the staging Postgres (`docker exec ... psql`). No production database is touched.

## Health check plan
Compose healthchecks (e.g. orchestrator `GET /health`); post-bring-up verify
`GET /operations/safety` shows all production toggles false and
`production_executed_true_count=0`.

## Smoke test plan
Run existing non-production smoke verifiers (`check_staging_runtime.sh`,
`verify_staging_runtime.sh`) read-only against the staging stack. No production smoke.

## Rollback / teardown approach
`stop_staging_runtime.sh` (compose down for project `aiagents-staging`). Teardown removes
only staging volumes/containers; it never touches `10.0.1.31` test data, production, or any
scheduled DR/regression artifacts.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
