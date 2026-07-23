# Lifecycle and Time Contract — Step 66C.4-P

> **Planning document only. No backend/frontend runtime change. No API implementation change. No
> database schema change. No migration created. No workflow change. No scheduler activated. No
> dispatch/resume executed. No deployment.**

## 7.1 Time source

```text
Authoritative clock: the Postgres server clock, read by a PostgreSQL time function at write time
  (already the pattern for `due_at`/`reminder_at` computation and for `answered_at`/`updated_at`).
  The scheduler process must NOT compute deadlines from its own local clock -- it only compares a
  PostgreSQL time reading against already-stored TIMESTAMPTZ values, and any write it performs uses
  a PostgreSQL time function, keeping a single source of truth for "current time."
Time-function selection (BINDING, corrected in Step 66C.4-BE1-R1):
  PostgreSQL `now()` and `transaction_timestamp()` are the SAME function: both return the time the
  CURRENT TRANSACTION started, and both stay frozen for every later statement in that transaction.
  They MUST NOT be used for a deadline decision that is required to reflect the execution time of
  the answer-claim statement: a transaction that BEGAN before the deadline would evaluate the
  predicate against its own start time and could claim after the deadline had already passed.
  The authoritative statement-time function for the answer claim is `statement_timestamp()`:
    - it reflects the time the current SQL statement started executing;
    - it does NOT freeze because the surrounding transaction began before the deadline;
    - it is CONSTANT within one SQL statement, so a single CAS statement compares the deadline and
      stamps `answered_at` from one identical reading;
    - it is preferable to `clock_timestamp()` here because `clock_timestamp()` advances on every
      call and would let the deadline predicate and the `answered_at` write inside the SAME CAS
      statement observe two different times.
  Non-claim scheduler scans (`reminder_at <= ...`, `due_at <= ...`) select rows for MATERIALIZATION
  only and do not decide answer eligibility; they may read PostgreSQL time by any of these
  functions. Only the answer-claim deadline decision is binding on `statement_timestamp()`.
Storage: UTC, TIMESTAMPTZ throughout (already the existing convention for every relevant column --
  no change needed).
Display timezone: the Admin Console's responsibility (existing convention: raw TIMESTAMPTZ values
  are returned by the API; frontend renders them in the viewer's local timezone). No backend
  change needed for this.
created_at / requested_at semantics: `operator_clarification_requests.created_at` is already the
  "requested_at" for a clarification (no separate column needed).
reminder_due_at semantics: the existing `reminder_at` column already IS this value
  (computed at insert as `created_at + 24h`) -- no new column, see data-model-contract.md.
expires_at semantics: the existing `due_at` column already IS this value
  (computed at insert as `created_at + 72h`) -- no new column.
Clock-semantics statement (canonical wording, corrected in Step 66C.4-P-R1 -- absolute
  skew-free phrasing is NOT used):
  "PostgreSQL database time is the authoritative lifecycle clock. This reduces cross-service clock
   divergence, but does not eliminate delayed polling, transaction-time semantics, database
   configuration risk, or display-timezone concerns."
  Concretely:
  - TIMESTAMPTZ storage: every relevant column is TIMESTAMPTZ (existing convention, unchanged).
  - UTC normalization: values are stored/compared in UTC; no naive local-time is introduced.
  - Transaction timestamp choice (corrected in Step 66C.4-BE1-R1): the answer-claim deadline
    comparison and its `answered_at` write both use `statement_timestamp()`, so they share one
    Postgres clock reading taken when the claim STATEMENT began, and that reading is not frozen at
    the start of a surrounding transaction. `now()`/`transaction_timestamp()` do NOT provide
    claim-execution time and are not used for this decision. There is no cross-machine wall-clock
    comparison in the trigger path.
  - Delayed scheduler tolerance: up to several minutes of delay between a timestamp becoming due and
    the reminder/expiry transition materializing is acceptable for this hour-granularity human-facing
    use case; this delays only materialization/notification, never the enforceability of the
    authoritative deadline (§7.3A).
  - Backlog processing: after an outage the poller re-derives correctness from persisted timestamps
    every cycle and works through the backlog; no in-flight state is lost (see
    scheduler-architecture-decision.md restart-recovery).
  - Display timezone responsibility: the Admin Console renders raw TIMESTAMPTZ values in the
    viewer's local timezone (existing convention); backend does not localize.
  - Monitoring for DB-clock anomalies: a materially misconfigured or drifting database clock is a
    residual risk that is monitored (the "last successful poll cycle" liveness gauge and
    poll-cycle-duration metrics in observability-and-audit-plan.md surface anomalous behavior),
    not assumed away.
```

