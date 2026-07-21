# Lifecycle and Time Contract — Step 66C.4-P

> **Planning document only. No backend/frontend runtime change. No API implementation change. No
> database schema change. No migration created. No workflow change. No scheduler activated. No
> dispatch/resume executed. No deployment.**

## 7.1 Time source

```text
Authoritative clock: Postgres server clock via `now()` at write time (already the pattern for
  `due_at`/`reminder_at` computation and for `answered_at`/`updated_at` in the existing CAS claim).
  The scheduler process must NOT compute deadlines from its own local clock -- it only compares
  its own `now()` reading against already-stored TIMESTAMPTZ values, and any write it performs
  uses the same `now()` SQL function, keeping a single source of truth for "current time."
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
Scheduler clock skew tolerance: recommend a conservative 60-second tolerance window is NOT needed
  given the actual precision requirement (reminders/expiry are hour-granularity human-facing
  events, not sub-second-precision triggers) -- the scheduler's own polling/consumption interval
  (see scheduler-architecture-decision.md) is the dominant source of latency, not clock skew
  between the scheduler process and Postgres (both read `now()` from the same Postgres server in
  the claim query itself, see race-condition-and-failure-analysis.md).
Delayed execution tolerance: recommend up to several minutes of delay between a timestamp becoming
  due and the reminder/expiry transition actually firing is acceptable for this human-facing use
  case (this is a PRODUCT decision, not purely technical -- see product-owner-decision-checklist.md
  item 5 is NOT this; this tolerance itself does not require PO sign-off since it does not change
  observable product behavior beyond "eventually," consistent with every existing async worker in
  this project).
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
6. Late answer (an answer attempt after `due_at` has passed but before the scheduler has processed
   the expiry): this is a genuine PO decision -- see product-owner-decision-checklist.md item 1.
   Recommended default: **NOT allowed** once the scheduler has actually transitioned the row to
   `expired` (the same `WHERE status='open'` CAS guard on the answer-claim query already prevents
   this by construction, with zero new code -- the answer-claim and the expiry-claim compete for
   the same row via the same guard, so whichever wins the race is authoritative; see
   race-condition-and-failure-analysis.md scenario 6). There is a narrow window where an answer
   submitted a few seconds before the scheduler runs still succeeds -- this is acceptable and
   requires no special-casing, since it is bounded by the scheduler's own polling/consumption
   latency (see scheduler-architecture-decision.md), not an indefinite grace period.
7. Late-answer UI/API response: if the CAS guard rejects the answer because the row already
   transitioned to `expired`, the existing `409 invalid_state_for_answer:{status}` error path
   already handles this correctly with zero new code (`workroom_api.py`'s existing status != 'open'
   branch already covers `status='expired'`).
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
