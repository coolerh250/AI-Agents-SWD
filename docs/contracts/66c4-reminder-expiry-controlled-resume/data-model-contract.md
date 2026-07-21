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

## Proposed new fields

| Field | Table | Type | Nullable | Purpose |
| --- | --- | --- | --- | --- |
| `reminder_sent_at` | `operator_clarification_requests` | TIMESTAMPTZ | yes (NULL until sent) | makes the reminder-claim idempotent (see below); also the audit/observability source for "was a reminder ever sent for this clarification" |
| `expired_at` | `operator_clarification_requests` | TIMESTAMPTZ | yes (NULL until expired) | the moment the expiry transition actually fired (distinct from `due_at`, which is the deadline, not the actual-firing time — needed for accurate audit/observability, and to distinguish "on-time" vs. "late" scheduler execution) |
| `resume_eligible_at` | `operator_clarification_requests` | TIMESTAMPTZ | yes (NULL until eligible) | set the moment an answer is recorded (i.e., at the same instant as `answered_at` — could theoretically be derived from `answered_at` alone, proposed as a distinct column only if Option A resume model is chosen; see controlled-resume-contract.md) |
| `resume_requested_at` / `resume_requested_by` | `operator_clarification_requests` | TIMESTAMPTZ / TEXT | yes | only needed under the Explicit Operator-Controlled Resume model (Option A) — records who asked for resume and when |
| `resume_authorized_at` | `operator_clarification_requests` | TIMESTAMPTZ | yes | records when a resume request passed its policy/safety check — needed under both Option A and Option B |
| `resume_dispatched_at` | `operator_clarification_requests` | TIMESTAMPTZ | yes | records when the (future, not-yet-built) resume dispatch actually occurred — the final state in the lifecycle chain |

## Fields explicitly NOT proposed

```text
reminder_due_at  -- redundant with the existing reminder_at; do not create a second source of truth.
expires_at       -- redundant with the existing due_at; do not create a second source of truth.
reminder_count   -- not needed if exactly one reminder is sent per clarification (the canonical
  default recommendation in lifecycle-and-time-contract.md); reminder_sent_at (a single nullable
  timestamp) is sufficient and simpler than a counter. If a future stage authorizes multiple
  reminders, reminder_count would be added then, not now.
answered_by      -- not proposed as a new column; the answerer's identity remains recoverable via
  answer_message_id -> task_messages.sender_id, exactly as it is today. Adding a redundant column
  would create a second source of truth for the same fact.
version / lock_version -- not needed; this schema's established idempotency idiom is the
  WHERE-clause CAS guard (already used for the answer-claim), not an optimistic-lock version
  column. Introducing a different idiom for 66C.4 alone would be inconsistent with the codebase.
```

## Field ownership / nullability / defaults

```text
All six proposed fields: NULLABLE, no default (NULL means "has not happened yet" -- the absence
  of a value IS the state, exactly matching the existing answered_at column's own convention).
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
```

## State transition summary

```text
open --(reminder scheduler claims reminder_at<=now() AND reminder_sent_at IS NULL)--> open
  (reminder_sent_at set, status unchanged)
open --(expiry scheduler claims due_at<=now() AND status='open')--> expired (expired_at set)
open --(existing answer-claim, status='open')--> answered (answered_at set,
  resume_eligible_at set if Option A/B requires it)
answered --(resume request, if Option A)--> answered (resume_requested_at/by set)
answered --(policy/safety check passes)--> answered (resume_authorized_at set)
answered --(future resume dispatch, out of scope for this stage's implementation)--> answered
  (resume_dispatched_at set)
```

No row ever transitions out of `expired`, `canceled`, or (for this stage's scope) `answered` back
to `open` -- consistent with the existing `canceled` state's own terminal behavior.

## Migration necessity and rollback strategy

```text
Migration necessary: YES, for the six proposed new columns plus the two proposed partial indexes
  and one CHECK constraint. NOT created by this stage (planning only) -- proposed for Step
  66C.4-BE1 (see implementation-stage-slicing-plan.md).
Rollback strategy: all six new columns are nullable with no default and no foreign-key dependency
  from any other table -- a rollback migration is a straightforward `ALTER TABLE ... DROP COLUMN`
  for each, with zero data-loss risk to any EXISTING column, and zero impact on any row that never
  reached the new states (i.e., every row created before this migration remains fully valid with
  all six new columns simply NULL). The two proposed partial indexes and the one CHECK constraint
  are dropped in the same rollback with no data implication.
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
