# Autonomous Team — Implementation Milestone Plan

> **Planning only. No milestone below is authorized. Each requires its own explicit Product Owner
> authorization. `production_executed_true_count: 0`.**

## 1. Dependency graph

```text
                    ActorPrincipal / AgentProfile          [AT-M2]  POC-BLOCKING
                              |
                    ProjectTeamMembership                  [AT-M2]  POC-BLOCKING
                              |
        Conversation / TeamDecision / Handoff / Ownership  [AT-M2]  POC-BLOCKING
                              |
          Goal / PlanRevision / Dynamic Dispatch           [AT-M3]  POC-BLOCKING
                              |
        Execution / Verification / Debug / Replan loop     [AT-M4]  POC-BLOCKING
                              |
                    Autonomous Team UX v2                  [AT-M5]  POC-USEFUL
                              |
                 Functional Autonomous Team POC            [AT-M6]  the goal
                              |
                Delivery & Acceptance Hardening            [AT-M7]  POC-USEFUL
                              |
              Enterprise / Production Platform             [AT-M8]  PRODUCTION-BLOCKING
```

### Classification

```text
POC-BLOCKING          AT-M2, AT-M3, AT-M4
POC-USEFUL            AT-M5 (needed to OBSERVE the POC, not to run it), AT-M7
PRODUCTION-BLOCKING   AT-M8
DEFERRED              vector retrieval, GitHub write, external delivery, Helm/ArgoCD/Vault, CI
```

## 2. AT-M2 — Team Identity & Collaboration Core

```text
Goal            principals exist, teams exist, and agents can address each other durably
Dependencies    AT-M1 merged
Deliverables    ActorPrincipal, AgentProfile, ProjectTeamMembership, ConversationThread,
                TeamMessage, TeamDecision, Handoff; collaboration APIs and events
Exit gates      two distinct agent principals exchange addressed, threaded, persisted messages
                about one project; one TeamDecision recorded with options and rationale summary;
                one Handoff accepted; INV-01/03/04 verified green
Deferred        LLM-authored content (agents may post structured messages without reasoning),
                UX surfaces, retrieval
Risk            HIGH -- introduces the root entity of the whole model
Classification  POC-BLOCKING
Authorization   NOT AUTHORIZED
```

## 3. AT-M3 — Autonomous Planner & Dynamic Dispatch

```text
Goal            a plan is generated from a Goal, revised when needed, and ownership is decided
                by capability rather than by a mapping file
Dependencies    AT-M2
Deliverables    Goal entity, PlanRevision with versioning/diff/supersession, goal decomposition,
                dependency generation, dynamic dispatcher, conditional routing
Exit gates      two different Goals produce two different plans; a replan produces revision 2 with
                a reason and a diff; every work item is owned with an assignment reason and no
                human assignment; INV-05/07 verified green
Deferred        debug-driven replanning (AT-M4 supplies the trigger)
Risk            HIGH -- first real reasoning dependency (B1) lands here
Classification  POC-BLOCKING
Authorization   NOT AUTHORIZED
```

## 4. AT-M4 — Autonomous Execution & Debug Loop

```text
Goal            failure leads to diagnosis, fix and re-execution without a human
Dependencies    AT-M3
Deliverables    team phase state model, DebugAttempt, attempt budgets and termination,
                debug -> replan back-edge, test-driven verification feeding diagnosis
Exit gates      a seeded failure is diagnosed, fixed and re-tested to PASS with no human action;
                a plan-invalid failure produces a replan; budget exhaustion escalates rather than
                looping; INV-06 verified green
Deferred        production execution, external actions
Risk            CRITICAL -- unbounded loops and runaway cost live here
Classification  POC-BLOCKING
Authorization   NOT AUTHORIZED
```

## 5. AT-M5 — Autonomous Team Product UX v2

```text
Goal            the six surfaces needed to observe and intervene in an autonomous team
Dependencies    AT-M2..AT-M4; 66D-DESIGN-v2 amendment
Deliverables    S1 Goal & Team Console, S2 Team Workroom, S3 Plan & Ownership, S4 Run & Debug,
                S5 Delivery Review (preserved), S6 Intervention Queue
Exit gates      an operator can watch a run end to end and intervene only through the six
                permitted actions; no surface offers manual assignment as a normal affordance
Deferred        final visual polish
Risk            MEDIUM
Classification  POC-USEFUL -- the POC can RUN without UX, but cannot be OBSERVED or accepted well
Authorization   NOT AUTHORIZED
```

## 6. AT-M6 — Functional Autonomous Team POC

```text
Goal            satisfy every clause of the functional POC capability contract
Dependencies    AT-M2..AT-M5
Deliverables    end-to-end POC run + an automated verifier asserting P01..P18
Exit gates      P01..P18 all pass; zero human actions outside the permitted six
Deferred        production readiness
Risk            MEDIUM -- integration risk, not new-concept risk
Classification  the goal
Authorization   NOT AUTHORIZED
```

## 7. AT-M7 — Delivery & Acceptance Hardening

```text
Goal            autonomous delivery flows into the frozen 66D acceptance contracts
Dependencies    AT-M6
Deliverables    66D DeliverySubmission persistence (PR #28 is the input here), review action and
                PO decision APIs, follow-up lifecycle, events/outbox/read model
Exit gates      an autonomously produced delivery is accepted through the canonical 66D path with
                a supersedable ProductOwnerDecision
Deferred        production deployment
Risk            MEDIUM -- contracts are already frozen and reviewed
Classification  POC-USEFUL
Authorization   NOT AUTHORIZED
Note            PR #28 becomes an input to this milestone. It is not merged before AT-M7, and it
                is not required by AT-M1..AT-M6.
```

## 8. AT-M8 — Enterprise / Production Platform

```text
Goal            verified identity, production authorization, real deployment
Dependencies    AT-M7
Deliverables    RA-2 verified human identity, workload identity, OIDC enablement, CI pipeline,
                Helm/ArgoCD/Vault materialisation, production gates
Exit gates      production authentication is genuinely complete and independently reviewed
Deferred        nothing -- this is the terminal milestone
Risk            CRITICAL
Classification  PRODUCTION-BLOCKING
Authorization   NOT AUTHORIZED
```

## 9. Deferred across all milestones

```text
Vector retrieval / semantic memory   until a cross-project or semantic need exists (AT-D)
GitHub write, real PR creation       no autonomous repo write before AT-M8 gates
External delivery / notifications    no autonomous external send
Multi-project autonomous concurrency after AT-M6
```

## 10. What AT-M1 authorizes

```text
Nothing. AT-M1 produces architecture, contracts, ADRs, evidence and a verifier.
AT-M2 requires its own explicit Product Owner authorization.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
