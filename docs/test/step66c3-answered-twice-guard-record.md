# Step 66C.3 — Answered-Twice Guard Record (G5)

> **Record only. No production action. No external action.**

## 1. Root cause

The 66C.1 `WorkroomStore.answer_clarification` method executed an unconditional
`UPDATE operator_clarification_requests SET status='answered', ... WHERE id=$1` — the WHERE clause
had **no `status='open'` condition**. The API layer's guard (`if clarification["status"] != "open":
raise 409`) read the clarification, then separately wrote to it — a classic read-then-write race.
Two concurrent `POST .../answer` requests on the same open clarification could both pass the read
check before either write landed, and both would then succeed: two answer messages, two
`clarification_answered` audit events, and a `answer_message_id` left pointing at whichever write
happened to run last.

## 2. Fix

`shared/sdk/tasks/workroom_store.py` replaces `answer_clarification` with two methods:

- **`claim_clarification_answer(clarification_id)`** — atomic:
  `UPDATE ... SET status='answered', answered_at=now() ... WHERE id=$1 AND status='open' RETURNING *`.
  Postgres row-level locking means only one concurrent UPDATE can ever match this WHERE clause; the
  loser gets `None` back.
- **`set_answer_message(clarification_id, answer_message_id=...)`** — a second, unconditional update
  that attaches the answer message id once the claim has succeeded.

`apps/orchestrator/src/workroom_api.py::answer_clarification` now:
1. Pre-checks `status == "answered"` → `409 clarification_already_answered` (fast path, no DB
   round-trip needed for the common sequential case).
2. Pre-checks `status not in ("open", "answered")` (e.g. `expired`/`canceled`) →
   `409 invalid_state_for_answer:{status}` (unchanged from 66C.1, preserves the more specific code).
3. Calls `claim_clarification_answer` **before** creating the answer message or emitting the audit
   event. If the claim returns `None` (lost a race that got past step 1/2), the request also fails
   with `409 clarification_already_answered` — **and, critically, no answer message and no
   `clarification_answered` audit event have been created**, unlike the old pre-check-only guard.

## 3. Error code

`409 clarification_already_answered` — a stable code, not interpolated with clarification state, so
the frontend can map it once. (`invalid_state_for_answer:{status}` is preserved for the
`expired`/`canceled` cases, which are a different situation, not addressed by G5.)

## 4. Requirements verified

| Requirement | Verified by |
| --- | --- |
| No second answer message created | `test_second_answer_creates_no_extra_message` |
| No second `clarification_answered` audit event | `test_second_answer_creates_no_clarification_answered_audit_event` |
| Second answer returns 409 | `test_second_answer_returns_409_clarification_already_answered` |
| Store-level atomicity (the actual race-safety mechanism) | `test_claim_clarification_answer_store_level_atomicity` |
| No workflow resume | unchanged — `resume_dispatch_enabled` is always `false`, this endpoint never touches workflow dispatch/resume |
| Readable frontend error | `WorkroomAuditVisibility.test.tsx`: *"shows a readable error if the answer endpoint returns clarification_already_answered"* |

## 5. Frontend

`workroomClient.ts`'s `READABLE_ERRORS` maps `clarification_already_answered` to *"This clarification
has already been answered."*, shown in the existing answer-form error slot (`workroom-answer-error`)
— no new UI element was needed, the existing error-display path already handles it.

## 6. Statement

No workflow dispatch occurred. No workflow resume occurred. No external action occurred. No
production action occurred. production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
