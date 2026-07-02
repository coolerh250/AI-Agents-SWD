# Product UI Known Gaps Before Staging Redeploy (Step 64E.4B)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Test/QA remediation only — no staging redeploy, no image rebuild, no container restart occurred.**

Known gaps after the test/QA formal-product-UI remediation, to be carried into the Step 64E.4C
staging redeploy and the Step 64E.4D operator re-review.

## Gaps
1. **SPA deep-link 404.** Hard-refreshing a deep route (e.g. `/admin/agent-executions`) 404s
   because the orchestrator's StaticFiles mount has no catch-all. **Workaround:** navigate via the
   top-nav tabs. Fix candidate: a catch-all serving `dist/index.html` for `/admin/*` (deferred).
2. **QA runs may be count-only in real staging.** `/operations/qa/runs` returned demo data with
   possibly empty `validation_runs` per-row detail. The QA / Code page shows the **count** and a
   labelled empty state; it does not fabricate rows. To be confirmed against live staging data at
   64E.4C.
3. **Live staging-browser render not yet confirmed.** Rendering is verified via vitest + endpoint
   shapes locally; a real staging browser session is part of 64E.4C/64E.4D, not this stage.
4. **Two project surfaces.** `/projects` (pilot rollup) and `/delivery` (delivery projects / work
   items) coexist; WI-0001 lives on `/delivery`. Nav now labels `/delivery` "Projects / Work Items"
   to disambiguate; further consolidation is optional future work.

## Non-gaps (resolved in 64E.4B)
- WI-0001 now visible on a formal page without a manual click.
- Agent executions, workflow trace, QA/code, and audit events each render on a formal page.
- Safety Center explicitly surfaces `production_executed_true_count=0`.
- Demo Evidence page is diagnostic-only (relabeled + moved last + in-page banner).

## Posture
- **Test/QA remediation only. No staging redeploy occurred. No image rebuild occurred. No container
  restart occurred. No production action occurred.**
- Step 64E remains **FAILED_STAGING_REPRESENTATIVENESS**; Step 64F remains **BLOCKED**.
- Staging redeploy requires **Step 64E.4C** after this test gate passes.
- `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
