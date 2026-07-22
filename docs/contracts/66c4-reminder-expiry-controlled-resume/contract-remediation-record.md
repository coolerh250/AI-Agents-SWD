# Contract Remediation Record — Step 66C.4-P-R1

> **Planning/remediation document only. No runtime code, backend, frontend, API, database,
> migration, workflow, scheduler, dispatch, resume, deployment, or external notification changed by
> this stage. No role authorized to begin implementation. Step 66C.4-BE1 remains not started.**

Marker: `STEP66C4_PLANNING_CONTRACT_REMEDIATION_VERIFY: PASS`

This record documents the seven corrections (A–G) applied to the Step 66C.4-P planning/contract set
following the Product Architect review verdict `PASS_WITH_GAPS`. Work continued on the SAME branch
(`planning/66c4-reminder-expiry-controlled-resume`); no competing branch was created.

## Read-only code re-inspection grounding this remediation

```text
- shared/sdk/audit/publisher.py -- CONFIRMED best-effort and drops on failure ("The publisher is
  best-effort ... Failures are swallowed"; returns None on drop). This is the direct evidence that
  the existing publish path provides NO durability/replayability on its own, grounding Correction D
  (transactional outbox) and disproving Option 3 (existing-mechanism equivalence).
- No outbox/pending-event pattern exists anywhere in the repository (grep: the only 'outbox' hit is
  an unrelated word; zero pending-event table pattern) -- so the outbox is genuinely new.
- shared/sdk/event_bus/redis_streams.py publish_event -> XADD; at-least-once transport, no
  exactly-once guarantee -- grounding the at-least-once + idempotent wording (Corrections C, D).
- dispatch_enabled / resume_dispatch_enabled remain hardcoded false -- grounding the "dispatch built
  gated/disabled-by-default in BE3" framing (Correction G / §11 slicing).
```

## Correction A — Data-field inventory reconciliation

```text
Problem: the draft's prose said "six proposed fields" while the table listed seven distinct columns
  (reminder_sent_at, expired_at, resume_eligible_at, resume_requested_at, resume_requested_by,
  resume_authorized_at, resume_dispatched_at).
Resolution (data-model-contract.md, controlled-resume-contract.md):
  - Reconciled to EXACTLY SIX new lifecycle columns on operator_clarification_requests:
    reminder_sent_at, expired_at, resume_eligible_at, resume_requested_at, resume_requested_by,
    resume_authorized_at -- each with a per-field decision (required/optional/remove · column vs
    audit-only · type · nullability · actor/reference semantics · index/constraint · lifecycle
    owner · rollback).
  - REMOVED resume_dispatched_at as a column. Dispatch and workflow-resumed confirmation are
    represented by durable outbox/audit evidence + the task's own status (minimal-columns
    principle), not by columns on the clarification table.
  - Additional candidates decided: resume_authorized_by NOT added (authorization is the automated
    policy check, not a human); policy_decision_id NOT added (no policy registry exists);
    resume_dispatch_event_id NOT added (the outbox row IS the reference); lock_version NOT added
    (CAS-via-WHERE is the established idiom).
  - Added a new durable outbox table (clarification_lifecycle_outbox) as the atomicity foundation.
```

## Correction B — Authoritative expiry semantics (binding)

```text
Problem: the draft allowed a late answer to succeed in the window between due_at passing and the
  scheduler materializing status='expired' (scheduler lag extended the answer window).
Resolution (lifecycle-and-time-contract.md §7.3A, binding):
  - due_at is the AUTHORITATIVE, EXCLUSIVE-upper-bound deadline; PostgreSQL database time is the
    authoritative clock.
  - The answer-claim gains an `AND due_at > now()` predicate, so a single CAS predicate decides the
    answer/expiry race regardless of whether the scheduler has run.
  - Answer exactly at due_at is rejected (exclusive bound). Scheduler lag never extends the window.
  - Scheduler MATERIALIZES status/audit/event; it does not decide whether the deadline was reached.
  - Late answer returns the existing 409 invalid_state_for_answer path (extended by the predicate).
```

## Correction C — Reminder semantics under scheduler lag

```text
Problem: reminder-under-lag semantics and delivery guarantees were under-specified.
Resolution (lifecycle-and-time-contract.md §7.2A, binding):
  - reminder_at is the authoritative reminder-due time; poller lag affects only WHEN the reminder
    is published, never the due time.
  - reminder_sent_at records the at-most-once STATE TRANSITION (CAS), not proof of delivery.
  - No reminder once answered/expired (guarded by WHERE status='open' AND reminder_sent_at IS NULL).
  - Deterministic idempotency key {clarification_id}:reminder.
  - Delivery is AT-LEAST-ONCE with IDEMPOTENT consumption; exactly-once is explicitly NOT claimed.
```

## Correction D — State/audit/event atomicity model (binding)

