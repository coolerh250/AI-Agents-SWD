# Autonomous Team — Canonical Terminology Registry

> **Terminology alignment only. No contract frozen beyond AT-D01..AT-D05, no schema defined, no
> implementation authorized. `production_executed_true_count: 0`.**

Authoritative for autonomous-team vocabulary as of 2026-08-11, per
`docs/contracts/autonomous-team/at-binding-decisions.md`.

Every term below is `CONTRACT_ONLY / NOT IMPLEMENTED` on canonical main
`fa5e5c4e6712fbbc59bf18d2ee33421c28f9b009` unless stated otherwise.

---

## ActorPrincipal

```text
Canonical definition:
  The single subject that can originate a message, own work, be handed work, or appear in an
  audit record. Types: human, runtime_agent, ai_partner, system.

Not to be confused with:
  Human authentication identity -- an ActorPrincipal is a LOGICAL principal and implies no
                                   verified production credential.
  TASK_ROLES                    -- human authorization roles; an agent principal never holds one.
  Agent functional role         -- what an agent is FOR (backend, qa, ...), not who it is.
  ProjectTeamMembership         -- which project it is working on, not its identity.

Authoritative source:  AT-D02
Current state:         CONTRACT_ONLY -- 0 occurrences on main
```

## AgentProfile

```text
Canonical definition:
  The functional identity of a runtime agent: role, declared capabilities, tool policy profile
  reference and model/provider reference.

Not to be confused with:
  ActorPrincipal -- the profile DESCRIBES a principal; it is not the principal.
  A secret store -- the profile holds REFERENCES only, never a key, token or DSN.

Authoritative source:  AT-D02
Current state:         CONTRACT_ONLY
```

## ProjectTeamMembership

```text
Canonical definition:
  The record that a principal is on a project's team, with a functional role and a membership
  state. Historical: leaving sets left_at rather than deleting.

Not to be confused with:
  An execution record. Membership says a principal is AVAILABLE, never that it did work.
  Execution stays on Work Item -> Run.

Authoritative source:  AT-D02, AT-D03
Current state:         CONTRACT_ONLY
```

## Team Workroom

```text
Canonical definition:
  A Project/Goal-scoped collaboration space in which runtime agents are first-class participants.

Not to be confused with:
  The existing task-scoped workroom (/tasks/:taskId/workroom, migration 030) -- PRESERVED and
  unchanged; it stays task-scoped and human-facing.
  agent_discussion (Stage 46) -- a deterministic template fixture, superseded as the
  collaboration model.

Authoritative source:  AT-D03
Current state:         CONTRACT_ONLY
```

## ConversationThread

```text
Canonical definition:
  A threaded conversation anchored on a project and goal, optionally narrowed to a work item or
  run, with an explicit type and lifecycle state.

Not to be confused with:
  A Redis stream. A stream is transport; a thread is a durable, addressable conversation.

Authoritative source:  AT-D03
Current state:         CONTRACT_ONLY
```

## TeamMessage

```text
Canonical definition:
  One durable, attributable, addressed collaboration record with a type, a summary and artifact
  references.

Not to be confused with:
  A reasoning trace. Chain of thought, system prompts, hidden reasoning and token traces are
  FORBIDDEN fields (AT-D03 R8 / INV-04).
  task_messages -- preserved, task-scoped, different substrate.

Authoritative source:  AT-D03
Current state:         CONTRACT_ONLY -- 0 recipient/addressing fields on main
```

## TeamDecision

```text
Canonical definition:
  A coordination or technical choice made by the team, recording options considered, the selected
  option, a rationale summary and any unresolved dissent.

Not to be confused with:
  Approval             -- policy authorization by a human holding a TASK_ROLES capability.
  ProductOwnerDecision -- delivery acceptance by the Product Owner.
  The three MUST NOT share enums and MUST NOT substitute for one another (INV-03).

Explicitly:
  A TeamDecision does NOT authorize a production action.
  A TeamDecision does NOT replace human approval.
  A TeamDecision does NOT replace Product Owner acceptance.

Authoritative source:  AT-D03
Current state:         CONTRACT_ONLY
```

## Handoff

