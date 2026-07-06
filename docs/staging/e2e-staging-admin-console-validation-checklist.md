# E2E Staging Admin Console Validation Checklist (Step 65G.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — the operator runs this checklist after Step 65G.2.**

What the operator must verify on the **formal** Admin Console pages after the Step 65G.2 run.
Diagnostics / `/demo-evidence` is **not** an acceptance path.

## Per-page checklist
### `/delivery` — Projects / Work Items
- **Object:** the new project + work item created by the fresh intake.
- **Status:** work item present, `production_effect=false`.
- **Look for:** the fresh correlation id / work-item id + creation timestamp.
- **Proves:** a fresh intake (not seeded) entered the platform.
- **Failure:** no new project/work item, or a production-scoped object.

### `/agent-executions` — Agent Executions
- **Object:** agent_execution rows for intake → requirement → development → qa → devops.
- **Status:** each hop recorded (ok).
- **Look for:** the shared task id across all five hops + timestamps.
- **Proves:** the real distributed agent pipeline ran for the fresh task.
- **Failure:** missing hops, or no rows for the fresh task id.

### `/task-graph` — Workflows / Task Graph
- **Object:** the workflow trace / task graph for the task.
- **Status:** stages progressed; trace id present.
- **Look for:** the task id + workflow/trace id.
- **Proves:** workflow orchestration is visible. *(Tracked gap: confirm the stream-mode fresh intake
  yields a `workflow_state` here — first read-only check of 65G.2.)*
- **Failure:** no trace for the task id after the tracked-gap follow-up.

### `/qa-code` — QA / Code
- **Object:** QA / code evidence for the task.
- **Status:** QA checks recorded.
- **Look for:** the task id + QA evidence rows.
- **Proves:** the QA stage produced evidence.
- **Failure:** no QA evidence for the task.

### `/cost-llm` — LLM Cost / Governance
- **Object:** the controlled LLM interaction + usage + budget events (65F rail).
- **Status:** one bounded call; `plan_only=true`; cost ≤ $1; `exceeded=false`.
- **Look for:** the interaction/usage ids + the task id + actual cost.
- **Proves:** the LLM call went through the platform budget/audit rail (not a direct call).
- **Failure:** no interaction record, or cost over cap, or an untracked call.

### `/sandbox-github` — Sandbox GitHub
- **Object:** the controlled sandbox draft-PR request + evidence (65D rail).
- **Status:** `created`; `draft=true`; `merge_enabled=false`; sandbox repo only.
- **Look for:** the draft-PR number/url + the task correlation id.
- **Proves:** the GitHub write went through the controlled sandbox rail.
- **Failure:** non-sandbox target, a merge, or no draft-PR record.

### `/audit-evidence` — Audit / Evidence
- **Object:** audit_log + integrity records for the task and each controlled step.
- **Status:** audit chain intact; no tamper.
- **Look for:** audit events correlated to the task id.
- **Proves:** the E2E flow is fully audited.
- **Failure:** missing audit events or an integrity break.

### `/safety` — Safety Center
- **Object:** the safety snapshot.
- **Status:** `production_executed_true_count=0`; live integrations disabled at rest after the run.
- **Look for:** the production-executed counter + integration flags.
- **Proves:** the run took no production action and reset to safe.
- **Failure:** the counter changed, or a live flag left enabled.

### `/metrics` — Operational Metrics (if relevant)
- **Object:** operational metrics snapshot (no external side effect).
- **Proves:** metrics reflect the run without triggering any external action.

## Operator confirmation required
- The operator must confirm the fresh workflow + all correlated controlled artifacts are visible on
  the formal pages above. **Claude Code must not self-accept** this operator validation.

## This stage's posture
Planning only. No workflow execution, no GitHub write, no Discord send, no LLM call, no production
action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
