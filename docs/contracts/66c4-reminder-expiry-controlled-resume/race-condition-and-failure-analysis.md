# Race-Condition and Failure Analysis — Step 66C.4-P

> **Planning document only. No code implemented. Every scenario below is a design analysis for a
> later implementation stage to build correctly against — this document does not run, simulate,
> or trigger any of these scenarios.**

All 16 scenarios use the same underlying guard idiom: a `WHERE <state-column> = <expected-value>`
CAS clause on the UPDATE that performs the transition, identical in shape to the existing,
already-proven `claim_clarification_answer` guard (`shared/sdk/tasks/workroom_store.py`).

## 1. Answer and reminder occur simultaneously

```text
Expected state: the answer-claim (WHERE status='open') and the reminder-claim (WHERE status='open'
  AND reminder_sent_at IS NULL) target DIFFERENT columns for their guard condition but both read
  the same row. Postgres row-level locking serializes the two UPDATEs; whichever commits first
  wins its own column, the second still succeeds on its own guard as long as status remains 'open'
  (the reminder-claim does not care whether an answer happened in the SAME instant, only whether
  status is still 'open' at the moment IT runs).
Locking/idempotency strategy: standard Postgres row lock via UPDATE; no explicit application-level
  lock needed.
Audit expectation: both `clarification_answered` and `clarification_reminder_sent` audit events
  may legitimately both exist for the same clarification if the reminder-claim's SELECT ran before
  the answer committed -- this is an acceptable, non-harmful "reminder for something already
  answered a moment ago" outcome, not a bug requiring prevention (the reminder is stale-but-
  harmless, an accepted product tradeoff for a 60-second poll interval).
Retry behavior: none needed -- both operations are idempotent single-shot CAS claims.
Operator recovery path: none needed -- no incorrect state results.
User-visible result: the user may see a reminder notification for a clarification they answered
  moments earlier; harmless, and bounded by the poll interval (60s recommended).
```

## 2. Answer and expiry occur simultaneously

```text
Expected state: EXACTLY ONE of the two competing CAS claims (WHERE status='open' -> 'answered' vs.
  WHERE status='open' -> 'expired') wins; the other's UPDATE matches zero rows and returns None.
  This is the single most safety-critical race in this entire contract.
Locking/idempotency strategy: identical CAS guard, same column (status), genuinely mutually
  exclusive targets -- Postgres guarantees exactly one of the two UPDATEs commits.
Audit expectation: exactly one of clarification_answered / clarification_expired fires, never
  both, for a given clarification.
Retry behavior: the losing side's caller receives a clear result -- if the answer lost, the
  existing 409 invalid_state_for_answer:{status='expired'} response fires with ZERO new code
  (already handles this exact case); if the expiry-claim lost (rare, since answer requests are
  synchronous/fast and expiry-claims run on a 60s cycle), the scheduler simply logs "already
  answered" and moves on, no retry needed.
Operator recovery path: none needed -- the user who lost the race sees the already-correct 409
  response; no manual intervention required.
User-visible result: a user submitting an answer in the same instant the scheduler expires it may
  occasionally see "this clarification has expired" instead of a successful answer -- an
  acceptable, narrow, and honest outcome, not a data-integrity risk.
```

## 3. Two scheduler workers claim same record

```text
Expected state: only relevant if the clarification-timeout worker is ever scaled to >1 replica
  (not required by this stage's recommended architecture, but the design must tolerate it for
  resilience). The CAS guard (WHERE reminder_sent_at IS NULL / WHERE status='open') makes this
  safe by construction -- exactly one replica's UPDATE matches, the other's matches zero rows.
Locking/idempotency strategy: same CAS guard; no leader election needed (per
  scheduler-architecture-decision.md).
Audit expectation: exactly one reminder_sent / expired audit event per clarification regardless of
  replica count.
Retry behavior: the losing replica simply continues its poll cycle; no error, no retry needed.
Operator recovery path: none needed.
User-visible result: none -- fully transparent.
```

## 4. Duplicate reminder execution

```text
Expected state: prevented entirely by the `reminder_sent_at IS NULL` guard -- a second poll cycle
  (or a second replica) that tries to claim the same row after reminder_sent_at is already set
  simply matches zero rows.
Locking/idempotency strategy: same CAS guard.
Audit expectation: exactly one clarification_reminder_sent event ever, per clarification.
Retry behavior: none needed (idempotent by construction).
Operator recovery path: none needed.
User-visible result: exactly one reminder notification per clarification, matching the canonical
  default in lifecycle-and-time-contract.md.
```

## 5. Duplicate expiry transition

```text
Expected state: prevented by the `status='open'` guard on the expiry-claim UPDATE -- once a row
  transitions to 'expired', no subsequent claim attempt (from any replica or poll cycle) can match
  it again.
Locking/idempotency strategy: same CAS guard.
Audit expectation: exactly one clarification_expired event ever, per clarification.
Retry behavior: none needed.
Operator recovery path: none needed.
User-visible result: none -- fully transparent, matches expectation.
```

## 6. Answer arrives after expiry

