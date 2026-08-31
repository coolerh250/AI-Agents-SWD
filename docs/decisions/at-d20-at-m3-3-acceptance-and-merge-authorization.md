# AT-D20 — AT-M3.3 Bounded Team Discussion product acceptance & canonical merge authorization

> **Product Owner decision record. Accepts AT-M3.3 and authorizes merging the exact validated
> candidate into `main`. Authorizes no real external LLM call (M3.6B), no production action, no
> AT-M4 execution, no AT-M3.4 runtime, no PCP remediation and no P3 backlog work.
> `production_executed_true_count: 0`.**

```text
AT-D20:                      RESOLVED / BINDING
Recorded_on:                 2026-08-31
Recorded_by:                 Product Owner
Canonical_main_at_decision:  2af3564a6f83b7a195d8a637aa856d52ea6d4016
Validated_candidate:         4f1003c083b722c3e724f79d9998f910c991ee80
Implementation_end:          4f1003c083b722c3e724f79d9998f910c991ee80
Branch:                      at-m3.3-bounded-team-discussion-1
Depends_on:                  AT-D14 (docs/decisions/at-d14-at-m3-live-reasoning-authorization.md)
                             AT-D18 (docs/decisions/at-d18-project-governance-reset.md)
                             AT-D19 (docs/decisions/at-d19-at-m3-2-acceptance-and-merge-authorization.md)
```

`Implementation_end` is the exact byte state that was independently validated. This record and the
PM/progress reconciliation it authorizes create a later branch tip; `Implementation_end` does not
move with it. Acceptance attaches to a commit, not to a branch name.

## 1. What this record is for

AT-D14 authorized non-production, non-external-network implementation of AT-M3.1 through AT-M3.6A.
It said nothing about accepting a specific AT-M3.3 implementation or merging one into `main`. This
record is that separate authorization: the Product Owner accepts the AT-M3.3 capability (bounded,
capability-aware team discussion) as validated, and approves canonicalizing the exact validated
candidate.

Same shape as AT-D13 for AT-M2, AT-D15 for AT-M3.1 and AT-D19 for AT-M3.2: implementation
authority and merge authority are separate decisions, and the second one names the commit. It is
the only place the AT-M3.3 acceptance and merge authorization is recorded.

## 2. Accepted product capability

Accepted exactly as validated, and no wider:

```text
durable bounded team discussion runtime
reuse of ConversationThread / TeamMessage -- no competing conversation or message hierarchy
Goal and exact PlanRevision binding
capability-aware participant selection from the existing Project team and AT-M2 router
persisted round / message / invocation / per-participant-turn bounds
database-clock deadline_at elapsed-time bound
exact deterministic stop reasons, one per bound
AT-M3.1 ReasoningInvocation integration only -- no direct provider call
no raw or hidden reasoning persistence
exactly one canonical turn, reasoning invocation and TeamMessage per slot
duplicate-start idempotency
durable restart / resume from rows alone
crash-window fail-closed behaviour
explicit stale-revision rejection at open
mid-flight PlanRevision supersession neither terminates nor rebinds a discussion
derived plan_revision_is_current / current_plan_revision_id read fields
a stale convergence remains historical evidence
M3.2 compare-and-swap is the future M3.4 stale-consumption safety boundary
migration 039 up / down / reapply safety
no AT-M3.4 runtime
no AT-M3.5 dispatch
no external provider or network access
no production action
```

This list is the acceptance boundary. Capability not named here is not accepted by this record,
whether or not code for it happens to exist.

## 3. What is authorized

```text
Merge scope:                   fast-forward canonicalization of the exact validated candidate
                               4f1003c into main
Documentation-only authority:  this record and the bounded PM/progress reconciliation commit it
                               authorizes
Post-merge verification:       bounded product and source-of-truth checks only
```

## 4. What is NOT authorized

```text
M3.6B / real external LLM calls  NOT AUTHORIZED -- unchanged from AT-D14, no path to one is added
External model credentials       NOT AUTHORIZED
Production action                NOT AUTHORIZED -- unchanged, no path to one is added
Production authorization         NOT GRANTED -- unchanged
AT-M4 implementation             NOT AUTHORIZED -- execution, DebugAttempt and the debug -> replan
                                   back-edge all remain out of scope
AT-M3.4 implementation           NOT STARTED by this record -- AT-D14 already authorizes the work;
                                   AT-M3.4 still needs its own implementation report and its own
                                   Validation 1/2 pass before it can be accepted the way AT-M3.3 is
                                   accepted here. In particular the M3.4 consumption contract in
                                   section 5 below is a specification it must satisfy, not code
                                   this record ships.
AT-M3.5 .. AT-M3.6A              unchanged -- authorized under AT-D14, none accepted here
PCP remediation                  NOT AUTHORIZED by this record
P3 backlog remediation           NOT AUTHORIZED by this record -- see section 7
Unrelated runtime changes        NOT AUTHORIZED -- this record covers AT-M3.3 acceptance and its
                                   merge only
```

