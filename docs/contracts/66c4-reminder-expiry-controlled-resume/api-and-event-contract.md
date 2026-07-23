# API and Event Contract — Step 66C.4-P

> **Planning document only. No API implementation created. No endpoint added. No event published.
> This document proposes contracts for a later implementation stage (66C.4-BE1/BE2/BE3) to build —
> it does not build them itself.**

## 11.1 Proposed API endpoints

Only endpoints with a genuine new caller need are proposed — no endpoint is added for convenience.

### GET /tasks/{task_id}/clarifications/{clarification_id}/lifecycle

```text
Purpose: expose the reminder/expiry/resume lifecycle state of a single clarification (today only
  the raw row fields are visible via the embedded workroom response; this endpoint adds no new
  DATA, only a purpose-built projection plus derived state for the frontend's future lifecycle
  banner — see frontend-ux-boundary.md).
Actor: any of the 6 TASK_ROLES already permitted to view the workroom (reuses can_view_workroom).
RBAC: same as GET /tasks/{id}/workroom (Requester scoped to own task).
Request: none beyond path params.
Response: { clarification_id, status, created_at, reminder_at, reminder_sent_at, due_at,
  expired_at, answered_at, resume_eligible_at, resume_requested_at, resume_requested_by,
  resume_authorized_at, dispatch_enabled: false, resume_dispatch_enabled: false }.
  (No resume_dispatched_at is exposed -- dispatch/resumed are represented by durable outbox/audit
  evidence, not a clarification column; dispatch is built gated/disabled-by-default in 66C.4-BE3;
  see data-model-contract.md and controlled-resume-contract.md, Step 66C.4-P-R1.)
Error codes: 404 task_not_found / clarification_not_found; 403 if Requester requests a task they
  do not own.
Idempotency: n/a (read-only GET).
Audit: none (a read has no side effect requiring audit, consistent with every other GET in this
  system).
Side effects: none.
Production-effect behavior: none — pure read.
```

### GET /tasks/{task_id}/clarifications/{clarification_id}/resume-eligibility

```text
Purpose: expose whether a clarification is currently resume-eligible and, if not, why not
  (answers "can this be resumed right now" without requiring the caller to re-derive the
  eligibility logic client-side — a genuine need since eligibility depends on task-state
  interactions that must remain server-authoritative, per rbac-and-safety-contract.md's
  no-client-side-RBAC-as-security rule).
Actor: pm_engineering_lead, platform_admin, agent_operator (the roles who may act on resume under
  Option A; see controlled-resume-contract.md).
RBAC: new capability function `can_view_resume_eligibility`, scoped to the same 3 roles as
  `can_request_resume` below (a role that cannot request resume has no actionable use for this
  endpoint either).
Request: none beyond path params.
Response: { eligible: bool, reason: string | null (e.g. "not_answered", "task_state_changed",
  "already_dispatched", "production_effect_blocked"), resume_eligible_at }.
Error codes: 404 (same as above); 403 (role not permitted).
Idempotency: n/a (read-only).
Audit: none.
Side effects: none.
```

### POST /tasks/{task_id}/clarifications/{clarification_id}/resume-request

```text
Purpose: the explicit operator action Option A requires (see controlled-resume-contract.md) —
  ONLY built if Option A is the Product-Owner-confirmed model (product-owner-decision-checklist.md
  item 3). If Option B is chosen instead, this endpoint is NOT built and is replaced by an
  internal-only automatic check with no caller-facing endpoint.
Actor: pm_engineering_lead, platform_admin, agent_operator.
RBAC: new capability function `can_request_resume`.
Request: {} (no body needed — the path identifies the clarification; no free-text justification
  is required by this contract, though a future stage could add one if the Product Owner wants
  it — not proposed here since it is not a genuine technical necessity).
Response: { resume_requested_at, status: "pending_authorization" | "authorized" | "rejected",
  reason: string | null }.
Error codes: 404; 403; 409 clarification_not_eligible (if §2's conditions are not met);
  409 resume_already_requested (idempotent re-confirmation, not an error in the strict sense —
  see controlled-resume-contract.md §10).
Idempotency: CAS guard on `resume_requested_at IS NULL`, per controlled-resume-contract.md §12.
Audit: `clarification_resume_requested`.
Side effects: sets `resume_requested_at`; triggers the synchronous policy/safety check (§2), which
  may immediately set `resume_authorized_at` in the same request if all conditions already hold.
Production-effect behavior: a production-effect task's request is accepted (recorded) but the
  policy check always returns not-authorized for such tasks (§15 of controlled-resume-contract.md).
```

### GET /tasks/{task_id}/clarifications/{clarification_id}/audit-evidence (reminder/expiry/resume
scoped)

```text
Purpose: this is NOT a new endpoint — the existing GET /tasks/{id}/audit-evidence endpoint already
  returns an allowlist projection of every audit event for the task, and the new event types
  proposed below (clarification_reminder_sent, clarification_expired, clarification_resume_*) are
  simply new entries in that SAME existing allowlist/projection, following the identical pattern
  already used for clarification_requested/clarification_answered. No new endpoint is proposed.
```

