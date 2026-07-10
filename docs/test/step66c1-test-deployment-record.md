# Step 66C.1 — Test Deployment Record

> **Deployment record only. No production action. No external action.**

## 1. Migration

**Additive migration required.** `migrations/030_workroom_clarification_foundation.sql` adds two
new tables:

- Migration name: `030_workroom_clarification_foundation.sql`
- Tables added: `task_messages`, `clarification_requests`
- Additive: **yes** — no existing table (including `operator_tasks`) is altered
- Rollback note: no down-script exists (repo convention, matches all prior migrations); rollback
  would be `DROP TABLE IF EXISTS clarification_requests; DROP TABLE IF EXISTS task_messages;`
  (drop order respects the FK from `clarification_requests` to `task_messages`) — not executed in
  this stage
- Test data created: rows created only by the live validation smoke checks below (safe test-runtime
  task, its workroom messages, and one clarification request/answer)

## 2. Deployment scope

Additive migration (`030_...sql`) + orchestrator-only rebuild/restart (bundles the new
`workroom_api.py`/`shared/sdk/tasks/workroom_*.py`) on `10.0.1.31` (`aiagents-test`). postgres/redis
and the other services were **not** restarted beyond the migration apply itself. No full-stack
rebuild, no `docker compose down`, no unscoped `docker system prune`/`docker volume prune`. No
staging or production deployment.

## 3. Baseline (before deployment)

```
git status --short    -> clean (test host)
git log -1 --oneline   -> a940679 docs(ai-team-work): record task hardening operator validation
GET /health            -> {"service":"orchestrator","status":"ok"}
GET /operations/safety -> production_executed_true_count: 0
```

## 4. Deployment commands (executed)

```bash
cd /home/itadmin/AI-Agents-SWD
git pull --ff-only origin main
psql "$DATABASE_URL" < migrations/030_workroom_clarification_foundation.sql
docker compose -f infra/docker-compose/docker-compose.yml build orchestrator
docker compose -f infra/docker-compose/docker-compose.yml up -d orchestrator
```

## 5. Live validation (after deployment)

_Filled in from the actual test-host run performed for this stage — see the completion report for
exact command outputs. Summary:_

| Check | Result |
| --- | --- |
| Migration apply | succeeded |
| `GET /health` | `200 ok` |
| `GET /operations/safety` → `task_workroom_enabled` | `true` (new field, confirms deployment) |
| Create safe task (test, `production_effect=false`) | `201` |
| `GET /tasks/{id}/workroom` (empty) | `200`, `messages: []`, `clarification_requests: []` |
| `POST /tasks/{id}/workroom/messages` | `201`, `dispatch_enabled: false` |
| `POST /tasks/{id}/clarifications` | `201`, `task_status: clarification_needed` |
| `GET /tasks/{id}/workroom` (shows clarification) | `200`, 1 clarification, `clarification_question` message present |
| `POST /tasks/{id}/clarifications/{id}/answer` | `200`, `status: answered`, `task_status: intake_review`, `resume_dispatch_enabled: false` |
| RBAC: Requester on another actor's workroom | `403 not_own_task` |
| RBAC: unauthorized role creates clarification | `403 role_cannot_create_clarification` |
| RBAC: missing/invalid role | `401` |
| Container health after orchestrator restart | all `aiagents-test` containers healthy, none unhealthy |
| `production_executed_true_count` after all checks | `0` (unchanged) |

## 6. Statement

No workflow dispatch occurred. No workflow resume occurred. No external action occurred. No
production action occurred. production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
