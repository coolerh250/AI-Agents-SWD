# Controlled Resume Contract — Step 66C.4-P

> **Planning document only. No workflow dispatch or resume performed. No resume code path
> implemented. This is the single most important safety boundary in this stage's entire output.**

## Distinct states (never conflated)

```text
1. answer recorded       -- operator_clarification_requests.status = 'answered', answered_at set
                            (already exists, Step 66C.3).
2. resume eligible       -- the clarification is answered AND the task's workflow is still at the
                            same waiting point it was at when the clarification was raised (i.e.
                            no cancel/abort/terminal transition occurred in between). This is a
                            NEW, distinct state from "answered" -- an answer does not automatically
                            imply eligibility if the workflow moved on for some other reason.
3. resume requested      -- (Option A only) an authorized actor has explicitly asked for the task
                            to resume. Does not exist under Option B.
4. resume authorized     -- the request (Option A) or the automatic eligibility check (Option B)
                            has passed its policy/safety check. This is the gate immediately before
                            any dispatch.
5. resume dispatched     -- the backend publishes a durable resume event. Designed by this planning
                            stage; the dispatch MECHANISM is built in 66C.4-BE3 but is
                            GATED/DISABLED-BY-DEFAULT (dispatch_enabled is hardcoded false today and
                            stays false until a separate authorization). This planning stage (66C.4-P)
                            builds nothing.
6. workflow resumed      -- the orchestrator CONFIRMS the workflow's own loop actually continued.
                            Designed here; the confirmation handler is built in 66C.4-BE3. Distinct
                            from "dispatched": dispatch does not imply resumed until confirmed.
```

