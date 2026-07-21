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
5. resume dispatched     -- the backend has actually sent the resume signal to the workflow engine.
                            NOT built by this stage's implementation scope at all (see
                            implementation-stage-slicing-plan.md) -- this stage designs the contract
                            up to and including "authorized," and explicitly stops before "dispatched."
6. workflow resumed      -- the workflow engine has actually continued execution. Downstream of
                            dispatch; out of this stage's scope entirely.
```

Each of these six is a **separate, independently-observable, independently-audited event**. No
code anywhere in this contract may collapse two of them into a single step (e.g., "answering
automatically resumes" is explicitly forbidden by this contract).

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
5. No prior resume_dispatched_at already exists for this clarification (prevents double-dispatch).
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

## 11. Resume idempotency key

```text
{clarification_id}:resume -- deterministic, since at most one resume lifecycle exists per
  clarification (matches the "no prior resume_dispatched_at" condition in §2.5).
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
clarification_answered (existing) -> resume_eligible (new) -> [resume_requested (new, Option A
  only)] -> resume_authorized (new) -> [resume_dispatched (new) -- NOT implemented by this stage's
  eventual implementation scope; recorded here only so the audit trail's own shape is complete and
  forward-compatible].
```

## 14. Failure / retry / DLQ behavior

```text
A failure between "authorized" and "dispatched" (e.g. the not-yet-built dispatch call itself
  fails) reuses the existing retry-scheduler/DLQ infrastructure exactly as any other service-to-
  service failure in this project does -- no new failure-handling mechanism is proposed. Since
  "dispatched" is out of this stage's implementation scope entirely, this is stated here as a
  forward-looking design note for whichever future stage actually builds dispatch, not something
  this stage resolves.
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
