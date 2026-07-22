# Data Model Contract — Step 66C.4-P

> **Planning document only. No database schema change. No migration created. This document
> proposes a future migration for a later implementation stage (66C.4-BE1) to create — it does
> not create one itself.**

## Existing fields reused (no change needed)

```text
operator_clarification_requests.due_at        -- expiry deadline (72h), already computed at insert
operator_clarification_requests.reminder_at    -- reminder deadline (24h), already computed at insert
operator_clarification_requests.answered_at    -- already set by the existing CAS answer-claim
operator_clarification_requests.status         -- 'open'|'answered'|'expired'|'canceled', reused
  for the new 'open' -> 'expired' transition (already a valid enum value, no CHECK constraint
  change needed)
operator_tasks.status                          -- clarification_expired already a valid enum value
```

## Proposed new lifecycle columns — reconciled inventory

> **Corrected in Step 66C.4-P-R1.** The original draft's prose said "six proposed fields" while the
> table listed seven distinct columns (the `resume_requested_at` / `resume_requested_by` row plus a
> `resume_dispatched_at` row). This section restates the inventory so the column count is internally
> consistent. The reconciled decision is **exactly six new lifecycle columns** on
> `operator_clarification_requests`, plus **one new durable outbox table** (see the next section).
> `resume_dispatched_at` is **removed** from the proposed lifecycle columns. Dispatch and
> workflow-resumed confirmation ARE planned for 66C.4-BE3 (built gated/disabled-by-default; see
> controlled-resume-contract.md and implementation-stage-slicing-plan.md), but per the
> minimal-columns principle they are represented by **durable outbox/audit evidence** (the resume
> event and confirmation event), not by new columns on `operator_clarification_requests`. The
> task's own status is the source of truth for "resumed." No `resume_dispatched_at` /
> `resume_dispatch_event_id` / `resumed_at` column is created by this stage's migration.

The reconciled per-field decisions (required/optional/remove · column-or-audit-only · type ·
nullability · actor/reference semantics · index/constraint · lifecycle owner · rollback):

| # | Field | Decision | Storage | Type | Nullable | Actor / reference semantics | Index / constraint | Lifecycle owner (writer) | Rollback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `reminder_sent_at` | required | DB column | TIMESTAMPTZ | yes (NULL until sent) | no actor ref — set by the timeout worker's reminder-claim | covered by partial index (status, reminder_at) WHERE status='open' AND reminder_sent_at IS NULL | clarification-timeout worker (Claude Code) | DROP COLUMN, no data-loss |
| 2 | `expired_at` | required | DB column | TIMESTAMPTZ | yes (NULL until expired) | no actor ref — the moment the expiry transition actually fired (distinct from `due_at`, the deadline) | covered by partial index (status, due_at) WHERE status='open' | clarification-timeout worker (Claude Code) | DROP COLUMN, no data-loss |
| 3 | `resume_eligible_at` | required (Option A) | DB column | TIMESTAMPTZ | yes (NULL until eligible) | no actor ref — set in the same transaction as the answer-claim IF the task is non-terminal; **not derivable from `answered_at` alone** because it also encodes the task-non-terminal decision | CHECK: resume_authorized_at IS NULL OR resume_eligible_at IS NOT NULL | answer-claim path (Claude Code) | DROP COLUMN, no data-loss |
| 4 | `resume_requested_at` | required (Option A) | DB column | TIMESTAMPTZ | yes (NULL until requested) | no actor ref itself — paired with #5 | CAS guard `WHERE resume_requested_at IS NULL` | resume-request endpoint (Claude Code) | DROP COLUMN, no data-loss |
| 5 | `resume_requested_by` | required (Option A) | DB column | TEXT | yes | **actor**: the authenticated principal (role-bearing user id) who took the explicit resume-request action; has no other source (unlike `answered_by`, there is no message row to recover it from) | none | resume-request endpoint (Claude Code) | DROP COLUMN, no data-loss |
| 6 | `resume_authorized_at` | required (Option A) | DB column | TIMESTAMPTZ | yes (NULL until authorized) | no human actor ref — authorization is performed by the automated policy/safety check, not a person; the check's evidence lives in the durable outbox/audit event, not a column | CAS guard `WHERE resume_authorized_at IS NULL AND resume_eligible_at IS NOT NULL` | resume-authorization path (Claude Code) | DROP COLUMN, no data-loss |

