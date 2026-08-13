# Autonomous Team — Human Intervention and Governance Boundary

> **Architecture contract only. Nothing here is implemented. No runtime, backend, API, frontend,
> identity, RBAC or policy change. `production_executed_true_count: 0`.**

Implements AT-D02, AT-D04 (D04-R9) and the L1/L5 boundaries.

## 1. The principle

```text
A human sets direction, resolves ambiguity, authorizes risk, and judges the result.
A human does not operate the machinery.
```

If a human must press "next" for work to advance, the system is a workflow tool with extra steps.
The boundary below is what separates the two, and it is a design constraint, not an aspiration.

## 2. Intervention matrix

| Human action | Normal flow? | Layer | Authorization | Effect |
| --- | --- | --- | --- | --- |
| **Set goal** | **YES** — expected | L1 | authenticated human | creates/amends a Goal; may trigger replan |
| **Answer clarification** | **YES** — expected | L1 | authenticated human | clears `WAITING_FOR_HUMAN`; may trigger replan |
| **Approve policy-gated high-risk action** | **YES** — expected | L5 | `TASK_ROLES` capability | authorizes one action; never blanket |
| **Inject correction** | **YES** — expected | L1 | authenticated human | scope/approach correction; recorded as intervention |
| **Halt** | **YES** — expected | L1 | authenticated human | `HALTED` immediately from any phase |
| **Accept / reject delivery** | **YES** — expected | L1 | Product Owner capability | `ProductOwnerDecision` (66D, preserved) |
| Assign an agent to work | **NO** | L3 | — | dispatcher's job; human override is an intervention |
| Advance the workflow | **NO** | L4 | — | orchestrator's job |
| Retry every failure | **NO** | L4 | — | retry is infra; diagnosis is the team's job |
| Create every Work Item | **NO** | L3 | — | planner's job |
| Author every PlanRevision | **NO** | L3 | — | planner's job; humans amend the Goal instead |
| Resolve missing evidence manually | **NO** | L4 | — | the team gathers or escalates it |

```text
The six YES rows are the complete set of human responsibilities in normal autonomous flow.
Anything else a human does is an INTERVENTION -- permitted, recorded as such, and a signal that
the team could not proceed.
```

## 3. Override versus normal path

Every NO row is still *possible* — a human may always take control. The distinction is recorded:

```text
normal        the responsible principal acted; no human involvement
intervention  a human took an action the team should have taken
              -> recorded with actor, reason and the phase it interrupted
              -> surfaced in the Intervention Queue (S6)
              -> a rising intervention rate is the primary autonomy regression signal
```

```text
Interventions are measured, not prevented. A system that cannot be overridden is unsafe; a system
that requires override is not autonomous. The metric is what tells them apart.
```

## 4. Three decision types that must not merge (INV-03)

```text
TeamDecision           WHO   the team (any principal)
                       WHAT  a coordination or technical choice
                       NOT   authorization; not acceptance

Approval               WHO   a human holding the required TASK_ROLES capability
                       WHAT  authorization for one policy-gated risky action
                       NOT   a technical choice; not delivery acceptance

ProductOwnerDecision   WHO   the Product Owner
                       WHAT  acceptance or rejection of delivered work
                       NOT   authorization to act; not a technical choice
```

```text
MUST NOT share enums.
MUST NOT substitute for one another.
```

Why it matters concretely: if `TeamDecision` could carry `ACCEPTED`, a team of agents could record
its own delivery acceptance. The separation is what keeps "the agents decided their work was
acceptable" from ever being expressible.

## 5. Governance preserved unchanged

```text
TASK_ROLES                    six human roles, unchanged; no agent role added (INV-01)
Approval policy + engine      unchanged
Audit chain + integrity       unchanged; every AT entity write is auditable
Policy engine                 unchanged; policy constraints are INPUTS to dispatch
Secret references             unchanged; AgentProfile stores references, never values
production_executed           stays false on every record
Clarification expiry (66C.4)  unchanged; AT-D09 is OPEN and must not be pre-empted
Delivery Review / PO Decision unchanged (66D preserved set)
```

## 6. Agent authority ceiling

```text
An agent MAY        plan, propose, challenge, decide technical approach with the team, own work,
                    hand work over, generate artifacts, run tests in the sandbox, diagnose
                    failures, fix and re-execute, request replanning, ask a human a clarification,
                    raise a blocker, prepare a delivery submission

An agent MUST NOT   hold a TASK_ROLES role
                    grant an approval
                    record a ProductOwnerDecision
                    authorize or perform a production action
                    answer its own clarification
                    write outside its sandbox root
                    read or emit a secret value
                    enable its own feature gate
```

```text
The ceiling is enforced at L5, not by agent goodwill. An agent asking for something it may not
have is normal; the platform refusing is the control.
```

## 7. Escalation

```text
budget exhausted            -> WAITING_FOR_HUMAN with an escalation summary
no-progress loop detected   -> WAITING_FOR_HUMAN
blocker the team cannot resolve -> BLOCKED, raised into the Intervention Queue
policy gate reached         -> WAITING_FOR_HUMAN (approval)
clarification needed        -> WAITING_FOR_HUMAN (answer)
repeated intervention on one goal -> autonomy regression signal, surfaced to the operator
```

Every escalation carries a summary a human can act on without reading the whole thread. An
escalation that requires archaeology is a failed escalation.

## 8. Dependencies

```text
Requires    ActorPrincipal (who intervened), team phase model (what was interrupted)
Preserves   TASK_ROLES, approval engine, audit chain, policy engine, 66D acceptance
Enables     S6 Intervention Queue, autonomy regression metrics
Verified by INV-01, INV-03, INV-09
Status      CONTRACT_ONLY
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