## 7.2 Reminder behavior

```text
1. 24-hour start point: `operator_clarification_requests.created_at` (the clarification's own
   creation time) -- already the basis for the existing `reminder_at` computation.
2. reminder_due_at computation: already computed and stored at creation time as
   `reminder_at = created_at + 24h` (existing column, existing app-layer logic in
   `shared/sdk/tasks/workroom_store.py` / `workroom_models.py`'s `CLARIFICATION_REMINDER_HOURS`
   constant). No new computation needed -- the scheduler only needs to find rows where
   `reminder_at <= now()` and the reminder has not yet been sent.
3. Default reminder count per clarification: **recommend exactly one** (see Canonical default
   recommendation below).
4. Scheduler delayed execution: a late-firing reminder still fires exactly once when the scheduler
   catches up -- no special handling needed beyond the claim query's own idempotency (see below).
5. Must NOT remind if: already answered (`status != 'open'`), already canceled
   (`status = 'canceled'`), or already expired (`status = 'expired'`) -- the claim query's
   `WHERE status = 'open'` clause already enforces this by construction.
6. Reminder event idempotency key: `clarification.reminder_due:{clarification_id}` (deterministic,
   derivable from the clarification id alone, since exactly one reminder is sent per clarification
   -- see api-and-event-contract.md).
7. Reminder audit event: `clarification_reminder_sent` (new audit event type, following the
   existing `clarification_requested`/`clarification_answered` naming convention in
   `shared/sdk/tasks/audit_events.py`).
8. Internal notification event payload: minimal -- `task_id`, `clarification_id`, `assigned_to`
   (or `requested_by_id` if unassigned), `reminder_at`, `due_at` -- reusing the existing
   notification-worker's event-consumption pattern (see api-and-event-contract.md).
9. External channel: OFF by default, per the standing project rule (no external notification
   send without explicit, scoped Product Owner authorization, matching the Discord notify-first
   pattern) -- this stage proposes only an INTERNAL event; any external send is out of scope here.
```

### Canonical default recommendation

```text
One reminder per clarification, at +24 hours (matches the existing `reminder_at` column exactly,
  and matches the already-operator-decided Q2 timeout from Stage 66A.3). No deviation proposed --
  this default is adopted directly, not re-litigated. Marking a reminder as "already sent" requires
  one new boolean/timestamp field (see data-model-contract.md); this is a technical necessity to
  make the claim idempotent, not a product-behavior change requiring PO sign-off.
```

### 7.2A Reminder semantics under scheduler lag (binding — added in Step 66C.4-P-R1)

This section is a **binding contract**. It uses `reminder_at` as the authoritative reminder time
in exactly the same way §7.3A uses `due_at` as the authoritative deadline.

```text
1. Authoritative reminder time: operator_clarification_requests.reminder_at (the existing 24h
   column) IS the authoritative "reminder due" time. Once authoritative DB time reaches reminder_at,
   the reminder is DUE.
2. Poller lag affects only WHEN the reminder is actually published, never the due time: a poller
   running minutes late still treats reminder_at as the due time and produces exactly the same
   single reminder when it catches up.
3. reminder_sent_at records only that the reminder STATE TRANSITION was durably recorded (the
   reminder-claim CAS committed and the outbox row was enqueued) -- it is the at-most-once
   state-transition marker, not a proof of downstream delivery.
4. No reminder is produced once the clarification is already answered or expired: the reminder-claim
   guard `WHERE status='open' AND reminder_sent_at IS NULL` excludes answered/expired/canceled rows
   by construction.
5. Duplicate poll cycles (or duplicate worker replicas) produce no duplicate reminder: the same CAS
   guard makes the second claim match zero rows.
6. Deterministic idempotency key: `{clarification_id}:reminder` (derivable from the clarification id
   alone), so any consumer can suppress a duplicate delivery idempotently.

Delivery semantics (binding wording):
  - Event/notification DELIVERY is AT-LEAST-ONCE with IDEMPOTENT processing (the deterministic
    idempotency key above lets consumers deduplicate).
  - The reminder STATE TRANSITION (reminder_sent_at set) is AT-MOST-ONCE via the CAS guard.
  - This contract does NOT claim exactly-once delivery. Exactly-once is not provided by Redis
    Streams or by the outbox relay; the correct guarantee is at-least-once delivery + idempotent
    consumption, which yields the observable behavior "each clarification is reminded once" without
    depending on an exactly-once transport that does not exist here.
```

