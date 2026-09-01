# AT-D21 — AT-M3.4 Durable Reasoning and Planning Decision product acceptance & canonical merge authorization

> **Product Owner decision record. Accepts AT-M3.4 (rebaselined lineage) and authorizes merging the
> exact independently validated candidate into `main`. Authorizes no real external LLM call
> (M3.6B), no production action, no AT-M4 execution, no AT-M3.5 dispatch runtime, no PCP
> remediation and no P3 backlog work. `production_executed_true_count: 0`.**

```text
AT-D21:                      RESOLVED / BINDING
Recorded_on:                 2026-09-01
Recorded_by:                 Product Owner
Canonical_main_at_decision:  83ae97fd273c0506aac067b3c13dbaff19933bc9
Validated_candidate:         35b2b8618fc649a2a1073aae7d574ef2a494e0fe
Implementation_end:          35b2b8618fc649a2a1073aae7d574ef2a494e0fe
Branch:                      at-m3.4-durable-reasoning-planning-decision-1
Depends_on:                  AT-D14 (docs/decisions/at-d14-at-m3-live-reasoning-authorization.md)
                             AT-D18 (docs/decisions/at-d18-project-governance-reset.md)
                             AT-D20 (docs/decisions/at-d20-at-m3-3-acceptance-and-merge-authorization.md)
```

`Implementation_end` is the exact byte state that was independently validated. This record and the
PM/progress reconciliation it authorizes create a later branch tip; `Implementation_end` does not
move with it. Acceptance attaches to a commit, not to a branch name.

## 1. What this record is for

AT-D14 authorized non-production, non-external-network implementation of AT-M3.1 through AT-M3.6A.
It said nothing about accepting a specific AT-M3.4 implementation or merging one into `main`. This
record is that separate authorization: the Product Owner accepts the AT-M3.4 capability (durable
reasoning artifacts, lease/takeover recovery, and a formal planning decision) as independently
validated, and approves canonicalizing the exact validated candidate.

Same shape as AT-D13 for AT-M2, AT-D15 for AT-M3.1, AT-D19 for AT-M3.2 and AT-D20 for AT-M3.3:
implementation authority and merge authority are separate decisions, and the second one names the
commit. It is the only place the AT-M3.4 acceptance and merge authorization is recorded.

This acceptance is of a **rebaselined lineage**. The prior AT-M3.4 lineage (`157b5cf`, and its
predecessor `28bdf43`) failed its own Validation 2 and was never continued or patched — see
section 5. Nothing in that lineage is accepted by this record, and neither commit is, or may
become, an ancestor of `main`.

## 2. Accepted product capability

Accepted exactly as validated, and no wider:

```text
structured, safe reasoning artifact persisted atomically with SUCCEEDED (one UPDATE, one row)
typed artifact replay from the durable row -- no provider re-call
DB-clock STARTED lease with compare-and-swap takeover -- never an application wall clock
attempt_token zombie protection -- a superseded attempt cannot terminalize a live one
bounded attempt exhaustion -- a truthful terminal FAILED, never permanent STARTED
honestly stated at-least-once provider attempts, exactly-one canonical durable artifact
the decompose_plan reasoning verb and its PlanDraftArtifact
seated, plan_project-capable planner provenance -- read from this discussion's own roster
no nonparticipant / capability-router fallback for plan authorship
the planner-authored candidate plan persisted as a durable `proposal` TeamMessage, never `replan`
candidate content byte-identical to its durable reasoning invocation's artifact
the accepted PlanRevision's plan byte-identical to the candidate it was accepted from
one AT-M2 TeamDecision as the sole formal decision authority -- no second decision entity
the planless root, changed-plan (M3.2 CAS successor), accept-current-draft and no_change outcomes
one-transaction canonical finalization -- revision, decision, acceptance and ledger row atomic
canonical replay / idempotency of a repeated finalize() command
migrations 040 and 041, including their NOT VALID legacy-preserving strategy and refuse-not-destroy
   down migrations
mock/local provider mode only -- no live provider or network path
unchanged HumanApproval boundary -- a TeamDecision remains not an Approval
```

