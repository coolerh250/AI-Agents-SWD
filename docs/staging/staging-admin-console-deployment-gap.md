# Staging Admin Console Deployment Gap & Remediation (Step 64E-R findings)

> **Staging only — non-production only. No production action. No production secret. No external write.**

The operator walkthrough (Step 64E) failed because the deployed staging Admin Console does not
surface the demo's per-item evidence. This records the root cause and the remediation required
**before Step 64F / re-review**. No fix is applied here (that needs an image rebuild —
authorization required).

## Symptom (operator-observed)
The deployed console shows aggregate counts + safety posture, but has **no visible pages** for:
work-item identity (`WI-0001`), agent executions, workflows, QA/code output, or audit events.
The operator judged it **not usable**.

## Root cause
- The orchestrator image ships the **committed zero-build static fallback** Admin Console:
  `apps/orchestrator/Dockerfile` → `COPY apps/admin-console/static/ ./admin_console_static/`.
- `apps/orchestrator/src/main.py` serves `admin_console_static/dist` (a built Vite bundle) **if
  present**, else the zero-build fallback `admin_console_static/`. **No dist is built into the
  image**, so the fallback is always served.
- The fallback renders **18 summary tabs** and has no per-item views. The full Vite React app
  (`apps/admin-console/src`, 23 nav items incl. Workspace Execution, Operator Console, Task
  Graph) is **not built into the image**, so the pages that would show agent/workflow/work-item
  detail are absent.

## Deployed vs full-app tabs
- **Deployed (fallback) tabs (18):** Executive Overview, Projects, Delivery Package, Safety
  Center, Regression, Cost/LLM, Incidents, Runtime Baseline, Identity Posture, Secret Posture,
  Security/Supply Chain, Multi-project Delivery, Operational Metrics, Sandbox GitHub Draft PR,
  Release Governance, Backup/Restore/DR, Production Readiness Gate, Controlled Rollout Review.
- **In the React app but NOT deployed:** Task Graph, Design Review, Workspace Execution, Mini
  Delivery Pilot, Operator Console.
- Even deployed pages (Projects, Multi-project Delivery) are **summary-only** — no work-item or
  agent-execution rows.

## Remediation options (require operator authorization to rebuild image)
1. **Build the Vite bundle into the image** — add an admin-console `npm ci && npm run build`
   stage to `apps/orchestrator/Dockerfile` producing `admin_console_static/dist`, so the full
   React app (with Workspace Execution / Operator Console / Task Graph) is served; then
   re-review.
2. **Or extend the zero-build fallback** — add per-item views (work items, agent executions,
   workflows, audit) to `apps/admin-console/static/`; lighter but duplicates UI.
3. Rebuild + redeploy the staging orchestrator image, re-run the demo visibility check, and have
   the operator re-review.

Recommended: **option 1** (build the real React bundle) then operator re-review.

## Remediation applied (Step 64E.1)
Option 1 was implemented: `apps/orchestrator/Dockerfile` now builds the Vite React bundle (stage
`admin-console-build`) and copies it into `admin_console_static/dist`; the orchestrator image was
rebuilt + recreated on `10.0.1.32` and now serves the full React app at `/admin` (assets 200; all
23 routes present). The zero-build fallback remains only as fallback. **This prepares the UI for
operator re-review; it does not by itself re-accept Step 64E.** See
[staging-admin-console-react-bundle-remediation-report.md](staging-admin-console-react-bundle-remediation-report.md)
+ [staging-admin-console-remediation-validation.md](staging-admin-console-remediation-validation.md).

## Status
- **Step 64E: FAILED_OPERATOR_VALIDATION** (until operator re-review of the remediated UI).
- **Step 64F: blocked** until operator re-acceptance (or explicit waiver).
- Remediation applied (image rebuilt locally, no push); no production action;
  `production_executed_true_count=0`. Claude Code does not decide production readiness.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
