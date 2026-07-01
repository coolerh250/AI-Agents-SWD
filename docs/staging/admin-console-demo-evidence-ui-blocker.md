# Admin Console Demo Evidence UI Blocker (Step 64E.2)

> **Staging only — non-production only. No production action. No production secret. No external write.**

The current blocker for operator acceptance of the staging Admin Console.

## Statement
- The full **React/Vite bundle is now deployed** (Step 64E.1): `/admin` serves the real SPA, all
  23 routes present, assets load.
- **But the deployed UI still does not surface the operator-required demo evidence** — work-item
  identity (WI-0001), agent executions, workflow, QA/code output, audit/evidence.
- **The blocker is no longer only bundle deployment.** It is the **Admin Console demo-evidence
  UI / API integration**: the pages exist but do not present the per-item demo data to the
  operator.
- **Backend data may exist** (verified via `/operations/*` APIs in Step 64D), but **operator
  usability requires UI-visible evidence** — the pages must fetch and render the per-item data
  the operator needs to see.

## Why deploying the bundle wasn't enough
The React pages that would show this data (e.g. Workspace Execution, Operator Console, Task
Graph, Multi-project Delivery) are now deployed, but in the operator's re-review they did not
display the demo's work item / agent executions / workflow / QA / audit. Possible reasons (to be
diagnosed in the next remediation): the pages call different endpoints than those the demo
populated, expect a different data shape, need a project/work-item selection the demo didn't set,
or the summary pages don't drill into per-item records. This requires UI/API-integration work,
not just a rebuild.

## Diagnosis complete (Step 64E.3A)
Read-only diagnosis identified the concrete UI/API mismatch per item — see
[admin-console-demo-evidence-ui-api-diagnosis.md](admin-console-demo-evidence-ui-api-diagnosis.md),
[admin-console-demo-evidence-endpoint-map.md](admin-console-demo-evidence-endpoint-map.md),
[admin-console-demo-evidence-frontend-route-map.md](admin-console-demo-evidence-frontend-route-map.md),
[admin-console-demo-evidence-ui-api-mismatch-report.md](admin-console-demo-evidence-ui-api-mismatch-report.md).
**Primary cause:** the pages read a delivery-pilot + aggregate-metrics model; the demo populated
the mock-workflow + seeded-work-item path. QA/code endpoints are entirely unwired; work items are
gated behind manual selection; agent-execution/workflow/audit have only aggregate or stub views.

## Next remediation
**Admin Console Demo Evidence UI Remediation (Step 64E.3B)** — wire the deployed pages to the
per-item endpoints per
[admin-console-demo-evidence-remediation-plan.md](admin-console-demo-evidence-remediation-plan.md),
then operator re-review. A future stage requiring its own authorization; **not** performed here.

## Status
- Step 64E: **FAILED_OPERATOR_VALIDATION**. Step 64F: **BLOCKED**.
- No production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
