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
M05 add an arbitrary 20th path         REJECTED     M11 AT-M2 authorization flip       REJECTED
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

## 17. AT-M1-RM2 — R2 blocking defect closure

```text
AT-M1-R2 verdict:  REMEDIATION_REQUIRED  (2 blocking defects, both inside the 19-path scope)
RM2 scope:         DEF-R2-01 and DEF-R2-02 only. No 20th path. No architecture change.
```

### DEF-R2-01 — canonical capability registry carried two false evidence strings

Reproduced verbatim on the pre-RM2 head before any edit:

```text
AgentPrincipal.evidence  "ActorPrincipal / principal_id: 0 occurrences on main. ..."
Handoff.evidence         "Only 2 matches for handoff on main, both legacy delivery-package
                          handoff_summaries (migration 021) ..."
```

RM1 diagnosed both in section 4a of this document and corrected them **here**, but never in the
registry — whose only RM1 change was the `canonical_baseline` re-pin. The registry is
`"status": "CANONICAL"` and a Tier-1 supporting registry in the precedence record, and AT-M2 is
scoped by it, so the false strings were the ones that would actually be read.

Machine-measured afresh at `fa5e5c4`, scope `apps/ shared/ agents/ services/ migrations/`:

```text
git grep -o  "principal_id"                          25 occurrences,  7 files
git grep -oi "ActorPrincipal|actor_principal"          0
git grep -o  "principal_type"                          0
git grep -oi "ProjectTeamMembership"                   0

git grep -oi "handoff"                               77 occurrences, 14 files
git grep -o  "HandoffSummary"                        11
git grep -o  "handoff_summar[a-z]*"                  24
git grep -o  "handoff_id"                             2
recipient_principal_id · assigned_to_agent · reassign · work_transfer ·
ownership_transfer · owner_principal_id · transfer_ownership          0 each
```

Both corrected strings now state the measured truth and, critically, say **the names are not
free**. `Actor.principal_id` is the task/authorization subject that drives two-person control in
`authorization_policy.py`; it carries no `principal_type`, no agent functional role and no
`ProjectTeamMembership`, so it does not establish AT-D02. The 14 handoff files are
delivery-package **document sections** with no from/to principal, no ownership field and no
acceptance state.

```text
AgentPrincipal state:  CONTRACT_ONLY   UNCHANGED
Handoff state:         NOT_IMPLEMENTED UNCHANGED
Capability states changed by RM2:      0
Totals changed by RM2:                 0   (30 · 7/10/2/5/5/1 · poc_blocking 18 · prod_exec 0)
Guarded by:                            check128a-h, read from the structured entries
```

### DEF-R2-02 — AT-D09 binding status could still be closed

`check92`/`check93` tested `"OPEN"` and `"DEFERRED"` against the **whole** binding document, which
holds several unrelated tokens of each. Reproduced on the pre-RM2 head, one authoritative surface
at a time:

```text
section-6 STATUS  -> RESOLVED / CLOSED    verifier 210/0 PASS · tests 72 passed   ESCAPED
line-20 summary   -> RESOLVED / BINDING   verifier 210/0 PASS · tests 72 passed   ESCAPED
section-6 Decision -> RESOLVED            verifier 210/0 PASS · tests 1 failed    verifier escaped
remove non-decision declaration           verifier 210/1 FAIL                     rejected
Step 66C.4 -> SUPERSEDED                  verifier 210/1 FAIL                     rejected
```

This is the **third** instance of the same whole-file-substring defect class in this workstream,
after INV-08 and the AT-D09 precedence guard. All five authoritative surfaces are now targeted
structurally: `section_text()` isolates the AT-D09 section, `labelled_line()` reads the summary and
STATUS lines, `indented_value()` reads the Decision value, and `claims_at_d09_closed()` discounts
the required "NOT decided" wording before testing for RESOLVED / CLOSED / BINDING / ACCEPTED /
DECIDED.