This list is the acceptance boundary. Capability not named here is not accepted by this record,
whether or not code for it happens to exist.

## 3. What is authorized

```text
Merge scope:                   fast-forward canonicalization of the exact validated candidate
                               35b2b86 into main
Documentation-only authority:  this record and the bounded PM/progress reconciliation commit it
                               authorizes
Post-merge verification:       bounded product and source-of-truth checks only
```

## 4. What is NOT authorized

```text
M3.6B / real external LLM calls   NOT AUTHORIZED -- unchanged from AT-D14, no path to one is added
External model credentials        NOT AUTHORIZED
Production action                 NOT AUTHORIZED -- unchanged, no path to one is added
Production authorization          NOT GRANTED -- unchanged
AT-M4 implementation              NOT AUTHORIZED -- execution, DebugAttempt and the debug -> replan
                                    back-edge all remain out of scope
AT-M3.5 implementation            NOT STARTED by this record -- AT-D14 already authorizes the work;
                                    AT-M3.5 (plan-driven delegation / dynamic dispatch) still needs
                                    its own implementation report and its own Validation 1/2 pass
                                    before it can be accepted the way AT-M3.4 is accepted here
AT-M3.6A                          unchanged -- authorized under AT-D14, not accepted here
PCP remediation                   NOT AUTHORIZED by this record
P3 backlog remediation            NOT AUTHORIZED by this record -- see section 6
Artifact/step-count hardening     NOT AUTHORIZED by this record -- see section 6
Unrelated runtime changes         NOT AUTHORIZED -- this record covers AT-M3.4 acceptance and its
                                    merge only
```

## 5. Validation evidence — recorded here, not re-run by this decision

AT-M3.4 went through the bounded remediation policy AT-M1 established and AT-D18 restated:
Validation 1 → at most one remediation → Validation 2, no Validation 3 — per lineage. The prior
lineage exhausted that budget and failed; a rebaseline began a new one, exactly as the standard
permits.

```text
Prior lineage (157b5cf, predecessor 28bdf43) -- FAILED_VALIDATION_2 / NONCANONICAL / DO_NOT_MERGE:

  Independent Validation 1: a caller-substitutable plan. The finalize command accepted a `plan`
    and a `decided_by` directly from the caller, so two callers racing one converged discussion
    with different plans let commit ordering decide which became "what the team selected". This
    is a design-premise defect, not an implementation bug, and per the execution standard section
    5 the validation returned it as a DESIGN FINDING rather than fixing it inside the round.

  AT-M3.4-PLAN-AUTHORSHIP-DECISION-DESIGN-REVIEW-1: DESIGN_RESOLVED. Selected canonical semantic:
    the plan is authored by the routed, seated planner principal through the AT-M3.1
    `decompose_plan` verb, persisted as a durable `proposal` TeamMessage, and read back from that
    message -- never supplied by a caller. Recorded in migration 041's own commentary and in
    `shared/sdk/agent_planning_decision/service.py`/`models.py`, both of which this acceptance
    carries forward unchanged in substance.

  Remediation implemented the resolved design: no caller-supplied plan or author, a candidate
    plan message, and a single-transaction TeamDecision/PlanRevision write.

  Independent Validation 2: FAIL. `complete_invocation` committed `status='succeeded'` on its own
    connection while the structured artifact existed only as a Python object returned to the
    caller. `try_begin_invocation`'s `INSERT ... ON CONFLICT DO NOTHING` meant a terminal
    correlation id was never re-invoked and a replay returned nothing, so any death between the
    reasoning commit and the downstream write -- crash, dropped connection, or the caller's own
    transaction rolling back -- stranded a converged discussion permanently. A second, independent
    defect on the same table: migration 037 had explicitly deferred lease/takeover recovery, so a
    worker that died before its terminal write owned its correlation_id forever.

  This was the lineage's Validation 2 -- the final one under the one-remediation policy. It
    failed, so the lineage closed as FAILED_VALIDATION_2 / NONCANONICAL rather than continuing to
    a disallowed Validation 3. `157b5cf` and `28bdf43` remain on the remote as evidence and were
    read, not continued or patched.

AT-M3.4-IMPLEMENTATION-REBASELINE-1: DESIGN_RESOLVED. A fresh implementation lineage branched
  directly from canonical main (83ae97f), preserving the already-resolved plan-authorship design
  (planner-authored candidate, no caller substitution) unchanged, and additionally closing the
  Validation 2 stranding defect: the terminal status and the structured artifact are now written
  by the SAME UPDATE to the SAME row (migration 040's chk_reasoning_invocations_success_artifact),
  and a DB-clock lease with compare-and-swap takeover replaces the deferred recovery from 037.

AT-M3.4-REBASELINED-IMPLEMENTATION-1 (new lineage, new validation budget):
  AT-M3.4-INDEPENDENT-VALIDATION-1: PASS. Independently reproduced against a fresh clone taken
    directly from origin (not the implementer's checkout) and real PostgreSQL 16, covering:
    lineage exclusion of both failed-lineage commits; the success-artifact invariant against raw
    SQL attack; terminal-row immutability against raw SQL attack; typed replay with zero
    additional provider calls, including 8-way concurrency; the exact Validation-2 crash window
    (C4) recovering with no second provider call and exactly one candidate; DB-clock lease
    takeover under 8 real contenders; zombie-attempt safety under a genuine race; bounded attempt
    exhaustion to a truthful terminal FAILED; legacy pre-040 row preservation through a real
    migration 040 application with new-write enforcement independently probed; seated-planner
    provenance with the capability-router fallback proven removed; candidate/invocation/revision
    plan equality as whole-database invariants; all four outcome branches; stale-race protection
    for both the changed-plan and no_change paths; 8-way planless-root replay; atomicity under
    fault injection at every stage of the one-transaction write; migrations 040/041 UP/DOWN/UP/UP
    with an independently seeded evidence-refusal probe; and a targeted regression selection
    (1,040 tests across M3.1/M3.2/M3.3/M3.4/M2/approval/audit) differenced against canonical main
    under an identical fresh environment, finding zero tests that fail on the candidate and pass
    on main.
```

