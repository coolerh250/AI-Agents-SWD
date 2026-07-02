# Product UI Test/QA Remediation Plan (Step 64E.4B, planned)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — this document defines the future 64E.4B test/QA work; no implementation here.**

Moves the formal product UI remediation **back to the test/QA phase** before any staging
acceptance, per the operator's direction that incomplete formal pages return to test/QA first.

## Step 64E.4B — Product UI Integration Fix in Test
Remediate the formal product pages so each evidence type renders on its formal page (per
[formal-admin-console-page-evidence-map.md](formal-admin-console-page-evidence-map.md)), verified
entirely in test — **no staging acceptance until tests pass**.

### Required frontend changes
- **Projects / Work Items** — render project → work-items → WI-0001 detail without manual
  pre-selection; link work items to their evidence.
- **Agent Executions** — formal list page for the pipeline executions with status + workflow
  correlation.
- **Workflows / Task Graph** — replace the stub with a workflow/stage view showing
  `production_executed=false`.
- **QA / Code** — wire the formal QA and Code/Workspace pages to `/operations/qa/runs` and
  `/operations/code/workspaces`.
- **Audit / Evidence** — formal audit page consuming per-work-item events.
- **Empty states** — meaningful empty state per page, distinct from error.
- All new/changed client calls remain **GET-only** (read-only invariant preserved).

### Required backend / read-only API changes (if needed)
- Reuse existing read-only endpoints where possible (`/operations/delivery/*`,
  `/operations/qa/runs`, `/operations/code/workspaces`, `/operations/agent-executions`,
  `/operations/workflows`, `/operations/delivery/work-items/{id}/events`, `/operations/safety`).
- Only add new **GET-only, shaped** endpoints if a formal page needs data no existing endpoint
  exposes; never expose raw error/metadata/secret fields; no write endpoints.

### Required tests
- **Unit tests** — data-shaping / selectors for each page.
- **Frontend component tests (vitest)** — each formal page renders its evidence from a mocked
  response (WI-0001; 5 pipeline executions; 2 workflows with `production_executed=false`; QA/code
  summaries; `work_item_created` event; safety `production_executed_true_count=0`).
- **API contract tests** — each endpoint returns the expected shape and exposes no raw
  error/metadata/secret fields.

### Test fixture / data strategy
- Deterministic fixtures mirroring the Step 64D demo (project `SaaS User Management Module`,
  `WI-0001`, mock-workflow executions, QA/code rows, `work_item_created` event).
- Mock the fetch layer in component tests; no live network, no external integration, no real
  secrets.
- Fixtures live in the test tree; no production data.

### Acceptance criteria (test/QA gate)
- All unit + component + contract tests pass in CI/local.
- Every evidence type renders on its formal page in a component test.
- Read-only invariant preserved (no write client methods).
- **No staging acceptance until this test gate passes.**

## Sequencing
64E.4B (this, test/QA) → 64E.4C (staging redeploy,
[product-ui-staging-redeploy-plan.md](product-ui-staging-redeploy-plan.md)) →
64E.4D (operator re-review,
[operator-product-ui-rereview-plan.md](operator-product-ui-rereview-plan.md)).

## Status
- Step 64E: **FAILED_STAGING_REPRESENTATIVENESS**. Step 64F: **BLOCKED**.
- Demo Evidence page: **diagnostic only — not staging acceptance**.
- **No production action**; `production_executed_true_count=0`. **No implementation claimed.**

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