```text
check92    AT-D09 section present            check92a/b  summary OPEN, no closure claim
check92c/d STATUS OPEN / DEFERRED, no closure check92e    Decision value == DEFERRED
check93    non-decision declaration present  check93a/b  Step 66C.4 authority, not superseded
```

The binding document itself is **unchanged** — its content was correct; this was a verifier defect.
The RM1 precedence hardening (`check104g1-g3`) is untouched.

### Mutation suite

```text
M01 old baseline            REJECT check03c      M10 remove AT precedence   REJECT check104a
M02 omit original path      REJECT check02/03/03a M11 authorize AT-M2       REJECT check104j
M03 admit GOV1 path         REJECT check02/03/03a M12a close AT-D09 (prec)  REJECT check104g1/g2/g3
M04 remove registration     REJECT check02/03a/03b M12b close AT-D09 (bind) REJECT check92c/92d
M05 arbitrary 20th path     REJECT check02/03    M13 false AgentPrincipal   REJECT check128b/128c
M06 private_chain_of_thought REJECT check45c     M14 false Handoff evidence REJECT check128f
M07 raw_reasoning           REJECT check45c      M15 binding STATUS closed  REJECT check92c/92d
M08 PR #28 canonical        REJECT check102/102a M16 binding Decision       REJECT check92e
M09 PR #28 dependency       REJECT check102b     M17 binding summary        REJECT check92a/92b
                                                 M18 remove 66C.4 authority REJECT check93a/93b
                            untampered control   PASS before and after
```

Every mutation is rejected by its intended semantic check. M02–M05 are registry-manipulation
mutations, so exact-set-equality and the cardinality/registration checks **are** their correct
semantic guards, not accidental bystanders.

### AT-D09 remains undecided

```text
Summary line:   AT-D09:  OPEN / DEFERRED -- not a decision, an open question (section 6)
Section 6:      STATUS:  OPEN / DEFERRED -- deliberately NOT decided by AT-M1
Decision:       DEFERRED
Step 66C.4 clarification expiry contract:  REMAINS AUTHORITATIVE
```

RM2 decides nothing. No clarification-expiry semantics were introduced or changed. Answering
AT-D09 still requires its own Product Owner decision.

### Advisory disposition

```text
ADV-R2-01  evidence section 12 free text        DEFERRED / NON-BLOCKING -- the authoritative
                                                treatment line and registry row are guarded
ADV-R2-02  AT_M1_M1_STAGE_HEAD_FREEZE_REQUIRED  CARRIED (section 16). R2 added a constraint:
                                                check04/05/06 derive from the same changed set,
                                                so AT-M1-M1 must separate positive stage scope
                                                from HEAD-relative rejection scope rather than
                                                freezing both
ADV-R2-03  INV-04 historical nuance             RECORDED, not rewritten: private_chain_of_thought
                                                escaped the old verifier but was caught by the old
                                                tests; raw_reasoning escaped BOTH. The forward
                                                behaviour was already correct.
```

---

## 18. AT-M1-RM3 — authorization register closure (DEF-R3-01)

AT-M1-R3 confirmed both R2 defects closed and found one blocking defect in the RM2 fix itself.

### Reproduction, before the fix

At `47d0246`, sole edit to the binding contract section 8:

The section-8 register value was changed from OPEN to a closure claim (the probe wording is not
reproduced here as a register line, so that this record cannot itself read as a canonical status):

```text
verifier:  checks=225 failures=0  PASS      <- complete escape
tests:     82 passed                        <- complete escape
```

RM2 hardened the AT-D09 gate by enumerating the surfaces the R2 finding named. The binding
contract states AT-D09's status on more surfaces than that list contained, so the same
false-canonical-status class survived on the surfaces nobody had enumerated.

### Surface inventory

Re-derived from the document rather than from the previous finding. Every line naming AT-D09 was
classified, not only the ones a review had cited.

