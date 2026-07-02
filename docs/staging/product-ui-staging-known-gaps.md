# Product UI Staging Known Gaps (Step 64E.4C)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Known gaps after the staging redeploy. No production action occurred.**

Known gaps observed on `10.0.1.32` after the Step 64E.4C orchestrator-only redeploy.

## Gaps
1. **SPA deep-link 404.** `GET /admin/agent-executions` (and other deep routes) hard-refresh 404s
   because the orchestrator StaticFiles mount has no catch-all; `/admin/` serves 200. **Workaround:**
   navigate via the top-nav tabs. Fix candidate: a catch-all serving `dist/index.html` for
   `/admin/*` (deferred — not a formal-page data gap).
2. **Operator visual re-review pending.** Technical validation confirms endpoints + bundle routes;
   the operator's live visual acceptance is **Step 64E.4D** and has not occurred.

## Resolved / not-a-gap in this snapshot
- QA runs returned **2 rows** (not count-only) — the 64E.4B count-only worst-case did not
  materialise here; the QA / Code page stays count-safe regardless.
- WI-0001, agent executions, workflow trace, QA/code, audit event, and safety posture all
  populated via GET on their formal-page endpoints.

## Boundary
Step 64E remains FAILED_STAGING_REPRESENTATIVENESS (pending operator re-review); Step 64F remains
BLOCKED. The Demo Evidence / Diagnostics page is not an acceptance path. No production action; no
image push; no volume deletion; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
