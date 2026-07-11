# Step 66C.3 — Test Deployment Record

> **Deployment record only. No production action. No external action.**

## 1. Migration

**No migration required.** Step 66C.3 adds no new table and no new column — the audit-evidence
endpoint reads the existing `audit_logs` table (Stage 19), and G1/G5 are query/logic changes only.
`migrations/030_workroom_clarification_foundation.sql` (66C.1) is unchanged.

## 2. Deployment scope

Orchestrator-only rebuild (`npm ci && npm run build` for the frontend bundle, plus the changed
Python source) + restart on the test host (`aiagents-test`). postgres/redis and the other services
were **not** restarted. No full-stack rebuild, no `docker compose down`, no unscoped `docker system
prune`/`docker volume prune`. No staging or production deployment.

## 3. Baseline (before deployment) — actual, 2026-07-11

```
git status --short    -> clean except pre-existing untracked source/dr-reports/*.json and
                          source/regression-reports/ (unrelated scheduled-job artifacts, not touched)
git log -1 --oneline   -> 1dc164e docs(ai-team-work): record workroom remediation validation
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
| `git pull --ff-only origin main` | fast-forward, `1dc164e..5cfe600`, 30 files changed |
| Docker build (`admin-console-build` stage) | succeeded, no errors |
| `GET /health` | `{"service":"orchestrator","status":"ok"}` |
| `GET /admin/` serves rebuilt bundle | `200`, `assets/index-4xVzIrBt.js` (same hash as the local `npm run build`) |
| Rebuilt bundle contains the new G1/G3 UI strings | confirmed — grep on the served JS: `Audit Evidence` (1), `may be hidden based on your role` (1), `audit-evidence` (1) all present |
| Create safe task (`alice-c3`, requester) | `201`, `dispatch_enabled:false` |
| Post normal message (requester) | `201` |
| Create clarification (`pm-c3`, pm_engineering_lead) | `201`, `status:"open"` |
| **G1** — `GET /tasks/{id}/workroom` as requester | `visibilities seen: ['task_participants']` only — no `operators`/`audit_only`/`private_system` leaked |
| Answer clarification (requester, first attempt) | `200`, `status:"answered"`, `task_status:"intake_review"`, `dispatch_enabled:false`, `resume_dispatch_enabled:false` |
| **G5** — answer the same clarification again | `409`, `detail:"clarification_already_answered"` — no second answer message, no second `clarification_answered` audit event (see next row) |
| **G3** — `GET /tasks/{id}/audit-evidence` as platform_admin | `200`, 4 events (`task_created`, `task_message_created`, `clarification_requested`, `clarification_answered` — exactly one of each, confirming the blocked second answer created no extra event); every event has only safe fields (`body_length`/`body_hash`, no raw text) |
| Raw message/answer text (`"Normal participant message"`, `"Use the test environment."`) searched in the audit-evidence response | **0 occurrences** |
| **G3** — `GET /tasks/{id}/audit-evidence` as requester | `403`, `detail:"role_cannot_view_audit_evidence"` |
| **G3** — `GET /tasks/{id}/audit-evidence` as reviewer_approver | `403`, `detail:"role_cannot_view_audit_evidence"` |
| **G3** — `GET /tasks/{id}/audit-evidence` as security_compliance_reviewer | `200` (allowed) |
| Same role (security_compliance_reviewer) attempts `POST .../workroom/messages` | `403`, `detail:"role_cannot_post_message"` — confirms read-only |
| Container health after orchestrator restart | **27 containers**, 26 report `healthy` (the 27th, `vault`, has no configured healthcheck — same as every prior stage), none `unhealthy` |
| `production_executed_true_count` after all checks above | **`0`** (unchanged before/after) |

## 6. Statement

No workflow dispatch occurred. No workflow resume occurred. No external action occurred. No
production action occurred. production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
