# Step 66C.1 — Test Deployment Record

> **Deployment record only. No production action. No external action.**

## 1. Migration

**Additive migration required.** `migrations/030_workroom_clarification_foundation.sql` adds two
new tables:

- Migration name: `030_workroom_clarification_foundation.sql`
- Tables added: `task_messages`, `operator_clarification_requests` (named with the `operator_`
  prefix, not `clarification_requests`, to avoid colliding with the pre-existing, differently-shaped
  `clarification_requests` table from the unrelated Discord requirement-agent pipeline —
  `007_flexible_task_execution_loop.sql`; discovered during live deployment, see §5)
- Additive: **yes** — no existing table (including `operator_tasks` and the legacy
  `clarification_requests`) is altered
- Rollback note: no down-script exists (repo convention, matches all prior migrations); rollback
  would be `DROP TABLE IF EXISTS operator_clarification_requests; DROP TABLE IF EXISTS
  task_messages;` (drop order respects the FK from `operator_clarification_requests` to
  `task_messages`) — not executed in this stage
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

## 5. Live validation (after deployment) — actual results, 2026-07-10

**First apply attempt failed to create the intended table** (see §1 note): `CREATE TABLE IF NOT
EXISTS clarification_requests` silently no-op'd against the pre-existing, differently-shaped legacy
table, causing `GET /tasks/{id}/workroom` to 500
(`asyncpg.exceptions.DataError: invalid input for query argument $1 ... expected str, got UUID`,
from `list_clarifications` querying the legacy TEXT `task_id` column with a UUID parameter).
Diagnosed via `docker logs aiagents-test-orchestrator-1`, confirmed via `\d clarification_requests`
showing the legacy `007_flexible_task_execution_loop.sql` schema (`clarification_id` PK,
`workflow_id`, `requested_by_agent`, ...). Fixed by renaming the new table to
`operator_clarification_requests` (migration + `workroom_store.py` + docs), re-applying the
corrected migration (fresh `CREATE TABLE` this time, no collision), rebuilding, and restarting.
All checks below are from the **post-fix** re-run:

| Check | Result (actual) |
| --- | --- |
| Migration apply (corrected) | succeeded — `operator_clarification_requests` created fresh, no collision |
| `GET /health` | `{"service":"orchestrator","status":"ok"}` |
| Create safe task (`alice2-c1`, requester, test, `production_effect=false`) | `201`, `dispatch_enabled:false` |
| `GET /tasks/{id}/workroom` (empty) | `200`, `messages: []`, `clarification_requests: []`, `dispatch_enabled:false`, `resume_dispatch_enabled:false` |
| `POST /tasks/{id}/workroom/messages` | `201`, `message_type:"human_message"`, `dispatch_enabled:false` |
| `POST /tasks/{id}/clarifications` (`pm1-c1`, pm_engineering_lead) | `201`, `status:"open"`, `task_status:"clarification_needed"`, `due_at`=created+72h, `reminder_at`=created+24h (verified: due 2026-07-13, reminder 2026-07-11 vs. created 2026-07-10) |
| `GET /tasks/{id}/workroom` (shows clarification) | `200`, 1 message + 1 `clarification_question` message, 1 `clarification_requests` entry |
| `POST /tasks/{id}/clarifications/{id}/answer` (`alice2-c1`, task owner) | `200`, `status:"answered"`, `task_status:"intake_review"`, `dispatch_enabled:false`, `resume_dispatch_enabled:false` |
| RBAC: `bob-c1` (other actor) views `alice2-c1`'s workroom | `403 {"detail":"not_own_task"}` |
| RBAC: Requester (`alice2-c1`) creates a clarification | `403 {"detail":"role_cannot_create_clarification"}` |
| Container health after orchestrator restart | **27/27** `aiagents-test` containers healthy, none unhealthy |
| `production_executed_true_count` after all checks above | **`0`** (unchanged before/after) |

## 6. Statement

No workflow dispatch occurred. No workflow resume occurred. No external action occurred. No
production action occurred. production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
