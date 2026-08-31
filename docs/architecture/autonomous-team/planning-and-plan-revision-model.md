# Autonomous Team — Planning and Plan Revision Model

> **Architecture contract only. Nothing here is implemented. No runtime, backend, API, frontend,
> database, migration or event change. `production_executed_true_count: 0`.**

Implements AT-D04. Machine-verified starting position: `PlanRevision` / `plan_revision` has **zero**
occurrences on canonical main, and the current task graph is a literal Python list.

## 1. The problem being fixed

`shared/sdk/project_planning/task_graph.py` contains `_FASTAPI_TODO_MILESTONES` (7 entries),
`_FASTAPI_TODO_WORK_ITEMS` (9) and `_FASTAPI_TODO_DEPENDENCIES` (11) as hard-coded Python literals.
The "plan" is selected by template match. Two consequences follow, and both are fatal to autonomy:

```text
The plan cannot respond to the Goal      -- a different goal yields the same nine work items
The plan cannot change                   -- there is no revision, so failure cannot alter it
```

## 2. Goal

The Goal is the human/system intent the team serves. It is **not** a Work Item.

```text
goal_id
project_id                 a Goal belongs to a Project (AT-D01)
statement                  what outcome is wanted, in the requester's words
acceptance_criteria        how the requester will know it was achieved
constraints                what the team must not do (scope, technology, safety, budget)
created_by                 principal
created_at
status                     draft | active | achieved | abandoned
```

```text
A Goal is intent. A Work Item is work. A Goal is never decomposed INTO itself, and a Work Item
never becomes a Goal.
```

Canonical location today: **none**. No Goal entity exists on `main`; `projects` carries a `title`
and `summary`, which are not acceptance criteria or constraints. AT-M1 defines the contract only —
it deliberately does not specify the table, which is AT-M3-BE work.

## 3. PlanRevision

```text
plan_revision_id
project_id
revision_number            1, 2, 3 ... monotonic per project
goal_ref                   the Goal this plan serves
created_by                 principal that authored the revision
reason                     why this revision exists (section 5)
supersedes_revision_id     nullable -- revision 1 has none
status                     draft | proposed | accepted | superseded | rejected
created_at
```

### Required properties (D04-R1, D04-R3, INV-05)

```text
VERSIONED                revision_number is monotonic per project
HISTORICALLY IMMUTABLE   an accepted revision is never rewritten in place
SUPERSEDABLE             a change is a NEW revision naming its predecessor
DIFFABLE                 any two revisions produce a structured diff (section 6)
TRACEABLE                every revision links to the discussion, decision or debug evidence that
                         caused it
```

```text
Mutable-history overwrite is FORBIDDEN. Editing an accepted revision destroys the record of what
the team was working from when a run failed -- which is precisely the evidence a replan needs.
```

This mirrors the shape already proven by `ProductOwnerDecision` (66D-D02): append-only, supersede
by reference, history permanently queryable. The two are separate entities in separate domains and
share no enum.

## 4. Planning pipeline

```text
Goal
  |  goal decomposition
PlanRevision (draft)
  |  work-item generation + dependency generation
WorkItems + WorkItemDependencies
  |  ownership assignment (dynamic dispatch)
Owned WorkItems
  |  team acceptance
PlanRevision (accepted)
```

### Stages

```text
initial planning        a planner principal decomposes the Goal into work items and dependencies,
                        producing a draft revision
plan validation         dependency validation (cycles, unreachable items, orphaned criteria)
                        reuses the EXISTING dependency validator -- that logic is sound and is
                        preserved
plan acceptance         the team records a TeamDecision accepting the revision; acceptance is a
                        team act, not a human gate (unless policy requires one)
plan supersession       a new revision names its predecessor; the predecessor becomes `superseded`
replanning              see section 5
work-item reconciliation see section 7
```

## 5. Replanning triggers

A revision's `reason` is one of:

```text
initial                       revision 1
goal_changed                  the human amended the Goal
clarification_answered        an answer invalidated an assumption the plan rested on
team_decision                 the team chose a different approach
debug_plan_invalid            debugging concluded the plan itself is wrong, not the code
                              (the debug -> replan back-edge, D04-R6)
dependency_discovered         execution revealed a dependency the plan did not model
scope_correction              a human correction narrowed or widened scope
blocked_resolution            a blocker was resolved in a way that changes the plan
```

```text
`debug_plan_invalid` is the load-bearing one. It is what makes the loop a loop rather than a
retry: the team may conclude that no amount of fixing the artifact will satisfy the goal, and
change the plan instead.
```

## 6. Plan diff

A revision comparison produces a structured diff, not a text diff:

```text
work_items_added          items present in B, absent in A
work_items_removed        items present in A, absent in B
work_items_modified       same identity, changed title/type/acceptance criteria
dependencies_added
dependencies_removed
ownership_changed         same item, different owner principal
rationale                 the reason + the decision/debug evidence that caused the change
```

The diff is what a human reviews when they want to know "what did the team change, and why",
without reading two full plans. It is also what the Plan & Ownership surface (S3) renders.

## 7. Work-item reconciliation

When revision N+1 supersedes N, existing work must not be orphaned:

```text
item unchanged and not started      carried forward unchanged
item unchanged and in progress      carried forward; run history preserved
item modified and not started       carried forward with new definition
item modified and in progress       carried forward; the in-flight run is marked as executing a
                                    superseded definition, and the owner is notified in-thread
item removed and not started        closed as `descoped`, never deleted
item removed and completed          RETAINED. Completed work and its artifacts are historical
                                    evidence and are never removed by a replan.
item added                          created unowned; dispatch assigns it
```

```text
No reconciliation path deletes a Run, an Artifact or QA evidence.
```

## 8. Ownership

```text
WorkItem
  owner_principal_id        nullable until dispatched
  assigned_at               nullable
  assignment_reason         why this principal (capability match, handoff, human correction)
  assignment_ref            reference to the dispatch decision or Handoff that produced it
```

```text
In normal autonomous flow a human does not assign owners (D04-R9).
A human MAY observe ownership, and MAY override it as an explicit correction.
Human override is an intervention, recorded as such -- not the normal path.
```

## 9. Template planner disposition (D04-R8, INV-07)

```text
shared/sdk/project_planning/task_graph.py

Current role      the only planner; produces a fixed nine-item graph
Future role       TEST / DEMO FIXTURE ONLY
Canonical?        NO -- it must not be described, documented or verified as the canonical
                  autonomous planner
Deletion          NOT required by AT-M1. It remains useful for deterministic tests that must not
                  depend on a model.
```

```text
A fixture that is honestly labelled is an asset. The same fixture described as a planner is a
false-complete risk, and INV-07 exists to catch exactly that.
```

## 10. Dependencies

```text
Requires    ActorPrincipal (who authored the revision), TeamDecision (what accepted it),
            Goal (what it decomposes)
Enables     dynamic dispatch, conditional routing, the debug -> replan back-edge
Preserves   the existing dependency validator and TaskGraph model shape
Slices      AT-M3-BE1 (Goal + PlanRevision), AT-M3-BE2 (decomposition), AT-M3-BE3 (dispatch)
Status      CONTRACT_ONLY / NOT IMPLEMENTED
```

## 11. Discussion staleness and the M3.4 consumption contract

Records AT-M3.3-PLAN-STALENESS-DESIGN-REVIEW-1, an architect-level clarification of semantics
AT-D14 already authorizes for M3.3/M3.4. It adds no entity, no state and no mechanism.

The gap it closes: an AT-M3.3 discussion binds to a PlanRevision when it opens, but a legitimate
successor may appear while it is still running. Nothing said what that means.

### 11a. Canonical semantic

```text
A discussion is about an EXACT, IMMUTABLE PlanRevision, permanently.
```

A successor appearing mid-discussion does NOT terminate it, mutate it, rebind it, or give it a
stale terminal state or a stale flag. It continues under its own bounds and may converge honestly
about the revision it opened against.

This is the same posture section 7 already takes toward in-flight work overtaken by a replan —
carried forward and marked, never destroyed — and it keeps collaboration lineage parallel to
execution lineage as `source-of-truth-and-lineage-model.md` R5 requires, rather than subordinate
to it. It also mirrors the revision itself: revision N does not change when N+1 appears, it stops
being *current*, which is a fact about the lineage and not about N.

### 11b. Staleness is derived, never stored

```text
stale  ==  a revision exists whose supersedes_revision_id names this discussion's plan_revision_id
```

Answered by `PlanningStore.is_current()` / `get_current_revision()`, which read lineage. No stale
column, no plan-current cache, no synchronization writer and no version registry: currency has no
stored form anywhere in this model (section 3), and a copy of it here would be the first — needing
a writer, a race story and a repair path that the derived form does not.

### 11c. What M3.4 must check before consuming a discussion outcome

```text
1  discussion.state = 'converged' AND stop_reason = 'convergence_reached'
2  discussion.result_message_id IS NOT NULL
3  discussion.goal_id is the Goal being planned
4  discussion.plan_revision_id is still that Goal's CURRENT revision
   (or is NULL and the Goal still has no revision)
```

### 11d. The currency check is a compare-and-swap, not a pre-read

The safety-critical write must carry the discussion's bound revision as the CAS token:

```text
create_successor_revision(
    goal_id                      = discussion.goal_id,
    expected_current_revision_id = discussion.plan_revision_id,
    reason                       = 'team_decision',
    trace_ref                    = discussion.result_message_id )
```

`create_successor_revision` locks the predecessor and re-checks currency inside that lock, and
`uq_plan_revisions_one_successor` permits at most one successor per predecessor even for a caller
that bypasses the store. A stale discussion's convergence therefore *cannot* become a successor:
the attempt raises `StalePlanRevisionError` from PostgreSQL, not from an application check someone
could forget to write. Where the discussion is bound to no revision, `create_initial_revision` and
`uq_plan_revisions_one_root_per_goal` give the same guarantee.

```text
A separate is_current() pre-read is worth doing for a clear error message.
It is NOT the safety boundary. The CAS is.
```

This is what removes the check-then-write window entirely: the check IS the write. Two consumers
holding converged discussions bound to the same revision resolve to exactly one successor, and the
loser learns it is stale rather than writing a second one.

### 11e. What a stale discussion is still good for

It is not discarded, not rewritten and not hidden. It remains queryable and citable as evidence
about the revision it deliberated — collaboration lineage, intact. What it may not do is stand in
as evidence about a revision it never discussed. Reusing its conclusions against the new current
revision requires a NEW discussion bound to that revision; rebinding is forbidden and is prevented
by trigger.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