### Explicitly NOT proposed

```text
POST /tasks/{id}/clarifications/{cid}/retry-timeout-transition -- no genuine need identified: the
  scheduler's own CAS-guarded poll cycle already re-evaluates every open row on every cycle, so
  there is no "stuck" transition that needs a manual retry trigger distinct from just waiting for
  the next poll cycle (see race-condition-and-failure-analysis.md scenario 14, worker-restart
  case, which confirms this self-heals without manual intervention).
```

## 11.2 Internal event contract

Candidate events (naming follows this repository's existing `noun.past_participle` /
`noun.adjective` convention seen in `stream.deadletter` and audit event names):

```text
clarification.reminder_due       -- published by the clarification-timeout worker the moment it
                                     claims a reminder-due row (before setting reminder_sent_at,
                                     mirroring the existing claim-then-side-effect ordering).
clarification.reminder_recorded  -- published after reminder_sent_at is durably set (the
                                     notification-worker's actual trigger to produce a real
                                     internal notification for the assignee).
clarification.expired            -- published after the expiry CAS claim succeeds and expired_at
                                     is set.
clarification.answered           -- ALREADY covered by the existing clarification_answered audit
                                     event; not a new event, listed here only for completeness of
                                     the full event sequence.
clarification.resume_eligible    -- published the instant resume_eligible_at is set (synchronous,
                                     same transaction as the answer-claim, per
                                     controlled-resume-contract.md §1).
clarification.resume_requested   -- published on a successful resume-request (Option A only).
clarification.resume_authorized  -- published when the policy/safety check passes.
clarification.resume_dispatched  -- published (as a durable outbox event) when a gated dispatch
                                     occurs; the dispatch MECHANISM is built in 66C.4-BE3 but is
                                     disabled-by-default (dispatch_enabled false), so in normal
                                     operation this is not emitted until dispatch is separately
                                     enabled. Idempotency key {clarification_id}:resume_dispatched.
clarification.workflow_resumed   -- published when the orchestrator CONFIRMS the resumed state
                                     (66C.4-BE3 confirmation handler); distinct from dispatched.
clarification.resume_failed      -- published on a dispatch/confirmation failure routed through the
                                     outbox/DLQ (66C.4-BE3); operator-recoverable per scenario 17.
```

Actual event naming must be confirmed against this repository's real event-bus registry
(`shared/sdk/event_bus/`) at implementation time — the names above are this stage's recommendation,
not a final binding decision, since a future implementation stage may find a more specific existing
convention this planning stage did not surface.

## Event payload (minimized, per this stage's own requirement)

```json
{
  "event_id": "<uuid>",
  "task_id": "<uuid>",
  "clarification_id": "<uuid>",
  "occurred_at": "<ISO-8601 UTC>",
  "idempotency_key": "<see per-event key below>",
  "reason_or_status_metadata": "<safe, minimal — e.g. 'reminder_sent', 'expired', 'eligible'>"
}
```

No `workflow_id` is included because no workflow-engine integration exists yet (out of this
stage's scope, per current-state-assessment.md §5's confirmation that no dispatch/resume code path
exists at all). No secret, token, or raw clarification question/answer body is included — this
matches the existing `safe_workroom_refs` pattern (`shared/sdk/tasks/audit_events.py`) of
hash/length-only references for message content, never raw text.

## Idempotency keys per event

```text
clarification.reminder_due / reminder_recorded : "{clarification_id}:reminder"
clarification.expired                          : "{clarification_id}:expired"
clarification.resume_eligible                  : "{clarification_id}:resume_eligible"
clarification.resume_requested                 : "{clarification_id}:resume_requested"
clarification.resume_authorized                : "{clarification_id}:resume_authorized"
```

Each key is deterministic and derivable from the clarification id alone, since every event in this
contract fires at most once per clarification (matches the "exactly one reminder" and "at most one
resume lifecycle" defaults established in lifecycle-and-time-contract.md and
controlled-resume-contract.md).

## 11.3 State / audit / event atomicity model (binding — added in Step 66C.4-P-R1)

This section replaces the original draft's treatment of audit/event-publish failure as a
"non-blocking gap that needs no handling." Direct inspection confirms the existing
`publish_audit_event` (`shared/sdk/audit/publisher.py`) is **best-effort and silently drops the
message on any failure** ("The publisher is best-effort ... Failures are swallowed"). Relying on it
alone would mean a committed state transition could have **no durable audit/event record**. That is
not acceptable for lifecycle transitions, so this stage selects a binding, durable consistency model.

### Options compared

