# AT-D19 — AT-M3.2 Goal + Immutable PlanRevision product acceptance & canonical merge authorization

> **Product Owner decision record. Accepts AT-M3.2 and authorizes merging the exact validated
> candidate into `main`. Authorizes no real external LLM call (M3.6B), no production action, no
> AT-M4 execution, no PCP remediation and no P2 backlog work.
> `production_executed_true_count: 0`.**

```text
AT-D19:                      RESOLVED / BINDING
Recorded_on:                 2026-08-27
Recorded_by:                 Product Owner
Canonical_main_at_decision:  d5880d26665e688c4cc39dff4c669678ae0353c0
Validated_candidate:         d6442bde67586bb8031365a5696cf74164c6c905
Implementation_end:          d6442bde67586bb8031365a5696cf74164c6c905
Branch:                      at-m3.2-goal-planrevision-1
Depends_on:                  AT-D14 (docs/decisions/at-d14-at-m3-live-reasoning-authorization.md)
                             AT-D18 (docs/decisions/at-d18-project-governance-reset.md)
```

`Implementation_end` is the exact byte state that was independently validated. This record and the
PM/progress reconciliation it authorizes may create a later branch tip; `Implementation_end` does
not move with it. Acceptance attaches to a commit, not to a branch name.

## 1. What this record is for

AT-D14 authorized non-production, non-external-network implementation of AT-M3.1 through AT-M3.6A.
It said nothing about accepting a specific AT-M3.2 implementation or merging one into `main`. This
record is that separate authorization: the Product Owner accepts the AT-M3.2 capability (Goal +
immutable PlanRevision) as validated, and approves canonicalizing the exact validated candidate.
It is the only place the AT-M3.2 acceptance and merge authorization is recorded.

Same shape as AT-D13 for AT-M2 and AT-D15 for AT-M3.1: implementation authority and merge
authority are separate decisions, and the second one names the commit.

## 2. Accepted product capability

Accepted exactly as validated, and no wider:

```text
durable Goal
Goal -> Project lineage
immutable PlanRevision plan/lineage-bearing content
same-revision lifecycle: draft -> accepted
accepted is terminal under the current approved lifecycle
derived supersession / current-revision semantics
structured Plan
server-computed structured PlanRevision diff
project-wide monotonic revision numbering
concurrency-safe project allocator
expected-current stale revision protection
one successor per predecessor
real PostgreSQL concurrency safety
team_decisions.resulting_plan_revision_id UUID foreign key
migration 038 up / down / reapply safety
audit-safe identifiers and metadata only
no production and no external calls
```

This list is the acceptance boundary. Capability not named here is not accepted by this record,
whether or not code for it happens to exist.

## 3. What is authorized

```text
Merge scope:                   fast-forward canonicalization of the exact validated candidate
                               d6442bd into main
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
AT-M3.3 implementation           NOT STARTED by this record -- AT-D14 already authorizes the work;
                                   AT-M3.3 still needs its own implementation report and its own
                                   Validation 1/2 pass before it can be accepted the way AT-M3.2 is
                                   accepted here
AT-M3.4 .. AT-M3.6A              unchanged -- authorized under AT-D14, none accepted here
PCP remediation                  NOT AUTHORIZED by this record
P2 backlog remediation           NOT AUTHORIZED by this record -- see section 6
Unrelated runtime changes        NOT AUTHORIZED -- this record covers AT-M3.2 acceptance and its
                                   merge only
```

## 5. Validation evidence — recorded here, not re-run by this decision

AT-M3.2 went through the bounded remediation policy AT-M1 established and AT-D18 restated:
Validation 1 -> at most one remediation -> Validation 2, no Validation 3.

