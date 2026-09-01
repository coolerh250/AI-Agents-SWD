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

## 12. Durable reasoning outcomes and planner provenance (AT-M3.4)

AT-M3.4 needed one thing from AT-M3.1 that AT-M3.1 never promised: that a successful reasoning
call could be **replayed**. It could not, and the gap only became load-bearing here.

### 12a. The failure this section exists to close

`reasoning_invocations` recorded call metadata. The structured artifact was returned to the caller
in memory and stored nowhere. So an invocation could commit `status='succeeded'` while the only
copy of what it produced lived in a process that then died — or merely rolled back its own
downstream transaction. The correlation id was now terminal, so no retry could re-invoke it; the
row held no artifact, so no replay could return one. A converged discussion whose planner call
landed in that window was stranded permanently: no plan, no decision, and no path to either.

AT-M3.3 had already met the same wall and worked around it at the product level — a turn whose
provider had run but whose message was lost fails the whole discussion closed
(`_resolve_unowned_turn`). M3.4 has no equivalent escape, because the discussion it consumes is
already terminal before M3.4 begins.

### 12b. The invariant

```text
An invocation for a verb that produces a structured artifact MUST NOT become durably
'succeeded' unless that validated artifact is durably stored in the SAME atomic write.
```

The terminal status and the artifact are set by one `UPDATE` on one row, so no ordering exists
between them and there is no window to crash inside. `chk_reasoning_invocations_success_artifact`
makes the alternative unrepresentable even for a caller that bypasses the service, and a
`BEFORE UPDATE` trigger freezes a terminal row — a successful artifact can never be replaced by a
different, equally well-formed one.

The artifact lives on the invocation row rather than in a second table because "a succeeded row
implies a row over there" is not something a `CHECK` can say, and every mechanism that can say it
buys a weaker guarantee with more moving parts.

### 12c. What is stored, and what is still forbidden

Exactly `_StrictArtifact.as_safe_dict()`: a closed-schema (`extra="forbid"`) business artifact that
has already passed the same content-safety screen a `TeamMessage` passes. No prompt, no completion,
no chain-of-thought, no scratchpad, no token trace, no credential — and `ReasoningRequest.context`,
the *input*, remains in memory and reaches no column at all.

This adds no new **class** of persisted data: AT-M3.3 already writes these identical payloads into
`team_messages.content` on every turn. What is new is the **role**. The invocation's copy is a
*recovery* copy, read only to rebuild what a crashed worker was holding. The `TeamMessage` remains
the copy the team can see and the only one the product cites. The duplication is deliberate and is
the fix itself: if either copy could be derived from the other, the crash window would not exist.

### 12d. Replay

A caller that arrives at an already-terminal invocation gets `disposition='replay'` and, for a
success, the artifact — reparsed through the model its verb declares, so it carries the same
guarantees a fresh one does. `disposition` still answers *did THIS call invoke a provider*; it is
no longer a proxy for *is there an artifact*. Two cases still carry none, and both are honest:
`in_progress` (nobody has finished yet) and a legacy pre-migration-040 success, which genuinely
stored nothing and says so rather than fabricating something plausible.

### 12e. Ownership is leased, not permanent

Migration 037 deferred recovery of a stranded `started` row explicitly, which left a second,
independent way to strand work: a worker that dies before its terminal write owns its correlation
id forever and every later caller is told `in_progress` in perpetuity. AT-M3.3 escapes this through
its own discussion deadline; AT-M3.4 has no deadline and would not.

Ownership is now bounded by `lease_expires_at` on the **database** clock — never an application
clock, which a paused or skewed worker could use to extend its own ownership. An expired lease is
claimable by exactly one contender through a compare-and-swap that also advances `attempt`.
`complete_invocation` is guarded on `attempt_token`, so a zombie that wakes up after its lease was
taken over learns it lost instead of silently committing a result nobody is waiting for. Takeover
is bounded by `attempt`; past the bound the invocation terminalizes as a truthful failure rather
than staying `started` forever. Nothing polls, retries in the background, or runs on a timer —
takeover happens only when a caller asks again.

A `started` row with a NULL lease predates this contract. It is read as *unowned* rather than
*owned forever*, which lets a legacy stranded attempt finally make progress without anyone editing
history to achieve it.

### 12f. What is honestly guaranteed

```text
exactly one canonical durable artifact per correlation id     — guaranteed
exactly one durable outcome per correlation id                — guaranteed
exactly one provider call per correlation id                  — NOT guaranteed
```

A process can always die after the wire response and before the local commit, so a real external
provider may be asked twice for one correlation id. This is **at-least-once provider attempts with
an exactly-once canonical result**, and it is stated plainly because assuming the stronger property
is how the stranding defect came to be written. Each attempt is counted and audited, so "how many
times was a provider actually asked" is answerable from the record rather than inferred. When a
live provider is authorized (M3.6B, still unauthorized), it must supply the provider an idempotency
token derived from `(correlation_id, attempt)` where the vendor supports one; that is what would
upgrade at-least-once to effectively-once at the wire.

### 12g. Who authors the plan

```text
The planner MUST be a seated participant of THIS discussion whose stored matched_capabilities
include plan_project. There is no fallback.
```

Deterministic when several qualify: lowest `seat_index`, so a replay attributes the plan to the
same principal rather than merely a valid one. Capabilities are read as the router matched them
**at open time**, not re-derived at decision time — a discussion is a record of who was in the
room, and re-deriving membership later would let a roster change rewrite the authorship of a
decision already reached.

An earlier implementation fell back to the capability router over current project membership when
no seated planner existed. That fallback is removed. What it produced was a false attribution: a
principal who had never seen the discussion recorded as the author of the plan that discussion
selected, indistinguishable afterwards from a plan its author had argued for. It is the same class
of defect as accepting `decided_by` from the request.

A discussion with no seated planner is refused — before any reasoning call, so the refusal is also
cheap. A discussion intended to produce a planning decision should therefore name `plan_project`
among its `required_capabilities` when it is opened; AT-M3.3 already fails closed at open time if
the roster cannot cover a required capability, which is the only moment that guarantee can honestly
be given. Legacy converged discussions without one are refused, never reopened, reseated or
rebound.

### 12h. The M3.4 candidate flow

1. Read the ledger. An already-finalized discussion replays its canonical result.
2. Admit the discussion; resolve the seated planner, or fail closed.
3. `decompose_plan`, **outside every lock and transaction**. Fresh or replayed, the artifact is the
   same one; `uq_reasoning_invocations_correlation` over a discussion-derived correlation id makes
   "one planner call per discussion" a database fact.
4. A short transaction: lock the discussion row, re-check the ledger, re-scan for a candidate,
   insert one if absent.
5. The decision transaction, unchanged.

The reasoning call used to happen *inside* the discussion row lock, because a worker that lost the
race had no way to obtain the artifact and had to wait for the winner to write the message. A
durable artifact removes that need — every worker recovers the same plan independently — so the
lock shrank to the message `INSERT`, which is also what makes this shape safe for a live provider,
where holding a database lock across a network call would not be.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
