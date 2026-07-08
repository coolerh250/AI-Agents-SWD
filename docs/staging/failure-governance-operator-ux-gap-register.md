# Failure & Governance — Operator UX Gap Register (Step 65H.5)

> **Staging only — non-production only. No production action. No production data.**
> **Documentation only. Operator-facing UX gaps found during Step 65H validation.**

Operator-facing UX gaps surfaced during the Step 65H failure/governance validation, for the operator's
Step 65I acceptance decision and pre-production backlog.

## UX-1 — No DLQ / Retry Admin Console page (operator-flagged, 65H.4)
- **What's missing:** a first-line Admin Console page for the dead-letter queue and retry state.
- **What exists today:** backend read-only APIs (`:18000/operations/dlq`, retry-scheduler
  `:18015/deadletter`, `POST :18015/deadletter/replay/{id}`); and **indirect** UI surfacing —
  Incidents (sev2 terminal-failure incidents), Task Graph (`failed` workflows), Audit-Evidence
  (`workflow_failed` events).
- **Operator impact:** an operator cannot, from the UI, see queue depth, per-entry failure reason
  (`task_id` / `original_stream` / `failure_reason` / `retry_count`), the retrying-vs-terminal split,
  or trigger a controlled manual replay.
- **Recommendation:** add a **DLQ / Retry** Admin Console page that reads the existing APIs and
  exposes queue depth, terminal vs in-flight, per-entry detail, and a governed manual-replay control.
- **Class:** OPERATOR_UX_GAP + POST-STAGING_BACKLOG (recommended before production operations).
- **Raised by:** operator, during 65H.4 UI validation ("Visible with gap").

## UX-2 — No dedicated `/approvals` Admin Console page (65H.1/65H.2)
- **What's missing:** a dedicated approvals view.
- **What exists today:** approval state on `/task-graph` (`approval_status`) + `/audit-evidence`
  (+ `/operations/approval-decisions/{task_id}` API).
- **Operator impact:** low — approval evidence is visible, just not on a purpose-built page.
- **Recommendation:** optional approvals page (nice-to-have).
- **Class:** OPERATOR_UX_GAP (non-blocking).

## Not UX gaps (recorded elsewhere)
- Approval expiry/timeout (governance mechanism gap → gap-classification), raw late-stream-event
  injection (safety-test gap → gap-classification), cancel-during in-flight events (async
  characteristic → gap-classification).

## This stage's posture
Documentation only. No new scenario executed; no external action; no production action.
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
