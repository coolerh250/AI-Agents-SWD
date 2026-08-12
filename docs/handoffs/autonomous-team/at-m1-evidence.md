# AT-M1 — Autonomous Team Architecture Reset (Evidence)

> **Architecture, contract and documentation only. No runtime, backend, API, frontend, database,
> migration, event, deployment, identity, secret or feature-gate change. No container, database,
> Redis, Kubernetes, Vault, OIDC provider, agent workflow or external provider started. No shared
> database touched. `production_executed_true_count: 0`.**

## 1. Canonical baseline and preflight

```text
origin/main:      2d4da808b1a89ea278fbb760e27f49047995165e   MATCH (expected SHA)
Worktree:         CLEAN
Branch:           architecture/at-m1-autonomous-team-reset, created from the exact baseline
PR #28:           OPEN, NOT MERGED, head c9145cd848a211a9dd2bbff672c532da364eaa55
PR #28 treatment: HOLD / PRESERVE / NON-CANONICAL -- not merged, modified, rebased or cherry-picked
```

## 2. AT_M1_CANONICAL_INPUT_REGISTRY

| Artifact | Authority tier | Current status | AT-M1 treatment |
| --- | --- | --- | --- |
| `docs/contracts/66d-delivery-acceptance/step66d-delivery-decision-model-binding-decisions.md` | Product Owner binding | CANONICAL / BINDING | **preserve** |
| `docs/contracts/66d-delivery-acceptance/step66d-d05-review-task-active-state-amendment.md` | Product Owner binding | BINDING | **preserve** |
| `docs/contracts/66d-delivery-acceptance/step66d-canonical-terminology-registry.md` | contract | canonical | **reference-only** |
| `docs/architecture/66d-delivery-acceptance/step66d-arch1-contract-freeze.md` | architecture contract | frozen | **preserve** |
| `docs/architecture/66d-delivery-acceptance/step66d-arch1-domain-and-state-model.md` | architecture contract | frozen, D05-annotated | **preserve** |
| `docs/architecture/66d-delivery-acceptance/step66d-arch1-api-event-audit-contracts.md` | architecture contract | frozen | **preserve** |
| `docs/architecture/66d-delivery-acceptance/step66d-arch1-read-model-and-security-boundary.md` | architecture contract | frozen | **preserve** |
| `docs/design/66d-delivery-acceptance/step66d-design-delivery-inbox-spec.md` | design contract | frozen | **amend** (66D-DESIGN-v2, middle journey only) |
| `docs/design/66d-delivery-acceptance/step66d-design-unified-control-center-ia.md` | design contract | frozen | **amend** (IA requirements only) |
| `docs/decisions/step66d-arch1-architecture-decisions.md` | ADR (ADR-66D-01..10) | ACCEPTED | **preserve** |
| `shared/sdk/tasks/rbac.py` (`TASK_ROLES`) | runtime contract | implemented | **preserve, unmodified** |
| `migrations/030_workroom_clarification_foundation.sql` (`task_messages`) | runtime | implemented | **preserve** |
| `shared/sdk/agent_discussion/` | runtime | implemented (template) | **supersede as the collaboration model; retain as fixture** |
| `shared/sdk/project_planning/task_graph.py` | runtime | implemented (template) | **supersede as the canonical planner; retain as fixture** |
| `shared/sdk/work_items/dispatcher.py` + `infra/delivery/work-item-dispatch-policy.yaml` | runtime | implemented (static) | **demote to fallback / policy seed** |
| `apps/orchestrator/src/workflow.py` (LangGraph) | runtime | implemented (linear) | **supersede with conditional routing (AT-M4)** |
| `shared/sdk/base_agent/stream_agent.py` | runtime | implemented | **reference-only** (retry/DLQ preserved) |
| `shared/sdk/workspace_operator/` | runtime | implemented (real exec) | **preserve** |
| Step 66C.4 clarification expiry contract | Product Owner binding | BINDING | **preserve; AT-D09 OPEN** |
| Binding decision D-1 (66SYNC.1) | Product Owner binding | BINDING | **preserve** |
| PR #28 (`implementation/66d-be1-...`) | non-canonical branch | OPEN / HELD | **hold; AT-M7 input** |

