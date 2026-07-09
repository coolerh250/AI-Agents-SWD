# Step 66B.1 — Test Deployment Record

> **Test runtime only (`10.0.1.31`, `aiagents-test`). No staging deployment. No production
> deployment. No external write. No unscoped docker prune.**

## 1. Pre-existing gap discovered: test database had zero tables

Before applying migration 029, inspection found the test Postgres database (`aiagents`) had **zero
tables and only the built-in `plpgsql` extension** — the Step 66A.0 environment reset (`docker
compose down --volumes` + `up -d`) correctly reset the runtime, but the migration-bootstrap step
(`for migration in migrations/*.sql; do psql < "$migration"; done`, per
`scripts/init_local_runtime.sh`) was never run afterward. `/health` and `/operations/safety` still
returned `200` in 66A.0 because those checks degrade gracefully on missing tables/rows — the gap was
silent until this stage tried to apply a real migration against a real table.

**Remediation (this stage):** ran the full migration loop, `migrations/001_init_core_tables.sql`
through `migrations/029_operator_task_api_foundation.sql` (29 files, in order), each via
`docker compose -f infra/docker-compose/docker-compose.yml exec -T postgres psql -U postgres -d aiagents -v ON_ERROR_STOP=1 < "$migration"`
— all 29 applied successfully (`rc=0`), matching `scripts/init_local_runtime.sh`'s exact loop. Also
ran `bash scripts/init_redis_streams.sh` (idempotent; 6 consumer groups created, 11 already existed,
17 total, including `stream.audit/audit-group` needed for this stage's audit events). No data was
lost — the database held no rows before this; this is initialization, not a destructive operation.

## 2. Migration 029 (this stage's own change)

- **Name:** `029_operator_task_api_foundation.sql`
- **Tables added:** `operator_tasks` (new; see `step66b1-task-api-foundation-report.md` §2 for
  columns). No existing table altered. Verified live via `\d operator_tasks` — all 19 columns,
  defaults, and 6 indexes present exactly as designed.
- **Rollback note:** no dedicated down-script (matches this repo's existing convention — zero
  migrations currently ship a down-script, see `scripts/check_migration_down_scripts.sh`). Manual
  rollback if ever needed: `DROP TABLE IF EXISTS operator_tasks;` (idempotent, safe — no other
  table references it).
- **Test data created:** 1 test task record from smoke validation (`environment='test'`,
  `production_effect=false`, id `1aaea422-2bde-4808-9ace-3a5d3d31ae94`).

## 3. Orchestrator rebuild/restart (scoped — orchestrator only)

```
docker compose -f infra/docker-compose/docker-compose.yml build orchestrator
docker compose -f infra/docker-compose/docker-compose.yml up -d orchestrator
```

Build succeeded; orchestrator recreated and reported `Up ... (healthy)` within 8s. postgres/redis and
the other 25 services were **not** restarted (they were already healthy). No full-stack rebuild. No
`docker compose down`. No unscoped `docker system prune` / `docker volume prune`.

## 4. Health & safety validation

See `step66b1-task-api-evidence.md` §3 for the full checklist (health, safety flags, and the four
task-API endpoints exercised with real HTTP calls against the live orchestrator). All 27/27
`aiagents-test` containers remained healthy after the orchestrator restart. Container health and
exact `/operations/safety` output are recorded there.

## 5. Forbidden actions — none performed

No staging deployment. No production deployment. No external write (GitHub/Discord/Slack/
Telegram/LLM/web). No unscoped docker prune. No full destructive reset. The migration-bootstrap
remediation in §1 was additive initialization against an empty database, not a destructive action.

## 6. Statement

Test runtime deployment completed on the verified test host `10.0.1.31`.
production_executed_true_count=0 on the test runtime after deployment (confirmed live before and
after all smoke-validation calls). No production action occurred. No unscoped docker prune was used.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
