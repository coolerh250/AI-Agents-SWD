# Deployment Management Rehearsal — Before/After Evidence (Step 64F.2)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **GET/HEAD read-only evidence around an orchestrator-only restart. No rebuild, teardown, or data change.**

Read-only evidence captured immediately before and after the orchestrator-only restart on
`10.0.1.32`. All probes were GET/HEAD (plus `docker compose ps`).

## Runtime
| Item | Before | After |
|---|---|---|
| staging HEAD | 44f9a40 | 44f9a40 (unchanged) |
| deployed bundle | index-B4s3Ud5S.js | index-B4s3Ud5S.js (unchanged) |
| orchestrator | running (healthy) up 5h | running (healthy) up ~1m |
| services running | 22 running | 22 running |
| `/health` | 200 | 200 |
| `/admin` | 307 (→ `/admin/` 200) | 307 (→ `/admin/` 200) |

## Formal-evidence endpoints (GET)
| Endpoint | Before | After |
|---|---|---|
| `/operations/delivery/projects` | 200, count=1 | 200, count=1 |
| `/operations/delivery/projects/{id}/work-items` | (WI-0001) | 200, WI-0001 |
| `/operations/delivery/work-items/{id}/events` | — | 200, `work_item_created` |
| `/operations/agent-executions` | 200, count=10 | 200, count=10 |
| `/operations/workflows` | 200, count=2 | 200, count=2 (`production_executed=false`) |
| `/operations/qa/runs` | 200, count=2 | 200, count=2 |
| `/operations/code/workspaces` | 200, count=2 | 200, count=2 |
| `/operations/safety` | 200, prod_exec=0 | 200, prod_exec=0 |

## Safety flags (after)
- `production_executed_true_count = 0`
- `github_external_write_enabled = false`
- `discord_external_send_enabled = false`
- `llm_external_call_enabled = false`

## Interpretation
- Orchestrator recovered to healthy; all 22 services remained running.
- Every formal-evidence count is identical before/after → **no data loss**.
- Bundle hash unchanged → the restart did **not** rebuild (as expected).
- Deep-link `/admin/agent-executions` still 404 (accepted non-blocking gap).

## Posture
Orchestrator-only restart rehearsal. No rebuild, no full-stack restart, no teardown, no restore, no
workflow re-run, no production action; `production_executed_true_count` remained 0.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
