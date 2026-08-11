# AT-M1 — Autonomous Team Architecture Decisions

> **Decision records only. Nothing implemented. `production_executed_true_count: 0`.**

Baseline: canonical main `2d4da808b1a89ea278fbb760e27f49047995165e`. None of these ADRs conflicts
with binding decisions AT-D01 … AT-D05; each either implements one or resolves a question those
decisions deliberately left open. None modifies a merged 66D contract.

Recorded in this file rather than a new `adr/` subdirectory, matching the existing convention set
by `step66d-arch1-architecture-decisions.md` and `docs/decisions/README.md`.

---

## AT-ADR-01 — Goal/Project/WorkItem/Run is the sole execution source of truth

**Status:** ACCEPTED · implements AT-D01

**Context.** Two user-facing models exist on `main`: `/tasks/*` with a task workroom, and
`/projects/*` with work items and a task graph. Both look like places work could originate. If
agents were allowed to execute against tasks as well as work items, the platform would carry two
execution lineages, two sets of state, and two answers to "what is this run for".

**Decision.** `Goal -> Project -> Work Item -> Workflow/Run` is the sole autonomous execution
lineage, preserving binding decision D-1 and 66D-D03. `/tasks` is preserved as a subordinate human
interaction surface. A Task may reference execution lineage; execution lineage must never require a
Task to advance.

**Consequences.** Two conversation surfaces coexist — task-scoped `task_messages` and the
project-scoped Team Workroom — which is accepted as the price of not deleting a working human
surface. Whether `/tasks` is eventually folded into the project surfaces is left to AT-M5 as a
product question; this ADR forbids a second execution lineage, not a route.

---

## AT-ADR-02 — ActorPrincipal is separate from human authorization

**Status:** ACCEPTED · implements AT-D02

**Context.** "Who did this" is currently answered four incompatible ways: an `actor_ref` string, an
`X-Task-Actor` header, an agent service name and a `created_by_agent` column. None can be joined or
authorized against. The obvious shortcut — give agents a `TASK_ROLES` role so existing
authorization works — would make "the system approved itself" expressible.

**Decision.** Introduce `ActorPrincipal` (`human`, `runtime_agent`, `ai_partner`, `system`) as the
attribution subject. Keep `TASK_ROLES` as the human authorization set, unchanged and human-only. A
runtime agent or AI partner must never hold a `TASK_ROLES` role. Identity, authorization role,
agent functional role and project-team membership stay four separate concepts.

**Consequences.** Agents gain attribution without gaining authority. Authorization checks stay
where they are and need no agent-aware branch. The cost is a second concept to explain — an agent
has a functional role and a membership, but no authorization role — and `agent_operator` remains a
confusingly named *human* role. INV-01 guards the boundary mechanically.

---

## AT-ADR-03 — Collaboration is evidence, not reasoning traces

**Status:** ACCEPTED · implements AT-D03

**Context.** Making agents collaborate creates immediate pressure to persist everything they
"thought", because it looks like the richest possible audit trail. It is not: raw reasoning is not
reviewable, not stable across models, and is a disclosure hazard containing prompt content and
sometimes secrets.

**Decision.** The Team Workroom stores collaboration artifacts — proposals, challenges, decision
rationale summaries, questions, answers, hypotheses, results, artifact and audit references. Fields
for private chain of thought, raw system prompts, hidden reasoning, token traces and unredacted
prompts are forbidden from every schema, DTO, event payload, projection and export.

**Consequences.** Debugging why an agent reached a conclusion is harder; the team sees the
conclusion and its stated rationale, not the derivation. That is accepted. The alternative is a
store that cannot be shown to a reviewer, cannot be retained safely, and grows without bound.
INV-04 verifies no such field is introduced.

---

## AT-ADR-04 — Plans are versioned revisions, and dispatch is dynamic

**Status:** ACCEPTED · implements AT-D04

**Context.** The current task graph is three hard-coded Python lists, and ownership comes from a
static `workType -> agent` YAML map. Neither can respond to the Goal, and neither can change when
execution reveals the plan was wrong.

**Decision.** `PlanRevision` becomes the canonical planning entity: versioned, historically
immutable, supersedable, diffable, and traceable to the discussion, decision or debug evidence that
caused it. Dispatch becomes dynamic, deciding ownership from work-item requirements, team
composition, agent capabilities, policy constraints and availability. The template planner and the
YAML map are demoted to fixtures and policy seeds.

**Consequences.** Reading "the plan" requires resolving the current accepted revision, exactly as
reading "the decision" requires resolving the effective `ProductOwnerDecision`. That cost is
accepted for the same reason: it is the price of an auditable history. Work-item reconciliation
across revisions becomes a real problem and is specified rather than left implicit; completed work
is never removed by a replan. INV-05 and INV-07 guard both halves.

---

