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
  expired_at, answered_at, resume_eligible_at, resume_requested_at, resume_authorized_at,
  resume_dispatched_at, dispatch_enabled: false, resume_dispatch_enabled: false }.
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
clarification.resume_dispatched  -- NOT published by this stage's eventual implementation scope
                                     (dispatch itself is out of scope); listed here only so the
                                     event-naming contract is forward-compatible for whichever
                                     future stage builds it.
clarification.resume_failed      -- same as above -- forward-compatible naming only, not built now.
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
