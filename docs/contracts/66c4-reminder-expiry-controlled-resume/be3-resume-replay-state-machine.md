# Step 66C.4-BE3-P — Resume and Replay State Machines

> **Planning/contract document only. No state-machine code implemented. Extends the Option-A resume
> model in controlled-resume-contract.md with a durable-authorization view and adds the replay
> state machine.**

## A. Resume state machine

States (names align with controlled-resume-contract.md; the durable authorization record backs the
authorization-bearing transitions):

```text
not_eligible -> eligible -> request_pending -> authorization_pending -> authorized
  -> execution_pending -> resumed
  (side exits: rejected, canceled, failed, expired)
```

Per-transition contract:

```text
not_eligible -> eligible
  Authoritative source: DB (operator_clarification_requests + operator_tasks).
  Actor:        answer-claim path (system, in the answer transaction).
  Precondition: status='answered' AND task not terminal at answer time.
  Idem key:     {clarification_id}:resume_eligible.
  Tx boundary:  same transaction as the answer-claim; resume_eligible_at set + outbox row.
  Audit event:  resume.eligible (a.k.a. clarification_resume_eligible).
  Failure:      task terminal -> eligibility NOT granted (resume_eligible_at stays NULL). No retry.
  Terminal?     no.

eligible -> request_pending
  Actor:        Operator (pm_engineering_lead | platform_admin | agent_operator), captured as requested_by.
  Precondition: eligible; resume_requested_at IS NULL (CAS); task not terminal; policy allows continuation.
  Idem key:     {clarification_id}:resume_requested.
  Tx boundary:  one transaction: CAS on resume_requested_at + resume_requested_by + outbox row.
  Audit event:  resume.requested.
  Failure:      409 clarification_not_eligible; duplicate -> idempotent re-confirm (no second request).
  Terminal?     no.

request_pending -> authorization_pending -> authorized
  Actor:        automated policy/safety evaluation (no human authorizer for non-production resume).
  Precondition: RE-EVALUATE §2 conditions at authorization time (task-non-terminal recheck,
                production-effect recheck, waiting-point invariant) AND resume_authorized_at IS NULL (CAS)
                AND resume_eligible_at IS NOT NULL; a durable authorization record is written.
  Idem key:     {clarification_id}:resume_authorized.
  Tx boundary:  one transaction: CAS on resume_authorized_at + durable authorization record + outbox row.
  Audit event:  resume.authorized (or resume.rejected on a negative decision, with reason_code).
  Failure:      recorded NOT authorized with reason (task_state_changed / production_effect_blocked /
                policy_denied); transient failures re-attempt, terminal failures become operator items.
  Terminal?     no (authorized) / rejected is terminal.

authorized -> execution_pending -> resumed   [built in BE3, GATED/DISABLED-BY-DEFAULT]
  Actor:        Service Identity publishes a durable resume command; the orchestrator CONFIRMS resumed.
  Precondition: valid, unexpired, unconsumed authorization; task not production-effect (unless prod
                approval present); dispatch enabled (hardcoded false until a separate authorization).
  Idem key:     {clarification_id}:resume_dispatched (outbox), consumed-once authorization.
  Tx boundary:  command publish is a durable outbox row (single destination); the resumed state is the
                TASK's own status transition confirmed by the orchestrator (no resumed_at column).
  Audit event:  resume.execution_requested then resume.resumed (orchestrator confirmation).
  Failure:      resume.failed -> DLQ + operator recovery; the authorization stays consumed (a fresh
                request/authorization is required, never a silent re-dispatch).
  Terminal?     resumed / failed are terminal.

side exits:
  rejected  (authorization negative), canceled (Operator cancels a pending request before execution),
  failed    (execution failed after bounded retries), expired (authorization expiry elapsed).
  All four are terminal for this attempt; recovery is a NEW request, never an in-place mutation.
```

Forbidden collapses (restated, binding):

```text
- operator request == workflow resumed        : FORBIDDEN.
- authorization only in memory                 : FORBIDDEN (must be a durable record).
- authorization succeeds but no durable evidence: FORBIDDEN.
- orchestrator executes and skips the policy re-check: FORBIDDEN.
```

## B. Replay state machine

```text
dead -> replay_requested -> replay_authorization_pending -> replay_authorized
  -> replay_execution_pending -> replayed (row: dead -> pending)
  (side exits: replay_rejected, replay_canceled, replay_failed, replay_expired)
```

Per-transition contract:

```text
dead (precondition)
  Only an outbox row in status='dead' may be the subject of a replay request. attempts are NOT reset.

dead -> replay_requested
  Actor:        Operator; captured as requested_by.
  Precondition: target row status='dead'; no active (non-terminal) replay request for this event_id.
  Idem key:     {event_id}:replay_requested.
  Tx boundary:  one transaction: durable replay-request record + audit outbox row.
  Audit event:  replay.requested.
  Failure:      404-masked if the event is not visible to the caller's team; 409 if already requested.

replay_requested -> replay_authorization_pending -> replay_authorized
  Actor:        Approver (reviewer_approver | platform_admin), requester != approver (two-person, D2).
  Precondition: request active; the row is STILL status='dead' at authorization time (re-check);
                a durable authorization record is written (single-use, time-bounded, state-version-bound).
  Idem key:     {event_id}:replay_authorized (+ authorization_id).
  Tx boundary:  one transaction: authorization record (decision) + audit outbox row.
  Audit event:  replay.authorized (or replay.rejected with reason_code).

replay_authorized -> replay_execution_pending -> replayed
  Actor:        Service Identity calls the internal replay_dead adapter under the durable authorization.
  Precondition: authorization valid/unexpired/unconsumed AND the row is STILL 'dead' AND the row's
                state version matches the authorized version (else abort -> replay_rejected).
  Effect:       replay_dead(event_id): status dead -> pending, event_id + idempotency_key PRESERVED,
                attempts NOT reset, available_at reset. The authorization is CONSUMED (single-use).
  Idem key:     event_id + idempotency_key are unchanged (at-least-once identity on re-publish).
  Tx boundary:  one transaction: dead->pending + authorization consumed + audit outbox row.
  Audit event:  replay.executed.
  Failure:      replay.failed -> operator item; if the row is no longer 'dead' (already replayed) the
                execution is a NO-OP that records replay.executed(idempotent) without a second flip.

side exits: replay_rejected, replay_canceled, replay_expired, replay_failed (all terminal for the attempt).
```

Replay hard rules (binding):

```text
- Only a dead row may be requested; a non-dead row -> 409/no-op (never a second dead->pending flip).
- event_id and idempotency_key are preserved; attempts are never reset.
- Downstream duplicate risk is bounded by the unchanged idempotency_key (consumers dedupe);
  exactly-once is NOT claimed.
- No public API calls replay_dead directly; no Admin Console touches the repository directly; a
  Service Identity may never both request and authorize; replay never bypasses policy or audit.
```

## C. Shared invariants

```text
Authoritative source: the DB row + the durable authorization record (never in-memory only).
Idempotency: per-transition deterministic keys above; each fires at most once per resource.
Transaction boundary: each state change and its audit/outbox row commit atomically (both or neither).
Retry: transient failures re-attempt on the persisted backoff; terminal failures become operator items.
Terminal states: resumed/failed/rejected/canceled/expired (resume); replayed/replay_failed/
  replay_rejected/replay_canceled/replay_expired (replay). Recovery is always a NEW request.
```

## Statement

Planning/contract document only. No state-machine code implemented. No dispatch/resume/replay
executed. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