```text
line  20  summary block AT-D09: OPEN / DEFERRED         AUTHORITATIVE   check92a, check92b
line 265  section-6 heading marker (OPEN)               AUTHORITATIVE   check92h, check92i  NEW
line 268  section-6 STATUS: OPEN / DEFERRED             AUTHORITATIVE   check92c, check92d
line 276  Step 66C.4 REMAINS AUTHORITATIVE              AUTHORITATIVE   check93a, check93b
line 279  section-6 Decision: DEFERRED                  AUTHORITATIVE   check92e
line 281  non-decision declaration                      AUTHORITATIVE   check93
line 308  section-8 register AT_D09: OPEN               AUTHORITATIVE   check92f, check92g  NEW
line 132  message-kind table entry "clarification"      DESCRIPTIVE     not gated
line 273  "UX suggestion under consideration"           DESCRIPTIVE     not gated
section 7 prohibited implications                       n/a -- states no AT-D09 status
```

The section-6 heading was a second escape, found by probing the inventory rather than the finding:
`(OPEN)` -> `(RESOLVED / BINDING)` also left verifier 225/0 PASS and 82 tests passing. It is fixed
under the same defect, not recorded as a new one.

### Closure

```text
check92f  section-8 register records AT-D09 as OPEN
check92g  section-8 register makes no closure claim
check92h  section-6 heading marks the question OPEN
check92i  section-6 heading makes no closure claim
check92j  no AT-D09 status surface exists that no named check reads
```

`AUTHORIZED` was added to `AT_D09_CLOSURE_CLAIMS`, so every AT-D09 surface rejects it uniformly.

`check92j` is the anti-subset guard: it collects every line that names AT-D09 **and** states a
state, and fails if any is not one of the surfaces a check reads. Adding a new status surface to
the contract now fails the verifier until that surface is guarded. Descriptive prose that names the
question without stating a state is not gated, per the RM3 constraint.

ADV-R3-02 closed: `test_at_d09_remains_open_and_not_an_adr` no longer carries the whole-document
`"AT-D09" in binding and "OPEN" in binding` form. Per-surface assertions replace it.

ADV-R3-01 recorded, not remediated: section 8 `AT_M2: NOT AUTHORIZED` is not gated on that line.
Its authoritative state is guarded on the manifest surface and in section 7. RM3 did not expand
into AT-M2 governance.

### AT-D09 status after RM3

```text
AT-D09:                                   OPEN / DEFERRED
Section-6 Decision:                       DEFERRED
Section-8 authorization register:         OPEN
Step 66C.4 clarification expiry contract: REMAINS AUTHORITATIVE
```

RM3 decides nothing. It makes the existing undecided state unfalsifiable.

---

## 19. AT-M1-RM4 — authority-surface completeness (DEF-R4-01, DEF-R4-02)

R4 established that RM3's guard was scoped along one axis only. This stage replaces it with a
domain-wide, subject-attributed mechanism.

### Why the previous mechanism could not hold

`states_at_d09_status` required the identifier AND a state token on the same physical line,
matched the identifier case-sensitively, and ran over one nominated file. Four independent
escapes followed from that single design: a label whose value continues on the next line; a value
whose subject is supplied by the enclosing section; a lowercase identifier; any assertion in the
other fifteen in-scope artifacts.

### Domain enumeration, performed before implementation

```text
in-scope markdown artifacts     16      (of the 19-path positive scope)
artifacts naming AT-D09          9
raw AT-D09 occurrences          46
attributed assertions           37
closure-claiming assertions      0      (after the evidence correction below)
```

Enumeration was re-derived from the artifacts, not from the R4 finding list. The R4 known
instances were treated as evidence of the class, not as the specification.

### Mechanism: attribution, not line matching

The unit is the ASSERTION, not the line. A value is attributed to AT-D09 only when AT-D09 is its
subject, across six structural forms:

