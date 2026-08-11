# AT-M1 — Autonomous Team Architecture Reset

> **Architecture contract only. Nothing here is implemented. No runtime, backend, API, frontend,
> database, migration, event, deployment, identity, secret or feature-gate change. No container,
> database, Redis, Kubernetes, Vault, OIDC provider, agent workflow or external provider started.
> `production_executed_true_count: 0`.**

```text
Canonical baseline:  main 2d4da808b1a89ea278fbb760e27f49047995165e
Binding decisions:   AT-D01 .. AT-D05 (RESOLVED / BINDING), AT-D09 (OPEN)
Marker:              AT_M1_ARCHITECTURE_RESET_VERIFY: PASS
```

## 1. What this reset is for

The platform on `main` is a well-governed multi-agent **workflow pipeline**. It has a real queue,
real dead-lettering, a tamper-evident audit chain, sandboxed command execution and 6513 tests. What
it does not have is a team: agents cannot address one another, cannot decide anything together, and
cannot hand work over. The plan they execute is a hard-coded Python list.

This stage fixes the target architecture so that gap is closed by construction rather than by
renaming existing parts. It answers, and freezes answers to, these questions:

```text
What is an actor, and how is an agent different from a human?   actor-principal-and-team-model.md
How do agents collaborate without storing reasoning traces?     collaboration-and-workroom-model.md
How is a plan generated, versioned and revised?                 planning-and-plan-revision-model.md
How does the failure -> debug -> replan loop terminate?         orchestration-debug-replan-model.md
Which entity owns which fact?                                   source-of-truth-and-lineage-model.md
What is a human still responsible for?                          human-intervention-and-governance-boundary.md
What must be true to call a POC functional?                     functional-poc-capability-contract.md
In what order is this built?                                    implementation-milestone-plan.md
```

## 2. Verified starting position

Re-derived from source at the canonical baseline, not carried over from a report:

```text
Fixed-chain workers        CONFIRMED  StreamAgent input_stream/output_stream are class attributes;
                                      the chain intake -> requirement -> development -> qa -> devops
                                      is compile-time
Simulated discussion       CONFIRMED  agent_discussion REVIEW_MODES has no live mode; all role
                                      contributions are hard-coded strings authored by one agent
Template planning          CONFIRMED  the task graph is a literal Python list
Dynamic delegation         ABSENT     0 recipient/addressing fields in shared/
Replanning                 ABSENT     0 occurrences of PlanRevision; the LangGraph has no
                                      conditional edges
Execution engine           REAL       subprocess with a module allowlist; real file writes under a
                                      path allowlist
Test execution             REAL       pytest is genuinely executed and recorded
Workroom substrate         PARTIAL    task_messages supports sender_type=agent, but no runtime
                                      agent writes one, and there is no recipient field
Task vs Project surfaces   SEPARATE   /tasks/* and /projects/* are distinct user-facing models
Delivery vs middle journey SKEWED     delivery/acceptance is far more mature than team collaboration
```

Absent on canonical main, machine-counted: `ActorPrincipal` / `principal_id` **0**, `PlanRevision`
**0**, `DebugAttempt` **0**, recipient-addressing fields **0**.

## 3. Layered architecture

```text
+------------------------------------------------------------------+
| L1  Product / Human Control Plane                                 |
|     goal setting, clarification answers, policy approval,         |
|     correction, halt, delivery acceptance                         |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
| L2  Autonomous Team Collaboration                                 |
|     principals, team membership, threads, messages, proposals,    |
|     challenges, team decisions, handoffs                          |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
| L3  Planning & Coordination                                       |
|     goal decomposition, PlanRevision, dependencies, ownership,    |
|     dynamic dispatch, conditional routing, replanning             |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
| L4  Execution / Verification / Debug                              |
|     workflow, run, artifacts, tests, QA evidence, diagnosis,      |
|     debug attempts, attempt budgets                               |
+------------------------------------------------------------------+
                                |
+------------------------------------------------------------------+
| L5  Governance / Audit / Policy                                   |
|     policy, approval, audit chain, RBAC, identity, secrets,       |
|     production gates                                              |
+------------------------------------------------------------------+
```

### L1 — Product / Human Control Plane

```text
Responsibility        express intent, resolve ambiguity the team cannot, authorize risk, accept
                      or reject delivered work, stop the team
Authoritative         Goal, ProductOwnerDecision, Approval, human-issued Correction and Halt
Commands              set_goal, answer_clarification, approve, reject, correct, halt,
                      accept_delivery, reject_delivery
Events                goal.created, clarification.answered, approval.granted/denied,
                      correction.issued, team.halted, delivery.accepted/rejected
Read models           Goal & Team Console, Intervention Queue, Delivery Review
Security boundary     the ONLY layer where a human authorization role (TASK_ROLES) is evaluated
Dependencies          none upward; every other layer may raise into it
```

