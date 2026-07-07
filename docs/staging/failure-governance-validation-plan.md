# Failure / Recovery / Governance Validation Plan (Step 65H.1)

> **Staging only — non-production only. No production action. No production secret. No production data.**
> **Planning / readiness only — no failure scenario, approval action, cancel/abort, retry/DLQ replay, workflow execution, external write, or runtime change occurred in this stage.**

Grounded plan for Step 65H (Failure / Recovery / Governance Validation), from a read-only inspection
of the real staging services, routes, and mechanisms on `10.0.1.32` (HEAD `27198d7`, 21 services
healthy, `/operations/safety` clean).

## Baseline confirmed (read-only)
- `/operations/safety`: `production_executed_true_count=0`, `hard_policy_enforced=true`,
  `production_delegation_allowed=false`, `github_external_write_enabled=false`,
  `discord_external_send_enabled=false`, `llm_real_enabled=false`,
  `admin_console_operator_actions_enabled=false`.

## Mechanisms mapped (real routes/streams)
### Approval / governance
- **approval-engine** (`:18002`): `POST /approval/request` → creates a `pending` request;
  `POST /approval/approve` / `POST /approval/reject`; `GET /approval/{request_id}`.
- **orchestrator resume**: a background consumer on `stream.approvals` resumes approved workflows
  (`ResumeEngine`); `POST /workflow/resume/{task_id}`.
- **policy-engine**: sets `approval_required` for restricted/production-shaped actions
  (`POST /workflow/policy-test`).
- **reads**: `/operations/approval-policies`, `/operations/approval-policies/{task_id}`,
  `/operations/approval-decisions/{task_id}`.
- Workflow approval fields: `approval_required`, `approval_status` (`none|pending|approved|rejected`).
- **Open item:** the `approval expired / timeout` path is not confirmed by a specific route; it is
  tracked as an unknown to confirm read-only at 65H.2 start (or simulate via an aged/pending request).

### Cancel / abort / ignore-after-abort
- `POST /workflow/cancel/{task_id}` → `canceled`; `POST /workflow/abort/{task_id}` → `aborted`
  (`_terminate_workflow`). Always sets `execution_result.production_executed=false`.
- **Ignore-after-abort:** `_terminate_workflow` returns **HTTP 409** if the workflow is already in a
  `TERMINAL_STAGES` = `{completed, canceled, aborted, rejected}` — a late cancel/abort is refused.
- **Note:** these operate on a `workflow_state`, which is created by the mock `/workflow/test`
  orchestration path (a stream-mode fresh intake creates no `workflow_state` — the 65G.2 finding).
  65H cancel/abort/retry scenarios therefore use `/workflow/test` to create a controlled, non-external
  workflow_state to act on.

### Retry / DLQ / replay / terminal failure
- `DEFAULT_MAX_RETRIES = 3`; an event is dead-lettered when `retry_count >= max_retries`.
- Streams: `stream.deadletter` and `stream.deadletter.terminal`.
- **retry-scheduler** (`:18008`-class): `GET /deadletter` (list), `POST /deadletter/replay/{message_id}`
  (replay).
- **reads**: `/operations/dlq` → `deadletter_length`, `deadletter_terminal_length`,
  `deadletter_events`, `terminal_events`, counts.

### Safety / no-production (kill switches)
- `hard_policy_enforced=true`; `production_delegation_allowed=false`; production-effect work items
  route to `waiting_approval` (they cannot be dispatched directly).
- Kill switches = the external-enable flags (`SANDBOX_GITHUB_LIVE`, `RUN_REAL_DISCORD_TEST`,
  `ENABLE_REAL_LLM_NETWORK_CALL`/`LLM_PROVIDER`, operator-action flags) — all disabled at rest.
- `/operations/safety` surfaces `production_executed_true_count` (must stay 0).

## Admin Console evidence (formal pages)
- `/task-graph` — approval_status + retry_timeline via the workflow progress/timeline APIs.
- `/audit-evidence` — approval/cancel/abort/DLQ audit events.
- `/incidents` — incident governance (ack/resolve/close/postmortem).
- `/safety` — kill switches + `production_executed_true_count`.
- `/delivery`, `/agent-executions`, `/qa-code`, `/metrics` — supporting evidence.
- **Known UI gap:** there is **no dedicated `/approvals` or `/dlq` page**; approval + DLQ evidence
  surfaces on `/task-graph` + `/audit-evidence` (+ `/operations/dlq` API). Documented, non-blocking.
- Diagnostics / `/demo-evidence` is **not** an acceptance path.

## Execution split
65H is planned as controlled sub-stages (see
[failure-governance-execution-split.md](failure-governance-execution-split.md)): **65H.2** approval &
governance, **65H.3** cancel / abort / ignore-after-abort, **65H.4** retry / DLQ / manual replay,
**65H.5** operator evidence review. None are executed in 65H.1.

## Default external-integration policy for 65H
- **GitHub write: NO · Discord send: NO · LLM call: NO** by default. Any scenario needing an external
  rail must justify it and obtain separate authorization (see
  [failure-governance-authorization-matrix.md](failure-governance-authorization-matrix.md)).

## This stage's posture
Planning / readiness only. No scenario executed; no workflow execution; no approval action; no
cancel/abort; no retry/DLQ replay; no GitHub write; no Discord send; no LLM call; no runtime change;
no production action. `production_executed_true_count=0`.

## Companion documents
- [failure-governance-scenario-matrix.md](failure-governance-scenario-matrix.md) ·
  [failure-governance-authorization-matrix.md](failure-governance-authorization-matrix.md) ·
  [failure-governance-admin-console-validation-checklist.md](failure-governance-admin-console-validation-checklist.md) ·
  [failure-governance-abort-reset-plan.md](failure-governance-abort-reset-plan.md) ·
  [failure-governance-risk-register.md](failure-governance-risk-register.md) ·
  [failure-governance-execution-split.md](failure-governance-execution-split.md) ·
  [failure-governance-operator-authorization-templates.md](failure-governance-operator-authorization-templates.md)

---
_Staging only — non-production only. No production action. No production secret. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