## Fields explicitly NOT proposed (and why)

```text
resume_dispatched_at / resumed_at -- NOT new columns. Dispatch and workflow-resumed confirmation
  are built (gated/disabled-by-default) in 66C.4-BE3, but represented by durable outbox/audit
  evidence (the resume event + the confirmation event) plus the task's own status transition -- not
  by columns on operator_clarification_requests. This follows the minimal-columns principle: prefer
  durable outbox/audit evidence over a column for a fact the task status + outbox already carry.
resume_authorized_by -- NOT a new column. Authorization is the automated policy/safety check's
  decision, not a human's; there is no distinct human "authorizer" under Option A (the human is the
  requester, captured by resume_requested_by). The authorization decision's evidence (what the
  check evaluated, its outcome/reason) is recorded in the durable outbox/audit event, not a column.
policy_decision_id -- NOT a new column. No policy-decision registry/table exists anywhere in this
  repository; the authorization outcome + reason are carried in the durable outbox/audit event. If
  a future stage introduces a real policy engine with its own decision records, a reference could
  be added then, not now.
resume_dispatch_event_id -- NOT a new column. The durable outbox resume-event row (with its own id
  and deterministic idempotency_key {clarification_id}:resume_dispatched) IS the dispatch-event
  reference; a duplicate column on the clarification row would be a second source of truth.
lock_version -- NOT a new column. This schema's established idempotency idiom is the WHERE-clause
  CAS guard (already proven for the answer-claim, Step 66C.3 G5), not an optimistic-lock version
  column. Introducing a different idiom for 66C.4 alone would be inconsistent with the codebase.
reminder_due_at -- redundant with the existing reminder_at; do not create a second source of truth.
expires_at (as a new column) -- redundant with the existing due_at, which is already the
  authoritative deadline (see lifecycle-and-time-contract.md §7.3A); do not create a second source.
reminder_count -- not needed if exactly one reminder is sent per clarification (the canonical
  default in lifecycle-and-time-contract.md). If a future stage authorizes multiple reminders,
  reminder_count would be added then, not now.
answered_by -- not a new column; the answerer's identity remains recoverable via
  answer_message_id -> task_messages.sender_id, exactly as it is today.
```

## Durable outbox / pending-event table (new, added in Step 66C.4-P-R1)

The state/audit/event atomicity model (api-and-event-contract.md §11.3, added in this remediation)
requires that every lifecycle transition and its corresponding notification/audit event become
durable **in the same database transaction**. The existing `publish_audit_event`
(`shared/sdk/audit/publisher.py`) is explicitly **best-effort and drops the message on any failure**
("Failures are swallowed" — verified directly), so it provides **no** durability on its own. This
stage therefore proposes one new durable outbox table as the atomicity foundation, created by
66C.4-BE1:

```text
Proposed table: clarification_lifecycle_outbox
  id               UUID PRIMARY KEY
  clarification_id UUID NOT NULL   -- FK to operator_clarification_requests(id)
  task_id          UUID NOT NULL
  event_type       TEXT NOT NULL   -- e.g. 'clarification_reminder_sent', 'clarification_expired',
                                     'clarification_resume_eligible', ...
  idempotency_key  TEXT NOT NULL   -- deterministic per (clarification_id, event_type); UNIQUE
  payload          JSONB NOT NULL  -- minimal, safe (no raw question/answer body; hash/length refs
                                     only, matching safe_workroom_refs)
  status           TEXT NOT NULL DEFAULT 'pending'  -- 'pending' | 'published' | 'dead'
  attempts         INT  NOT NULL DEFAULT 0
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
  available_at     TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
                                         -- BE1-R1: earliest time a relay may claim this row
  published_at     TIMESTAMPTZ            -- NULL until the relay confirms publication
  dead_at          TIMESTAMPTZ            -- BE1-R1: set only in the terminal 'dead' state
  last_error       TEXT                   -- BE1-R1: bounded, secret-free last failure reason
  UNIQUE (idempotency_key)
  CHECK (last_error IS NULL OR length(last_error) <= 500)
  CHECK (status/timestamp coherence -- see "Status semantics" below)
```