Each of these six is a **separate, independently-observable, independently-audited event**. No
code anywhere in this contract may collapse two of them into a single step (e.g., "answering
automatically resumes" is explicitly forbidden by this contract).

## Binding resume state model (per-transition contract — added in Step 66C.4-P-R1)

The state machine, with each transition's actor / trigger / precondition / persisted evidence /
audit event / idempotency key / failure state / retry-recovery. **Under Option A**, the four roles
are strictly distinct: the Operator REQUESTS, the automated policy/safety evaluation AUTHORIZES, a
Dispatcher DISPATCHES, and the Workflow/orchestrator CONFIRMS the resumed state. An operator's
request is **never** equivalent to the workflow having resumed.

```text
ANSWERED -> RESUME_ELIGIBLE
  Actor:        answer-claim path (system, in the answer transaction).
  Trigger:      a successful answer-claim on a non-terminal task.
  Precondition: status just became 'answered' AND task not terminal at answer time.
  Evidence:     resume_eligible_at set (column) + outbox row.
  Audit event:  clarification_resume_eligible.
  Idem key:     {clarification_id}:resume_eligible.
  Failure:      if task already terminal, eligibility is NOT granted (resume_eligible_at stays NULL).
  Retry/recov:  none needed; re-derived from persisted state.

RESUME_ELIGIBLE -> RESUME_REQUESTED  (Option A only)
  Actor:        an authorized Operator/PM-Lead/Platform-Admin (human), captured in
                resume_requested_by.
  Trigger:      explicit POST .../resume-request action.
  Precondition: §2 conditions hold; resume_requested_at IS NULL (CAS).
  Evidence:     resume_requested_at + resume_requested_by set + outbox row.
  Audit event:  clarification_resume_requested.
  Idem key:     {clarification_id}:resume_requested.
  Failure:      409 clarification_not_eligible (conditions unmet) or idempotent re-confirm (§10).
  Retry/recov:  operator may re-request; CAS makes it idempotent.

RESUME_REQUESTED -> RESUME_AUTHORIZED
  Actor:        the automated policy/safety evaluation (NOT a human; there is no human "authorizer"
                -- this is why no resume_authorized_by column exists, per data-model-contract.md).
  Trigger:      synchronous policy/safety check invoked by the request handler.
  Precondition: §2 conditions RE-EVALUATED at authorization time (incl. task-non-terminal recheck,
                §7/§16) AND resume_authorized_at IS NULL (CAS) AND resume_eligible_at IS NOT NULL.
  Evidence:     resume_authorized_at set (column) + outbox row carrying the decision/reason (the
                policy-decision evidence lives in the durable outbox/audit event, not a column --
                no policy_decision_id column, per data-model-contract.md).
  Audit event:  clarification_resume_authorized.
  Idem key:     {clarification_id}:resume_authorized.
  Failure:      recorded as NOT authorized with reason (e.g. task_state_changed,
                production_effect_blocked); a repeated policy failure is an operator item
                (race-condition-and-failure-analysis.md recovery-semantics split).
  Retry/recov:  transient failures re-attempt; terminal failures are operator-recovered.

RESUME_AUTHORIZED -> RESUME_DISPATCHED   [designed here; built in 66C.4-BE3, GATED/DISABLED-BY-DEFAULT]
  Actor:        a Dispatcher that publishes a DURABLE resume event (an outbox row -> resume event).
  Trigger:      an authorized resume whose dispatch is enabled.
  Precondition: resume_authorized_at IS NOT NULL AND task NOT production-effect AND
                dispatch is enabled (dispatch_enabled -- currently hardcoded false everywhere, per
                current-state-assessment.md; remains false until a SEPARATE authorization flips it).
  Evidence:     a durable outbox resume event (idempotency_key {clarification_id}:resume_dispatched)
                -- NOT a new lifecycle column. Per data-model-contract.md, dispatch is represented
                by durable outbox/audit evidence, keeping the clarification-table columns minimal;
                no resume_dispatched_at / resume_dispatch_event_id column is added.
  Audit event:  clarification_resume_dispatched.
  Idem key:     {clarification_id}:resume_dispatched.
  Failure:      DLQ + operator recovery (race-condition-and-failure-analysis.md scenarios 11, 17).
  Note:         because dispatch_enabled is false by default, 66C.4-BE3 builds the dispatch
                MECHANISM but does not turn on real production-effecting resume; enabling it is a
                separate, explicit authorization.

RESUME_DISPATCHED -> WORKFLOW_RESUMED    [designed here; orchestrator confirmation built in 66C.4-BE3]
  Actor:        the workflow/orchestrator, which CONFIRMS the actual resumed state (it does not
                merely trust that dispatch happened).
  Trigger:      the orchestrator's confirmation handler observing the task's loop actually continued.
  Precondition: a durable resume event has been published (the dispatch transition completed).
  Evidence:     the task's own status transition + a durable outbox/audit confirmation event
                (no dedicated resumed_at column on the clarification -- the TASK's own status is the
                source of truth for "resumed"; see data-model-contract.md).
  Audit event:  clarification_workflow_resumed (or the task-level resume audit event).
  Note:         "Authorized", "dispatched", and "resumed" are THREE separate states. Reaching
                "authorized" -- or even "dispatched" -- does NOT mean the workflow has resumed; only
                the orchestrator's confirmation establishes WORKFLOW_RESUMED. An operator's request
                is never equivalent to any of these later states.
```

## 1. How an answer becomes resume-eligible

```text
Immediately upon a successful answer-claim (the existing CAS transition to status='answered'),
  the backend evaluates eligibility as a synchronous, deterministic check (not a separate async
  worker cycle) -- because the check only needs the just-updated row and the task's current
  workflow state, both already in hand at that point:
  1. The clarification's own status is now 'answered' (guaranteed by the CAS that just fired).
  2. The task's status has NOT transitioned to a terminal or unrelated state since the
     clarification was raised (i.e., task.status is still clarification_needed at the moment of
     answering -- if a concurrent operation already moved the task to canceled/archived/rejected,
     eligibility is NOT granted; see race-condition-and-failure-analysis.md scenario 7).
  3. If both hold, resume_eligible_at is set (see data-model-contract.md) in the same transaction
     as the answer-claim.
```

## 2. Conditions that must hold for resume to proceed

```text
1. Clarification status = 'answered' (not 'expired'/'canceled' -- those never become eligible).
2. resume_eligible_at IS NOT NULL.
3. Task status has not changed to a terminal state (canceled/archived/rejected/accepted) since
   resume_eligible_at was set.
4. The task is NOT flagged production-effect (per the existing `production_effect` safety field
   already surfaced on TaskDetail -- a production-effect task remains blocked regardless of
   resume eligibility; see rbac-and-safety-contract.md's safety invariants).
5. resume_authorized_at IS NULL for this clarification (authorize-at-most-once). NOTE (corrected in
   Step 66C.4-P-R1): there is no resume_dispatched_at COLUMN. Dispatch is built gated/disabled-by-
   default in 66C.4-BE3 and represented by a durable outbox resume event; its double-DISPATCH guard
   is the outbox UNIQUE(idempotency_key {clarification_id}:resume_dispatched), not a column on this
   table. The pre-dispatch guard here is authorize-once via resume_authorized_at.
```

## 3. Who may request resume (Option A) / who the automatic check applies to (Option B)

```text
Option A: pm_engineering_lead, platform_admin, agent_operator (the same roles already trusted with
  clarification-creation and operational actions elsewhere in this system -- reusing an existing,
  already-vetted role set rather than inventing a new one).
Option B: no "requester" role exists -- the automatic policy/safety check runs for every eligible
  clarification uniformly; the "who" question becomes "who may configure/override the policy,"
  which is Claude-Code-owned architecture, not a per-request actor.
```

## 4. Who may authorize resume

```text
Both options: the SAME policy/safety check function, regardless of who (or what) requested it.
  This function is the actual safety boundary -- see §4 below is really "what does the check
  verify," which is exactly the "conditions that must hold" list in §2 plus (if Option A)
  confirming the requester had a permitted role. No human "authorizes" by fiat outside this
  check -- an operator's resume REQUEST is not itself an authorization; the check is.
```

## 5. Does it require explicit Operator action?

```text
Option A: YES, by definition -- an operator (or PM/Eng Lead, or Platform Admin) must take an
  explicit UI/API action to request resume, after which the automated check still gates it.
Option B: NO -- eligibility + the automated policy/safety check is sufficient; no human clicks
  anything. This is the core product-experience difference between the two options (see the
  comparison table below).
```

## 6. Controlled internal automatic resume — is it ever allowed?

```text
Under Option B, yes, by design -- that IS Option B. Under Option A, no -- resume never happens
  without the explicit request step. This is exactly why this is presented as a genuine two-option
  comparison rather than a single recommendation with no alternative: it is a real product-
  behavior fork, not a technical implementation detail (see product-owner-decision-checklist.md
  item 3).
```

## 7. Workflow-waiting-point invariant

```text
Resume must verify, at authorization time (not just at eligibility time -- these can be minutes
  or hours apart under Option A), that the workflow is STILL at the same waiting point it was at
  when eligibility was granted. If anything else moved the task's state in the interim (e.g. an
  operator manually intervened, or -- while unlikely given no other code path currently exists --
  a future feature introduces a new transition), resume must NOT proceed and must instead surface
  a clear "no longer eligible" result rather than dispatching against stale state.
```

## 8. Cancel/abort/terminal protection

```text
Any of operator_tasks.status IN ('canceled','archived','rejected','accepted') at authorization
  time unconditionally blocks resume, regardless of how far the resume-request/eligibility chain
  had already progressed. This is enforced by the SAME check described in §2.3, re-evaluated at
  authorization time, not only at eligibility time (see race-condition-and-failure-analysis.md
  scenario 7 for the exact interleaving this protects against).
```

## 9. Expired clarification late-answer handling

```text
Per lifecycle-and-time-contract.md §7.3 item 6: once a clarification has actually transitioned to
  status='expired' (i.e., the expiry-claim already won the race), no answer can succeed against it
  (the existing 409 invalid_state_for_answer:{status} path already covers this with zero new
  code) -- and therefore no resume-eligibility chain can ever begin for an expired clarification.
  There is no separate "late answer resume" case to design: expired and answered are mutually
  exclusive terminal outcomes of the same CAS race.
```

## 10. Duplicate resume request handling (Option A)

```text
A second resume-request against a clarification whose resume_requested_at is already set is
  idempotent by design: the request handler checks resume_requested_at IS NULL as its own CAS
  guard (identical pattern to the existing answer-claim), so a duplicate request either (a) is a
  no-op if the first request already progressed past authorization, returning the current state,
  or (b) simply re-confirms the same pending request if authorization hasn't yet completed -- it
  never creates two competing resume attempts.
```

## 11. Resume idempotency keys

```text
Per-transition deterministic keys (each fires at most once per clarification):
  resume-request    : {clarification_id}:resume_requested
  resume-authorized : {clarification_id}:resume_authorized
Deterministic and derivable from the clarification id alone, matching the authorize-at-most-once
  condition in §2.5 (corrected in Step 66C.4-P-R1 -- no longer keyed on the removed
  resume_dispatched_at column).
```

## 12. Optimistic locking / compare-and-set

```text
Same idiom as every other transition in this contract: a WHERE-clause guard on the relevant
  nullable timestamp column (e.g. `WHERE resume_requested_at IS NULL` for the request step,
  `WHERE resume_authorized_at IS NULL AND resume_eligible_at IS NOT NULL` for the authorization
  step) -- no new locking primitive introduced.
```

## 13. Resume audit sequence

```text
clarification_answered (existing) -> clarification_resume_eligible (new) ->
  [clarification_resume_requested (new, Option A only)] -> clarification_resume_authorized (new).
Each new audit event is written via a durable outbox row committed in the SAME transaction as its
  state transition (api-and-event-contract.md §11.3), so the audit trail cannot be silently lost.
The dispatched/resumed audit events (clarification_resume_dispatched, clarification_workflow_resumed)
  are written by 66C.4-BE3's gated dispatch + confirmation handlers via durable outbox rows; because
  dispatch_enabled is false by default they are not emitted in normal operation until dispatch is
  separately enabled. This planning stage (66C.4-P) writes none of them.
```

## 14. Failure / retry / DLQ behavior

```text
A failure between "authorized" and "dispatched" (the durable resume-event publish fails) is handled
  by the transactional-outbox model (api-and-event-contract.md §11.3): the resume-event outbox row
  is durable, re-published by the relay, and after bounded retries dead-lettered for explicit
  operator recovery (race-condition-and-failure-analysis.md scenarios 11, 17). Dispatch is built
  (gated/disabled-by-default) in 66C.4-BE3; because dispatch_enabled is false by default, no real
  production workflow is affected until a separate authorization enables it. No new failure-handling
  mechanism beyond the existing retry-scheduler/DLQ + outbox is introduced.
```

## 15. Production-effect task protection

```text
A task flagged production_effect=true (existing safety field, already surfaced on TaskDetail)
  remains BLOCKED from resume regardless of how far the eligibility/authorization chain has
  progressed -- this is a hard, non-negotiable invariant restated from rbac-and-safety-contract.md,
  not something either Option A or Option B may override.
```

## Option comparison

| Dimension | Option A — Explicit operator-controlled resume | Option B — Policy-controlled automatic resume |
| --- | --- | --- |
| Product experience | Matches this project's established "no implicit auto-resume" posture exactly (core-loop-experience-definition.md: "Paused — will not resume automatically"); an operator sees a clear "ready to resume" state and takes a deliberate action | Faster for the requester (no extra click), but risks reading as "the system resumed itself," which the Master Plan's own UX definition explicitly warns against ("answering never implies auto-dispatch/resume") |
| Safety | Strictly safer: a human decision point exists between eligibility and dispatch, matching the project's standing safety posture for every other consequential action | Weaker by design — relies entirely on the automated policy/safety check being complete and correct, with no human backstop; any gap in the check's logic becomes a real safety gap with no operator catching it first |
| Race conditions | Same underlying CAS mechanics either way; Option A has one MORE state transition (the request step) which is one more opportunity for a race, but each is independently guarded | Fewer states means fewer race windows, but a bug in the automatic check has a larger blast radius since nothing else stops it |
| Auditability | Naturally richer — the audit trail records WHO asked and WHEN, in addition to WHY it was authorized | Audit trail records only the automated decision, no human-requester attribution |
| Implementation complexity | Slightly higher (one more endpoint, one more state, one more RBAC check) | Slightly lower (no request endpoint, no requester RBAC) |
| Operator burden | Adds an explicit step operators must remember to take — a real UX cost if clarifications are frequent | Zero added operator burden |
| Failure recovery | An operator can simply re-request if something went wrong, with full visibility into "did I already ask" | Recovery from a failed automatic resume requires the same technical retry mechanics either way; no behavioral difference here |
| Production-effect risk | Lower — matches this project's established pattern of gating every consequential action behind an explicit human action (e.g. deployment/merge authorizations throughout this project's entire history) | Higher — introduces this project's first-ever automatic (non-human-triggered) state transition with real workflow effect, a meaningful precedent |

## Recommended option: **Option A — Explicit operator-controlled resume**

```text
Rationale: this project has, without exception, gated every consequential action behind an
  explicit human decision throughout its entire history (merge authorizations, deployment
  authorizations, production authorizations, external-send authorizations) -- Option B would be
  the FIRST automatic, non-human-triggered state transition with real workflow effect anywhere in
  this project. That is a significant behavioral precedent, not a routine technical choice, and
  this contract does not adopt it unilaterally.
```

**This recommendation changes established product behavior (introducing the first-ever automated
resume path would be Option B; recommending against it preserves the existing all-explicit-
authorization pattern) and is therefore listed in product-owner-decision-checklist.md item 3 as a
genuine PO decision, not silently adopted.**

## Statement

Planning document only. No workflow dispatch or resume performed. No resume code path
implemented.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
