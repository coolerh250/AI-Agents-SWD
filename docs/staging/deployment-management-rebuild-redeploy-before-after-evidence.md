# Rebuild/Redeploy Rehearsal — Before/After Evidence (Step 64F.3)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **GET/HEAD read-only evidence around an orchestrator-only rebuild/redeploy. No full-stack rebuild, no down/down -v, no data change.**

Read-only evidence captured before and after the orchestrator-only rebuild/redeploy on `10.0.1.32`.
All probes were GET/HEAD (plus `docker compose ps` and git inspection).

## Runtime
| Item | Before | After |
|---|---|---|
| staging HEAD | 44f9a40 | 9ec9676 (ff-only) |
| deployed bundle | index-B4s3Ud5S.js | index-B4s3Ud5S.js (unchanged) |
| orchestrator | running (healthy) | running (healthy) up ~2m |
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
- The rebuild + redeploy succeeded; orchestrator recovered healthy; all 22 services remained
  running.
- Every formal-evidence count is identical before/after → **no data loss**.
- Bundle hash unchanged because the `44f9a40..9ec9676` diff is docs/scripts/tests only (no `apps/`
  code change) — the rehearsal validates the **procedure**, not a UI change.
- Deep-link `/admin/agent-executions` still 404 (accepted non-blocking gap).

## Posture
Orchestrator-only rebuild/redeploy rehearsal. No full-stack rebuild, no full-stack restart, no down
and no down -v occurred, no teardown, no restore, no rollback, no workflow re-run, no image push, no
production action; `production_executed_true_count` remained 0.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