```text
Problem: the draft treated audit/event-publish failure as a "non-blocking gap that needs no
  handling," despite the existing publisher silently dropping on failure.
Resolution (api-and-event-contract.md §11.3, binding; data-model-contract.md outbox table):
  - Compared Option 1 (transactional outbox), Option 2 (durable pending-event table), Option 3
    (existing mechanism). Option 3 REJECTED with evidence (publisher swallows failures, no durable
    replayable record). Selected Option 1 (transactional outbox).
  - Lifecycle state UPDATE + outbox INSERT commit in the SAME transaction; a relay publishes,
    marks published, and DLQs after bounded retries.
  - Documented all 8 required failure modes (DB-commit-then-publisher-down, publish-then-ack-fail,
    duplicate publisher, audit down, Redis down, backlog recovery, poison/terminal DLQ, operator
    replay).
  - Audit/event publication failure is NO LONGER a "non-blocking gap"; it is durable + replayable
    or explicitly dead-lettered for operator reconciliation.
```

## Correction E — Clock semantics wording

```text
Problem: the draft used absolute clock-risk-free wording (an unqualified "no ... risk" phrasing and
  an "...by design" elimination claim for the clock-skew failure mode).
Resolution (lifecycle-and-time-contract.md §7.1; race-condition-and-failure-analysis.md scenario 15):
  - Adopted the canonical non-absolute wording: "PostgreSQL database time is the authoritative
    lifecycle clock. This reduces cross-service clock divergence, but does not eliminate delayed
    polling, transaction-time semantics, database configuration risk, or display-timezone concerns."
  - Defined TIMESTAMPTZ storage, UTC normalization, transaction-timestamp choice, delayed-scheduler
    tolerance, backlog processing, display-timezone responsibility, and DB-clock-anomaly monitoring.
```

## Correction F — Recovery semantics (automatic vs operator)

```text
Problem: the draft used blanket "no manual intervention / self-heals" wording.
Resolution (race-condition-and-failure-analysis.md recovery-semantics section + scenario 17;
  observability-and-audit-plan.md):
  - Split recovery into AUTOMATIC (transient DB/Redis retry, process restart, outbox backlog
    replay, duplicate suppression) and OPERATOR (terminal DLQ, poison event, repeated policy
    failure, inconsistent legacy record, audit-reconciliation exception, manual replay after
    investigation).
  - No failure is assumed to always self-heal; each is explicitly classified.
```

## Correction G — Resume request/authorization state model (binding)

```text
Problem: request/authorization/dispatch/resumed were under-separated; the operator request risked
  reading as "resumed."
Resolution (controlled-resume-contract.md binding per-transition state model):
  - ANSWERED -> RESUME_ELIGIBLE -> RESUME_REQUESTED -> RESUME_AUTHORIZED -> RESUME_DISPATCHED ->
    WORKFLOW_RESUMED, each with actor/trigger/precondition/persisted-evidence/audit-event/
    idempotency-key/failure-state/retry-recovery.
  - Under Option A: Operator REQUESTS (resume_requested_by), the automated policy/safety evaluation
    AUTHORIZES, the Dispatcher publishes a DURABLE resume event, and the orchestrator CONFIRMS the
    resumed state. An operator request is NEVER equivalent to workflow-resumed.
  - Dispatch and confirmation are built gated/disabled-by-default in 66C.4-BE3 (dispatch_enabled
    stays false), represented by durable outbox/audit evidence rather than new columns.
  - Field decisions confirmed: no resume_authorized_by / policy_decision_id / resume_dispatch_event_id
    / resumed_at columns; evidence lives in the durable outbox/audit trail and the task's own status.
```

## Downstream updates (consistency)

```text
- implementation-stage-slicing-plan.md: BE1 now includes authoritative-deadline predicates +
  durable-outbox atomicity foundation; BE2 includes idempotent outbox relay + retry/DLQ +
  metrics/health; BE3 includes resume eligibility/request/authorization + gated durable resume
  event + orchestrator confirmation + recovery/audit.
- product-owner-decision-checklist.md: Decisions 1, 2, 4 refined to the corrected recommended
  defaults (deadline-authoritative late-answer; "Blocked — clarification expired" label over
  existing expired backend semantics; explicit request IS the confirmation with production-effect
  approval unchanged). All six remain advisory, NOT approved.
- test-and-validation-plan.md: added authoritative-deadline, state/outbox atomicity, resume-state-
  separation, at-least-once/idempotent, outbox relay+DLQ, and gated-dispatch tests.
- observability-and-audit-plan.md: added outbox_pending_depth / outbox_publish_retry_total /
  outbox_dead_total metrics and the durable-event reconciliation section.
- frontend-ux-boundary.md: resume UX states reframed for the gated-dispatch model.
```

## Scope and safety

```text
Backend runtime changed: NO. Frontend runtime changed: NO. API implementation changed: NO.
Database changed: NO. Migration created: NO. Workflow changed: NO. Scheduler activated: NO.
Dispatch/resume executed: NO. Deployment: NO. External notification sent: NO.
Codex authorized: NO. Claude Design authorized: NO. Step 66C.4-BE1 started: NO.
Production/external action: NO. production_executed_true_count: 0 (unaffected).
```

## Statement

Planning/remediation document only. Only planning documents, the handoff, stage records, the
verifier, and its tests were modified. No runtime, backend, frontend, API, database, migration,
workflow, scheduler, dispatch, resume, deployment, or external-notification change occurred. No role
was authorized to begin implementation. Step 66C.4-BE1 remains not started.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->

<!-- STEP66C4_PLANNING_CONTRACT_REMEDIATION_VERIFY: PASS -->