### Durability columns (BINDING — added in Step 66C.4-BE1-R1)

The Step 66C.4-BE1-R independent review found the original column set insufficient: binding
`api-and-event-contract.md` §11.3 failure mode 1 ("publisher unavailable → no loss") and failure
mode 7 ("bounded retries → dead") cannot both hold without a PERSISTED backoff schedule, because a
bounded-attempt relay exhausts its cap within seconds of an outage and dead-letters healthy rows.
The following three columns are therefore part of the canonical contract, not optional refinements.

```text
available_at
  TIMESTAMPTZ NOT NULL.
  The earliest time a relay may claim this row.
  Set on INSERT to PostgreSQL statement time.
  Updated forward by the backoff policy on each transient failure.
  NOT NULL so no row can become permanently unclaimable through a NULL comparison.

dead_at
  TIMESTAMPTZ NULL.
  Set ONLY when the row enters the terminal 'dead' state; it is the time of death, which
  created_at cannot express. DLQ age, alert thresholds and reconciliation SLAs derive from it.
  Cleared when an operator replays the row back to 'pending'.

last_error
  Bounded TEXT, NULL when there has been no failure.
  Carries a short, safe failure reason only: an exception class, a status code, a transport
  error label. It MUST NOT contain a secret, token, credential, raw payload, or raw
  clarification/question/answer content.
  The 500-character bound is enforced at the repository boundary AND by a DB CHECK constraint
  (defense in depth).

Deliberately NOT added: no claim-owner and no lease-expiry column. They are unnecessary while the
  relay claims rows with FOR UPDATE SKIP LOCKED inside its own transaction, because a worker crash
  rolls the uncommitted claim back and the row returns to 'pending'. BINDING CONSTRAINT on BE2: a
  relay MUST NOT hold a claim across a process/transaction boundary. If a future stage needs a
  lease that outlives a transaction, it must add those columns by amending this contract first.
No synonym columns are introduced: published_at, attempts and status already exist and are reused.
```

### Status semantics (BINDING)

```text
pending    published_at IS NULL     AND dead_at IS NULL     AND available_at IS NOT NULL
published  published_at IS NOT NULL AND dead_at IS NULL
dead       dead_at      IS NOT NULL AND published_at IS NULL

A CHECK constraint enforces exactly these three combinations, so a row can never claim to be both
published and dead, and a terminal row can never lack its terminal timestamp.
```

### Retry semantics (BINDING)

```text
1. Claim eligibility: a relay may claim ONLY rows where
     status = 'pending' AND available_at <= statement_timestamp()
   (statement time, for the same reason as the answer-claim deadline -- see
   lifecycle-and-time-contract.md §7.1 time-function selection).
2. Transient failure: attempts := attempts + 1; available_at := the next retry time from the
   backoff policy; last_error := a bounded, secret-free reason. status stays 'pending'.
3. Bounded retries exhausted: status := 'dead'; dead_at := statement_timestamp(); last_error
   retains the final bounded, secret-free reason, so the operator item is diagnosable.
4. Success: status := 'published'; published_at := statement_timestamp(); last_error is CLEARED
   (set to NULL) — a published row carries no residual failure text.
```

### Operator replay semantics (BINDING, contract only)

```text
Transition: dead -> pending.
  id                preserved (the event keeps its identity)
  idempotency_key   preserved (deterministic; replay stays idempotent for consumers)
  status            := 'pending'
  available_at      := statement_timestamp() (immediately eligible)
  dead_at           := NULL
  last_error        := NULL (the failure reason moves into the audit evidence for the replay
                      action; it is not retained on the live row)
  attempts          NOT reset -- the full delivery-attempt history is preserved as evidence.
                      A separate replay_count column may be added by a FUTURE stage if a
                      per-replay budget is needed; BE1-R1 does not add unauthorized columns.
No replay endpoint, no runtime replay path, and no relay exist in BE1/BE1-R1. This section defines
  semantics that BE2 and the operator tooling must implement; it authorizes no implementation here.
```

