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
Expected state: CORRECTED in Step 66C.4-P-R1 to use the transactional-outbox model
  (api-and-event-contract.md §11.3). The lifecycle CAS UPDATE and the outbox INSERT commit in the
  SAME transaction, so a committed transition ALWAYS has a durable 'pending' outbox row. The
  audit/event publish is a downstream relay step; if it fails, the outbox row simply remains
  'pending' and is re-published on the next relay pass. There is NO missing-audit gap and this is
  NO LONGER described as a "non-blocking residual gap" -- the durable outbox row is the guarantee.
Locking/idempotency strategy: outbox UNIQUE(idempotency_key) + each event's deterministic
  idempotency key = at-least-once delivery with idempotent, deduplicated consumption (never
  exactly-once).
Audit expectation: the audit event is eventually published from the durable outbox row, or -- after
  bounded retries -- the row is marked 'dead' and routed to the existing DLQ for explicit operator
  reconciliation (scenario 17). It is never silently lost.
Retry behavior: automatic relay retries (bounded), then DLQ -- reusing the existing
  retry-scheduler/stream.deadletter infrastructure, not new retry logic.
Operator recovery path: only needed for the terminal DLQ case (scenario 17); the transient case
  self-heals via the relay with no operator action.
User-visible result: none directly -- internal consistency is preserved by the outbox; no
  user-facing failure.
```

## 11. Audit succeeds but resume dispatch fails

```text
Expected state: CORRECTED in Step 66C.4-P-R1. Dispatch is built gated/disabled-by-default in
  66C.4-BE3 as a durable outbox resume event. A dispatch-publish failure leaves the resume-event
  outbox row 'pending' (or, after bounded retries, 'dead' -> DLQ), exactly as scenario 10/17. The
  audit trail correctly shows "authorized"; "dispatched" is only recorded once the durable resume
  event is published. Because dispatch_enabled is false by default, in normal operation no dispatch
  is attempted at all, so this failure mode does not arise until dispatch is separately enabled.
Locking/idempotency strategy: outbox UNIQUE(idempotency_key {clarification_id}:resume_dispatched)
  makes re-publication idempotent.
Audit expectation: the resume event is eventually published from the outbox or dead-lettered; never
  silently lost.
Retry behavior: automatic bounded relay retries, then DLQ (scenario 17).
Operator recovery path: replay the 'dead' resume-event outbox row via the existing DLQ tooling.
User-visible result: at most a delayed resume; no data loss. (Moot while dispatch stays disabled.)
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
Expected state: REPHRASED in Step 66C.4-P-R1 to avoid absolute "eliminated / does not exist"
  wording. PostgreSQL database time is the authoritative lifecycle clock: both the deadline
  computation (at creation) and the due-check (at poll/claim time) read PostgreSQL time from the
  SAME Postgres server, so cross-service/cross-machine wall-clock divergence is REDUCED and does not
  affect the trigger path (the scheduler's own wall clock is never compared against a stored
  timestamp; only a PostgreSQL time function appears in the WHERE clause, e.g.
  `WHERE due_at > statement_timestamp()`).
  Time-function correctness (corrected in Step 66C.4-BE1-R1): the answer-claim deadline MUST use
  `statement_timestamp()`, not `now()`/`transaction_timestamp()`. The latter pair return the
  TRANSACTION START time and stay frozen for the whole transaction, so a transaction that began
  before due_at could claim after due_at and would additionally backdate `answered_at` to the
  transaction start. See scenario 18 below.
  This does NOT eliminate every clock concern: a materially misconfigured or drifting DATABASE
  clock and display-timezone rendering remain real considerations
  (lifecycle-and-time-contract.md §7.1, corrected).
Locking/idempotency strategy: n/a -- this is a time-source concern, not a race.
Audit expectation: n/a.
Retry behavior: n/a.
Operator recovery path: n/a for the normal case; a suspected DB-clock anomaly is surfaced by the
  worker-liveness gauge / poll-cycle-duration metrics (observability-and-audit-plan.md), not
  assumed away.
User-visible result: none under normal operation; a DB-clock misconfiguration would be detected via
  monitoring rather than silently trusted.
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

## 17. Outbox backlog / poison event / terminal DLQ (added in Step 66C.4-P-R1)

```text
Expected state: with the transactional-outbox model (api-and-event-contract.md §11.3), a committed
  lifecycle transition always has a durable 'pending' outbox row. If the relay cannot publish it
  (publisher down, Redis down, audit service down), the row stays 'pending' and the backlog is
  drained oldest-first once the dependency recovers. A row that fails BOUNDED retries (a poison
  event) is marked 'dead' and routed to the existing stream.deadletter / retry-scheduler DLQ.
Locking/idempotency strategy: outbox UNIQUE(idempotency_key) + deterministic per-event keys keep
  re-publication idempotent; consumers deduplicate. At-least-once, never exactly-once.
Audit expectation: every transition is eventually published OR explicitly dead-lettered -- never
  silently lost.
Retry behavior: automatic, bounded relay retries for transient failures; terminal DLQ after the
  bound.
Operator recovery path: a 'dead' outbox row (or an audit-reconciliation exception) is an EXPLICIT
  operator item -- an authorized operator replays it via the existing DLQ replay tooling after
  investigation. This is deliberately NOT auto-retried forever.
User-visible result: at most a delayed internal notification for the affected clarification; no
  data loss, no incorrect state.
```