```text
register         AT-D09: <value>            value may continue on the next line
heading-marker   ## 6. AT-D09 ... (OPEN)    parenthesised state in a heading that names it
section-label    Decision: / DEFERRED       subject supplied by the enclosing AT-D09 section
table-cell       | ... AT-D09 OPEN |        the cell naming it, not the whole row
block-entry      AT-D09  <tail>             inside a fenced register block
prose            AT-D09 is/remains <state>  requires a copula, so a title is not an assertion
```

Attribution is what makes the guard both complete and quiet. It is why
`AT-D01 .. AT-D05 (RESOLVED / BINDING), AT-D09 (OPEN)` yields `OPEN` rather than a false closure,
and why the finding title *"AT-D09 binding status could still be closed"* is correctly not an
assertion.

### Checks

```text
check92j  no assertion anywhere in the domain claims closure
check92k  any assertion stating a state must state OPEN / DEFERRED
check92l  anti-vacuity floor -- a broken extractor fails loudly instead of passing vacuously
check92m  AT-M2 authorization registers remain discoverable
check92n  AT-M2 registers still state NOT AUTHORIZED   (ADV-R3-01, same defect class)
```

`check92l` is a floor, not proof by count. `check92j` is what proves closure absence; the floor
exists only so that disabling discovery cannot make `check92j` vacuously true — probe P-EXTRACT
confirms it fires when the extractor is stubbed out.

Closure vocabulary extended to ANSWERED, COMPLETE, COMPLETED, SUPERSEDED, SUPERSEDES with
word-boundary matching. AUTHORITATIVE is deliberately excluded: *"Step 66C.4 REMAINS
AUTHORITATIVE"* is a preservation statement, and treating it as closure would have made the
guard reject the very sentence it exists to protect.

### Adversary matrix

```text
axis                              probe       verdict  intended check
cross-file                        P-CROSS     REJECT   check92j
cross-section                     P-SECT      REJECT   check92j
case variation                    P-CASE      REJECT   check92j
same-line                         P-LINE      REJECT   check92j
multiline / indented value        P-MULTI     REJECT   check92j
section-context subject           P-CTX       REJECT   check92j
alternate vocabulary (ANSWERED)   P-VOCAB     REJECT   check92j
semantic supersession of 66C.4    P-VOCAB2    REJECT   check92j
new authoritative surface         P-NEW       REJECT   check92j
extractor disabled                P-EXTRACT   REJECT   check92l
AT-M2 register authorization flip P-M2        REJECT   check92n

descriptive prose                 C-PROSE     PASS
historical / finding title        C-HIST      PASS
benign non-state metadata         C-META      PASS
negated closure claim             C-NEG       PASS
preservation statement            C-PRESERVE  PASS
```

P-MULTI escaped the first implementation and is recorded as an escape, not a pass: the label
pattern admitted only a parenthetical between identifier and colon, so `AT-D09 authorization
state:` fell through to the block-entry rule and its indented value was never read. Fixed by
bounding a qualifier window before the colon; the probe was not weakened.

### Evidence correction

This document's own section-8 reproduction line stated a mutation in register form
(`AT_D09:` followed by a closure value) and so read as a canonical status claim in the very
artifact set the guard protects. It is now described in prose. A record of a defect must not be
indistinguishable from the defect.

### Status after RM4

```text
AT-D09:                                   OPEN / DEFERRED
Section-6 Decision:                       DEFERRED
Section-8 authorization register:         OPEN
Step 66C.4 clarification expiry contract: REMAINS AUTHORITATIVE
AT-M2:                                    NOT AUTHORIZED
```

RM4 decides nothing. Guarding the AT-M2 register changes no AT-M2 authorization.

---

## 20. AT-M1-RM5 — authoritative state semantic validation (DEF-R5-01..07)

R5 returned seven blockers against RM4. They share one root cause, so RM5 replaces the model
rather than patching seven shapes.