## AT-ADR-05 — Orchestration is loop-aware and bounded

**Status:** ACCEPTED · implements AT-D04

**Context.** The orchestrator's LangGraph is a linear chain with no conditional edges. A linear
graph cannot express "verification failed, so diagnose, fix and re-execute", and it certainly
cannot express "the plan itself was wrong". Meanwhile the existing retry mechanism repeats the same
payload, which is reliability, not debugging.

**Decision.** Adopt a team phase model with four back-edges: `VERIFYING -> DEBUGGING`,
`DEBUGGING -> EXECUTING`, `DEBUGGING -> REPLANNING`, `REPLANNING -> READY/EXECUTING`. Introduce
`DebugAttempt` as a distinct entity from infrastructure retry. Bound every loop with an attempt
budget and define termination, including a structural no-progress rule: an attempt that changed
neither an artifact nor a `PlanRevision` was a retry wearing a debug label, and the loop stops.

**Consequences.** The system can now loop, which means it can loop forever if budgets are wrong;
budgets become a first-class safety control rather than an optimisation. Concrete budget values are
deliberately not set here — they are policy owned by AT-M4, following the precedent of ADR-66D-09
where the QA rerun bound was fixed by an authorized stage rather than invented. INV-06 keeps retry
and debug from being conflated.

---

## AT-ADR-06 — TeamDecision, Approval and ProductOwnerDecision stay separate

**Status:** ACCEPTED · implements AT-D03, AT-D02

**Context.** Three things in this platform are called a decision: the team choosing an approach, a
human authorizing a risky action, and the Product Owner accepting delivered work. Collapsing any
two would be convenient and would destroy a guarantee.

**Decision.** They are three separate contracts with separate enums, separate records and separate
authorities. `TeamDecision` does not authorize a production action, does not replace human
approval, and does not replace Product Owner acceptance. No mapping between the three is permitted.

**Consequences.** Three records where a naive design would have one. In exchange, "the agents
decided their own work was acceptable" is not expressible: `TeamDecision` has no `ACCEPTED` value
to reach for. This mirrors ADR-66D-01, which kept Review Gate Actions separate from Product Owner
Final Decisions for the same reason. INV-03 verifies the separation.

---

## AT-ADR-07 — Shared team context is relational; vector retrieval is deferred

**Status:** ACCEPTED · implements AT-D03, AT-D04

**Context.** "Agents need shared memory" usually becomes "add a vector database". The repository
has no embedding dependency, no vector store and no retrieval code, so this would be a new
subsystem with new failure modes, added before any evidence that similarity search is the missing
capability.

**Decision.** Canonical shared team context is composed of `Goal`, `Project`,
`ProjectTeamMembership`, `ConversationThread`, `TeamMessage`, `TeamDecision`, `PlanRevision`,
`WorkItem`, `Artifact` and run evidence — all relational, all already-modelled shapes. Vector
retrieval is `DEFERRED` until a cross-project or genuinely semantic retrieval need is demonstrated.

**Consequences.** Context assembly is explicit and query-shaped rather than similarity-shaped,
which is more predictable and fully auditable, and cheaper to reason about. If the team later needs
to answer "has anything like this been solved before" across projects, that is the trigger to
revisit — and the relational record is exactly what an embedding pipeline would index anyway, so
nothing is wasted.

---

## AT-ADR-08 — 66D-DESIGN-v2 is a versioned amendment, not an edit-in-place

**Status:** ACCEPTED · implements AT-D05

**Context.** The autonomous-team middle journey needs design work that the frozen 66D design did
not anticipate: team, discussion, plan, ownership, team phase, failure, debug, replan. The tempting
move is to edit the 66D design documents so they read as though they always covered it.

**Decision.** Reopen only the middle journey. Preserve Delivery Review, Review Gate Actions,
`ProductOwnerDecision`, safety, evidence and cost/external-action contracts unchanged. Record the
change as a versioned amendment with explicit supersession: superseded statements are annotated in
place and remain readable, never deleted, never silently rewritten. AT-M1 produces IA amendment
requirements only — no wireframes, no routes, no UI code.

**Consequences.** Reading the current design requires following supersession links, which is the
same cost 66D-D05 already accepted when it superseded the ARCH1 `review_status` sentence while
leaving it annotated in place. In exchange, a reviewer can always see what was decided before, what
replaced it, and why. INV-09 verifies the preserved set stays untouched.

---

## Open decisions (not ADRs)

```text
AT-D09  Clarification expiry execution semantics
        STATUS: OPEN / DEFERRED

        A UX suggestion proposes that on expiry an agent MAY proceed under an explicitly stated
        assumption. The existing Step 66C.4 clarification expiry contract REMAINS AUTHORITATIVE.
        AT-M1 must not canonicalize permissive continuation; recording the question is the
        deliverable. Answering it requires its own Product Owner decision.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
