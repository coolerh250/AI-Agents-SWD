# Admin Console Demo Evidence Known Gaps After Remediation (Step 64E.3B)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Gaps remaining after the Step 64E.3B Demo Evidence UI remediation. None is a production
readiness sign-off; **Claude Code does not decide production readiness** and cannot self-accept
operator usability.

## 1. SPA deep-link 404 (unchanged)
`/admin/` serves the SPA, but client-side routes 404 on direct/hard-refresh (StaticFiles has no
catch-all). The Demo Evidence page is reachable by clicking the "Demo Evidence" tab from
`/admin/`; hard-refreshing `/admin/demo-evidence` 404s.
- **Fix (future):** add a catch-all route serving `admin_console_static/dist/index.html` for
  unmatched `/admin/*` paths.

## 2. QA runs per-run rows
`/operations/qa/runs` reports a count but its `validation_runs` array may be empty, so the QA
table can show "No records found" while the count is displayed. The QA data model for the demo
differs from `validation_runs`; a future stage could map the demo's QA runs into that list.

## 3. Governed delivery / release still gated
The Demo Evidence page notes that delivery package / release candidate are pending
operator-session authorization; they are not present (governed dispatch requires operator auth,
disabled in staging). Not a defect of this stage.

## 4. Browser render not self-verified
The bundle contains the page and the endpoints return data; the frontend vitest renders the
sections from mocked data. Confirming the live browser render is the **operator re-review**, not a
Claude Code self-check.

## 5. Image not pushed
The rebuilt orchestrator image stays local on `10.0.1.32`; **no registry push**.

## Status
- **Step 64E: FAILED_OPERATOR_VALIDATION** until operator re-review.
- **Step 64F: BLOCKED** until operator re-review passes.
- No production action; no production secret; no external write; no image push;
  `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
