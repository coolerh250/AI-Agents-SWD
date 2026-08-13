# Autonomous Team — Orchestration, Debug and Replan Model

> **Architecture contract only. Nothing here is implemented. No runtime, backend, API, frontend,
> database, migration or event change. `production_executed_true_count: 0`.**

Implements AT-D04. Machine-verified starting position: the orchestrator's LangGraph is a linear
chain (`intake -> requirement -> policy -> approval -> audit -> dispatch -> END`) with **no
conditional edges**, and `DebugAttempt` / `debug_attempt` has **zero** occurrences.

## 1. Team phase state model

This vocabulary describes the **team/project phase**. It is a different domain from
`DeliverySubmission.status` and must never replace it (section 8).

```text
PLANNING            decomposing a Goal into a PlanRevision
DISCUSSING          the team is converging on an approach; a decision is pending
READY               an accepted plan exists with owned, unblocked work
EXECUTING           one or more runs are in flight
VERIFYING           execution finished; tests and acceptance criteria are being evaluated
DEBUGGING           verification failed; a DebugAttempt is open
REPLANNING          debugging concluded the plan is wrong; a new revision is being authored
WAITING_FOR_HUMAN   blocked on a clarification answer or a policy approval
BLOCKED             blocked on something the team cannot resolve and no human request is open
DELIVERING          work is complete and a delivery submission is being prepared
COMPLETED           delivery accepted
HALTED              stopped by human intervention or by budget exhaustion
```

## 2. Transitions

```text
PLANNING     -> DISCUSSING          plan drafted, team review needed
PLANNING     -> READY               plan accepted without contest
DISCUSSING   -> PLANNING            decision requires a different decomposition
DISCUSSING   -> READY               TeamDecision accepted the plan
READY        -> EXECUTING           a work item is dispatched to its owner
EXECUTING    -> VERIFYING           run completed; evidence available
EXECUTING    -> BLOCKED             a hard dependency is unmet
VERIFYING    -> DELIVERING          PASS, and no work remains
VERIFYING    -> READY               PASS, and work remains
VERIFYING    -> DEBUGGING           FAIL  (the back-edge entry)
DEBUGGING    -> EXECUTING           fix ready; re-execute
DEBUGGING    -> REPLANNING          plan invalid; the artifact is not the problem
DEBUGGING    -> WAITING_FOR_HUMAN   diagnosis needs information only a human has
REPLANNING   -> READY               new PlanRevision accepted
REPLANNING   -> EXECUTING           new revision accepted and immediately dispatchable
any          -> WAITING_FOR_HUMAN   clarification asked or approval required
WAITING_FOR_HUMAN -> previous       answer or approval received
any          -> HALTED              human halt, or attempt budget exhausted
DELIVERING   -> COMPLETED           ProductOwnerDecision accepted
DELIVERING   -> READY               ProductOwnerDecision requested changes
```

## 3. Back-edge semantics (D04-R6)

The four transitions that make this a loop rather than a pipeline:

```text
VERIFYING  --failure-->        DEBUGGING
DEBUGGING  --fix ready-->      EXECUTING
DEBUGGING  --plan invalid-->   REPLANNING
REPLANNING --revision accepted--> READY / EXECUTING
```

```text
Removing any of these four reduces the model to the current linear pipeline.
INV-06 and the negative probes verify the back-edge is present and that retry is not substituted
for it.
```

The second and third are the genuine decision point: debugging must be able to conclude *the code
is wrong* (fix and re-execute) **or** *the plan is wrong* (replan). A system that can only do the
first will loop forever on a goal its plan cannot satisfy.

## 4. DebugAttempt

```text
debug_attempt_id
work_item_id
run_id                          the failing run being diagnosed
failure_ref                     QA finding / test failure / error evidence
diagnosing_principal            who is diagnosing
hypothesis_summary              what is believed to be wrong -- a conclusion, not a reasoning trace
planned_fix_ref                 the artifact change or plan change proposed
result                          fix_applied | fix_failed | plan_invalid | inconclusive |
                                escalated | abandoned
resulting_run_id                nullable -- the re-execution this attempt produced
resulting_plan_revision_id      nullable -- set when result = plan_invalid
attempt_number                  monotonic per (work_item_id, failure_ref)
created_at
```

```text
hypothesis_summary is a SUMMARY. The chain-of-thought prohibition (AT-D03 / INV-04) applies to
DebugAttempt exactly as it applies to TeamMessage.
```

## 5. Retry versus Debug (D04, INV-06)