Validation 1 PASS on the rebaselined lineage. No blockers. No Validation 2 required. This record
does not claim Independent Validation 1 was performed by the acceptance or merge step — it was
performed independently, against `35b2b86`, before this decision, and this record states its
result rather than re-deriving it.

## 6. Retained non-blocking backlog

Recorded here so they are not rediscovered as if new. Neither blocks AT-M3.4 acceptance or this
merge, and neither is authorized for remediation by this record.

```text
1  `reasoning_invocations.artifact` (JSONB) has no explicit size bound. Harmless under the
   deterministic mock provider in use today; worth a decision before a live provider can write
   into the column.

2  `PlanContent` has no global step-count bound. Inherited from AT-M3.2, unchanged by this slice.
```

Under AT-D18-R05 both are `NON-BLOCKING` by default: neither reaches a production-authorization,
human-approval, external-model, secret-handling, destructive-action, audit-integrity or
security-boundary control. Both are `PRE-M3.6B` / `PRODUCT_HARDENING` — real, and worth closing
before a live provider is authorized, gating no non-production milestone. They become blocking
only on concrete P0/P1 evidence, which does not exist today.

The six AT-M3.3 observations recorded in AT-D20 section 7, the four AT-M3.2 observations recorded
in AT-D19 section 6, and the one AT-M3.1 observation recorded in AT-D15 are unchanged and are not
restated here.

## 7. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B or any real external LLM/network call
Does NOT authorize AT-M3.5 or AT-M3.6A implementation -- AT-D14 already authorizes that work; this
   record accepts and merges AT-M3.4 only
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT authorize AT-M4
Does NOT relax TASK_ROLES, RBAC, policy or approval
Does NOT retire, reduce or reclassify PCP debt
Does NOT amend AT-D14 or AT-D20
Does NOT amend or reopen AT-D18, and does not reopen AT-D16 or AT-D17
Does NOT add a verifier, registry, decision-discovery or canonical-activation mechanism
Does NOT remediate any observation in section 6
Does NOT relabel the prior FAILED_VALIDATION_2 lineage (157b5cf / 28bdf43) as accepted, reviewed,
   or a candidate for future merge
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
