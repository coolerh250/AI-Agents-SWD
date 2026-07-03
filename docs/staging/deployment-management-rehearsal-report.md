# Deployment Management Rehearsal Report (Step 64F.2)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Orchestrator-only restart rehearsal — no rebuild, no full-stack restart, no teardown, no restore, no data change.**

Records the first controlled, low-risk operations rehearsal of the Step 64F.1 SOP: an
**orchestrator-only restart** of the `aiagents-staging` runtime on `10.0.1.32`, followed by the
validation-plan run.

## Overall result
- Overall result: **PASS_WITH_GAPS** — the orchestrator-only restart completed, the Admin Console
  recovered, all formal-evidence endpoints returned the same data as before, and
  `production_executed_true_count` stayed **0**. One carry-over non-blocking gap: SPA deep-link
  hard-refresh 404 (navigate via tabs).

## Rehearsal action
- **Action executed:** orchestrator-only restart.
- **Exact command:**
  `docker compose -p aiagents-staging -f infra/docker-compose/docker-compose.staging.yml --env-file infra/runtime/.env.staging.local restart orchestrator`
- **Services affected:** `orchestrator` only (recreated container process; container
  `aiagents-staging-orchestrator-1`).
- **Services not affected:** the other 21 services (postgres, redis, agents, gateways,
  observability, …) stayed up.
- **Rebuild:** none. **Full-stack restart:** none. **Rollback:** none. **Teardown/restore:** none.
  **Workflow re-run:** none. **Down / down -v:** none. **Image push:** none.

## Baseline
- **Source HEAD:** `0eecd0b` (= origin/main). **Staging HEAD:** `44f9a40` (unchanged — no sync, no
  rebuild). Staging tree clean.
- **Deployed bundle:** `/admin/assets/index-B4s3Ud5S.js` (unchanged before/after — restart does not
  rebuild).

## Before / after (see before-after-evidence doc)
| Check | Before | After |
|---|---|---|
| orchestrator | running (healthy) up 5h | running (healthy) up ~1m |
| services running | 22/22 | 22/22 |
| `/health` | 200 | 200 |
| `/admin` | 307 → `/admin/` 200 | 307 → `/admin/` 200 |
| `/operations/safety` prod_exec | 0 | 0 |

## Formal evidence (after restart)
- Projects / Work Items: `/operations/delivery/projects` 200 (1 project); work-items 200 →
  **WI-0001**; events → `work_item_created`.
- Agent Executions: `/operations/agent-executions` 200, count=10.
- Workflows: `/operations/workflows` 200, count=2 (`production_executed=false`).
- QA / Code: `/operations/qa/runs` 200 count=2; `/operations/code/workspaces` 200 count=2.
- Safety Center: `/operations/safety` 200, `production_executed_true_count=0`; github/discord/llm
  external all false.
- **No data loss** — every count matches the pre-restart capture.

## Known gaps
- SPA deep-link hard-refresh 404 (e.g. `/admin/agent-executions`) — unchanged accepted non-blocking
  gap; navigate via tabs. See
  [deployment-management-rehearsal-known-gaps.md](deployment-management-rehearsal-known-gaps.md).

## Posture
This was an **orchestrator-only restart rehearsal**. No rebuild occurred. No full-stack restart
occurred. No down and no down -v occurred. No rollback occurred. No teardown occurred. No restore
occurred. No workflow re-run occurred. No production action occurred.
`production_executed_true_count` remained 0. This is
staging deployment management, not production readiness. Claude Code does not decide production
readiness.

## Status
- Step 64E: **PASS**. Step 64F: **REHEARSAL_COMPLETED**.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
