# Admin Console Demo Evidence UI Remediation Report (Step 64E.3B)

> **Staging only — non-production only. No production action. No production secret. No external write. No image push.**

Overall result: **PASS_WITH_GAPS** (remediation implemented + technically validated; operator
re-review still required). Under operator authorization, the deployed Admin Console now includes a
read-only **Demo Evidence** page that surfaces the Step 64D staging demo evidence. **Step 64E
remains `FAILED_OPERATOR_VALIDATION` and Step 64F remains `BLOCKED`** until the operator re-reviews
and accepts. Claude Code cannot self-accept operator usability.

## Remediation implemented
- **New page:** `apps/admin-console/src/pages/DemoEvidence.tsx` (route `/demo-evidence`, nav entry
  "Demo Evidence" placed second). Read-only; GET-only client.
- **WI-0001 visibility:** the page auto-loads the first delivery project and its work items and
  renders a work-items table (project id/key/name/env/production + `WI-0001` key/id/title/lifecycle/
  production_effect) — no manual selection needed.
- **Agent executions visibility:** new read-only `GET /operations/agent-executions` (shaped:
  agent/status/task_id/started/completed) + a table.
- **Workflow visibility:** new read-only `GET /operations/workflows` (shaped: task_id/stage/
  approval_status/risk_level/production_executed) + a table.
- **QA/code visibility:** frontend getters + tables for the existing `/operations/qa/runs` +
  `/operations/code/workspaces`.
- **Audit/evidence visibility:** consumes `/operations/delivery/work-items/{id}/events` for the
  demo work item + a table (event_type/from→to/actor/role).
- **Safety posture:** shows `production_executed_true_count` from `/operations/safety`.
- **Backend:** two GET-only endpoints added to `apps/orchestrator/src/operations.py`, shaped to
  safe fields (no raw generated code / logs / large blobs). No write path; no other backend change
  (QA/code/delivery/events endpoints already existed).

## Frontend honesty
The page states it is non-production, integrations disabled/mocked, and that governed delivery /
release evidence is pending operator-session authorization (so a delivery package / release
candidate may not be present). It does not claim production-ready/approved/deployed.

## Staging deployment
- Rebuilt `aiagents-staging-orchestrator` on `10.0.1.32` (in-image Vite build) and recreated **only
  the orchestrator** (`up -d orchestrator`), `running (healthy)`. No `down -v`; no volume/DB reset;
  **no image push**. Deployed commit `d72c835`.

## Technical validation (see [admin-console-demo-evidence-ui-validation.md](admin-console-demo-evidence-ui-validation.md))
- `/health` 200; `/admin/` 200 (Vite bundle `index-CoRvi971.js` contains `demo-evidence` route +
  "Demo Evidence" nav + the new endpoint paths).
- `/operations/agent-executions` 200 (**10** executions, all completed);
  `/operations/workflows` 200 (**2**, completed, `production_executed=false`);
  `/operations/qa/runs` 200; `/operations/code/workspaces` 200; `/operations/delivery/projects` 200.
- `/operations/safety` `production_executed_true_count=0`.
- Frontend vitest renders the Demo Evidence sections (WI-0001, agent executions, audit) from mocked
  data.

## Gaps (see [admin-console-demo-evidence-known-gaps-after-remediation.md](admin-console-demo-evidence-known-gaps-after-remediation.md))
- **SPA deep-link 404** persists (navigate via tabs from `/admin/`, don't hard-refresh a sub-route).
- **QA runs rows:** `/operations/qa/runs` reports a count but `validation_runs` may be empty, so the
  QA table can show "No records found" while the count is shown — minor.
- **Browser render** confirmed via vitest + endpoint data, not a staging browser session — operator
  re-review confirms the rendered page.

## Status
- **Step 64E: FAILED_OPERATOR_VALIDATION** (until operator re-review). **Step 64F: BLOCKED.**
- No production action; no production secret; no external write; no image push;
  `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
