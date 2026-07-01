# Staging Admin Console Remediation Validation (Step 64E.1)

> **Staging only — non-production only. No production action. No production secret. No external write. No image push.**

Validation evidence for the Step 64E.1 remediation on the staging runtime (`10.0.1.32`). All
checks are read-only against `http://127.0.0.1:18000`. UI evidence is from the **deployed
console assets/routes**, not backend-API-only.

## Runtime
- Orchestrator recreated on the rebuilt image; `running (healthy)`; all 22 services healthy.

## Endpoints
| Check | Result |
|---|---|
| `/health` | 200 |
| `/admin` → `/admin/` | 200 |
| `/operations/safety` | 200 |

## Deployed UI is the Vite bundle (not the fallback)
- Served `/admin/` HTML contains:
  - `<script type="module" crossorigin src="/admin/assets/index-BlzdM7zQ.js">`
  - `<link rel="stylesheet" crossorigin href="/admin/assets/index-CM9mrCR0.css">`
  - `<div id="root">` (React mount)
- The JS asset `/admin/assets/index-BlzdM7zQ.js` loads → **200**.
- The old zero-build fallback rendered pages via inline JS in a single `index.html`; the served
  HTML now delegates to the hashed Vite assets — confirming the React bundle is served.

## Full route set present in the bundle
Grepping the served JS bundle shows the previously-missing routes are now present:
`/task-graph`, `/workspace`, `/operator`, `/design-review`, `/mini-delivery`,
`/controlled-rollout-review` (plus the 18 already in the fallback) — the full 23-route app.

## Backend data intact
- `/operations/metrics/overview`: `project_count_total=1`, `work_item_count_total=1`,
  `production_executed_true_count=0`.

## Known limitations (validated)
- **SPA deep-link 404:** `/admin/workspace` → 404, `/admin/metrics` → 404 (direct/hard-refresh).
  `/admin/` → 200. Client-side tab navigation works; hard-refresh/deep-link does not (StaticFiles
  has no SPA catch-all).
- **Per-item render:** confirming each page renders the demo's per-item data requires a browser
  (JS execution) — deferred to operator re-review.
- **Safety `result=warning`** driven by `warnings=['mock_vault_provider_in_use']`; other lists
  (`missing_required_secrets`, `backup_gaps`, `runtime_non_production_limitations`) are known
  non-production staging limitations; `production_executed_true_count=0`; no production toggle
  true.

## Not done
No SPA catch-all fix; no image push; no production action; no external write;
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