```text
Canonical definition:
  A first-class transfer of work-item ownership from one principal to another, with a reason,
  context references and a state (offered/accepted/declined/withdrawn/expired). Ownership moves on
  ACCEPTANCE.

Not to be confused with:
  A `next_owner` string -- forbidden as the mechanism; it cannot express a declined or pending
  transfer.
  handoff_summaries (migration 021) -- legacy delivery-package SUMMARY documents, an unrelated
  concept that happens to share the word.

Authoritative source:  AT-D03
Current state:         CONTRACT_ONLY
```

## Goal

```text
Canonical definition:
  Human or system INTENT: a statement, acceptance criteria and constraints, belonging to a
  Project.

Not to be confused with:
  A Work Item. A Goal is intent; a Work Item is work. A Goal is never decomposed into itself.
  A project title/summary -- the existing `projects` columns are not acceptance criteria.

Authoritative source:  AT-D01, AT-D04
Current state:         CONTRACT_ONLY -- no canonical Goal entity exists on main
```

## PlanRevision

```text
Canonical definition:
  A versioned, historically immutable, supersedable, diffable plan for a Goal, carrying the reason
  it was authored and traceable to the discussion, decision or debug evidence that caused it.

Not to be confused with:
  The template task graph (shared/sdk/project_planning/task_graph.py) -- a hard-coded nine-item
  list, permitted as a TEST/DEMO FIXTURE and forbidden as the canonical autonomous planner
  (INV-07).
  Mutable plan state -- editing an accepted revision in place is FORBIDDEN (INV-05).

Authoritative source:  AT-D04
Current state:         CONTRACT_ONLY -- 0 occurrences on main
```

## Dynamic Dispatch

```text
Canonical definition:
  Deciding a work item's owner from required capabilities, dependencies, team composition, agent
  capabilities, policy constraints and availability -- emitting an owner, a decision and a reason.

Not to be confused with:
  Static YAML mapping (infra/delivery/work-item-dispatch-policy.yaml) -- DEMOTED to fallback,
  test fixture or policy seed; never the autonomous source of truth.

Authoritative source:  AT-D04
Current state:         CONTRACT_ONLY
```

## DebugAttempt

```text
Canonical definition:
  Analysing a failure, modifying an artifact or the plan, and re-executing -- with a hypothesis
  summary, planned fix, result classification and resulting run or plan revision.

Not to be confused with:
  Infrastructure retry -- repeating the SAME operation with the SAME inputs, changing nothing.
  DLQ -- a reliability mechanism, not an autonomous debugging model (INV-06).
  The three-bucket auto-fix path -- PARTIAL: it diagnoses and modifies, but cannot select a
  responsible principal and its diagnosis is a lookup table.

Authoritative source:  AT-D04
Current state:         CONTRACT_ONLY -- 0 occurrences on main
```

## Team Phase

```text
Canonical definition:
  What the TEAM is currently doing: PLANNING, DISCUSSING, READY, EXECUTING, VERIFYING, DEBUGGING,
  REPLANNING, WAITING_FOR_HUMAN, BLOCKED, DELIVERING, COMPLETED, HALTED.

Not to be confused with:
  DeliverySubmission status (the nine canonical 66D values) -- a DIFFERENT DOMAIN. The two must
  not be merged, mapped or substituted. A team may be DEBUGGING while its submission is
  UNDER_REVIEW.

Authoritative source:  AT-D04
Current state:         CONTRACT_ONLY
```

## Intervention

```text
Canonical definition:
  A human action that the team should have taken itself. Permitted, recorded with actor, reason
  and interrupted phase, and surfaced in the Intervention Queue.

Not to be confused with:
  The six normal human responsibilities: set goal, answer clarification, approve a policy-gated
  action, inject correction, halt, accept/reject delivery. Those are not interventions.

Authoritative source:  AT-D04 (D04-R9)
Current state:         CONTRACT_ONLY
```

## Preserved 66D terminology

```text
Review Gate Action          six actions -- UNCHANGED (66D-D01)
Product Owner Final Decision three decisions -- UNCHANGED (66D-D01)
Delivery Review Status      nine statuses -- UNCHANGED (66D-D02)
DeliverySubmission          the acceptance aggregate -- UNCHANGED (66D-D04)
DeliveryReviewTask          active := closed_at IS NULL -- UNCHANGED (66D-D05)
DeliveryPackage             legacy Step 47/49 evidence object -- UNCHANGED (66D-D04)
Execution Lineage           project -> work item -> workflow -> run -- PRESERVED, extended with
                            Goal made explicit (AT-D01)
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