```text
Writer: the same transaction that performs each lifecycle CAS UPDATE also INSERTs the matching
  outbox row (state + intent-to-publish commit atomically -- either both or neither).
Relay: a publisher step (the clarification-timeout worker for reminder/expiry events; the API
  request handler's follow-on for resume events) reads eligible 'pending' rows, publishes the
  audit/event, marks 'published', and after bounded, BACKED-OFF retries marks 'dead' (routed to the
  existing stream.deadletter / retry-scheduler DLQ). See api-and-event-contract.md §11.3 and
  race-condition-and-failure-analysis.md scenarios 10, 17, 19.
Rollback: DROP TABLE clarification_lifecycle_outbox -- no other table references it, zero data-loss
  to any existing table.
```

## Field ownership / nullability / defaults

```text
All six new lifecycle columns: NULLABLE, no default (NULL means "has not happened yet" -- the
  absence of a value IS the state, matching the existing answered_at column's own convention).
Field ownership: all six are written exclusively by the backend (Claude-Code-owned scheduler/API
  code) -- never client-writable, never exposed as a request-body field on any endpoint.
```

## Indexes / constraints

```text
Proposed: a partial index on (status, reminder_at) WHERE status = 'open' AND reminder_sent_at IS
  NULL -- supports the reminder-claim scan efficiently without scanning answered/expired/canceled
  rows.
Proposed: a partial index on (status, due_at) WHERE status = 'open' -- supports the expiry-claim
  scan efficiently.
No new CHECK constraint needed on status (expired is already a valid enum value).
Proposed CHECK: resume_authorized_at IS NULL OR resume_eligible_at IS NOT NULL (a resume cannot be
  authorized before it became eligible) -- a lifecycle-ordering guard, cheap and unambiguous.
Outbox: UNIQUE (idempotency_key) enforces at-most-once durable enqueue per (clarification, event).
```

## State transition summary

```text
open --(reminder scheduler claims reminder_at<=now() AND reminder_sent_at IS NULL; same txn
  INSERTs outbox row)--> open (reminder_sent_at set, status unchanged)
open --(expiry scheduler claims due_at<=now() AND status='open'; same txn INSERTs outbox row)
  --> expired (expired_at set)
open --(existing answer-claim, status='open' AND expires_at>now(); same txn sets resume_eligible_at
  if the task is non-terminal, INSERTs outbox row)--> answered (answered_at set)
answered --(resume request, Option A only; CAS on resume_requested_at IS NULL)--> answered
  (resume_requested_at + resume_requested_by set)
answered --(policy/safety check passes; CAS on resume_authorized_at IS NULL)--> answered
  (resume_authorized_at set)
[resume dispatched / workflow resumed -- built gated/disabled-by-default in 66C.4-BE3; represented
  by durable outbox/audit evidence + the task's own status, not by a column on this table]
```

No row ever transitions out of `expired`, `canceled`, or (for this stage's scope) `answered` back
to `open` -- consistent with the existing `canceled` state's own terminal behavior.

## Migration necessity and rollback strategy

```text
Migration necessary: YES, for the six new lifecycle columns, the two partial indexes, the one CHECK
  constraint, AND the new clarification_lifecycle_outbox table. NOT created by this stage (planning
  only) -- proposed for Step 66C.4-BE1 (see implementation-stage-slicing-plan.md).
Rollback strategy: all six new columns are nullable with no default and no foreign-key dependency
  from any other table -- rollback is a straightforward `ALTER TABLE ... DROP COLUMN` for each,
  with zero data-loss risk to any EXISTING column, and zero impact on any row that never reached
  the new states (every pre-migration row remains valid with all six new columns simply NULL). The
  two partial indexes, the one CHECK constraint, and the outbox table are dropped in the same
  rollback with no data implication for any existing table.
```

## Statement

Planning document only. No database schema change. No migration created. This document proposes a
future migration for a later implementation stage to create — it does not create one itself.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