```text
INFRASTRUCTURE RETRY
    definition   repeat the SAME operation with the SAME inputs after a transient failure
    changes      nothing -- no artifact, no plan, no ownership
    mechanism    StreamAgent._handle_failure, retry_count, stream.deadletter
    layer        L4 reliability
    evidence     retry_count, dead-letter rows

DEBUG ATTEMPT
    definition   ANALYSE a failure, MODIFY an artifact or the plan, then RE-EXECUTE
    changes      an artifact, or a PlanRevision, or both
    mechanism    DebugAttempt
    layer        L4 autonomous behaviour
    evidence     hypothesis, planned fix, resulting run, result classification
```

```text
DLQ is a reliability mechanism. It is NOT an autonomous debugging model.
Counting retries as debugging would let "we retried it five times" be reported as "the team
debugged it", which is the specific false-complete this contract forbids.
```

The existing three-bucket auto-fix path (`CodeAutoFixAgent`: missing test file, PR draft sections,
syntax error) is closer to debugging than retry is — it diagnoses and modifies. It is still not a
DebugAttempt, because it cannot select a responsible principal and its diagnosis is a lookup table.
It is classified `PARTIAL` and is a valid AT-M4 starting point, not a completed capability.

## 6. Attempt budget and termination (D04-R7)

Every loop is bounded. Unbounded autonomy is not autonomy, it is a runaway.

```text
per-failure debug budget      max DebugAttempts for one (work_item, failure_ref)
per-work-item execution budget max runs for one work item across all revisions
per-goal replan budget        max PlanRevisions for one Goal
per-goal wall-clock budget    max elapsed time before escalation
per-goal cost budget          references the EXISTING llm_budget / cost governance contracts
```

```text
Concrete values are NOT set by AT-M1. They are policy, owned by AT-M4, and must be
project-configurable rather than compiled in -- the same mistake ADR-66D-09 avoided by fixing the
QA rerun bound in an authorized stage rather than inventing it.
```

### Termination

```text
budget exhausted        -> WAITING_FOR_HUMAN with an escalation summary, or HALTED
no progress detected    -> the same failure_ref recurring with no artifact or plan change between
                           attempts is NOT progress; it terminates the loop
human halt              -> HALTED immediately, from any phase
goal achieved           -> DELIVERING
goal abandoned          -> HALTED
```

```text
"No progress" is defined structurally, not heuristically: if attempt N+1 changed neither an
artifact nor a PlanRevision, it was a retry wearing a debug label, and the loop stops.
```

## 7. Dynamic dispatch (D04-R4)

```text
INPUTS
    work item                required capabilities, work type, acceptance criteria
    dependencies             what must complete first
    current team             ProjectTeamMembership for the project
    agent capabilities       AgentProfile.capabilities
    policy constraints       production-effect refusal, tool policy, approval requirements
    availability             current load / in-flight ownership

OUTPUTS
    owner principal
    dispatch decision        assigned | deferred | refused | escalated
    reason summary           why this principal, or why not dispatched
```

```text
Static YAML mapping (infra/delivery/work-item-dispatch-policy.yaml) is DEMOTED.
    permitted as   fallback, test fixture, policy seed
    forbidden as   the autonomous source of truth for ownership
```

Conditional routing replaces the linear graph: the next node is a function of run outcome, budget
state, policy result and plan validity — not a fixed edge.

## 8. Domain separation (hard)

```text
Team phase vocabulary          PLANNING ... HALTED         (this document)
DeliverySubmission statuses    DRAFT ... EXPIRED           (66D, PRESERVED)
```

```text
These are DIFFERENT DOMAINS and MUST NOT be merged, mapped or substituted.
The team phase describes what the TEAM is doing.
The submission status describes where a DELIVERY is in review.
A team may be DEBUGGING while its submission is UNDER_REVIEW; both are true at once.
```

The nine canonical submission statuses, the six Review Gate Actions and the three Product Owner
Final Decisions are untouched by this document.

## 9. Dependencies

```text
Requires    PlanRevision, ownership, ActorPrincipal, TeamDecision
Preserves   DLQ / retry machinery, QA evidence model, audit chain, DeliverySubmission statuses
Enables     the functional POC loop
Slices      AT-M4-BE1 (phase model), AT-M4-BE2 (DebugAttempt), AT-M4-BE3 (budgets/termination),
            AT-M4-BE4 (conditional routing)
Status      CONTRACT_ONLY / NOT IMPLEMENTED
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