## 3. Rebaseline verification (§4)

Re-derived from source at this baseline. Not carried over from the audit report.

| # | Finding | Verdict | Machine evidence |
| --- | --- | --- | --- |
| A | agents are fixed-chain workflow workers | **CONFIRMED** | `StreamAgent.input_stream` / `output_stream` are class attributes; chain `stream.tasks -> requirements -> development -> qa -> deployments` is compile-time |
| B | "agent discussion" is deterministic/template-driven | **CONFIRMED** | `REVIEW_MODES = (deterministic_template, llm_assisted_disabled, human_review)`; `contribution_templates.py` holds hard-coded strings, all authored by `design-review-agent` |
| C | project planning is template-driven | **CONFIRMED** | `_FASTAPI_TODO_MILESTONES` (7), `_FASTAPI_TODO_WORK_ITEMS` (9), `_FASTAPI_TODO_DEPENDENCIES` (11) are Python literals |
| D | dynamic delegation is absent | **CONFIRMED** | 0 recipient/addressing fields in `shared/` |
| E | replanning is absent | **CONFIRMED** | 0 occurrences of `PlanRevision`/`plan_revision`; LangGraph has no conditional edges |
| F | execution and test runners are real | **CONFIRMED** | `command_runner.py` `subprocess.run(shell=False)` with `ALLOWED_MODULES`; `run_pytest` records real results |
| G | workroom substrate exists but is not team collaboration | **CONFIRMED** | `task_messages` supports `sender_type=agent`, but no runtime agent writes one and there is no recipient field |
| H | Task and Project/WorkItem are separate user-facing models | **CONFIRMED** | `App.tsx`: `/tasks`, `/tasks/:taskId`, `/tasks/:taskId/workroom` vs `/projects`, `/projects/:projectId`, `/task-graph` |
| I | delivery/acceptance is more mature than the middle journey | **CONFIRMED** | legacy `delivery_packages` implemented; `DeliverySubmission` appears on main only in verifiers/tests/docs |

```text
Discrepancies against the audit: NONE. All nine findings still hold at this baseline.
```

Additional machine counts taken at this baseline:

```text
ActorPrincipal / principal_id      0 occurrences        <- SUPERSEDED, see section 4a
PlanRevision / plan_revision       0 occurrences
DebugAttempt / debug_attempt       0 occurrences
recipient/addressing fields        0 occurrences
Handoff                            2 occurrences, both legacy delivery `handoff_summaries`
                                   (migration 021) -- an unrelated document concept
                                                        <- SUPERSEDED, see section 4a
TASK_ROLES                         6 roles, all human, unchanged
```

## 4a. Evidence corrections (AT-M1-RM1)

AT-M1-R1 proved two of the counts above were wrong. Both are corrected here from fresh
machine measurement at `POST_GOV1_CANONICAL_MAIN` (`fa5e5c4`). The rows above are left in place,
annotated, because they are what this stage originally reported.

### EVIDENCE-01 — `principal_id`

The original row conflated two different names. `ActorPrincipal` is genuinely absent; `principal_id`
is not.

```text
Scope:     git grep at fa5e5c4 -- apps/ shared/ agents/ services/ migrations/
Command:   git grep -o "principal_id"            -> 25 occurrences across 7 files
           git grep -o "ActorPrincipal|actor_principal" -> 0
           git grep -o "principal_type"          -> 0
           git grep -o "ProjectTeamMembership"   -> 0
```

```text
apps/orchestrator/src/operations_replay_api.py          2
apps/orchestrator/src/operations_resume_api.py          3
shared/sdk/tasks/authorization_policy.py                2
shared/sdk/tasks/authorization_service.py               7
shared/sdk/tasks/production_approval_service.py         3
shared/sdk/tasks/replay_service.py                      4
shared/sdk/tasks/resume_service.py                      4
```

Classification: every occurrence is `AuthorizationActor.principal_id: str` — the identifier of the
**task/authorization actor** answering "who requested or approved this operation". It is not
`ActorPrincipal`, carries no `principal_type`, expresses no autonomous-agent functional role, and
has no `ProjectTeamMembership`. The existing `Actor` is an authorization subject, not a team member.