### Why the lexical model could not close

RM4 asked *does this text contain a forbidden word?* That question is unclosable:

```text
DEF-R5-03  every unenumerated synonym is a new escape (SETTLED, RATIFIED, FINALIZED)
DEF-R5-02  deleting negators to control false positives made NO LONGER OPEN read as OPEN
DEF-R5-07  a token test cannot tell NOT BINDING from BINDING, so valid non-decisions
           were falsely rejected
```

The false-positive and false-negative failures were the same defect seen from two sides: a bag
of tokens carries no proposition, so it can neither be completed nor negated correctly.

### The model

Each discovered assertion is assigned a KIND, its CURRENT value is parsed with negation
preserved, and it is accepted only if it affirms a canonical allowed state for that kind.

```text
KIND                   ALLOWED CURRENT STATE
status                 OPEN or DEFERRED
decision               DEFERRED, or an explicit denial of a decision
authorization          NOT AUTHORIZED / NOT DECIDED, or an open state
authority              AUTHORITATIVE, and never superseded
non-decision           an explicit denial, and never a closure
at-m2-authorization    NOT AUTHORIZED
```

Acceptance is affirmative, so an authoritative value that does not affirm an allowed state is
rejected **without the offending term being enumerated anywhere**. CONCLUDED, ADJUDICATED and
PROMULGATED are all rejected although no list contains them. That is what ends the synonym
arms race.

Negation is preserved rather than deleted, so these are three different propositions:

```text
OPEN                 allowed
NOT OPEN             rejected -- negates the canonical state
NO LONGER OPEN       rejected -- negates the canonical state
```

Current state outranks history: `AUTHORIZED (previously NOT AUTHORIZED)` reads as AUTHORIZED and
is rejected, while `NOT AUTHORIZED (previously AUTHORIZED)` is accepted. A trailing `-- FALSE` is
read as the predicate, not a footnote, so the prohibited-implications block is not misread as
affirming its own claims.

### Discovery

```text
register         AT-D09: / AT_D09_STATUS: / AT-D09 authorization state:
heading-marker   ## 6. AT-D09 ... (OPEN)
section-label    Decision: / DEFERRED, subject supplied by the enclosing section
table-cell       the cell naming the subject, not the whole row
block-entry      a fenced register column
prose            any assertive sentence; no specific copula is required
```

Every branch is attempted; none exits past the others because its own pattern failed. Qualified
keys are part of the identifier, since `` cannot see `AT_D09_STATUS`. A label value may
continue on the next line or across a blank line. A label naming a different AT-family subject is
not attributed to AT-D09 even inside the AT-D09 section.

### Adversary matrix

```text
axis                              probe        verdict  intended check
cross-file                        A-FILE       REJECT   check92j
cross-section                     B-SECTION    REJECT   check92j
identifier case                   C-CASE       REJECT   check92j
qualified identifier key          D-QUALKEY    REJECT   check92j
same-line value                   E-SAMELINE   REJECT   check92j
label + indented value            F-MULTILINE  REJECT   check92j
label + blank line + value        G-BLANKLINE  REJECT   check92j
nonstandard assertive verb        H-VERB       REJECT   check92j
unknown closure synonym           I-UNKNOWN    REJECT   check92j
negated open state                J-NEGOPEN    REJECT   check92j
history qualifier                 K-HISTORY    REJECT   check92n
AT-M2 qualified key               L-M2QUAL     REJECT   check92n
AT-M2 predicated prose            M-M2PROSE    REJECT   check92n
new authoritative surface         N-NEWSURF    REJECT   check92j
contradictory current state       O-CONTRA     REJECT   check92j
extractor disabled                P-VACUITY    REJECT   check92l

descriptive prose                 C-DESC       PASS
historical finding title          C-HIST       PASS
benign metadata                   C-META       PASS
future / hypothetical             C-HYPO       PASS
hypothetical in a fenced block    C-HYPOF      PASS
NOT DECIDED                       C-NOTDEC     PASS
NOT BINDING                       C-NOTBIND    PASS
REMAINS AUTHORITATIVE             C-PRESERVE   PASS
AT-M2 NOT AUTHORIZED restated     C-M2NOT      PASS
```