### L2 — Autonomous Team Collaboration

```text
Responsibility        let principals talk to each other about a Goal, and record what the team
                      concluded
Authoritative         ActorPrincipal, AgentProfile, ProjectTeamMembership, ConversationThread,
                      TeamMessage, TeamDecision, Handoff
Commands              open_thread, post_message, propose, challenge, record_team_decision,
                      offer_handoff, accept_handoff, raise_blocker, ask_clarification
Events                thread.opened, message.posted, proposal.raised, proposal.challenged,
                      team_decision.recorded, handoff.offered/accepted, blocker.raised
Read models           Team Workroom, team roster / presence
Security boundary     agents are principals, never TASK_ROLES holders; no chain-of-thought field
                      exists to write to
Dependencies          L5 for audit; L3 consumes its decisions
```

### L3 — Planning & Coordination

```text
Responsibility        turn a Goal into work, keep the plan current, decide who owns what
Authoritative         PlanRevision, WorkItem, WorkItemDependency, Ownership assignment
Commands              generate_plan, revise_plan, accept_plan, assign_owner, reassign_owner,
                      dispatch_work_item
Events                plan.generated, plan.revised, plan.accepted, plan.superseded,
                      work_item.assigned, work_item.dispatched
Read models           Plan & Ownership surface, plan diff view
Security boundary     dispatch refuses production-effect targets; policy constraints are inputs to
                      the dispatcher, never overridden by it
Dependencies          L2 (decisions justify revisions), L4 (failures trigger revisions)
```

### L4 — Execution / Verification / Debug

```text
Responsibility        do the work, prove whether it worked, diagnose it when it did not
Authoritative         Workflow, Run, Artifact, QA evidence, DebugAttempt
Commands              execute_work_item, run_tests, record_qa_evidence, open_debug_attempt,
                      record_debug_result, request_replan
Events                run.started/completed/failed, qa.completed, debug.opened,
                      debug.result_recorded, replan.requested
Read models           Run & Debug surface
Security boundary     sandboxed roots, command allowlist, no repo/main write, no deploy;
                      production-effect execution is refused, not gated
Dependencies          L3 for what to run and who owns it; L5 for audit
```

### L5 — Governance / Audit / Policy

```text
Responsibility        make every consequential act attributable and every risky act authorized
Authoritative         Policy, Approval, AuditEvent, TASK_ROLES, secret references
Commands              evaluate_policy, request_approval, record_audit_event
Events                policy.evaluated, approval.requested/granted/denied, audit.recorded
Read models           Audit evidence, safety centre, identity/secret posture
Security boundary     the only layer that may assert authorization; production_executed stays false
Dependencies          none -- every layer depends on it, it depends on none
```

## 4. Architecture invariants

Ten invariants are machine-verified by `scripts/verify_at_m1_architecture_reset.py`:

```text
INV-01  TASK_ROLES contains no runtime agent role
INV-02  Project/WorkItem/Run remains the sole autonomous execution lineage
INV-03  TeamDecision is contractually separate from ProductOwnerDecision
INV-04  TeamMessage carries no chain-of-thought field
INV-05  PlanRevision is versioned and supersedable, never mutable-history overwrite
INV-06  DebugAttempt is not infrastructure retry
INV-07  the template planner is not marked the canonical autonomous planner
INV-08  PR #28 remains non-canonical and held
INV-09  Delivery Review and ProductOwnerDecision remain preserved
INV-10  AT-M1 introduces no runtime implementation
```

## 5. What this stage does not decide

```text
Clarification expiry semantics   AT-D09, OPEN -- the 66C.4 contract stays authoritative
LLM provider selection           capability contract only; no SDK, no network, no key
Vector retrieval                 DEFERRED until a cross-project/semantic need exists
Final IA and wireframes          AT-M5; AT-M1 produces amendment requirements only
Production identity              RA-2 / AT-M8; ActorPrincipal is a logical principal
Whether /tasks is eventually     product/IA question for AT-M5; AT-D01 forbids only a second
merged into project surfaces     execution lineage, not the route's existence
```

## 6. Status

```text
AT_M1:                           PASS
AUTONOMOUS_TEAM_ARCHITECTURE:    DEFINED
AT_D01_D05:                      DOCUMENTED / PROPOSED FOR CANONICAL MERGE
AT_D09:                          OPEN
RUNTIME_IMPLEMENTATION:          NOT STARTED
MIGRATION:                       NONE
FRONTEND:                        NONE
PR28:                            HOLD / UNCHANGED / NON-CANONICAL
AT_M2:                           NOT AUTHORIZED
PRODUCTION_EXECUTED_TRUE_COUNT:  0
```

No agent gained a capability in this stage. No table, endpoint, route or provider was created.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
