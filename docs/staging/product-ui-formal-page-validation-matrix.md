# Product UI Formal-Page Validation Matrix (Step 64E.4B)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Test/QA remediation only — no staging redeploy, no image rebuild, no container restart occurred.**

Maps each demo-evidence type to the **formal product page** now wired to surface it, the read-only
endpoint it consumes, and the test that covers it. The Demo Evidence page is **diagnostic only** and
is not part of this acceptance matrix.

| Evidence | Formal page (route) | Read-only endpoint | UI behavior | Test |
|---|---|---|---|---|
| WI-0001 | Projects / Work Items (`/delivery`) | `/operations/delivery/projects`, `.../{id}/work-items` | auto-selects first project on load → work items visible (no manual click) | `ProductUiFormalPages.test.tsx` — WI-0001 auto-loads |
| Agent executions | Agent Executions (`/agent-executions`) | `/operations/agent-executions` | lists intake→…→devops executions with status | pipeline renders |
| Workflow | Workflows / Task Graph (`/task-graph`) | `/operations/workflows` | workflow/stage table with `production_executed` | workflow trace renders |
| QA/code | QA / Code (`/qa-code`) | `/operations/qa/runs`, `/operations/code/workspaces` | QA runs + code workspaces (count-safe) | QA/code renders |
| Audit/evidence | Audit / Evidence (`/audit-evidence`) | `/operations/delivery/work-items/{id}/events` | resolves demo work item → renders `work_item_created` | audit events render |
| Safety | Safety Center (`/safety`) | `/operations/safety` | explicit `production_executed_true_count` + integration-disable flags | prod_exec surfaced |

## Notes
- All new/changed client calls are **GET-only**; the read-only guard test invariant is preserved.
- No new backend endpoint was required — every evidence type is served by an existing read-only
  `/operations/*` endpoint.
- The **Demo Evidence** page (`/demo-evidence`) is relabeled **"Diagnostics (Demo Evidence)"**,
  moved last in navigation, and carries an in-page "developer diagnostic — not a staging acceptance
  path" banner.

## Posture
- This is **test/QA remediation only**. **No staging redeploy occurred. No image rebuild occurred.
  No container restart occurred. No production action occurred.**
- Step 64E remains **FAILED_STAGING_REPRESENTATIVENESS**; Step 64F remains **BLOCKED**.
- Staging redeploy requires **Step 64E.4C** after this test gate passes.
- `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
