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
ActorPrincipal / principal_id      0 occurrences
PlanRevision / plan_revision       0 occurrences
DebugAttempt / debug_attempt       0 occurrences
recipient/addressing fields        0 occurrences
Handoff                            2 occurrences, both legacy delivery `handoff_summaries`
                                   (migration 021) -- an unrelated document concept
TASK_ROLES                         6 roles, all human, unchanged
```

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

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