```text
ActorPrincipal capability state:  CONTRACT_ONLY   (unchanged -- 0 implementation occurrences)
```

### EVIDENCE-02 — `Handoff`

The original count of 2 was scoped to migration 021 alone. Repo-wide the legacy concept is far more
present, and none of it is the autonomous work-transfer entity.

```text
Scope:     git grep at fa5e5c4 -- apps/ shared/ agents/ services/ migrations/
Command:   git grep -oi "handoff"                        -> 77 occurrences across 14 files
           git grep -o "handoff_summaries|handoff_summary" -> 24
           git grep -o "class Handoff|CREATE TABLE handoffs|handoff_id" -> 3
           git grep -o "assigned_to_agent|reassign|work_transfer" -> 0
```

The only declared type is `HandoffSummary` in `shared/sdk/delivery_package/models.py`; the other two
hits are `handoff_ids` / `handoff_summary_ids` in `package_builder.py`. All 14 files sit in the
legacy `delivery_package` domain.

Classification: these are **delivery-package document sections** — a summary written into an
exported delivery package. They transfer no ownership, name no from/to principal, carry no
acceptance state, and there is no agent reassignment primitive anywhere (0 occurrences).

```text
Legacy delivery handoff_summaries:        IMPLEMENTED, but a document concept
Autonomous work-transfer Handoff entity:  NOT_IMPLEMENTED / CONTRACT_ONLY target (unchanged)
```

Legacy delivery handoff summaries do **not** implement autonomous team handoff.

## 4. Binding decisions recorded

```text
AT-D01  Execution source of truth        RESOLVED / BINDING
AT-D02  Agent principal model            RESOLVED / BINDING
AT-D03  Collaboration model              RESOLVED / BINDING
AT-D04  Planning / orchestration model   RESOLVED / BINDING
AT-D05  66D-DESIGN-v2 scoped amendment   RESOLVED / BINDING
AT-D09  Clarification expiry semantics   OPEN / DEFERRED -- deliberately not decided
```

## 5. Canonical entities defined (all CONTRACT_ONLY)

```text
ActorPrincipal          principal_id, principal_type, display_name, status
AgentProfile            agent_id, principal_id, role, capabilities, tool policy ref, provider ref
ProjectTeamMembership   project_id, agent_principal_id, functional_role, membership_state, dates
ConversationThread      thread_id, project_id, goal_ref, optional work_item/run, type, state
TeamMessage             addressing (principal/role/team), threading, type, summary, refs, audit
TeamDecision            options_considered, selected_option, rationale_summary, dissent_summary
PlanRevision            revision_number, reason, supersedes_revision_id, status
Ownership               owner_principal_id, assigned_at, assignment_reason, assignment_ref
Handoff                 from/to principal, reason, context refs, state, accepted_at
DebugAttempt            failure_ref, hypothesis_summary, planned_fix_ref, result, attempt_number
Goal                    statement, acceptance_criteria, constraints, created_by
```

## 6. Supersessions and preservations

```text
SUPERSEDED (as target architecture, retained as fixture)
  shared/sdk/agent_discussion         superseded as the COLLABORATION MODEL
  shared/sdk/project_planning/task_graph.py  superseded as the CANONICAL PLANNER
  static dispatch YAML                demoted to fallback / test fixture / policy seed
  linear LangGraph routing            superseded by conditional, loop-aware routing

PRESERVED UNCHANGED
  binding decision D-1                66SYNC.1 execution lineage
  66D-D01 .. 66D-D05                  delivery decision model
  ADR-66D-01 .. ADR-66D-10
  Delivery Review, Review Gate Actions, ProductOwnerDecision
  Safety, evidence and cost/external-action contracts
  TASK_ROLES (six human roles)
  task_messages and the task-scoped workroom
  clarification expiry contract (66C.4)
  retry / DLQ reliability machinery
  workspace operator execution and test runners
  audit chain, approval engine, policy engine, secret references
```

## 7. Open decisions

```text
AT-D09  Clarification expiry execution semantics -- OPEN
        The 66C.4 contract REMAINS AUTHORITATIVE. AT-M1 did not canonicalize permissive
        continuation. It is recorded as an open question, not as an ADR.
```