C-M2NOT failed on the first implementation and is recorded as a failure, not a pass: an AT-M2
label inside the AT-D09 section was attributed to AT-D09. Fixed by subject attribution; the
control was not weakened.

### Status after RM5

```text
AT-D09:                                   OPEN / DEFERRED
Section-6 Decision:                       DEFERRED
Section-8 authorization register:         OPEN
Step 66C.4 clarification expiry contract: REMAINS AUTHORITATIVE
AT-M2:                                    NOT AUTHORIZED
```

RM5 decides nothing.

### Deferred

```text
ADV-R5-01  raw AT-D09 occurrence counts in this narrative go stale as the narrative itself
           adds references. Counts are NOT an invariant; R6 must re-derive the domain
           independently. Evidence-hygiene advisory only.
```

---

## 21. AT-M1-RM6 — canonical state carrier policy (AT-D10)

R6 returned four blockers and one design decision. The Product Owner decided AT-D10; this stage
canonicalizes it and rebuilds state validation on it.

### What R6 proved about RM5

RM5 replaced value-vocabulary enumeration with an affirmative allow-state predicate and reported
that as ending the synonym arms race. R6 showed the enumeration had been RELOCATED, not removed:

```text
record() returned early unless the VALUE held one of 21 enumerated state terms
                          or the KEY held one of 4 enumerated keyword groups
```

An assertion outside both enumerations never reached the semantic predicate at all. The RM5
fail-closed demonstration only ever exercised stateful keys -- the path where the gate lets
things through -- so the evidence of closure was itself scoped to the passing case.

### AT-D10

Recorded as a binding decision in section 9 of the binding contract, and in the summary block.
Structured carriers are the sole canonical authority; free prose is non-authoritative; the
structured carrier wins over contradictory prose; contradiction detection is advisory-only; the
policy governs AT-D09, AT-M2 and equivalent state until superseded.

### Carrier inventory, taken before the parser changed

```text
form              canonical instances   example
register                        11      AT_D09: OPEN   AT-M2..AT-M8: NOT AUTHORIZED
section-field                    3      Decision: / DEFERRED  (subject from the section)
heading-status                   1      ## 6. AT-D09 ... (OPEN)
table-state                      0      declared; unused by the corpus today
```

Exactly ONE heading in the whole domain carries a parenthesised state marker, and no canonical
artifact uses a table row to carry AT-D09 or AT-M2 state. The grammar was derived from that
inventory, not from the R6 escape examples.

### Ordering is the fix

```text
DISCOVERY (structural)  ->  KIND (from the key)  ->  VALUE  ->  VALIDATION
```

A subject-keyed field in a canonical artifact IS a carrier whatever noun qualifies its key and
whatever its value says. `AT_D09_XYZZY: ENACTED` is rejected, and neither XYZZY nor ENACTED
appears anywhere in the verifier -- a test asserts that absence, so the fix cannot silently
degrade into another word list.

### Heading authority — declared outcome B

The dash-delimited heading form is NOT a canonical carrier. Only a parenthesised marker in a
subject-declaring heading binds. That follows from the inventory rather than from making a probe
pass, and it leaves no "sometimes headings are authoritative" ambiguity. Reshaping the required
heading therefore does not change state by prose; it removes a REQUIRED carrier and fails
check92l.

### Free prose

Removed from canonical determination entirely. This resolves R6-B2 and R6-B3 together, in
opposite directions, without any natural-language inference:

```text
"AT-D09 should now be treated as RESOLVED"      cannot close AT-D09   (was an escape)
"It would be wrong to say AT-D09 is RESOLVED"   cannot break the gate (was a false positive)
```