```text
AT-M3.2 Validation 1: FAIL -- 2 material implementation blockers
  D1  PlanRevision status was frozen from creation by a blanket immutability trigger, which made
      the approved pipeline's own team-acceptance stage (draft -> accepted on the SAME revision)
      unreachable.
  D2  Per-project revision numbering computed max(revision_number)+1 without serialising, so two
      Goals of one project racing to create their initial revisions collided -- measured at 1 of 6
      succeeding. The losing writers were additionally misdiagnosed as "goal already has an
      initial revision", and a raw asyncpg UniqueViolationError reached FastAPI as an HTTP 500.

AT-M3.2-IMPLEMENTATION-REMEDIATION-1 (bounded, single pass):
  - trg_plan_revisions_immutable now runs plan_revisions_enforce_lifecycle, which permits exactly
    two writes and nothing else: audit_ref NULL -> value once, and status draft -> accepted. Plan,
    diff and lineage stay immutable in BOTH states. Supersession stayed derived; no stored mutable
    superseded state was introduced. No new HTTP endpoint was added, because the approved contract
    does not place one in M3.2 -- acceptance lands as a store/service primitive for M3.4 to call.
  - Both write paths take SELECT ... FROM projects ... FOR UPDATE before computing the number and
    before inserting, in one fixed module-wide lock order (project row, then predecessor).
  - Each unique constraint maps to its own domain meaning; the write routes map an allocation
    conflict to 409 and any remaining asyncpg.PostgresError to 503.
  - Migration 038 was amended in place rather than superseded by a 039: it has never been
    canonical on main.

AT-M3.2 Independent Validation 2 / 2 (final): PASS
  - D1 closed. draft -> accepted succeeds on the same revision; accepted -> draft/proposed/rejected,
    draft -> proposed/rejected, proposed -> accepted, rejected -> accepted and unknown status values
    all fail closed with SQLSTATE 23001. All 11 plan/lineage-bearing columns are immutable both
    before and after acceptance, and all 9 multi-column smuggling attempts that pair the authorized
    status transition with a forbidden field mutation are blocked, leaving the row still draft.
    An end-to-end column diff across the lifecycle changed exactly status and audit_ref.
  - D2 closed, on real PostgreSQL 16 with independent connections, 5 rounds each: 8/8 concurrent
    initial revisions across 8 Goals of ONE project succeeded every round with contiguous unique
    numbers; 8/8 concurrent independent successors succeeded every round with correct predecessors
    and no cross-goal contamination; the same-predecessor race still resolved to exactly 1 winner
    and 7 fail-closed with the predecessor byte-identical; and a mixed workload of roots,
    successors and same-predecessor contenders produced no deadlock and no timeout.
  - Error classification verified per constraint, with the false duplicate-root diagnostic gone.
    HTTP: duplicate root 409, stale successor 409, allocation conflict 409, simulated upstream
    PostgresError 503 with no driver text and no DSN leaked. No HTTP 500 reachable.
  - Migration 038 verified from a canonical pre-M3.2 database built by applying the repository's
    own 001..037 chain: UP / DOWN / UP / UP all clean, the old blanket trigger function absent
    after UP, TeamDecision FK correct. The already-applied early-candidate path was characterised
    separately and is safe in both directions.
  - TeamDecision TEXT -> UUID FK conversion re-confirmed data-safe under hostile pre-state:
    non-UUID text and dangling UUID both fail closed with full rollback; NULL converts cleanly;
    blank/empty text becomes NULL, which discards no identifier; and no writer has ever populated
    the column.
  - Regression: 216 focused M3.2/M3.1/M2 tests and 40 approval/audit/registry tests pass. A full
    suite comparison against the pre-remediation candidate and against canonical main produced
    ZERO new failures; the pre-existing historical/meta failures are identical on canonical main.

Validation 2 PASS. No blockers. No Validation 3 required or permitted. This record does not claim
Validation 2 was re-run by the acceptance or merge step -- it was performed independently, from a
fresh checkout of d6442bd, before this decision.
```

## 6. Retained non-blocking observations

Recorded here so they are not rediscovered as if new. None of them blocks AT-M3.2 acceptance or
this merge, and none is authorized for remediation by this record.

```text
1  A PlanRevision may currently be CREATED directly with a creation-time status of accepted,
   proposed or rejected, bypassing the draft -> accepted stage. The architecture's own status
   vocabulary admits these as authored values, and the behaviour predates the remediation.
   Revisit in M3.4 so that TeamDecision remains the canonical chooser of what gets accepted.

2  Repeating acceptance of an already-accepted revision is a correct no-op on the row, but still
   emits an acceptance audit event. Observability / audit-hardening backlog.

3  Audit emission depends on an injected audit client, and the HTTP surface constructs the service
   without one, so the API path writes no audit event. This is the established AT-M2 / AT-M3.1
   convention, not something this slice changed. Pre-production audit-completeness backlog.

4  Inherited store-level gaps: the semantic forbidden-key screen misses some equivalent markers,
   there is no free-text value screening, and a leaf revision with no successor remains deletable
   by raw SQL. P2 / PRE-PRODUCTION backlog.
```

Under AT-D18-R05 these are `NON-BLOCKING` by default: none reaches a production-authorization,
human-approval, external-model, secret-handling, destructive-action, audit-integrity or
security-boundary control. They become blocking only on concrete P0/P1 evidence, which does not
exist today.

## 7. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B or any real external LLM/network call
Does NOT authorize AT-M3.3 .. AT-M3.6A implementation -- AT-D14 already authorizes that work; this
   record accepts and merges AT-M3.2 only
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT authorize AT-M4
Does NOT relax TASK_ROLES, RBAC, policy or approval
Does NOT retire, reduce or reclassify PCP debt
Does NOT amend AT-D14
Does NOT amend or reopen AT-D18, and does not reopen AT-D16 or AT-D17
Does NOT add a verifier, registry, decision-discovery or canonical-activation mechanism
Does NOT remediate any observation in section 6
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
