# Deployment Management Rebuild/Redeploy Rehearsal Report (Step 64F.3)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Orchestrator-only rebuild/redeploy rehearsal — no full-stack rebuild, no full-stack restart, no down/down -v, no teardown, no restore, no rollback, no data change.**

Records the controlled, low-risk rehearsal of the Step 64F.1 SOP **rebuild/redeploy** procedure: a
git ff-only sync followed by an **orchestrator-only** `build` + `up -d` on the `aiagents-staging`
runtime on `10.0.1.32`, then the validation-plan run.

## Overall result
- Overall result: **PASS_WITH_GAPS** — the orchestrator-only build + redeploy completed, the
  orchestrator recovered healthy, the Admin Console is reachable, all formal-evidence endpoints
  returned the same data as before, and `production_executed_true_count` stayed **0**. One
  carry-over non-blocking gap: SPA deep-link hard-refresh 404 (navigate via tabs).

## Rehearsal action
- **Repo sync:** `git fetch` + `git checkout main` + `git pull --ff-only origin main` →
  **44f9a40 → 9ec9676** (fast-forward; no hard reset; no git clean; no evidence/volume deletion).
- **Exact build command:**
  `docker compose -p aiagents-staging -f infra/docker-compose/docker-compose.staging.yml --env-file infra/runtime/.env.staging.local build orchestrator`
- **Exact up command:**
  `docker compose -p aiagents-staging -f infra/docker-compose/docker-compose.staging.yml --env-file infra/runtime/.env.staging.local up -d orchestrator`
- **Services rebuilt:** `orchestrator` only. **Services recreated:** `orchestrator` only
  (postgres/redis only health-waited).
- **Services not affected:** the other 21 services stayed up (22/22 running throughout).
- **Full-stack rebuild:** none. **Full-stack restart:** none. **Down / down -v:** none.
  **Teardown/restore:** none. **Rollback:** none. **Workflow re-run:** none. **Image push:** none.

## Baseline
- **Source HEAD:** `9ec9676` (= origin/main). **Staging HEAD before:** `44f9a40` → **after:**
  `9ec9676`. The `44f9a40..9ec9676` diff is **docs/scripts/tests only** (no `apps/` code change), so
  the rebuilt bundle is expected to be identical.

## Before / after
| Check | Before | After |
|---|---|---|
| staging HEAD | 44f9a40 | 9ec9676 |
| deployed bundle | index-B4s3Ud5S.js | index-B4s3Ud5S.js (unchanged — docs-only diff) |
| orchestrator | running (healthy) | running (healthy), up ~2m |
| services running | 22/22 | 22/22 |
| `/health` | 200 | 200 |
| `/admin` | 307 → `/admin/` 200 | 307 → `/admin/` 200 |
| `/operations/safety` prod_exec | 0 | 0 |

## Formal evidence (after redeploy)
- Projects / Work Items: `/operations/delivery/projects` 200 (1 project); work-items 200 →
  **WI-0001**; events → `work_item_created`.
- Agent Executions: `/operations/agent-executions` 200, count=10.
- Workflows: `/operations/workflows` 200, count=2 (`production_executed=false`).
- QA / Code: `/operations/qa/runs` 200 count=2; `/operations/code/workspaces` 200 count=2.
- Safety Center: `/operations/safety` 200, `production_executed_true_count=0`; github/discord/llm
  external all false.
- **No data loss** — every count matches the pre-rebuild capture.

## Known gaps
- SPA deep-link hard-refresh 404 (`/admin/agent-executions`) — unchanged accepted non-blocking gap;
  navigate via tabs. See
  [deployment-management-rebuild-redeploy-known-gaps.md](deployment-management-rebuild-redeploy-known-gaps.md).

## Rehearsal acceptance boundary
This reports only that the **orchestrator rebuild/redeploy rehearsal completed**. It does **not**
mean production ready, production approved, production deploy validated, external integrations
validated, or full DR validated.

## Posture
This was an orchestrator-only rebuild/redeploy rehearsal. No full-stack rebuild occurred. No
full-stack restart occurred. No down and no down -v occurred. No teardown occurred. No restore
occurred. No rollback occurred. No workflow re-run occurred. No image push occurred. No production
action occurred. `production_executed_true_count` remained 0. This is staging deployment
management, not production readiness. Claude Code does not decide production readiness.

## Status
- Step 64E: **PASS**. Step 64F: **REBUILD_REDEPLOY_REHEARSAL_COMPLETED**.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
