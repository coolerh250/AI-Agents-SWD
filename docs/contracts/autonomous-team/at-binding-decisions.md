# Autonomous Team — Binding Decisions (AT-D01 … AT-D05)

> **Product Owner binding decision record. Architecture and contract documentation only. No runtime,
> backend, API, frontend, database, migration, event, deployment, identity, secret or feature-gate
> change was made. No container, database, Redis, Kubernetes, Vault, OIDC provider, agent workflow or
> external provider was started. `production_executed_true_count: 0`.**

```text
DOCUMENT_STATUS:     CANONICAL / BINDING
DECISION_AUTHORITY:  Product Owner
DECISION_DATE:       2026-08-11
RECORDED_BY:         Claude Code (Step AT-M1), acting as recorder only
CANONICAL_BASELINE:  main fa5e5c4e6712fbbc59bf18d2ee33421c28f9b009

AT-D01:  RESOLVED / BINDING
AT-D02:  RESOLVED / BINDING
AT-D03:  RESOLVED / BINDING
AT-D04:  RESOLVED / BINDING
AT-D05:  RESOLVED / BINDING
AT-D09:  OPEN / DEFERRED -- not a decision, an open question (section 6)

RUNTIME_IMPLEMENTATION:  NOT STARTED / NOT AUTHORIZED BY THIS RECORD
```

## Why this record exists

Three capability audits established that the platform on `main` is a **governed multi-agent
workflow pipeline**, not an autonomous team. The gap is not missing polish; it is that the three
faculties which make a team — discuss, decide, delegate — are absent or simulated. These five
decisions reset the target architecture so that the gap is closed deliberately rather than by
renaming what already exists.

Nothing here reopens a merged 66D contract. Section 5 defines exactly what is amended and what is
preserved.

---

## AT-D01 — Execution source of truth

```text
STATUS:     RESOLVED / BINDING
SELECTION:  Binding decision D-1 is preserved unchanged. The autonomous execution lineage is
            Goal -> Project -> Work Item -> Workflow / Run, and it is the SOLE one.
```

```text
Goal
  -> Project
    -> Work Item
      -> Workflow / Run
```

### Binding requirements

```text
D01-R1  Goal -> Project -> Work Item -> Workflow/Run is the sole autonomous execution source of
        truth. Preserves 66SYNC.1 binding decision D-1 and 66D-D03.
D01-R2  The Task API, Task UI and Task Workroom MUST NOT become a second autonomous execution
        lineage. There is never a "task pipeline" running beside a "project pipeline".
D01-R3  `/tasks` is preserved as a human interaction surface. Preserving it is not permission to
        anchor autonomous execution on it.
D01-R4  A Task may REFERENCE execution lineage. Execution lineage MUST NOT depend on a Task to
        advance.
D01-R5  Any future autonomous run, artifact or QA evidence resolves to a Work Item and a Run,
        never to a Task alone.
```

### What this does not decide

Whether `/tasks` is eventually merged into the project surfaces is a product/IA question owned by
AT-M5. AT-D01 only forbids a second execution lineage; it mandates no route deletion.

---

## AT-D02 — Agent principal model

```text
STATUS:     RESOLVED / BINDING
SELECTION:  A new ActorPrincipal abstraction is introduced. Human authorization stays on
            TASK_ROLES. Agents are principals, never TASK_ROLES holders.
```

Minimum principal types:

```text
human            a person acting through an authenticated session
runtime_agent    a deployed agent workload inside this platform
ai_partner       an external AI partner (Claude Code, Codex, Claude Design)
system           the platform itself (schedulers, relays, migrations)
```

### Binding requirements

```text
D02-R1  ActorPrincipal is a distinct abstraction with its own identifier.
D02-R2  TASK_ROLES remains the HUMAN authorization role set and is NOT modified by this decision.
D02-R3  A runtime_agent MUST NOT be added to TASK_ROLES.
D02-R4  An ai_partner MUST NOT be added to TASK_ROLES.
D02-R5  Four concepts stay separate and MUST NOT be collapsed:
            identity                  who or what this is
            authorization role        what a HUMAN is permitted to authorize (TASK_ROLES)
            agent functional role     what an agent is for (backend, qa, planner, ...)
            project-team membership   which project this principal is currently working on
D02-R6  An ActorPrincipal identifier is a LOGICAL principal. It is not, and must not be described
        as, an authenticated production credential.
D02-R7  External AI partners are `ai_partner`. They are never recorded as `runtime_agent`; they
        are not deployed workloads. This preserves ARCH1 section 7.
```

### Why agents are kept out of TASK_ROLES

`TASK_ROLES` answers "may this **human** authorize this action". Adding a runtime agent to it would
make "the system approved itself" expressible, which is precisely the property the approval and
audit contracts exist to prevent. An agent needs a functional role and a team membership; it never
needs a human authorization role.

---

## AT-D03 — Collaboration model

```text
STATUS:     RESOLVED / BINDING
SELECTION:  The Workroom is promoted from a task-only concept to a Project/Goal-scoped Team
            Workroom in which runtime agents are first-class participants.
```

Required canonical semantics:

```text
thread              address / recipient    reply
proposal            challenge              team decision
handoff             blocker                clarification
debug hypothesis    debug result           replan
artifact reference  audit reference
```

### Binding requirements

