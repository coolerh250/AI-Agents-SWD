# Failure / Governance Abort & Reset Plan (Step 65H.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — recovery is planned, not executed. No reset is run in this stage.**

Global abort conditions and reset expectations for the Step 65H execution sub-stages.

## Global abort conditions (stop immediately if any occurs)
- `production_executed_true_count` changes from 0.
- A production action is attempted.
- Any unexpected external write occurs.
- A secret value appears in any log or output.
- A workflow cannot be safely stopped.
- A **retry storm** begins (retries beyond `max_retries=3` / unbounded).
- A **DLQ replay exceeds the authorized count**.
- An approval state changes **outside** the authorized test case.
- The Admin Console cannot show the required evidence on the formal pages.

## On abort
- Stop the current scenario; do **not** auto-retry.
- Capture the failing state read-only (safety snapshot, workflow state, DLQ counts, the offending
  record).
- Report to the operator and await instructions — do not self-continue.

## Reset expectations (after each sub-stage, or on abort)
- All test flags disabled; **no live external integration enabled** unless a scenario was explicitly
  authorized to use one (default: GitHub/Discord/LLM all NO).
- No production action; no merge/release/tag/deploy; no image push.
- **Retry / DLQ state documented** — record `deadletter_count` / `terminal_count` and any replay
  performed; do not silently drain or delete DLQ entries.
- **Approval state documented** — record the final `approval_status` for any request created; do not
  leave a request in an unintended state.
- Any controlled workflow created via `/workflow/test` is left in its terminal/recorded state
  (canceled/aborted/rejected/completed) — no dangling running workflow.
- `/operations/safety` re-checked read-only: `production_executed_true_count=0`; external flags
  disabled; `hard_policy_enforced=true`.
- Only the minimal affected service recreated **if** a temporary flag was applied — never a
  full-stack restart, never `down` / `down -v` / volume deletion.

## Not executed here
No abort or reset is performed in Step 65H.1 — this document only plans them.

## This stage's posture
Planning only. No scenario executed; no external write; no LLM call; no Discord send; no production
action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
