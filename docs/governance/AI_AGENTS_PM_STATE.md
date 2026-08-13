# AI_AGENTS_PM_STATE

> **Governance artifact only. No backend/frontend runtime change. No production action.**

The canonical, repository-versioned **PM State Snapshot** for this project. It is the compact
project-control truth derived from engineering truth plus binding Product Owner decisions, and it
is the artifact a fresh session reads first.

It is **derived**, never primary. Where this file and `main` disagree, `main` wins and the
disagreement is a **PM_STATE_CONFLICT** that must stop work — see
[project-control-plane-v2.md](project-control-plane-v2.md).

This file does not replace `source/progress.md`, which remains the chronological ledger of record
under [the source-of-truth policy](../process/source-of-truth-policy.md). This is a recovery
snapshot, not a history.

## 1. Snapshot identity

```text
PM_STATE_VERSION:            1
PM_STATE_SCHEMA:             pcp-v2
RECONCILED_ON:               2026-08-13
RECONCILED_AGAINST_MAIN:     2a2facc898aa3738322d4487cbfce591cfbadc46
RECONCILED_BY_STAGE:         PCP-V2.1-A
```

`RECONCILED_AGAINST_MAIN` is the commit this snapshot was verified against. It is expected to fall
behind as work lands. Falling behind is **staleness**, which is tolerated and reported; naming a
commit that is unknown to the repository, or that is not an ancestor of `main`, is **drift**, which
is a conflict.

## 2. Position

```text
CURRENT_MILESTONE:           AT-M1
CURRENT_MILESTONE_STATE:     CLOSED / CANONICAL
PREVIOUS_COMPLETED_STAGE:    AT-M1-M1
CURRENT_GATE:                PCP-V2.1
CURRENT_STAGE:               PCP-V2.1-A
NEXT_PERMITTED_STAGE:        PCP-V2.1-B
```

## 3. Engineering truth

```text
AT_M1:                       CLOSED / CANONICAL
AT_M1_BASELINE:              fa5e5c4e6712fbbc59bf18d2ee33421c28f9b009
AT_M1_STAGE_HEAD:            c80350ecc19e28212d9a95cddeb80a24aabe6eae
AT_M1_MERGE_COMMIT:          db4e7a781dcddf4f5ab4ac413457a88bc7bdefa0
AT_M1_POSITIVE_SCOPE_PATHS:  19
PR29:                        MERGED
PR28:                        OPEN / HOLD / NON-CANONICAL
PR28_HEAD:                   c9145cd848a211a9dd2bbff672c532da364eaa55
```

`AT_M1_STAGE_HEAD` is the independently reviewed implementation state. It is the merge commit's
second parent, which is what pins it; `AT_M1_BASELINE` is the first parent.

## 4. Product Owner decisions

```text
AT-D01:                      RESOLVED / BINDING
AT-D02:                      RESOLVED / BINDING
AT-D03:                      RESOLVED / BINDING
AT-D04:                      RESOLVED / BINDING
AT-D05:                      RESOLVED / BINDING
AT-D10:                      RESOLVED / BINDING
AT-D10.1:                    RESOLVED / BINDING
```

```text
AT-D09:                      OPEN / DEFERRED
STEP_66C4_CONTRACT:          REMAINS AUTHORITATIVE
```

AT-D09 is an open question, not a decision. Nothing downstream may represent it as settled.

## 5. Authorization and safety

```text
AT_M2:                       NOT AUTHORIZED
AT_M3_TO_AT_M8:              NOT AUTHORIZED
PCP_V2_1:                    REQUIRED BEFORE AT_M2
RUNTIME_IMPLEMENTATION:      NOT STARTED
PRODUCTION_AUTHORIZATION:    NOT GRANTED
PRODUCTION_EXECUTED_TRUE_COUNT: 0
```

## 6. Active HOLD items

```text
PR28_HOLD:                   HOLD / PRESERVE / NON-CANONICAL, future AT-M7 input
```

PR #28 blocks nothing in AT-M1 through AT-M6 and is not a dependency of any current work. It must
never be treated as a canonical dependency while it is on hold.

## 7. Blockers and debt

```text
BLOCKERS:                    NONE
```

Carried governance debt, none of it blocking. Nothing here is closed by being listed.

| id | subject |
| --- | --- |
| ADV-R8-01 | carrier key must head with the subject; contract wording is looser than the rule |
| ADV-R8-02 | atomicity enforces punctuation shapes, narrower than its normative wording |
| ADV-R8-03 | subject-leading prose containing a colon is over-classified as a carrier |
| ADV-R8-04 | required-carrier registry has no self-integrity protection |
| ADV-R8-05 | a line that is only a backticked register is treated as a carrier |
| ADV-R8-06 | binding policy ownership rests on the focused tests, not the main verifier |
| ADV-R7-01 | canonical-artifact set is computed as a superset of its documented enumeration |
| ADV-R7-03 | prose contradiction advisory is implemented but never invoked |
| ADV-R7-04 | section-field discovery is asymmetric between subjects |
| ADV-R7-05 | dead historical verifier symbols with a now-false comment |
| ADV-R7-07 | register-looking non-subject-keyed lines read as authoritative to humans |
| ADV-R5-01 | stale self-referential counts in narrative evidence |
| ADV-R4-01 | ALIGN1 historical fixed-range debt; two known pre-existing test failures |

`ADV-R6-02` is closed for its pull-request metadata portion only. That closure does not generalize
to stale evidence elsewhere.

## 8. Known transition hazard

```text
HAZARD_AT_M1_DENYLIST:       OPEN / DISPOSITION REQUIRED BEFORE FIRST CROSSING MILESTONE
```

The AT-M1 verifier's current-state rejection checks are HEAD-relative from a fixed baseline, by
design, so that a forbidden path landing after the reviewed stage head is still caught. A later
**authorized** milestone may legitimately introduce paths AT-M1 currently rejects — `agents/`,
`apps/`, `shared/`, `migrations/`, `infra/` among them — and AT-M2 is the likely first.

This is not authorization to weaken AT-M1. The rule is: **before the first future authorized
milestone that legitimately crosses an AT-M1 HEAD-relative denylist boundary, an explicit verifier
lifecycle and supersession disposition is required.** That decision is not made here.

## 9. Source-of-truth precedence

```text
1  GitHub canonical main          engineering source of truth
2  this PM State Snapshot         derived project-control truth
3  persistent assistant memory    durable principles and decisions only
4  conversation history           convenience context, never required
```

Volatile facts — any SHA, pull-request state, test count, path count, current stage, current
blocker, merge state — must never be trusted from memory or from chat history alone. They are
reconcilable against canonical evidence and must be reconciled before use.

## 10. Freshness requirement

Before relying on this snapshot, run the drift gate:

```text
python scripts/verify_pcp_v2_control_plane.py
python scripts/verify_pcp_v2_control_plane.py --remote     # also machine-confirms PR state
```

A `PM_STATE_CONFLICT` verdict means this file and canonical engineering truth disagree. Stop, do
not pick the more convenient source, and reconcile from `main`.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