```text
D03-R1  A Team Workroom is scoped to a Project/Goal, not to a Task.
D03-R2  Runtime agents are first-class participants: they may originate messages, not only be
        described by them.
D03-R3  A message may be addressed to a specific principal, to a functional role, or to the team.
D03-R4  Threading is explicit: a reply names its parent.
D03-R5  A proposal may be challenged, and both are durable.
D03-R6  A team decision is a distinct artifact, not a message type that happens to sound final.
D03-R7  Collaboration records are EVIDENCE, not reasoning traces. See D03-R8.
```

### D03-R8 — the storage prohibition (hard)

```text
MUST NOT be stored, projected, rendered, logged or exported:
    private chain of thought        raw system prompt
    raw hidden reasoning            token traces / reasoning token streams
    secrets                         unredacted prompts
    private scratchpad
```

```text
MAY be stored as durable collaboration evidence:
    action summary                  proposal
    decision rationale summary      artifact reference
    handoff                         debug hypothesis / debug result
    audit evidence                  question / answer
```

The distinction is between a **conclusion an agent stands behind** and the **process by which it
arrived there**. The first is team evidence and belongs in the record. The second is neither
reviewable nor safe to retain, and the contract forbids designing a field for it.

---

## AT-D04 — Planning and orchestration model

```text
STATUS:     RESOLVED / BINDING
SELECTION:  Template-driven planning is retired as the autonomous control-path target
            architecture. PlanRevision becomes the canonical planning entity.
```

Target orchestration loop:

```text
Goal
  |
Plan
  |
Work
  |
Execute
  |
Verify
  |
  +-- PASS --> Deliver
  |
  +-- FAIL
        |
      Diagnose
        |
      Debug
        |
      Replan
        +-------------> Execute
```

### Binding requirements

```text
D04-R1  PlanRevision is versioned, historically immutable and supersedable. A revision is never
        rewritten in place.
D04-R2  A plan is GENERATED from a Goal. It is not selected from a fixed template list.
D04-R3  Every revision records a reason and is diffable against its predecessor.
D04-R4  Dispatch is DYNAMIC: ownership is decided from work-item requirements, team composition,
        capability and policy -- not from a static mapping file.
D04-R5  Routing is CONDITIONAL. A linear, unconditional graph cannot express the loop above.
D04-R6  The debug -> replan back-edge is a first-class transition, not an error path.
D04-R7  Every loop carries a bounded attempt budget and a defined termination condition.
D04-R8  The existing template planner MAY remain as a test/demo fixture. It MUST NOT be described
        or verified as the canonical autonomous planner.
D04-R9  In normal autonomous flow a human does not press assign, next, retry, or author the next
        plan. Those become human actions only at an explicit policy gate.
```

---

## AT-D05 — 66D-DESIGN-v2 scoped amendment

```text
STATUS:     RESOLVED / BINDING
SELECTION:  The autonomous-team middle journey is reopened for design. The delivery end of the
            journey stays frozen. The amendment is VERSIONED, never edit-in-place.
```

### Preserved, unchanged

```text
Delivery Review                Review Gate Actions (the six)
ProductOwnerDecision           Safety contracts
Evidence contracts             Cost / external-action contracts
66D-D01  66D-D02  66D-D03  66D-D04  66D-D05
ADR-66D-01 .. ADR-66D-10
```

### Reopened for 66D-DESIGN-v2

```text
Team                    Discussion              Plan
Ownership               Team phase              Failure
Debug                   Replan                  manual CTA assignment corrections
```

### Binding requirements

```text
D05-R1  The amendment is recorded as a VERSIONED amendment/supersession. The original 66D design
        artifacts are annotated in place, never deleted and never silently rewritten.
D05-R2  No 66D frozen contract listed above may be edited by an autonomous-team stage.
D05-R3  A superseded 66D design statement remains readable, with its supersession named.
D05-R4  AT-M1 produces IA amendment REQUIREMENTS only -- no wireframes, no routes, no UI code.
```

---

## 6. AT-D09 — clarification expiry execution semantics (OPEN)

```text
STATUS:  OPEN / DEFERRED -- deliberately NOT decided by AT-M1
```

```text
UX suggestion under consideration:
    on clarification expiry, an agent MAY proceed under an explicitly stated assumption

Current canonical implementation:
    the existing clarification expiry contract (Step 66C.4) REMAINS AUTHORITATIVE

Decision:
    DEFERRED
```

AT-M1 must not canonicalize permissive continuation. Recording the question is the deliverable;
answering it requires its own Product Owner decision. Until then, expiry behaves exactly as the
merged 66C.4 contract specifies.

---

## 7. Prohibited implications

None of the following is true, and none may be inferred from this record:

```text
An autonomous team is implemented                     -- FALSE
Agents can currently discuss, decide or delegate      -- FALSE
A plan is currently generated from a goal             -- FALSE
ActorPrincipal exists in the codebase                 -- FALSE
PlanRevision exists in the codebase                   -- FALSE
TASK_ROLES has been changed                           -- FALSE
Production authentication is complete                 -- FALSE
PR #28 is canonical                                   -- FALSE
AT-M2 is authorized                                   -- FALSE
```

## 8. Authorization status

```text
AT_D01_D05:                      RESOLVED / BINDING
AT_D09:                          OPEN
AUTONOMOUS_TEAM_ARCHITECTURE:    DEFINED (contract only)
RUNTIME_IMPLEMENTATION:          NOT STARTED / NOT AUTHORIZED
AT_M2:                           NOT AUTHORIZED
PR28:                            HOLD / PRESERVE / NON-CANONICAL
PRODUCTION_EXECUTED_TRUE_COUNT:  0
```

Deciding an architecture is not building one. AT-M2 requires its own explicit Product Owner
authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