## 8. Capability matrix

Full registry: `docs/contracts/autonomous-team/at-capability-state-registry.json`.

```text
Entries          30
IMPLEMENTED       7    Execution, TestExecution, Retry, DLQ, Audit, Approvals, Secrets
PARTIAL          10    Decision, Assignment, CodeGeneration, QA, Diagnosis, Debug, Delivery,
                       SharedContext, RuntimeDeployment, LLMReasoning
MOCK_ONLY         2    Discussion, Planning
CONTRACT_ONLY     5    Goal, Team, AgentPrincipal, Acceptance, Identity
NOT_IMPLEMENTED   5    Proposal, PlanRevision, Delegation, Handoff, Replan
DEFERRED          1    VectorRetrieval
POC-blocking     18
```

Totals are recomputed from the entries by the verifier (`check125`), so they cannot drift from the
data they summarise.

## 9. Dependency graph

```text
ActorPrincipal / AgentProfile                    AT-M2   POC-BLOCKING
        |
ProjectTeamMembership                            AT-M2   POC-BLOCKING
        |
Conversation / TeamDecision / Handoff / Ownership AT-M2   POC-BLOCKING
        |
Goal / PlanRevision / Dynamic Dispatch            AT-M3   POC-BLOCKING
        |
Execution / Verification / Debug / Replan         AT-M4   POC-BLOCKING
        |
Autonomous Team UX v2                             AT-M5   POC-USEFUL
        |
Functional Autonomous Team POC                    AT-M6   goal
        |
Delivery & Acceptance Hardening                   AT-M7   POC-USEFUL
        |
Enterprise / Production Platform                  AT-M8   PRODUCTION-BLOCKING
```

## 10. Milestones

```text
AT-M2  Team Identity & Collaboration Core     NOT AUTHORIZED
AT-M3  Autonomous Planner & Dynamic Dispatch  NOT AUTHORIZED
AT-M4  Autonomous Execution & Debug Loop      NOT AUTHORIZED
AT-M5  Autonomous Team Product UX v2          NOT AUTHORIZED
AT-M6  Functional Autonomous Team POC         NOT AUTHORIZED
AT-M7  Delivery & Acceptance Hardening        NOT AUTHORIZED
AT-M8  Enterprise / Production Platform       NOT AUTHORIZED
```

## 11. Architecture invariants

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

## 12. PR #28

```text
State           OPEN / NOT MERGED
Head            c9145cd848a211a9dd2bbff672c532da364eaa55
Treatment       HOLD / PRESERVE / NON-CANONICAL
Modified?       NO -- not merged, not modified, not rebased, not cherry-picked, not closed
Future role     AT-M7 input
Blocks          nothing in AT-M1 .. AT-M6
```

## 13. Safety

```text
Runtime implementation  NONE       Migration              NONE
API                     NONE       Frontend               NONE
Infra                   NONE       Deployment             NONE
Shared DB               NOT TOUCHED  Secret access        NONE
External action         NONE       TASK_ROLES             UNCHANGED
Identity                UNCHANGED  source/progress.md     UNCHANGED
PR #28                  UNCHANGED
production_executed_true_count:  0
```

No secret, credential, private key, client secret, DSN, internal credential identifier, real
account identifier, raw token or private reasoning appears in any AT-M1 artifact.

## 14. Regression (§36)

```text
Suites run:  66SYNC.1 canonical (5 modules), 66D alignment/architecture/design (9 modules),
             66D-D05 / CR1 / CR1-M1, TASK_ROLES and project/work-item lineage tests
Result:      4 failed, 889 passed
```

### Classification

