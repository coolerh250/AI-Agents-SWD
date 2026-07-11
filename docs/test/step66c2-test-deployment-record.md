# Step 66C.2 — Test Deployment Record

> **Deployment record only. No production action. No external action.**

## 1. Migration

**No migration required.** Step 66C.2 is frontend-only — no schema change, no backend behavior
change. `migrations/030_workroom_clarification_foundation.sql` (66C.1) is unchanged.

## 2. Deployment scope

Orchestrator-only rebuild (bundles the new Workroom UI via the existing `node:20-slim` Docker build
stage — `npm ci && npm run build`) + restart on the test host (`aiagents-test`). postgres/redis and
the other services were **not** restarted. No full-stack rebuild, no `docker compose down`, no
unscoped `docker system prune`/`docker volume prune`. No staging or production deployment.

## 3. Baseline (before deployment)

```
git status --short    -> clean (test host)
git log -1 --oneline   -> 45634f3 docs(ai-team-work): record workroom api validation
GET /health            -> {"service":"orchestrator","status":"ok"}
GET /operations/safety -> production_executed_true_count: 0
```

## 4. Deployment commands

```bash
cd <test-host-repo-path>
git pull --ff-only origin main
docker compose -f infra/docker-compose/docker-compose.yml build orchestrator
docker compose -f infra/docker-compose/docker-compose.yml up -d orchestrator
```

## 5. Live validation (after deployment) — actual results, 2026-07-11

| Check | Result (actual) |
| --- | --- |
| `GET /health` | `{"service":"orchestrator","status":"ok"}` |
| Docker build (`admin-console-build` stage) | succeeded, no errors |
| `GET /admin/` serves rebuilt bundle | `200`, `assets/index-DbfaQOce.js` |
| Rebuilt bundle contains the new UI | confirmed — grep on the served JS: `Open Workroom` (1), `workroom` (1), `dispatch_enabled` (1), `resume_dispatch_enabled` (1) all present |
| Create safe task (`alice-c2`, requester) | `201`, `dispatch_enabled:false` |
| `GET /tasks/{id}/workroom` (empty, UI request pattern) | `200`, `dispatch_enabled:false`, `resume_dispatch_enabled:false` |
| `POST /tasks/{id}/workroom/messages` with an XSS-shaped body (`<img src=x onerror=alert(1)> ...`) | `201`, `message_type:"human_message"`, `dispatch_enabled:false` — stored as opaque text by the backend; rendering-safety is enforced client-side (see `step66c2-workroom-ui-security-record.md`) |
| `POST /tasks/{id}/clarifications` (`pm-c2`, pm_engineering_lead, via API — create-clarification UI deferred per known gap) | `201`, `status:"open"`, `task_status:"clarification_needed"` |
| `GET /tasks/{id}/workroom` (shows clarification, UI request pattern) | `200`, `messages:2`, `clarification_requests:1`, `task_status:"clarification_needed"` |
| `POST /tasks/{id}/clarifications/{id}/answer` (`alice-c2`, task owner, UI request pattern) | `200`, `status:"answered"`, `task_status:"intake_review"`, `dispatch_enabled:false`, `resume_dispatch_enabled:false` |
| Container health after orchestrator restart | **27/27** `aiagents-test` containers healthy, none unhealthy |
| `production_executed_true_count` after all checks above | **`0`** (unchanged before/after) |

## 6. Statement

No workflow dispatch occurred. No workflow resume occurred. No external action occurred. No
production action occurred. production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
