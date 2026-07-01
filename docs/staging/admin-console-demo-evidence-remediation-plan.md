# Admin Console Demo Evidence Remediation Plan (Step 64E.3B, proposed)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Proposed plan only — no remediation implemented in this stage.**

Concrete remediation for a future **Step 64E.3B** to make the five demo-evidence items visible in
the deployed Admin Console, then operator re-review.

## Frontend changes needed
1. **Work items (WI-0001):** in `MultiProjectDelivery`, auto-select the first project on load (or
   default-load its work items) and render a visible work-items table; make Projects rows link to
   `/projects/:id`.
2. **Agent executions:** add an executions list view (new page or section) that renders per-agent
   executions (agent / status / task_id).
3. **Workflows:** add a workflows list view rendering per-workflow rows (id / stage / status).
4. **QA / code:** add getters `getQaRuns()` / `getCodeWorkspaces()` and a QA/Code page (or wire
   the Regression / Workspace pages) to render them.
5. **Audit:** add an audit-events view rendering `/operations/delivery/work-items/{id}/events`.
6. Keep all new views **read-only** (GET-only client) — no write methods.

## Backend API changes needed (if any)
- **QA/code/work-items/events:** endpoints already exist (`/operations/qa/runs`,
  `/operations/code/workspaces`, `/operations/delivery/…/work-items`, `…/events`) — **no backend
  change required**; the UI just needs to call them.
- **Agent executions / workflows per-item:** if a read-only `/operations/*` list is preferred over
  app-level `/workflow` / gateway `/executions`, add GET-only read endpoints (redacted, no write).

## Data mapping needed
- Map the demo's mock-workflow + seeded-work-item records to the new views (agent-execution store,
  workflow store, `project_work_items`, work-item `events`, `qa_runs`, `code_workspaces`).
- Alternatively/additionally, exercise the demo through the delivery-pilot path so the existing
  `latest_pilot` / delivery-package pages also populate.

## Navigation changes needed
- Ensure the new/existing per-item pages are reachable from the top nav and clearly labelled.

## Empty-state changes needed
- Where a page currently shows a pilot-based empty state, add a data-present branch for the
  demo's records so it doesn't read as "nothing here".

## Tests needed
- Frontend: vitest for the new views (renders rows from a mocked response; read-only client
  invariant preserved).
- Backend: if new GET endpoints are added, add read-only API tests.
- A verifier asserting the five items are wired to real endpoints.

## Staging rebuild / redeploy needed
- Rebuild the orchestrator image (Vite build already in the Dockerfile since Step 64E.1) and
  recreate only the orchestrator; no `down -v`, no image push.

## Operator re-review checklist (after 64E.3B)
- WI-0001 visible · agent executions visible · workflow visible · QA/code visible · audit visible ·
  `production_executed_true_count=0` · operator verdict recorded (usable / usable-with-gaps /
  not-usable). Claude Code must not self-accept.

## Status
Plan only; nothing implemented. Step 64E FAILED_OPERATOR_VALIDATION; Step 64F BLOCKED;
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