## 7.3 Expiry / blocked behavior

```text
1. 72-hour start point: `operator_clarification_requests.created_at` (same base as reminder) --
   already the basis for the existing `due_at` computation.
2. expires_at computation: already computed and stored at creation time as
   `due_at = created_at + 72h` (existing column, existing `CLARIFICATION_DUE_HOURS` constant). No
   new computation needed -- the scheduler only needs to find rows where `due_at <= now()` and
   `status = 'open'`.
3. Clarification status change: `operator_clarification_requests.status` transitions
   `'open' -> 'expired'` via the same CAS pattern as the existing answer-claim
   (`WHERE status = 'open'` guard).
4. Task/workflow status change: `operator_tasks.status` transitions to `clarification_expired`
   (the enum value already exists, per current-state-assessment.md -- no new task-status value
   required, confirmed).
5. New task status required: **NO** -- `clarification_expired` already exists in both backend and
   frontend enums. This directly confirms the Master Plan's own prior statement
   (canonical-milestone-manifest.md: "no new task-status value needed").
6. Late answer (an answer attempt after `due_at` has passed): this is a genuine PO decision -- see
   product-owner-decision-checklist.md item 1. Recommended default: **NOT allowed** once
   authoritative DB time has reached `due_at`, **regardless of whether the scheduler has yet
   materialized `status='expired'`**. See §7.3A below for the binding authoritative-deadline
   contract -- the corrected design does NOT rely on the scheduler winning a race to close the
   answer window; the deadline predicate `due_at > statement_timestamp()` in the answer-claim itself closes
   it, so scheduler lag can never extend the window (correcting the original draft, which allowed a
   "narrow window" answer to succeed until the scheduler ran).
7. Late-answer UI/API response: an answer rejected by the deadline predicate (or because the row
   already transitioned to `expired`) returns the existing `409 invalid_state_for_answer:{status}`
   error path; when the row is still `open` but past `due_at`, the answer-claim's added deadline
   predicate causes the same 409 (`workroom_api.py`'s handler surfaces the expiry reason). This is a
   contract addition to the existing answer-claim query (the added
   `AND due_at > statement_timestamp()` predicate),
   to be implemented in 66C.4-BE1/BE3 -- no code changed by this planning stage.
8. Blocked vs. expired distinction: this stage's own required behaviors use "expired" as the
   clarification-level terminal state and `clarification_expired` as the task-level status: there
   is no separate "blocked" transition introduced by 66C.4 itself -- the existing `blocked`
   task-status value remains reserved for its current, unrelated meaning (operational failure,
   per the Master Plan's canonical-milestone-manifest.md M1 definition) and is NOT reused for
   clarification timeout. This is a deliberate, low-risk choice (reuses an already-modeled,
   already-named status rather than overloading `blocked`), stated here for PO awareness rather
   than as an open decision (no ambiguity or safety impact either way).
9. Expiry audit event: `clarification_expired` (new audit event type, following the existing
   naming convention).
10. Notification/action item event: `clarification.expired` internal event (see
    api-and-event-contract.md) -- this is exactly the kind of item the Master Plan's M4 Action
    Center is designed to eventually aggregate ("overdue/expiring" tile), though M4 itself is out
    of scope for this stage.
```

### Canonical default recommendation

