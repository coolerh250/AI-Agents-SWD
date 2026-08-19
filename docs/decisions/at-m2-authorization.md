# AT-D11 — AT-M2 authorization and PCP-V2.1 gate re-sequencing

> **Product Owner decision record. Authorizes one non-production milestone. Authorizes no
> production action, no external action and no further milestone.
> `production_executed_true_count: 0`.**

```text
AT-D11:                      RESOLVED / BINDING
Recorded_on:                 2026-08-19
Recorded_by:                 Product Owner
Canonical_main_at_decision:  192ebb74ba600f7a53ddf5967a7254a1f7a72fb8
```

## 1. What this record is for

The AT-M1 implementation milestone plan states that every milestone "requires its own explicit
Product Owner authorization". This is that authorization for AT-M2, and it is the only place the
live authorization state is recorded.

It does **not** rewrite AT-M1. The binding-decisions contract still records
`AT_M2: NOT AUTHORIZED`, because that is what AT-M1 decided and that statement stays true of
AT-M1. A later authorization supersedes an earlier position; it does not falsify the record of it.

```text
AT_M2:                       AUTHORIZED / IN PROGRESS
AT_M2_SCOPE:                 AT-M2-TEAM-CORE only
```

## 2. What is authorized

```text
Runtime team identity        ActorPrincipal, AgentProfile, ProjectTeamMembership
Addressed collaboration      ConversationThread, TeamMessage, TeamDecision, Handoff
Capability routing           a runtime router and durable routing decisions
Persistence                  additive migrations for the entities above
Minimal read-only surface    a team roster / conversation / routing view
```

The capability router and one conditional workflow route are pulled forward from AT-M3 into AT-M2
by this decision. That is a deliberate re-scope made at the AT-REBASELINE-PRODUCT-1 review: the
rebaseline found that team identity without routing leaves the compile-time successor chain in
place, so the two halves of "the successor is decided at runtime" cannot be delivered separately
and still be demonstrable.

## 3. What is NOT authorized

```text
AT-M3 .. AT-M8               NOT AUTHORIZED -- each still needs its own decision
Live LLM reasoning           NOT AUTHORIZED in AT-M2
Real code / test execution   NOT AUTHORIZED in AT-M2
Autonomous diagnosis         NOT AUTHORIZED in AT-M2
Production action            NOT AUTHORIZED -- unchanged, and no path to one is added
Production authorization     NOT GRANTED -- unchanged
```

## 4. PCP-V2.1 gate re-sequencing

```text
PREVIOUS_GATE:               PCP-V2.1 REQUIRED BEFORE AT-M2
PCP_V2_1_GATES:              PRODUCTION AUTHORIZATION
PCP_V2_1_STATE:              IN PROGRESS / REMEDIATION -- unchanged, not waived, not reduced
```

The open PCP-V2.1 item is `PCP-V2.1-RM5 CANONICAL DEBT NOT RECONCILED`: a governance measurement
reconciliation. The AT-REBASELINE-PRODUCT-1 assessment established that it touches no
authorization boundary, no production-safety control, no security boundary, no destructive-action
guard, no data-integrity rule and no runtime migration. AT-M2's own authorization and
production-safety controls are enforced at runtime by the approval and policy engines, which this
debt does not reach.

The gate is therefore **moved, not removed**. PCP-V2.1 must be reconciled before a production
authorization milestone. It no longer gates a non-production milestone that cannot cross any of
the boundaries it protects.

```text
This decision does NOT mark PCP-V2.1 PASS.
This decision does NOT retire, reduce or reclassify any registered governance debt.
This decision does NOT authorize a third validation round for any capability.
```

## 5. AT-M1 lifecycle

```text
AT_M1_LIFECYCLE:             SUPERSEDED BY AT-M2
AT_M1_SUPERSESSION_COMMIT:   192ebb74ba600f7a53ddf5967a7254a1f7a72fb8
```

AT-M1 remains `CLOSED / CANONICAL`. Supersession closes AT-M1's **no-implementation window** at
the canonical main that was HEAD when this decision was made, and does nothing else. Every commit
AT-M1 could have contributed is inside that window and is still checked; code written after it
belongs to AT-M2's authorization and is not an AT-M1 scope breach.

Nothing else about AT-M1 relaxes. Its architecture invariants INV-01 … INV-09 stay live and
HEAD-relative, the reviewed-scope proof stays frozen, and `shared/sdk/tasks/rbac.py` stays
permanently protected — a successor milestone inherits the right to write implementation, never
the right to make a runtime agent an authorization subject.

## 6. Validation policy

```text
AT_M2_VALIDATION_ROUNDS_PERMITTED:   2
AT_M2_VALIDATION_ROUNDS_USED:        0
```

If two independent validation rounds do not close AT-M2, the project rule applies: STOP and
rebaseline. A third round is not authorized by this decision.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
