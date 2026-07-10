# Step 66B.3 — Test Deployment Record

> **Deployment record only. No production action. No external action.**

## 1. Migration

**No migration required.** Step 66B.3 is RBAC/audit/safety hardening only — no schema change. The
`operator_tasks` table (migration `029_operator_task_api_foundation.sql`, from 66B.1) is unchanged.

- Migration name: n/a (none added)
- Tables/columns changed: none
- Additive: n/a
- Rollback note: n/a (no migration to roll back)
- Test data impact: none

## 2. Deployment scope

Orchestrator-only rebuild (bundles the hardened backend `task_api.py`/`shared/sdk/tasks/*` and the
hardened frontend via the existing `node:20-slim` Docker build stage) + restart on `10.0.1.31`
(`aiagents-test`). postgres/redis and the other services were **not** restarted. No full-stack
rebuild, no `docker compose down`, no unscoped `docker system prune`/`docker volume prune`. No
staging or production deployment.

## 3. Baseline (before deployment)

```
git status --short    -> clean (test host)
git log -1 --oneline   -> a96d655 docs(ai-team-work): record task ui operator validation
GET /health            -> {"service":"orchestrator","status":"ok"}
GET /operations/safety -> production_executed_true_count: 0
```

## 4. Deployment commands (executed)

```bash
cd /home/itadmin/AI-Agents-SWD
git pull --ff-only origin main   # -> 8b68609 feat(ai-team-work): harden task rbac audit safety
docker compose -f infra/docker-compose/docker-compose.yml build orchestrator
docker compose -f infra/docker-compose/docker-compose.yml up -d orchestrator
```

Build succeeded (bundles the hardened `task_api.py`/`shared/sdk/tasks/*` and the hardened frontend
via the existing `node:20-slim` stage). Only the `orchestrator` container was recreated;
postgres/redis and the other 25 services were untouched (`Waiting` → `Healthy` in the compose output
refers to the pre-existing dependency health checks, not a restart of those services).

## 5. Live validation (after deployment) — actual results, 2026-07-10

| Check | Result (actual) |
| --- | --- |
| `GET /health` | `{"service":"orchestrator","status":"ok"}` |
| `GET /operations/safety` → `task_api_rbac_denied_audit_enabled` | `True` (new field, confirms hardening deployed) |
| Missing `X-Task-Role` → `POST /tasks` | `401 {"detail":"missing_role"}` |
| Invalid `X-Task-Role` → `POST /tasks` | `401 {"detail":"invalid_role"}` |
| Requester (`alice`) creates own task | `201`, `created_by:"alice"`, `dispatch_enabled:false` |
| `alice` views own task (`GET /tasks/{id}`) | `200`, `dispatch_enabled:false` |
| **`bob` (requester) views `alice`'s task** | `403 {"detail":"not_own_task"}` |
| Platform Admin (`admin1`) views all tasks | `200`, `count:6`, includes tasks created by `bob`, `alice`, `test-operator`, `ui-validation` (multiple actors, not scoped) |
| `production_effect=true`, `initial_status=submitted` | `201`, `status:"blocked"`, `requires_approval:true`, `dispatch_enabled:false` |
| `GET /tasks/{id}` includes `dispatch_enabled` | confirmed present, value `false` |
| Container health after orchestrator restart | **27/27** `aiagents-test` containers healthy, none unhealthy |
| `production_executed_true_count` after all checks above | **`0`** (unchanged before/after) |

## 6. Statement

No workflow dispatch occurred. No external action occurred. No production action occurred.
production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
