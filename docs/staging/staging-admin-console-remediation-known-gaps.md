# Staging Admin Console Remediation Known Gaps (Step 64E.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Known gaps remaining after the Step 64E.1 remediation (full React bundle deployed). None is a
production readiness sign-off; **Claude Code does not decide production readiness** and cannot
self-confirm operator usability.

## 1. SPA deep-link 404 (StaticFiles has no catch-all)
`/admin/` returns 200, but client-side routes 404 on direct/hard-refresh:
`/admin/workspace` → 404, `/admin/metrics` → 404. React Router handles tab navigation
client-side (no HTTP request), so navigating **from** `/admin/` works; hard-refresh, bookmarking,
or pasting a deep link does not.
- **Fix (future, needs authorization):** add a SPA fallback in the orchestrator that serves
  `admin_console_static/dist/index.html` for unmatched `/admin/*` paths (catch-all route), so
  deep-links/refresh resolve.

## 2. Per-item rendering not self-verified
The deployed bundle **contains** the pages/routes that should show work-item identity, agent
executions, workflows, QA/code, and audit — but confirming each renders the demo data requires a
browser. That confirmation is the **operator re-review**
([staging-admin-console-operator-rereview-plan.md](staging-admin-console-operator-rereview-plan.md)),
not a Claude Code self-check.

## 3. Safety result = warning (mock-vault)
`/operations/safety` `result` is `warning`, driven by `warnings=['mock_vault_provider_in_use']`
(the staging Vault dev/mock escape hatch). Other lists (`missing_required_secrets`,
`backup_gaps`, `runtime_non_production_limitations`) are known non-production staging
limitations. `production_executed_true_count=0`; no production toggle is true. The `safe→warning`
change was observed after the fresh orchestrator restart; the safety-computation code is
unchanged (only the Dockerfile frontend build changed).

## 4. Image not pushed
The rebuilt orchestrator image stays local on `10.0.1.32` — **no registry push** (per
authorization). It is not available elsewhere.

## Status
- **Step 64E: FAILED_OPERATOR_VALIDATION** until operator re-review.
- **Step 64F: BLOCKED** until operator re-review passes.
- No production action; no production secret; no external write; no image push;
  `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