## 5. The M3.4 consumption contract this acceptance carries forward

Recorded in `docs/architecture/autonomous-team/planning-and-plan-revision-model.md` section 11 by
AT-M3.3-PLAN-STALENESS-DESIGN-REVIEW-1, and preserved unchanged by this acceptance. A future M3.4
may consume an M3.3 discussion outcome only when all of the following hold:

```text
1  discussion.state = 'converged'
2  discussion.stop_reason = 'convergence_reached'
3  discussion.result_message_id IS NOT NULL
4  discussion.goal_id is the Goal being planned
5  discussion.plan_revision_id is still that Goal's CURRENT revision,
   or is NULL and the Goal still has no revision
```

The safety-critical write must use the existing AT-M3.2 compare-and-swap:

```text
create_successor_revision(
    goal_id                      = discussion.goal_id,
    expected_current_revision_id = discussion.plan_revision_id,
    reason                       = 'team_decision',
    trace_ref                    = discussion.result_message_id )
```

A separate `is_current()` pre-read may improve error reporting. It is explicitly **not** the safety
boundary; the compare-and-swap is, because it fails closed inside PostgreSQL rather than in an
application check a future implementer could omit. Where the discussion is bound to no revision,
`create_initial_revision` and `uq_plan_revisions_one_root_per_goal` give the same guarantee.

This record does not implement any of it.

## 6. Validation evidence — recorded here, not re-run by this decision

AT-M3.3 went through the bounded remediation policy AT-M1 established and AT-D18 restated:
Validation 1 -> at most one remediation -> Validation 2, no Validation 3.

```text
AT-M3.3 Independent Validation 1: FAIL
  B1  No elapsed-time bound existed. AT-D14 section 2 names "max-rounds/timeout/budget bounds",
      and only the count bounds were implemented. Because a counter moves only when a worker moves
      it, a discussion whose worker died mid-turn -- a claimed turn against a ReasoningInvocation
      left 'started' forever -- could reach no bound at all and stayed `open` permanently.
  B2  Two bounds reported under other bounds' names. A per-participant turn cap was recorded as
      `round_limit_reached`, naming a limit the discussion had not approached; and a team whose
      capabilities were fully covered but which seated fewer than the minimum participants was
      recorded as `insufficient_capability_coverage`, pointing a reader at the roster's skills
      rather than its size.
  Plus a DESIGN FINDING rather than an implementation defect: the approved architecture did not
  say what an in-flight discussion means once the PlanRevision it is bound to stops being current.
  Per the execution standard section 5, validation returned it and STOPPED instead of implementing
  a fix inside the validation round.

AT-M3.3-PLAN-STALENESS-DESIGN-REVIEW-1: DESIGN_RESOLVED
  Selected canonical semantic: a discussion is about an EXACT, IMMUTABLE PlanRevision, permanently.
  Mid-flight supersession does not terminate, mutate, rebind or flag it. Staleness is DERIVED from
  AT-M3.2 lineage at read time and stored nowhere, and the rule that protects the plan lives in the
  M3.4 consumption contract (section 5), where the risk actually is. Grounded in
  source-of-truth-and-lineage-model.md R5 (collaboration lineage is parallel to execution lineage,
  not subordinate to it) and planning-and-plan-revision-model.md section 7, which already decided
  that in-flight work overtaken by a replan is carried forward and marked, never destroyed.
  Authority: ARCHITECT_DECISION_SUFFICIENT. No new PO decision was required, no schema was added.

AT-M3.3-IMPLEMENTATION-REMEDIATION-1 (bounded, single pass):
  - B1: discussion_sessions.deadline_at TIMESTAMPTZ NOT NULL, computed by PostgreSQL at insert and
    frozen by the same trigger clause that freezes the four count bounds. Every session read
    carries (now() >= deadline_at) evaluated by the database, so every worker shares one clock.
    Enforced at four points: before a slot is claimed, on encountering a slot another worker holds,
    after the provider returns and before anything is written, and at the round boundary. A
    stuck 'started' invocation now closes the discussion `exhausted / timeout_reached`, with the
    abandoned invocation preserved, never re-invoked and never deleted, and no message invented.
  - B2: `participant_turn_limit_reached` and `insufficient_participants` added, so all five bounds
    carry distinct reasons, enforced by CHECK. Precedence is applied in the WHERE clause -- every
    non-timeout closure is written under `now() < deadline_at` and falls back to the timeout when
    refused -- so two workers at the same boundary cannot record different reasons.
  - D1: exact-revision semantics implemented with NO schema change. Opening explicitly against an
    already-superseded revision is refused before any write; mid-flight supersession changes
    nothing about the discussion; currency is exposed as two derived read fields and stored nowhere.
  - Migration 039 was amended in place rather than superseded by a 040: it has never been canonical
    on main. It also now refuses to run over an earlier draft of itself, because the repository's
    forward-only runner plus CREATE TABLE IF NOT EXISTS would otherwise report success over a
    table with no deadline_at.

AT-M3.3 Independent Validation 2 / 2 (final): PASS
  B1 closed, B2 closed, the design finding resolved and implemented. Six residual observations were
  carried out as non-blocking backlog and are recorded in section 7 rather than remediated.
```

