# E2E Staging Workflow — Known Gaps (Step 65G.2)

> **Staging only — non-production only. No production action. No production data.**
> **Documentation only. No secret value appears here.**

## Gaps
1. **[non-blocking] `/intake/mock/project-work-item` broken in staging (missing PyYAML).** The
   communication-gateway image lacks PyYAML (`ModuleNotFoundError: No module named 'yaml'` via
   `shared.sdk.work_items.dispatcher`), so that convenience endpoint returns HTTP 500. Not caused by
   this run; **no image rebuild performed** (out of scope + forbidden). Worked around by creating the
   formal project + work item through the orchestrator's operator-authenticated multi-project API
   (which has PyYAML). A future maintenance pass should add PyYAML to the communication-gateway
   image (or make the import lazy) so the convenience intake path works.
2. **[non-blocking] Stream-mode fresh intake creates no `workflow_state`.** The `/task-graph`
   surface is populated only by the mock `/workflow/test` path; a stream-mode intake records
   agent_executions + audit instead. Pipeline evidence for this run is on `/agent-executions`. No
   `workflow_state` was fabricated. A future enhancement could thread a workflow registration into
   the stream pipeline so `/task-graph` shows a trace for real intakes.
3. **[non-blocking] Sandbox rail naming differs from the spec suggestion.** The rail uses its
   validated Step-59 scheme (`sandbox/ai-agents/…` branch, `[Sandbox][Draft]` title) rather than the
   spec's aspirational `staging/agents-sandbox/*` + `[STAGING-SANDBOX]`. Safety scope is identical
   (sandbox repo only, draft only, no merge). Documented, not changed.
4. **[pending] Operator UI validation.** The technical execution succeeded and API evidence is
   captured, but the operator has not yet visually confirmed the evidence on the formal Admin
   Console pages. Tracked in
   [e2e-staging-operator-validation-request.md](e2e-staging-operator-validation-request.md).

## Non-gaps (done)
- Exactly one fresh intake; the 5-hop pipeline completed; one controlled LLM call ($0.05073 ≤ $1);
  one sandbox draft PR (#16, no merge); one `[STAGING]` Discord send; 0 direct diagnostic calls; all
  flags reset; `production_executed_true_count=0`; no secrets; no production/customer data.

## Blocking gaps
- **None.** No gap blocks the technical E2E result; the only open item is the pending operator UI
  validation (expected, by design).

## Status
Step 65G.2: **PASS_WITH_OPERATOR_VALIDATION_PENDING**. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=controlled-e2e github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