Both were the same defect -- a fragment read without its sentence -- and both disappear once
prose is not a state channel.

### Anti-vacuity

Required-carrier COVERAGE, at (artifact, subject, kind, form) granularity. Probe D-HEADDEL first
rejected via the older nominated heading checks rather than the protocol guard, because coverage
was keyed without the form and the artifact's other status carriers still satisfied it. Recorded
as a miss and fixed; it now fails check92l on its own.

### Mutation matrix

```text
class                                probe        verdict  intended check
A unknown value on a carrier         A-*          REJECT   check92j   (3 unseen values)
B qualified structured field         B-*          REJECT   check92j   (3 unseen keys)
C multiline / blank-line value       C-MULTI/BLANK REJECT  check92j
D canonical heading form             D-HEADPAR    REJECT   check92j
  required heading removed           D-HEADDEL    REJECT   check92l
F structured conflict                F-CONFLICT   REJECT   check92j + check92n
G AT-M2 authorization (4 carriers)   G-*          REJECT   check92m
  anti-vacuity: discovery disabled   V-DISCOVERY  REJECT   check92l
  anti-vacuity: register deleted     V-REGDROP    REJECT   check92l

E non-canonical heading / prose      E-HEADNEW    PASS     state unchanged
  deontic prose closure              E-PROSE      PASS     state unchanged
  register shape in an evidence record E-EVID     PASS     state unchanged
controls: descriptive, historical, hypothetical, quoted, NOT DECIDED, NOT BINDING,
          criticism of a closure claim, noncanonical heading    all PASS
```

### Status after RM6

```text
AT-D09:                                   OPEN / DEFERRED
Section-6 Decision:                       DEFERRED
Step 66C.4 clarification expiry contract: REMAINS AUTHORITATIVE
AT-D10:                                   RESOLVED / BINDING
AT-M2:                                    NOT AUTHORIZED
```

RM6 introduces no Product Owner decision beyond the authorized AT-D10.

### Deferred, not bundled

```text
ADV-R5-01   stale narrative counts        different concern
ADV-R4-01   ALIGN1 fixed-range debt       different concern, outside AT-M1
ADV-R6-02   PR #29 body is stale in four places (17 paths / 164 checks / 52 tests /
            old baseline). Body text, not a contract; not bundled into a G2 repair.
AT_M1_M1_STAGE_HEAD_FREEZE_REQUIRED        future G3 canonicalization requirement
```

## 22. AT-M1-RM7 — atomic canonical carrier value rule (AT-D10.1)

Closes DEF-R7-01 and DEF-R7-02, both raised by the AT-M1-R7 independent audit. Both were
reproduced on the prior head before any change: with the escaping lines in place the verifier
reported 234 checks and 0 failures and the whole focused suite passed.

### What was wrong

DEF-R7-01. RM6 removed the state-vocabulary gate from carrier discovery but left a LEXICAL gate
in its place: the key qualifier had to be drawn from `[A-Za-z0-9 _'-]` and be at most 48
characters. A comma, an em dash, a slash, a period, a parenthetical after the noun, a longer
qualifier or a markdown list prefix therefore made a structured carrier invisible. The defect
family was not closed at RM6; the enumeration had moved from words to characters.

DEF-R7-02. The value reaching validation was truncated at the first ` -- ` or `;`, on the theory
that a trailing clause is a qualifier. An acceptable head could therefore shield a second
predicate, and check92j, check92m and check92n were blinded together because all three consumed
the same truncated value.

### AT-D10.1

The Product Owner resolved the underlying ambiguity: a canonical carrier expresses exactly ONE
proposition. Section 10 of the binding decisions contract records it. The verifier no longer has
to decide which clause of a multi-clause value wins; such a value is invalid as a carrier and
fails closed. Explanation moves outside the carrier, where AT-D10 already makes it
non-authoritative.

### Implementation

