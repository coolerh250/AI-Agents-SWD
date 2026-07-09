# Step 66B.1 — Task API Evidence

> **Evidence only. No production action. No external action.**

## 1. Local test evidence (isolated router, in-memory fake store, no DB/Redis)

`pytest tests/test_step66b1_task_api_foundation.py` — **16 passed**. Covers: create success,
auth-disabled 403, missing-actor 401, invalid-role 401, role-cannot-create 403, non-first-class
type → `intake_planning_only=true`, `production_effect=true`+submitted → `blocked` + policy audit,
list scoped-to-own for Requester, list all-visible for Platform Admin, get 404, get
not-own-task 403, submit → `intake_review`, submit `production_effect=true` → `blocked` (never
dispatch), submit invalid-state 409, submit role-denied 403, `dispatch_enabled` always false.

## 2. Example request/response (local TestClient)

**Create (Requester, first-class type):**
```
POST /tasks
X-Task-Actor: alice
X-Task-Role: requester
{"title": "Build the thing", "task_type": "software_delivery"}

201
{"id": "...", "status": "draft", "task_type": "software_delivery",
 "production_effect": false, "requires_approval": false,
 "intake_planning_only": false, "dispatch_enabled": false, ...}
```

**Create with `production_effect=true` + `initial_status=submitted` (Platform Admin):**
```
POST /tasks
X-Task-Actor: admin1
X-Task-Role: platform_admin
{"title": "...", "task_type": "software_delivery", "production_effect": true,
 "initial_status": "submitted"}

201
{"status": "blocked", "requires_approval": true, "dispatch_enabled": false, ...}
-> audit: task_created, then task_rejected_by_policy
```

**Submit (Requester, own draft task):**
```
POST /tasks/{id}/submit
X-Task-Actor: alice
X-Task-Role: requester

200
{"status": "intake_review", "dispatch_enabled": false, ...}
-> audit: task_submitted
```

## 3. Live test-runtime smoke validation (10.0.1.31, `aiagents-test`)

Performed after migration `029_operator_task_api_foundation.sql` was applied and the orchestrator
service was rebuilt/restarted (orchestrator only — see `step66b1-test-deployment-record.md`).

| Check | Result |
| --- | --- |
| `GET /health` | `{"service":"orchestrator","status":"ok"}` |
| `GET /operations/safety` → `production_executed_true_count` | `0` |
| `GET /operations/safety` → `task_api_enabled` / `task_api_write_enabled` | `true` / `true` |
| `GET /operations/safety` → `task_api_test_auth_enabled` | `true` (test compose sets `TASK_API_TEST_AUTH_ENABLED=true`) |
| `GET /operations/safety` → `task_api_workflow_dispatch_enabled` / `..._production_effect_enabled` / `..._external_integration_enabled` | `false` / `false` / `false` |
| `POST /tasks` with test headers → 201, task recorded with `dispatch_enabled:false` | confirmed |
| `GET /tasks` with test headers → 200, lists the created task | confirmed |
| `GET /tasks/{id}` → 200, matches created task | confirmed |
| `POST /tasks/{id}/submit` → 200, `status:"intake_review"`, `dispatch_enabled:false` | confirmed |
| `POST /tasks` without `X-Task-Role` header → 401 | confirmed |
| `production_executed_true_count` after all above | `0` (unchanged) |

Full container health + before/after safety snapshot in `step66b1-test-deployment-record.md`.

## 4. Statement

No Admin Console task UI implemented. No workflow dispatch occurred. No external action occurred.
No production action occurred. production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