Validation 2 PASS. No blockers. No Validation 3 required or permitted. This record does not claim
Validation 2 was performed by the acceptance or merge step — it was performed independently,
against `4f1003c`, before this decision, and this record states its result rather than re-deriving
it.

## 7. Retained non-blocking backlog

Recorded here so they are not rediscovered as if new. None of them blocks AT-M3.3 acceptance or
this merge, and none is authorized for remediation by this record.

```text
1  Residual TOCTOU between the post-provider re-read and the message write. The deadline is
   re-checked after reasoning returns and before anything is persisted, which closes the realistic
   window, but forced injection between those two steps can still land a TeamMessage and a recorded
   turn after the deadline. What stays protected in that case is everything that carries a claim:
   the terminal state, the stop reason, the budget counters and result_message_id are all still
   correct, so an expired discussion cannot be made to look converged or to have run longer than
   it did. Closing the remaining window means writing the message and the turn inside one
   transaction that re-checks the deadline, which is a bounded change and is not authorized here.

2  STOP_REASON_PRECEDENCE is a declarative constant. The precedence it names is real, but it is
   enforced by control flow plus the database guards on close_session, not by any code reading the
   constant. The constant and the implementation can therefore drift apart without a test noticing.

3  Crash-window B still reports `reasoning_provider_failure` when the provider SUCCEEDED and the
   message persistence failed. The discussion fails closed, which is the safe outcome; the reason
   names the wrong participant in the failure. Inherited from the original slice, not introduced by
   the remediation.

4  discussion_turns.speaker_principal_id has no direct foreign key to discussion_participants. It
   references actor_principals, and the service path is what enforces that a speaker is actually
   seated in this discussion. A raw-SQL writer could record a turn for a non-participant.

5  A challenge with zero concern_count is unreachable through classify_intent, which routes a
   concern-free critique to support or clarification. The branch is dead rather than wrong.

6  Inherited content-screening backlog: the semantic forbidden-key screen misses some equivalent
   markers, and there is no free-text value screening. Predates AT-M3.3.
```

Under AT-D18-R05 these are `NON-BLOCKING` by default: none reaches a production-authorization,
human-approval, external-model, secret-handling, destructive-action, audit-integrity or
security-boundary control. Items 1, 4 and 6 are additionally `PRE-PRODUCTION` — real, and to be
closed before production authorization, gating no non-production milestone. They become blocking
only on concrete P0/P1 evidence, which does not exist today.

## 8. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B or any real external LLM/network call
Does NOT authorize AT-M3.4 .. AT-M3.6A implementation -- AT-D14 already authorizes that work; this
   record accepts and merges AT-M3.3 only
Does NOT implement the M3.4 consumption contract in section 5 -- it records a specification
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT authorize AT-M4
Does NOT relax TASK_ROLES, RBAC, policy or approval
Does NOT retire, reduce or reclassify PCP debt
Does NOT amend AT-D14 or AT-D19
Does NOT amend or reopen AT-D18, and does not reopen AT-D16 or AT-D17
Does NOT add a verifier, registry, decision-discovery or canonical-activation mechanism
Does NOT remediate any observation in section 7
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