```text
Expected state: the answer-claim's own `WHERE status='open'` guard fails to match (status is now
  'expired'), so the existing answer-claim returns None and the existing
  `409 invalid_state_for_answer:{status}` response fires -- ZERO new code needed, this is already
  handled correctly by the current implementation's own guard clause once expiry starts setting
  status='expired'.
Locking/idempotency strategy: reuses the existing CAS guard, unmodified.
Audit expectation: no clarification_answered event; the existing clarification_expired event
  (from scenario 5) is the only record.
Retry behavior: n/a -- the user simply receives the 409 and must be told (frontend, out of this
  stage's implementation scope) that the clarification expired.
Operator recovery path: if a late answer is genuinely needed, the ONLY path is a NEW clarification
  (per lifecycle-and-time-contract.md §7.3 item 6's recommended default) -- no reopen mechanism is
  proposed by this stage.
User-visible result: "this clarification has expired" -- an honest, already-correctly-coded
  response.
```

## 7. Workflow cancelled before answer

```text
Expected state: if `operator_tasks.status` transitions to `canceled` while a clarification is
  still `open`, the clarification itself is NOT automatically canceled by this contract (no
  cascading-cancel logic is proposed, since task cancellation semantics are out of this stage's
  scope) -- but the resume-eligibility check (controlled-resume-contract.md §2.3) will correctly
  refuse eligibility for a canceled task even if the clarification is later answered, preventing
  an orphaned resume attempt against a cancelled workflow.
Locking/idempotency strategy: the eligibility check reads the task's CURRENT status at evaluation
  time, not a cached value -- no additional locking needed since it's a simple read-then-decide,
  re-evaluated at both eligibility time and authorization time (controlled-resume-contract.md §7).
Audit expectation: an answer to a clarification on a cancelled task still records
  clarification_answered (the answer itself is not prevented -- only resume eligibility is
  blocked), which is intentional: the human's answer is a legitimate record even if it can no
  longer affect a cancelled workflow.
Retry behavior: n/a.
Operator recovery path: none needed -- the resume-eligibility check's "task_state_changed" reason
  code (api-and-event-contract.md) surfaces this clearly to any caller.
User-visible result: an operator attempting resume-request against a cancelled task's answered
  clarification receives a clear "not eligible: task state changed" result.
```

## 8. Workflow aborted during answer processing

```text
Expected state: identical reasoning to scenario 7 -- the answer-claim itself is a single atomic
  CAS operation independent of the task's own status column, so an abort happening
  MID-answer-processing cannot corrupt the clarification's own state transition; only the
  DOWNSTREAM resume-eligibility check is affected, exactly as in scenario 7.
Locking/idempotency strategy: same as scenario 7.
Audit expectation: same as scenario 7.
Retry behavior: n/a.
Operator recovery path: same as scenario 7.
User-visible result: same as scenario 7.
```

## 9. Resume request duplicated

```text
Expected state: covered exactly by controlled-resume-contract.md §10 -- the
  `resume_requested_at IS NULL` CAS guard makes a second request either a no-op (if authorization
  already progressed) or a harmless re-confirmation (if still pending).
Locking/idempotency strategy: same CAS guard idiom.
Audit expectation: exactly one clarification_resume_requested event ever, per clarification.
Retry behavior: none needed.
Operator recovery path: none needed -- the response to the duplicate request simply reflects
  current state.
User-visible result: a second click on "request resume" is harmless and shows the same result as
  the first.
```

## 10. Resume succeeds but audit/event publish fails

```text
Expected state: the two-phase pattern (claim first via DB transaction commit, THEN attempt the
  audit/event side effect) means the CLAIM itself is already durable and correct even if the
  side-effect publish fails afterward -- exactly the same pattern the existing answer-claim
  already uses (claim commits, then message/audit creation follows).
Locking/idempotency strategy: n/a for this scenario -- it's a failure-after-success case, not a
  race.
Audit expectation: the state transition (e.g. resume_authorized_at set) is correct in the
  database even if the corresponding audit event failed to publish; a reconciliation job or
  manual review (out of this stage's scope to build, noted as a residual gap in
  observability-and-audit-plan.md) would be needed to detect and backfill a missing audit event.
Retry behavior: the event publish itself can be retried using the existing
  retry-scheduler/DLQ infrastructure (per scheduler-architecture-decision.md's dead-letter
  behavior) -- reusing existing infra rather than inventing new retry logic.
Operator recovery path: platform_admin/agent_operator can inspect the raw row state directly (via
  existing DB-level tooling, not a new UI) if an audit gap is suspected; no new tooling proposed
  by this stage.
User-visible result: none directly -- this is an internal consistency concern, not a user-facing
  failure.
```

## 11. Audit succeeds but resume dispatch fails

