# Step 66C.4-BE3-P — API, Event, Durable-Authorization and Concurrency Contract

> **Planning/contract document only. No route is registered, no endpoint implemented, no migration
> created. Paths follow the existing `/operations/*` operational-action convention
> (approval-decisions, approval-policies, audit/*, backup-dr), analogous to the existing operator
> governance surface.**

## A. Durable authorization record (design only; NO migration created here)

One authorization model backs BOTH resume and replay (shared shape, discriminated by action_type):

```text
authorization_id       (uuid, pk)
action_type            ('resume' | 'replay')
resource_type          ('clarification' | 'outbox_event')
resource_id            (clarification_id or outbox event_id)
request_id             (fk -> the resume/replay request)
requested_by           (principal id; role captured)
requested_at           (timestamptz)
authorized_by          (principal id; NULL until decided; MUST differ from requested_by for replay)
authorized_at          (timestamptz, NULL until decided)
decision               ('pending' | 'authorized' | 'rejected')
decision_reason_code   (bounded allowlist enum; never free text with raw content)
policy_result          ('allow' | 'deny' | 'not_applicable')
policy_version         (string; the evaluated policy version)
resource_state_version (the resource version the authorization is bound to)
expires_at             (timestamptz; time-bounded validity)
consumed_at            (timestamptz, NULL until single-use consumption)
idempotency_key        (deterministic; unique)
created_at, updated_at (timestamptz)
```

Binding authorization semantics (PO-recommended defaults):

```text
- resource-bound : valid only for its resource_id.
- action-bound   : valid only for its action_type.
- single-use     : consumed_at is set on execution; a consumed authorization can never be reused
                   (a replay after execution needs a NEW request + NEW authorization).
- time-bounded   : unusable after expires_at.
- state-version-bound : if resource_state_version no longer matches the resource at execution time,
                   the authorization is invalid (execution aborts, no side effect).
- revocation     : an authorization may be revoked (decision -> rejected / explicit revoke) before
                   consumption; revocation is durable and audited.
- resume and replay SHARE this model but never share an authorization_id across action types.
```

## B. API endpoints (design only; NO route added)

Resume:

```text
POST /operations/resume-requests                      actor: Operator            create a resume request
GET  /operations/resume-requests/{id}                 actor: Operator/Approver/Audit   read state
POST /operations/resume-requests/{id}/authorize       actor: policy (system) / Approver(prod)   authorize
POST /operations/resume-requests/{id}/reject          actor: Operator/Approver   reject
POST /operations/resume-requests/{id}/cancel          actor: Operator (own request) / Platform Admin
GET  /tasks/{task_id}/clarifications/{cid}/resume-eligibility   actor: Operator (existing read path)
```

Replay:

```text
POST /operations/replay-requests                      actor: Operator            create a replay request
GET  /operations/replay-requests/{id}                 actor: Operator/Approver/Audit   read state
POST /operations/replay-requests/{id}/authorize       actor: Approver (requester != approver)
POST /operations/replay-requests/{id}/reject          actor: Approver
POST /operations/replay-requests/{id}/cancel          actor: Operator (own request) / Platform Admin
GET  /operations/dead-outbox-events/{event_id}        actor: Operator/Audit      view a dead event
```

Per-endpoint contract (applies to every endpoint above):

```text
actor permission : per be3-rbac-permission-matrix.md (checked before any state read that could leak).
request schema   : minimal typed body (resource id, reason_code from a bounded allowlist); NO raw
                   clarification/answer content, NO secret/DSN.
response schema  : the resource's current state + authorization state; NO raw content; NO internal DSN.
idempotency      : create endpoints carry a deterministic idempotency key (state-bound CAS); repeat
                   calls re-confirm the same request, never create a competing one.
403              : caller lacks the action permission (or is the same principal trying to authorize
                   its own replay -> 403 two_person_required).
404 masking      : a resource the caller may not see returns 404 (never 403) so existence is not
                   leaked across team/project boundaries; a genuinely missing id also returns 404.
409              : conflicting state -- clarification_not_eligible, resume_already_requested,
                   authorization_expired, resource_state_changed, event_not_dead, already_replayed.
audit evidence   : every state-changing endpoint writes a durable audit/outbox row in the SAME
                   transaction as the state change.
transaction boundary : one transaction per state change (state + authorization + outbox commit together).
no-side-effect failure : any validation/permission failure returns before any mutation; a failed
                   execution leaves the resource recoverable (no partial commit, no consumed auth on failure).
```

## C. Event and audit contract

```text
resume.requested             -> audit stream (durable outbox); may trigger the policy evaluation.
resume.authorized            -> audit stream (durable outbox).
resume.rejected              -> audit stream (durable outbox).
resume.execution_requested   -> durable outbox -> orchestrator COMMAND (single destination).
resume.resumed               -> audit stream (durable outbox), written on orchestrator confirmation.
resume.failed                -> audit stream (durable outbox) + DLQ for operator recovery.
resume.canceled              -> audit stream (durable outbox).

replay.requested             -> audit stream (durable outbox).
replay.authorized            -> audit stream (durable outbox).
replay.rejected              -> audit stream (durable outbox).
replay.executed              -> audit stream (durable outbox); the dead->pending flip's evidence.
replay.failed                -> audit stream (durable outbox) + operator item.
replay.canceled              -> audit stream (durable outbox).
```

Classification:

```text
- Audit-only projection: requested / authorized / rejected / canceled / resumed / executed / failed
  (they record evidence; the downstream audit-worker projects them).
- Triggers an orchestrator command: resume.execution_requested ONLY (a durable outbox row consumed
  by the orchestrator; GATED/DISABLED-BY-DEFAULT until a separate activation).
- Single durable destination: EVERY event uses one durable outbox destination with a downstream
  projection. NO outbox row tracks multiple destinations. If both an audit projection and an
  orchestrator command are needed, they are SEPARATE outbox rows, each with one destination.
```

## D. Transaction and concurrency contract

Each scenario -> mechanism (locking/CAS, idempotency, state version, rollback, retry, reconciliation,
audit):

```text
1. two operators request the same resume
   -> CAS on resume_requested_at IS NULL; the loser gets an idempotent re-confirm; one request only.
2. operator authorizes while the task was canceled
   -> re-check task-terminal at authorize time (state-version-bound); decision=rejected(task_state_changed).
3. authorization expires during execution
   -> execution checks expires_at + consumed_at; expired -> abort (no side effect); 409 authorization_expired.
4. resume executes twice
   -> single-use authorization (consumed_at) + outbox UNIQUE(idempotency_key); the second is a no-op.
5. replay executes twice
   -> row must still be 'dead' + authorization single-use; the second is a no-op (already_replayed).
6. request rejected while the service begins execution
   -> execution re-reads decision under a row lock; a non-authorized decision aborts before any flip.
7. policy result changes after authorization
   -> execution is state-version-bound; a changed resource/policy version invalidates the authorization.
8. orchestrator ack lost
   -> at-least-once command redelivery with the same idempotency_key; the orchestrator dedupes;
      reconciliation compares the durable command against the task's confirmed status.
9. execution succeeds but the DB confirmation write fails
   -> the command row stays until confirmed; reconciliation re-derives from the task's own status
      (the task status is the source of truth for "resumed"); no double-dispatch (idempotency_key).
```

Formal model (binding):

```text
at-least-once command delivery + state-bound idempotency + durable authorization +
orchestrator reconciliation.  exactly-once is NOT claimed.
```

## Statement

Planning/contract document only. No route registered, no endpoint implemented, no migration created.
No dispatch/resume/replay executed. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
