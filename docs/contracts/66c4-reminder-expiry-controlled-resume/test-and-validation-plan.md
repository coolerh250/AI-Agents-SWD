# Test and Validation Plan — Step 66C.4-P

> **Planning document only. No test code implemented by this document. This plan is executed by
> future, separately authorized implementation stages (66C.4-BE1/BE2/BE3/FE/E2E/POV).**

## Unit tests

```text
Time calculation: reminder_at = created_at+24h, due_at = created_at+72h computed correctly
  (already covered by existing tests for the current implementation — this stage's tests extend
  coverage to the NEW reminder_sent_at/expired_at fields' interaction with these existing values).
Eligibility: resume_eligible_at set if and only if answered AND task not in a terminal state at
  answer time (controlled-resume-contract.md §1).
State transition: open->answered, open->expired, answered->(eligible)->(requested, Option A)->
  authorized, each tested as an isolated unit.
Idempotency: a second claim attempt against an already-claimed row returns None/no-op for every
  CAS guard in this contract (reminder, expiry, resume-request, resume-authorization).
Late answer: an answer attempt against status='expired' returns the EXISTING
  409 invalid_state_for_answer response with zero new code path (regression test confirming this,
  not a new behavior).
Duplicate reminder: a second reminder-claim attempt against a row with reminder_sent_at already
  set matches zero rows.
Duplicate expiry: a second expiry-claim attempt against a row with status already 'expired'
  matches zero rows.
Duplicate resume: a second resume-request against a row with resume_requested_at already set is
  idempotent (no-op or re-confirmation, per controlled-resume-contract.md §10).
RBAC: can_request_resume / can_view_resume_eligibility return correct booleans for all 6
  TASK_ROLES.
Production-effect blocking: resume authorization always fails for a production_effect=true task
  regardless of eligibility state.
```

## Integration tests

```text
DB locking: two concurrent claim attempts against the same row (simulated via two connections)
  resolve to exactly one winner, verified against a real (test) Postgres instance, not mocked.
Worker concurrency: two clarification-timeout worker instances polling the same table
  simultaneously produce no duplicate transitions (exercises race-condition-and-failure-analysis.md
  scenario 3).
Outbox/stream publishing: the notification event for a claimed reminder/expiry/resume-eligible
  transition is correctly published to the internal event bus (verified against a real Redis
  Streams instance in the test environment, not mocked).
Audit ordering: the audit-evidence endpoint returns the new event types in correct chronological
  order alongside existing clarification_requested/clarification_answered events.
Scheduler restart: killing and restarting the clarification-timeout worker mid-poll-cycle produces
  no duplicate or lost transitions (exercises scenario 14).
Redis failure: a simulated Redis outage during the notification-publish step does not corrupt or
  duplicate the underlying DB state transition (exercises scenario 12).
DB failure: a simulated transient DB outage during a poll cycle results in a clean retry on the
  next cycle with no partial state (exercises scenario 13).
Resume failure and retry: a resume-request against a task whose state changed since eligibility
  correctly returns "not eligible: task_state_changed" (exercises scenario 16).
```

## API tests

```text
401 / 403: unauthenticated and wrong-role requests to the new GET .../lifecycle,
  GET .../resume-eligibility, and POST .../resume-request endpoints are correctly rejected.
404: requests against a nonexistent task_id/clarification_id.
409: answered-twice (existing, regression-tested unchanged), expired-answer-attempt (new),
  resume_already_requested (new, idempotent-not-error framing).
422: malformed request bodies (mostly moot for the near-empty request bodies proposed, but tested
  for completeness).
Idempotency: repeated identical requests to POST .../resume-request produce the same observable
  result (per controlled-resume-contract.md §10).
Answered twice: existing regression test re-run unchanged to confirm this stage introduces no
  regression to Step 66C.3's own guard.
Expired answer: new test confirming the 409 invalid_state_for_answer:{status='expired'} path
  fires correctly once the expiry transition is live.
Cancelled/aborted workflow: a resume-eligibility check against a cancelled task's answered
  clarification correctly returns eligible=false, reason="task_state_changed".
```

## E2E tests (executed in 66C.4-E2E, per implementation-stage-slicing-plan.md)

```text
Clarification created -> real row exists with correct due_at/reminder_at.
24h reminder -> (test-only) a clarification created with an artificially past reminder_at is
  correctly claimed by the next poll cycle, reminder_sent_at set, audit event recorded.
72h expiry/blocked -> similarly, an artificially past due_at row is correctly claimed, status
  transitions to expired, task status transitions to clarification_expired, audit event recorded.
Answer -> existing flow, regression-tested unchanged.
Resume eligibility -> an answered clarification on a still-active task correctly reports eligible.
Controlled resume -> (if Option A) a resume-request from an authorized role against an eligible
  clarification correctly reaches resume_authorized_at, with the resume-eligibility endpoint
  reflecting the updated state.
Workflow continuation -> explicitly OUT OF SCOPE for any test in this plan, since dispatch does
  not exist in any stage this planning covers.
Audit evidence -> the full new-event sequence (reminder_sent, expired OR resume_eligible/
  requested/authorized) is visible via the existing, unmodified audit-evidence endpoint.
Notification event -> the internal event (not external) is correctly published for each new
  transition.
production_executed_true_count = 0 -> confirmed unchanged before/after the entire E2E run, exactly
  matching this project's established safety-verification pattern for every prior stage.
```

## Product Owner validation (observable checklist — NOT executed by this planning stage)

```text
- Waiting state is understandable (the existing "waiting on you" pattern, unchanged).
- Reminder is visible (once 66C.4-FE ships the lifecycle banner).
- Expired/blocked state is understandable (a calm, honest "this decision window has closed"
  presentation, per frontend-ux-boundary.md).
- Answer is accepted exactly once (regression-verified, existing behavior).
- Resume behavior is transparent (no hidden action — if Option A, the operator sees exactly what
  they are requesting and why; if Option B were chosen, this checklist item would instead verify
  the automatic-resume rationale is fully visible after the fact, though Option A is this
  contract's own recommendation).
- No hidden action (matches this project's standing safety posture — restated, not new).
- Recovery path is visible (a rejected/ineligible resume attempt clearly states why).
- Audit evidence is available (via the existing, unmodified audit-evidence endpoint).
```

This checklist is defined here for the FUTURE 66C.4-POV stage to execute against a real
test-runtime deployment — it is not run, simulated, or scored by this planning stage.

## Statement

Planning document only. No test code implemented by this document. This plan is executed by
future, separately authorized implementation stages.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