```text
Option 1 -- State transaction + transactional outbox:
  The lifecycle CAS UPDATE and an INSERT into a durable outbox table commit in the SAME database
  transaction. A separate relay publishes outbox rows to audit/Redis, marks them published, and
  DLQs after bounded retries. Durability and replayability come from the DB row, not the transport.

Option 2 -- State transaction + durable pending-event table:
  Functionally the same durability property as Option 1 (a durable row written in the state
  transaction); differs only in framing/table shape. Equivalent reliability.

Option 3 -- Existing repository mechanism (publish_audit_event / direct XADD), only if it can be
  shown to provide equivalent durability and replayability:
  REJECTED. Evidence disproves equivalence: publish_audit_event explicitly swallows failures and
  returns None on drop; there is no durable record of an unpublished event, so it cannot be
  replayed. It provides neither durability nor replayability for a committed state transition.
```

### Selected model (binding): Option 1 — transactional outbox

```text
- Every lifecycle transition (reminder-sent, expired, resume-eligible, resume-requested,
  resume-authorized) writes its state column(s) AND inserts one clarification_lifecycle_outbox row
  (data-model-contract.md) in a SINGLE database transaction -- both commit or neither does.
- A relay/publisher step (the clarification-timeout worker for reminder/expiry; the API handler's
  follow-on for resume events) reads ELIGIBLE 'pending' outbox rows
  (`status='pending' AND available_at <= statement_timestamp()`), produces the audit projection and
  the Redis event, marks the row 'published', and after bounded, BACKED-OFF retries marks it 'dead'
  (with dead_at and a bounded, secret-free last_error) and routes it to the EXISTING
  stream.deadletter / retry-scheduler DLQ. The retry schedule is PERSISTED in available_at, not held
  in worker memory -- see the durability columns in data-model-contract.md (Step 66C.4-BE1-R1).
- BINDING relay constraint: a relay MUST claim rows with FOR UPDATE SKIP LOCKED inside its own
  transaction and MUST NOT hold a claim across a process/transaction boundary. This is what makes a
  claim-owner/lease column unnecessary; a worker crash rolls the uncommitted claim back.
- The outbox UNIQUE(idempotency_key) plus each event's deterministic idempotency key give
  at-least-once delivery with idempotent, deduplicated consumption (never exactly-once).
- Audit/event publication failure is therefore NO LONGER a "non-blocking gap": the durable outbox
  row guarantees the event is eventually published or explicitly dead-lettered for operator
  reconciliation -- it is never silently lost.
```

### Failure modes this model must handle (all binding)

```text
1. DB commit succeeds but publisher unavailable: the outbox row is durably 'pending'; the relay
   publishes it when the publisher recovers. No loss. This requires the PERSISTED backoff schedule
   in available_at: without it, a relay polling every few seconds exhausts its bounded attempts
   within seconds of the outage and dead-letters healthy rows, which is exactly the loss this mode
   forbids and would make modes 1 and 7 mutually unsatisfiable (Step 66C.4-BE1-R blocking finding
   B-2; race-condition-and-failure-analysis.md scenario 19).
2. Publisher succeeds but acknowledgement/mark-published fails: the row stays 'pending', is
   re-published on the next relay pass; the consumer deduplicates via idempotency_key. At-least-once
   + idempotent = no duplicate observable effect.
3. Duplicate publisher execution: two relays publishing the same 'pending' row produce two
   deliveries with the same idempotency_key; consumers dedupe. Safe.
4. Audit service unavailable: same as (1) -- the outbox row waits; nothing is dropped.
5. Redis unavailable: same as (1) -- publication is deferred until Redis recovers; the state
   transition is already durable.
6. Outbox backlog recovery: after any outage the relay drains ELIGIBLE 'pending' rows oldest-first
   (available_at, then created_at); the backlog is bounded by outage duration, not unbounded.
7. Poison event / terminal DLQ: a row that fails bounded, backed-off retries is marked 'dead' with
   dead_at set and a bounded, secret-free last_error retained, and is routed to the existing DLQ; it
   is NOT retried forever and NOT silently dropped -- it becomes an explicit, DIAGNOSABLE
   operator-reconciliation item (recovery-and-audit, race-condition-and-failure-analysis.md
   scenarios 17 and 19).
8. Operator replay path: a 'dead' outbox row (or a reconciliation exception) is replayable by an
   authorized operator via the existing DLQ replay tooling, exactly as any other dead-lettered
   message in this project. The replay transition (dead -> pending, preserving id/idempotency_key
   and NOT resetting attempts) is defined in data-model-contract.md "Operator replay semantics".
```

Because Option 1 is selected, no "equivalent-reliability evidence for the existing mechanism" is
required; the evidence above instead documents why the existing best-effort publisher is NOT
sufficient on its own and why the outbox is added.

## External notification

```text
OFF by default for every event above, matching the standing project rule and the existing Discord
  notify-first pattern (external_send disabled by default, explicit per-channel Product Owner
  authorization required before any real external send). This stage proposes ONLY internal event
  production; no external channel integration is in scope (M4 territory per the Master Plan).
```

## Statement

Planning document only. No API implementation created. No endpoint added. No event published.
This document proposes contracts for a later implementation stage to build — it does not build
them itself.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
