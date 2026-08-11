# Autonomous Team — Source of Truth and Lineage Model

> **Architecture contract only. Nothing here is implemented. No runtime, backend, API, frontend,
> database or migration change. `production_executed_true_count: 0`.**

Implements AT-D01. Preserves binding decision D-1 (66SYNC.1) and 66D-D03.

## 1. The one execution lineage

```text
Goal
  -> Project
    -> Work Item
      -> Workflow / Run
```

```text
This is the SOLE autonomous execution source of truth.
There is exactly one. There will not be a second.
```

## 2. Authoritative lineage matrix

| Entity | Write authority | Read authority | Source of truth | History behaviour | UI surface |
| --- | --- | --- | --- | --- | --- |
| **Goal** | human (L1); system on import | team + humans | `Goal` | amendable; amendments trigger replan | S1 Goal & Team Console |
| **Project** | human (L1) | team + humans | `projects` (existing) | mutable metadata | S1 |
| **Project Team** | L2 membership service | team + humans | `ProjectTeamMembership` | historical — `left_at`, never deleted | S1 roster |
| **Conversation** | any principal (L2) | thread participants | `ConversationThread` + `TeamMessage` | append-only; threads resolve/supersede | S2 Team Workroom |
| **Team Decision** | any principal (L2) | team + humans | `TeamDecision` | append-only; never overwritten | S2, S3 |
| **PlanRevision** | planner principal (L3) | team + humans | `PlanRevision` | versioned + supersedable; immutable once accepted | S3 Plan & Ownership |
| **Work Item** | L3 planning; L4 status | team + humans | `project_work_items` (existing) | definition versioned via PlanRevision; status mutable | S3 |
| **Ownership** | dynamic dispatcher (L3); human override | team + humans | `WorkItem.owner_principal_id` + `Handoff` | assignment history via Handoff | S3 |
| **Workflow** | orchestrator (L4) | team + humans | `workflow_states` (existing) | mutable state, persisted transitions | S4 Run & Debug |
| **Run** | executing agent (L4) | team + humans | `agent_executions` / run records (existing) | append-only | S4 |
| **Artifact** | executing agent (L4) | team + humans | `code_workspace` artifacts (existing) | append-only + content hash | S4 |
| **QA evidence** | qa principal (L4) | team + humans | `qa_validation_runs` / findings (existing) | append-only | S4 |
| **DebugAttempt** | diagnosing principal (L4) | team + humans | `DebugAttempt` | append-only; attempt_number monotonic | S4 |
| **Delivery** | delivery path (66D) | reviewers + PO | `DeliverySubmission` (66D, contract) | versioned via supersedes | S5 Delivery Review |
| **PO Decision** | Product Owner (L1) | everyone | `ProductOwnerDecision` (66D) | append-only + supersedable | S5 |
| **Approval** | human w/ TASK_ROLES (L5) | auditors + team | approval records (existing) | append-only | S6 Intervention Queue |
| **Audit** | `system` (L5) | auditors | audit chain (existing) | append-only, HMAC-chained | Audit evidence |

## 3. Rules

```text
R1  Every autonomous execution fact resolves to a Work Item and a Run. Never to a Task alone.
R2  Every artifact, QA evidence item and DebugAttempt resolves to a Run.
R3  Every Run resolves to a Work Item; every Work Item to a PlanRevision; every PlanRevision to a
    Goal; every Goal to a Project.
R4  A Work Item's DEFINITION is owned by PlanRevision. Its STATUS is owned by execution.
    The two are separate writers and must not overwrite each other.
R5  Collaboration lineage (thread -> message -> decision) is parallel to execution lineage, joined
    at Project and optionally at Work Item / Run. It is not a second execution path.
R6  A Task may reference execution lineage. Execution lineage MUST NOT require a Task to advance.
R7  Delivery lineage (submission -> review action -> PO decision) is downstream of execution
    lineage and is governed by the preserved 66D contracts.
```

## 4. Path A / Path B reconciliation (§9 hard requirement)

Two user-facing models exist today, machine-verified in `apps/admin-console/src/App.tsx`:

```text
Path A   /tasks, /tasks/new, /tasks/:taskId, /tasks/:taskId/workroom
Path B   /projects, /projects/:projectId, /task-graph
```

### Canonical target relationship

```text
/tasks and its workroom
    = SUBORDINATE HUMAN INTERACTION SURFACE
      operator intake, human task tracking, human/agent task-scoped messaging
      NOT an autonomous execution source

/projects/:projectId  (Project / Work Item / Run)
    = AUTONOMOUS EXECUTION SOURCE
      the only lineage a runtime agent plans, executes, verifies, debugs and delivers against
```

```text
Workroom promotion is BOUND to Project/Goal execution context (AT-D03).
The Team Workroom is reached from the Project, not from a Task.
The existing task-scoped workroom at /tasks/:taskId/workroom is PRESERVED and stays task-scoped.
```

### Forbidden outcome

```text
Task autonomous pipeline
        +
Project autonomous pipeline
        =  TWO EXECUTION SYSTEMS  -- FORBIDDEN (AT-D01 / INV-02)
```

### What is deliberately not decided

Whether `/tasks` is eventually folded into the project surfaces, kept as a separate intake queue,
or reduced to a filtered view is a **product/IA question owned by AT-M5**. AT-D01 forbids a second
execution lineage; it does not mandate deleting a route, and AT-M1 deletes none.

### Bridge (contract only)

```text
A Task MAY carry a reference to a Project and/or Goal it contributed to.
A Project/Goal MUST NOT depend on that reference to plan, execute, verify or deliver.
The reference is for human navigation and traceability, never for control flow.
```

## 5. Preserved lineage decisions

```text
D-1 (66SYNC.1)   Dedicated POC Development Goal -> Project -> Work Item -> Workflow/Run
                 PRESERVED UNCHANGED. AT-D01 restates and extends it with Goal made explicit.
66D-D03          execution anchors on project -> work item -> workflow -> run; the Task is the
                 human-review/RBAC anchor and NOT the agent execution source of truth
                 PRESERVED UNCHANGED.
66D-D03 R3       the non-dispatching Task API must not be re-described as an agent pipeline entry
                 point -- PRESERVED, and AT-D01-R2 restates it for the autonomous team.
```

## 6. Dependencies

```text
Requires    nothing -- this document constrains every other AT document
Constrains  planning (what a plan attaches to), collaboration (where threads anchor),
            orchestration (what a run resolves to), UX (which surface owns which fact)
Verified by INV-02
Status      CONTRACT_ONLY
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