## 18. Transaction opened before the deadline claims after it (added in Step 66C.4-BE1-R1)

```text
Expected state: an answer-claim executed inside an explicit transaction that BEGAN before due_at but
  whose CAS statement executes AFTER due_at MUST be rejected, and answered_at MUST remain NULL.
Root cause if unguarded: PostgreSQL now() IS transaction_timestamp() -- it is fixed at BEGIN and
  frozen for the whole transaction. A predicate `due_at > now()` therefore evaluates against the
  transaction START time. Independently reproduced in Step 66C.4-BE1-R: a transaction opened ~2.95 s
  before due_at executed the CAS ~2.06 s AFTER due_at, claimed the row, and wrote an answered_at
  backdated by ~5.0 s.
Why it matters even though the single-statement autocommit path is safe: the binding atomicity model
  (api-and-event-contract.md §11.3) requires BE2 to wrap this CAS and the outbox INSERT in ONE
  transaction. That wrapping is exactly the shape that activates the defect, and the answer window
  would silently widen by the whole transaction duration.
Locking/idempotency strategy: unchanged -- single CAS predicate, row-level locking.
Binding resolution: the deadline predicate and the answered_at write both use
  `statement_timestamp()` (lifecycle-and-time-contract.md §7.1 / §7.3A.6). statement_timestamp() is
  taken when the CAS STATEMENT starts and is constant within that statement, so wrapping the CAS in
  a transaction cannot extend the answer window and cannot backdate answered_at.
Audit expectation: answered_at is claim-statement time, so it is admissible evidence of WHEN the
  answer was accepted, not of when some enclosing transaction happened to begin.
Retry behavior: none -- rejection is terminal for that attempt (409).
Operator recovery path: none required; the user raises a new clarification if a decision is still
  needed.
User-visible result: 409 invalid_state_for_answer with the expired reason. No silent late success.
```

## 19. Relay exhausts bounded retries during a publisher outage (added in Step 66C.4-BE1-R1)

```text
Expected state: a transient publisher/Redis outage must NOT dead-letter healthy outbox rows. Binding
  §11.3 failure mode 1 requires "no loss"; failure mode 7 requires bounded retries to end in 'dead'.
Root cause if unguarded: with no PERSISTED next-attempt time, a relay polling every few seconds
  re-attempts every pending row on every pass and burns its whole attempts budget within seconds of
  an outage, marking healthy non-poison rows 'dead'. Failure modes 1 and 7 are then mutually
  unsatisfiable. In-memory backoff does not close this: it dies with the worker and is not shared
  between the multiple relay workers the contract permits.
Binding resolution: `available_at` persists the next eligible attempt time. A relay may only claim
  rows with `status='pending' AND available_at <= statement_timestamp()`, and a transient failure
  pushes available_at forward by the backoff policy. Bounded retries are therefore bounded in TIME
  as well as in COUNT, so an outage delays delivery instead of destroying it.
Locking/idempotency strategy: FOR UPDATE SKIP LOCKED within the relay transaction; the row returns
  to pending on worker crash because the claim was never committed. UNIQUE(idempotency_key) keeps
  re-publication idempotent.
Audit expectation: a dead row carries dead_at (when it died) and last_error (a bounded, secret-free
  reason), so an operator reconciliation item is diagnosable rather than opaque.
Retry behavior: automatic, bounded, backed off; then terminal 'dead'.
Operator recovery path: an authorized operator replays a dead row (dead -> pending, available_at
  reset, dead_at/last_error cleared, attempts NOT reset so the full attempt history is preserved).
  No replay endpoint or runtime replay exists in BE1/BE1-R1 -- contract semantics only.
User-visible result: at most a delayed internal notification; no lost lifecycle event.
```

## Recovery semantics (binding — added in Step 66C.4-P-R1)

This section corrects the original draft's blanket "no manual intervention needed / self-heals"
phrasing. The full M1 contract may reuse the existing DLQ/replay capability, but it must NOT assume
every failure is automatically recoverable. Recovery is explicitly split:

```text
Automatic recovery (no operator action):
  - transient DB error on a poll cycle -> retried on the next cycle (scenario 13).
  - transient Redis unavailability -> publication deferred, state already durable (scenario 12).
  - worker process restart -> next poll cycle re-derives from persisted state (scenario 14).
  - outbox backlog after a dependency outage -> relay drains 'pending' rows oldest-first
    (scenario 17).
  - duplicate reminder/expiry/resume claims or duplicate publications -> suppressed by CAS guards
    and idempotency keys (scenarios 1-5, 9).

Operator recovery (explicit human action required):
  - terminal DLQ ('dead' outbox row after bounded retries) -> operator investigates and replays
    (scenario 17).
  - poison event (repeatedly failing publish) -> operator investigation before replay.
  - repeated policy/authorization failure on a resume -> operator investigation; not silently
    retried.
  - inconsistent legacy record (e.g. a pre-migration row in an unexpected combination of states) ->
    operator review; no automatic mutation.
  - audit-reconciliation exception -> operator-reviewed reconciliation, not an automatic backfill.
```

No failure in this contract is assumed to "always self-heal"; each is classified above as either
automatically recovered or explicitly operator-recovered.

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