```text
PRE-EXISTING -- not caused by AT-M1 (2)
    tests/test_step66d_align1_rm1_fixed_range_remediation.py::test_66d_decisions_untouched_by_this_remediation
    tests/test_step66d_align1_rm1_fixed_range_remediation.py::test_rm1_verifier_passes
    Cause: the ALIGN1-RM1 verifier's check23 diffs the 66D decision documents against HEAD, so
    Step 66D-BE1-CR1 adding 66D-D05 to the binding-decisions registry, the terminology registry
    and the supersession matrix already trips it on canonical main. Measured at 2d4da80.

CURRENT-STATE ARCHITECTURE TEST needing AT-M1-aware supersession (2)
    tests/test_step66d_align1_delivery_decision_model.py::test_verifier_passes
    tests/test_step66d_align1_delivery_decision_model.py::test_changed_paths_are_within_scope
    Cause: scripts/verify_step66d_align1_delivery_decision_model.py check30 allows only
        ("docs/", "scripts/verify_step66", "tests/test_step66")  + source/progress.md
    Every other path in ALIGN1_BASELINE...HEAD is reported as "outside the allowed alignment
    scope". AT-M1's verifier and tests are scripts/verify_at_m1_* and tests/test_at_m1_*, which
    do not carry the `step66` stage prefix.
```

```text
NOT REPAIRED BY THIS STAGE.
§36 forbids rewriting a historical verifier in the same stage that needs the change. Reported for
an authorized remediation stage instead.
```

The finding is narrower and more interesting than a drifting range: the allowlist is bound to a
**stage naming convention**, not to a path category. `AT` is the first stage family that is not
named `step66`, so AT-M1 is simply the first change to expose it. Every future non-`step66` stage
will trip the same guard. The repair is to widen the allowlist to cover an authorized stage's own
verifier and tests regardless of naming prefix, or to freeze the range to the ALIGN1 stage head —
the same frozen-range repair Step 66D-BE1-CR1-RM1 applied to the DESIGN-M1 test.

### Environment note

Two further failures observed in a first run
(`test_no_be1_implementation_exists`, `test_no_migration_or_implementation_was_created`) were
caused by stale `__pycache__` bytecode left in `shared/sdk/delivery_acceptance/` by an earlier
branch's test run. The directory was untracked and gitignored, so `git status` was clean while the
path still existed on disk. Removing the generated bytecode cleared both; they are **not** AT-M1
findings and **not** repository changes.

## 15. Advisories

```text
ADV-DRIFT-PROGRESS-01     TRACKED / OUT OF SCOPE -- source/progress.md deliberately unchanged
ADV-UTF8-01               TRACKED / OUT OF SCOPE
ADV-SUITE-01              TRACKED / OUT OF SCOPE
GOV-REPO-IDENTIFIER-01    TRACKED / OUT OF SCOPE
ADV-DRIFT-BE1-GUARDS-01   TRACKED / OUT OF SCOPE -- raised by PR #28, unaffected by AT-M1 because
                          AT-M1 touches no migrations/ or shared/ path
```

## 16. AT-M1-RM1 closure

```text
POST_GOV1_CANONICAL_MAIN:   fa5e5c4e6712fbbc59bf18d2ee33421c28f9b009
Sync merge into PR #29:     b11acbe2d0f467a359cafc3f13932cba275d60ec
                            parents 3f18e07 (AT-M1 head) + fa5e5c4 (canonical main)
                            non-squash; the five original AT-M1 commits are untouched
```

### A-01 — post-GOV1 baseline re-pin

Reproduced against real canonical main, not a simulated overlay:

```text
BEFORE  AT_M1_BASELINE = 2d4da80 (pre-GOV1)
        AT_M1_ARCHITECTURE_RESET_VERIFY: checks=164 failures=2
        check02  8 unexpected GOV1 paths inside 2d4da80...HEAD
        check09  the non-docs set no longer equals [verifier, tests]

AFTER   AT_M1_BASELINE = fa5e5c4
        AT_M1_ARCHITECTURE_RESET_VERIFY: checks=210 failures=0
        GOV1 paths in AT-M1 positive scope: 0   (check03c enforces this permanently)
```

References found 7, updated 7 — the verifier constants, the test constant, the architecture reset,
the binding decisions, the terminology registry, the capability state registry and the ADRs. Two
occurrences in this document (section 1 preflight, section 14) record what was measured at AT-M1
time and are **preserved as historical truth**. GOV1's own baseline constants were not touched.

### Verifier effectiveness (INV-04, INV-08)

Both findings were reproduced as real escapes before being fixed:

```text
INV-04  checks 38-44 compared a whole-document count against an identically computed
        whole-document count, so they reduced to "the name appears somewhere".
        ESCAPE  contracting private_chain_of_thought inside the TeamMessage block passed all 7.
        FIX     check45a-e parse the ACTUAL contract into field names; prohibition prose still
                passes, a contracted member cannot.

INV-08  check101/102 searched the whole evidence file for HOLD and NON-CANONICAL.
        ESCAPE  "PR #28 treatment: CANONICAL / ACTIVE / MERGE-READY" passed, rescued by
                incidental text elsewhere in the file.
        FIX     check101a / check102a-e target the authoritative treatment line and the
                canonical-input-registry row; claims_canonical() discounts the NON-CANONICAL
                denial so a canonical claim cannot hide inside it.

AT-D09  Found by probe M12 DURING this stage, not by review: check104g tested "OPEN" in the
        whole precedence document, and an unrelated line contains OPEN_PRODUCT_OWNER_DECISIONS,
        so closing AT-D09 passed. Same defect class as INV-08; fixed the same way
        (check104g1-g3 target the AT-D09 statement).
```

### Mutation probes (§30)

Each applies one forbidden change in a disposable worktree and runs the real verifier as a
subprocess.

```text
M01 revert baseline to pre-GOV1        REJECTED     M07 contract raw_reasoning         REJECTED
M02 omit an original AT-M1 path        REJECTED     M08 PR #28 declared canonical      REJECTED
M03 admit a GOV1 path                  REJECTED     M09 PR #28 merge dependency        REJECTED
M04 remove a registration path         REJECTED     M10 remove AT precedence           REJECTED
M05 add an arbitrary 20th path         REJECTED     M11 AT-M2 marked authorized        REJECTED
M06 contract private_chain_of_thought  REJECTED     M12 close AT-D09                   REJECTED
                                    untampered control  PASS before and after
```

### Canonical registration

```text
docs/alignment/66-project-completion/master/canonical-source-of-truth-precedence.md
  AT-D01..AT-D05 registered as CURRENT TARGET ARCHITECTURE for the middle journey.
  Scoped, not global. 66D Delivery Review, the six Review Gate Actions, ProductOwnerDecision,
  Delivery/Acceptance boundaries, safety/evidence/cost contracts, the six human TASK_ROLES and
  binding decision D-1 are all listed as PRESERVED. AT-D09 stays OPEN / DEFERRED.

docs/alignment/66-project-completion/master/canonical-milestone-manifest.md
  AT-M0..AT-M8 registered as a SEPARATE track; M0-M7 are not renumbered or reordered.
  AT-M0 CLOSED · AT-M1 PENDING CANONICAL MERGE (not canonical -- PR #29 is not merged)
  AT-M2..AT-M6 NOT AUTHORIZED · AT-M7 deferred delivery/acceptance hardening · AT-M8 not started
  PR #28 recorded as a held AT-M7 input, not a dependency of AT-M1..AT-M6.
```

### Scope

```text
Baseline:            fa5e5c4        Changed paths: 19        Exact equality: YES
17 original AT-M1 paths + canonical-source-of-truth-precedence.md + canonical-milestone-manifest.md
Unexpected paths:    0              source/progress.md:      UNCHANGED
GOV1 files modified: 0              PR #28:                  UNCHANGED
```

### Forward handoff — AT-M1-M1 positive-scope hazard

`AT_M1_POSITIVE_RANGE` is still `AT_M1_BASELINE...HEAD`. That is correct while PR #29 is open,
because the 19-path registry bounds it exactly. It will **not** survive canonicalization: once
PR #29 merges, `HEAD` becomes main and advances, and the merge record's own paths will be reported
as unexpected — precisely what happened to GOV1 at AT-M1-GOV1-M1.

```text
AT-M1-M1 MUST, in the same commit as its merge record:
  freeze AT_M1_POSITIVE_RANGE to AT_M1_BASELINE...AT_M1_STAGE_HEAD (the merged PR #29 head)
  leave the rejection guards HEAD-relative so later runtime paths are still caught
Deliberately NOT done here: RM1 is not authorized to change canonicalization semantics, and the
frozen stage head is not knowable until PR #29 merges.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
