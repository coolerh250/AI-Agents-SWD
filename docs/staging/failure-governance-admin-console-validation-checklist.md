# Failure / Governance Admin Console Validation Checklist (Step 65H.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — the operator runs this after 65H.2–65H.4. Formal pages only; `/demo-evidence` is not an acceptance path.**

What the operator verifies on the **formal** Admin Console pages after each 65H execution sub-stage.

## Formal pages + expected evidence
| Page | Scenario group | What the operator should see |
|---|---|---|
| `/task-graph` | approval (A), cancel/abort (B), retry (C) | `approval_status` (pending/approved/rejected), stage `canceled`/`aborted`, and `retry_timeline` for the task |
| `/audit-evidence` | all | audit events: `approval_requested/granted/denied`, `workflow.canceled/aborted`, retry/DLQ/terminal, correlated by task id; chain intact, no tamper |
| `/incidents` | failure/governance | any incident opened/acknowledged/resolved for a controlled failure scenario |
| `/safety` | safety/no-production (D) | `production_executed_true_count=0`; kill switches disabled; `hard_policy_enforced=true`; `production_delegation_allowed=false` |
| `/delivery` | production-block (A6/D1) | production-effect work item routed to `waiting_approval`, not dispatched |
| `/agent-executions` | cancel/abort/retry | executions stop/adjust as expected for the task |
| `/qa-code` | supporting | QA evidence where relevant |
| `/metrics` | supporting | operational metrics reflect the scenarios, no external side effect |

## Known UI gaps (non-blocking)
- **No dedicated `/approvals` page** — approval state is validated on `/task-graph`
  (`approval_status`) + `/audit-evidence`, and via `/operations/approval-decisions/{task_id}` API.
- **No dedicated `/dlq` page** — DLQ/terminal evidence is validated on `/task-graph`
  (`retry_timeline`) + `/audit-evidence`, and via the `/operations/dlq` API.
- `/task-graph` shows a trace only for `workflow_state`-backed workflows (the mock `/workflow/test`
  path) — which is exactly what 65H cancel/abort/retry scenarios use, so the trace is expected.

## Per-scenario expected operator-visible evidence
- **Approval:** the request appears `pending`; after grant → `approved` (+ resume); after reject →
  `rejected`; the decision is in the audit timeline.
- **Cancel/abort:** the workflow shows `canceled`/`aborted` with the reason; ignore-after-abort shows
  the terminal state unchanged (the late attempt is refused).
- **Retry/DLQ:** the retry_timeline shows attempts up to `max_retries=3`; DLQ/terminal counts appear;
  a manual replay (if authorized) shows one controlled replay event.
- **Safety:** `production_executed_true_count=0` throughout; no external write recorded.

## Operator confirmation required
The operator confirms the expected evidence per sub-stage and records
`VISIBLE`/`NOT_VISIBLE`/`PARTIAL_WITH_GAPS`. **Claude Code must not self-accept** this validation.

## This stage's posture
Planning only. No scenario executed; no external write; no LLM call; no Discord send; no production
action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