| concern | before | after |
| --- | --- | --- |
| key grammar | character class + 48-char bound | split at the first colon, no class, no bound |
| decoration | part of the grammar | stripped as formatting |
| value | truncated at ` -- ` / `;` | complete, including continuation lines |
| multi-clause | silently reduced to its head | rejected as non-atomic |
| section label | character class, any line in section | any label, fenced blocks only |

`keyed_field` splits a line at the first colon and accepts whatever precedes it;
`SUBJECT_KEY_START` then decides subject membership. `atomicity_verdict` tests the value's SHAPE
for clause constructions; `carrier_verdict` runs atomicity first and allowed-state validation
second, on the complete value.

### Live carriers normalized

Four canonical carriers carried commentary inside the value. Each was rewritten atomically with
its assertion unchanged, and the commentary now sits beside it as ordinary prose.

| artifact | was | is |
| --- | --- | --- |
| binding summary register | open state plus an aside naming section 6 | the open state alone |
| binding section-6 status field | open state plus "deliberately not decided" | the open state alone |
| binding section-6 authority field | parenthesised contract reference | the same reference, unbracketed |
| milestone manifest register | open state plus "not decided by AT-M1" | the open state alone |

No decision changed. The two summary lines for AT-D10 and AT-D10.1 in the same register block were
made atomic at the same time, for consistency of the block.

### Adversary matrix

51 probes on a disposable worktree; 50 behaved as specified and none was an accidental-only
rejection. Probe values `ABATED`, `REMITTED` and `VACATED` were grep-proven absent from the
verifier and from the test module before use.

| class | probes | result |
| --- | --- | --- |
| fresh key shapes | bracketed, tilde, at-sign, quoted, lower-case, 220-char, comma, em dash | REJECT, check92j each |
| decoration | list marker, bold, blockquote | REJECT, check92j each |
| same shapes for the second subject | comma, bracketed | REJECT, check92m |
| atomicity A-F | semicolon, dash comment, em dash, en dash, historical aside, comment, sentence break, bad value plus comment | REJECT, check92j |
| atomicity G | one clean compound value | PASS |
| atomicity across forms | section-field, continuation line, two heading markers, manifest, precedence, all six required registers at once | REJECT |
| unknown atomic values | three fresh words | REJECT, check92j / check92m |
| second subject | authorized value on two surfaces | REJECT, check92m |
| conflict | two individually valid carriers disagreeing | REJECT, check92n |
| anti-vacuity | heading form converted, register deleted, section field deleted, discovery disabled | REJECT, check92l |
| prose controls | descriptive, historical, hypothetical, quoted, deontic, criticism, declarative | PASS, truth unchanged |
| structural controls | noncanonical heading, in-section narrative, register syntax inside this record | PASS |

The fifty-first probe removed one of the two redundant status registers in the binding contract.
Required-carrier coverage tolerated it, which is the specified behaviour; the verifier still
rejected, because two older nominated checks pin those particular documentary lines. Removing both
registers makes coverage report the missing category. The anti-vacuity granularity is therefore
intact and the rejection came from a separate, pre-existing requirement.

### Incidental consequence

Scoping section-field discovery to fenced blocks also removes the in-section prose false positive
recorded as ADV-R7-02. That was not the goal; it follows from replacing the label character class
with structural scoping, and is reported rather than claimed as separate work. Every other R7
advisory is untouched and remains deferred.

### Gate G2

| gate | result |
| --- | --- |
| AT-M1 verifier | 234 checks, 0 failures |
| focused tests | 180 passed |
| governance sentinels | four verifiers PASS, 321 tests |
| positive scope | 19 paths, 0 new |
| ruff / black / mypy / diff-check | PASS |
| identifier and credential scan | 0 |

No runtime, API, database, schema, identity, security, dependency, infrastructure, CI or
deployment path was touched. This record states no governance decision; the canonical state lives
in the binding decisions contract.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
