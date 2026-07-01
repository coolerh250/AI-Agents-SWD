# Staging Admin Console React Bundle Remediation Report (Step 64E.1)

> **Staging only — non-production only. No production action. No production secret. No external write. No image push.**

Overall result: **PASS_WITH_GAPS** (remediation-prepared). The full React/Vite Admin Console
bundle is now built into the orchestrator image and served at `/admin` on the staging runtime
(`10.0.1.32`), replacing the zero-build static fallback as the primary UI. **Operator re-review
is still required**: Step 64E stays **FAILED_OPERATOR_VALIDATION** and Step 64F stays
**BLOCKED** until the operator re-reviews and accepts. Claude Code cannot self-confirm operator
usability and does not decide production readiness.

## Root cause (confirmed)
- `apps/orchestrator/Dockerfile` copied only `apps/admin-console/static/` (the zero-build
  fallback); the full Vite React bundle was never built into the image.
- `apps/orchestrator/src/main.py` serves `admin_console_static/dist` if present, else the
  fallback. No `dist` existed → the 18-tab summary-only fallback was always served.

## Remediation implemented
- **`apps/orchestrator/Dockerfile`:** added a `node:20-slim` build stage `admin-console-build`
  that runs `npm ci` + `npm run build` (Vite, `base: "/admin/"`, router `basename="/admin"`,
  `outDir: static/dist`), then `COPY --from=admin-console-build … static/dist/ →
  ./admin_console_static/dist/`. The zero-build `static/` index.html remains only as the
  fallback.
- **`.dockerignore`:** excludes `**/node_modules/`, `apps/admin-console/static/dist/`,
  `tsconfig.tsbuildinfo` so the image builds the bundle itself (reproducible; no host
  artifacts).
- **Build strategy:** multi-stage; bundle output `admin_console_static/dist`; orchestrator
  static serve path `admin_console_static/dist` (preferred) with `admin_console_static/`
  fallback.

## Staging rebuild / redeploy
- Rebuilt the `aiagents-staging-orchestrator` image on `10.0.1.32` (in-image `npm ci` + Vite
  build: 79 modules, built in ~0.8s) and recreated **only the orchestrator** container
  (`docker compose up -d orchestrator`), now `running (healthy)`. No `down -v`; no volume
  deletion; no DB reset; **no image push**.

## Validation (see [staging-admin-console-remediation-validation.md](staging-admin-console-remediation-validation.md))
- `/health` 200; `/admin` → `/admin/` 200; `/operations/safety` 200.
- Served `/admin/` HTML now references **`/admin/assets/index-*.js` + `.css`** with
  `<div id="root">` — the **Vite bundle**, not the fallback. The JS asset loads (200).
- The bundle contains the previously-missing routes (`/task-graph`, `/workspace`, `/operator`,
  `/design-review`, `/mini-delivery`, `/controlled-rollout-review`) — the full 23-route app is
  deployed.
- Backend data intact: `project_count_total=1`, `work_item_count_total=1`,
  `production_executed_true_count=0`.

## Gaps (see [staging-admin-console-remediation-known-gaps.md](staging-admin-console-remediation-known-gaps.md))
- **SPA deep-links 404:** `/admin/workspace`, `/admin/metrics` return 404 on direct/hard-refresh
  (StaticFiles has no SPA catch-all). Tab navigation from `/admin/` works client-side. Operators
  must navigate via tabs, not deep-link/refresh.
- **Per-item rendering unverified by Claude Code:** the bundle *contains* the pages, but whether
  each page renders the demo's per-item data (agent executions, work-item detail, audit) in a
  browser is for the operator re-review — not self-confirmed here.
- **Safety `result=warning`** (`mock_vault_provider_in_use`) — expected staging mock-vault
  escape hatch; `production_executed_true_count=0`; no production toggle true. Observed
  `safe→warning` after the fresh orchestrator restart (safety code unchanged; only the Dockerfile
  frontend build changed).

## Status
- **Step 64E: FAILED_OPERATOR_VALIDATION** (unchanged until operator re-review).
- **Step 64F: BLOCKED** (unchanged).
- Operator re-review plan:
  [staging-admin-console-operator-rereview-plan.md](staging-admin-console-operator-rereview-plan.md).
- No production action; no production secret; live integrations disabled/mocked; no external
  write; no image push; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