```text
Expected state: out of this stage's implementation scope entirely (dispatch is not built by any
  stage this planning covers) -- noted here only so the eventual dispatch-building stage inherits
  awareness of this failure mode. The audit trail already correctly shows "authorized" even if a
  later dispatch attempt fails; the not-yet-designed dispatch step must itself decide its own
  retry/DLQ posture at that future stage.
Locking/idempotency strategy: n/a for this stage (dispatch does not exist yet).
Audit expectation: n/a for this stage.
Retry behavior: n/a for this stage.
Operator recovery path: n/a for this stage.
User-visible result: n/a for this stage.
```

## 12. Redis unavailable

```text
Expected state: under the recommended Option 2 architecture (DB polling), Redis unavailability
  affects ONLY the notification-event publish step (the poll/claim logic itself is pure Postgres,
  no Redis dependency for the trigger). A claimed-but-unpublished transition is durable in
  Postgres regardless of Redis state.
Locking/idempotency strategy: n/a -- this is an infra-availability concern, not a race.
Audit expectation: the DB-level state transition (e.g. reminder_sent_at set) is correct even if
  the Redis-published notification event is delayed until Redis recovers.
Retry behavior: standard Redis Streams reconnect/retry semantics, already relied upon by every
  existing service in this project (audit-worker, notification-worker, retry-scheduler) -- no new
  behavior needed.
Operator recovery path: none needed -- self-heals when Redis recovers, matching every other
  service's existing resilience posture.
User-visible result: a delayed internal notification, bounded by however long Redis is down; no
  data loss.
```

## 13. Database temporarily unavailable

```text
Expected state: the clarification-timeout worker's poll cycle simply fails that cycle and retries
  on the next scheduled interval (60s later) -- no special handling needed since every state
  change this contract proposes is idempotent and DB-durable; there is no in-memory state that
  could be lost.
Locking/idempotency strategy: n/a.
Audit expectation: no partial/incorrect state possible -- either the whole poll-cycle transaction
  commits or it doesn't; Postgres transactional guarantees apply.
Retry behavior: the next poll cycle after DB recovery re-evaluates every still-relevant row from
  scratch.
Operator recovery path: none needed -- self-heals.
User-visible result: a delayed reminder/expiry transition, bounded by the DB outage duration plus
  one more poll interval; no incorrect data.
```

## 14. Worker restarts during transition

```text
Expected state: because the CAS claim and its immediate side effects happen within (or
  immediately following) a single DB transaction commit, a worker restart can only ever interrupt
  BEFORE a claim commits (in which case nothing happened, the next poll cycle retries cleanly) or
  AFTER it commits but before the audit/event side effect (covered by scenario 10) -- there is no
  possible "half-claimed" row state.
Locking/idempotency strategy: same CAS guard; restart-safety is a direct consequence of using
  DB-transaction-committed state as the sole source of truth (per
  scheduler-architecture-decision.md's "restart recovery: trivial" comparison-table entry).
Audit expectation: at most one missing-but-recoverable audit event per restart (scenario 10's
  concern), never a duplicate or corrupted state transition.
Retry behavior: automatic on next poll cycle.
Operator recovery path: none needed for the state transition itself; only the residual audit-gap
  concern from scenario 10 might warrant future reconciliation tooling.
User-visible result: none, beyond the same delayed-notification effect as scenarios 12/13.
```

## 15. Clock skew

```text
Expected state: NOT a meaningful risk under the recommended architecture, because both the
  deadline computation (at clarification creation) and the due-check (at poll time) read `now()`
  from the SAME Postgres server -- there is no cross-machine clock comparison in this design at
  all (the scheduler process's own wall clock is never compared against a stored timestamp; only
  Postgres's own `now()` is used in the WHERE clause, e.g. `WHERE due_at <= now()`).
Locking/idempotency strategy: n/a -- eliminated by design, not mitigated.
Audit expectation: n/a.
Retry behavior: n/a.
Operator recovery path: n/a.
User-visible result: none -- this failure mode does not exist under this design.
```

## 16. Existing task/workflow state changed between eligibility and resume

```text
Expected state: this is exactly why controlled-resume-contract.md §7 mandates re-checking the
  task-state invariant at AUTHORIZATION time, not only at the moment eligibility was first granted
  -- covered in full detail there; restated here for completeness of this scenario catalogue. The
  authorization-time recheck is what prevents a stale-eligibility resume from proceeding against a
  task that has since moved to a terminal state.
Locking/idempotency strategy: a fresh read of operator_tasks.status at authorization time, not a
  cached value from eligibility time.
Audit expectation: if the recheck fails, the authorization attempt is recorded as
  NOT authorized with reason "task_state_changed" (per api-and-event-contract.md's resume-
  eligibility response shape) -- no silent failure.
Retry behavior: n/a -- this is a permanent block for that clarification's resume path, not a
  transient failure to retry.
Operator recovery path: none within the resume path itself -- if the task's new state is
  legitimate (e.g. it was correctly cancelled for an unrelated reason), no resume should occur;
  this is working as intended, not a gap.
User-visible result: a clear "not eligible: task state changed" result if resume is attempted
  after the task's state changed underneath the answered clarification.
```

## Statement

Planning document only. No code implemented. Every scenario above is a design analysis for a later
implementation stage to build correctly against — this document does not run, simulate, or
trigger any of these scenarios.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