```text
No new task-status value; reuse `clarification_expired` exactly as already modeled. This is
  adopted directly, not re-litigated, since it is confirmed both by direct schema/enum inspection
  (current-state-assessment.md) and by the Master Plan's own prior statement.
```

## 7.3A Authoritative expiry semantics (binding — added in Step 66C.4-P-R1)

This section is a **binding contract**, not a recommendation. It resolves the original draft's gap
where a late answer could succeed in the window between `due_at` passing and the scheduler
materializing `status='expired'`.

```text
1. Authoritative deadline: operator_clarification_requests.due_at (the existing 72h column) IS the
   authoritative expiry deadline. It is an EXCLUSIVE upper bound: the answer window is [created_at,
   due_at). (The name "expires_at" is used interchangeably in prose; there is no separate
   expires_at column -- due_at is that value, per data-model-contract.md.)
2. Authoritative clock: PostgreSQL database time read by `statement_timestamp()` inside the claim
   statement is the authoritative lifecycle clock for this decision. No process's local wall clock
   decides whether the deadline has passed, and no transaction-start time does either -- see the
   time-function selection rule in §7.1 (corrected in Step 66C.4-BE1-R1).
3. When authoritative DB time >= due_at:
   a. The answer endpoint must NOT accept a normal answer, even if status is still 'open'.
   b. This holds even when the scheduler has not yet run to set status='expired' -- the deadline,
      not the scheduler, closes the window.
   c. The answer/expiry race is decided by a SINGLE CAS predicate on the answer-claim (see below),
      not by which of the answer-claim and the scheduler commits first.
   d. Scheduler lag never extends the answer window: lag only delays the visible materialization of
      status='expired' and the expiry audit/event, not the enforceability of the deadline.
   e. The scheduler's job is to MATERIALIZE the expired status, write the audit event, and enqueue
      the notification event -- not to decide whether the deadline has been reached.

Binding answer-claim CAS predicate (contract only; SQL shown for precision, no implementation
performed by this stage):

    UPDATE operator_clarification_requests
       SET status = 'answered', answered_at = statement_timestamp(), ...
     WHERE id = :clarification_id
       AND status = 'open'
       AND answered_at IS NULL
       AND due_at > statement_timestamp()   -- authoritative deadline, exclusive upper bound
    RETURNING *;

  A zero-row result means the answer lost to either a prior answer, a prior/materialized expiry, or
  the deadline itself -- all of which correctly reject the late answer.

4. Answer submitted exactly at due_at (statement_timestamp() == due_at): REJECTED, because due_at is
   an EXCLUSIVE upper bound (`due_at > statement_timestamp()` is false at equality). Recommended,
   for determinism.
5. Delayed poller: because the answer-claim enforces the deadline itself, a poller that runs
   minutes late changes only WHEN status flips to 'expired' and WHEN the audit/notification event
   is produced -- never whether a late answer could have slipped through.
6. Transaction timestamp semantics (BINDING, corrected in Step 66C.4-BE1-R1): `statement_timestamp()`
   is evaluated when the claim STATEMENT begins executing, so the deadline comparison holds even when
   the claim runs inside an explicit transaction that BEGAN before due_at. `now()` /
   `transaction_timestamp()` return transaction-start time and MUST NOT be used here: a transaction
   opened before due_at would otherwise be able to claim after due_at, and `answered_at` would be
   backdated to the transaction start. Both the answer-claim and the expiry-claim read the same
   Postgres clock, so there is no cross-service comparison (see §7.1 time-function selection).
   This rule is what makes the CAS remain correct once BE2 wraps it, per the binding §11.3 atomicity
   model, in one transaction together with the outbox INSERT.
7. Late-answer API status/error code: 409 invalid_state_for_answer (with an "expired"/"past due"
   reason), the existing error path -- extended only by the added `due_at > statement_timestamp()`
   predicate.
8. User-facing result: a user answering at or after the deadline sees "this clarification has
   expired / the decision window has closed," never a silent success.
```

## Statement

Planning document only. No backend/frontend runtime change. No API implementation change. No
database schema change. No migration created. No workflow change. No scheduler activated. No
dispatch/resume executed. No deployment.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
