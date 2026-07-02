# Admin Console Demo Evidence UI Validation (Step 64E.3B)

> **Staging only — non-production only. No production action. No production secret. No external write. No image push.**

Technical validation of the Step 64E.3B remediation on the staging runtime (`10.0.1.32`,
deployed commit `d72c835`). Read-only GET checks against `http://127.0.0.1:18000`. Operator
acceptance is separate and still required.

## Vite bundle
- `/admin/` serves the Vite bundle `index-CoRvi971.js`; grepping the served bundle shows
  `demo-evidence`, `Demo Evidence`, `agent-executions`, `/operations/workflows`, `code/workspaces`
  — the new page + nav + endpoint calls are deployed.

## UI routes / nav
- Route `/demo-evidence` present; nav entry "Demo Evidence" present (second item).

## Read-only API endpoints (all 200)
| Endpoint | Status | Demo evidence |
|---|---|---|
| `/operations/agent-executions` | 200 | **10** executions, all `completed` (intake→requirement→development→qa→devops ×2) |
| `/operations/workflows` | 200 | **2** workflows, `stage=completed`, `production_executed=false` |
| `/operations/qa/runs` | 200 | count present (`validation_runs` may be empty — see gaps) |
| `/operations/code/workspaces` | 200 | code workspaces present |
| `/operations/delivery/projects` | 200 | SaaS User Management Module (nonprod) |
| `/operations/delivery/projects/{id}/work-items` | 200 | `WI-0001` "Create user CRUD API" |
| `/operations/delivery/work-items/{id}/events` | 200 | `work_item_created` |
| `/operations/safety` | 200 | `production_executed_true_count=0` |

## Frontend test
- `apps/admin-console/src/__tests__/DemoEvidence.test.tsx` renders the Demo Evidence page from
  mocked responses and asserts WI-0001 title, `WI-0001` key, `intake-agent`, `work_item_created`,
  and the Safety Posture section appear.

## Backend test
- `tests/test_operations_demo_evidence_lists.py` asserts the two new endpoints return shaped rows
  and do **not** expose raw fields (`error`/`metadata`/`request`/`state`/`execution_result`).

## Not browser-verified here
Rendering in a real browser is confirmed by operator re-review, not by Claude Code. Endpoint data
+ bundle contents + vitest are the technical evidence.

## Status
Step 64E FAILED_OPERATOR_VALIDATION; Step 64F BLOCKED; `production_executed_true_count=0`; no image
push; no production action.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
