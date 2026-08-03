# Step 66SYNC.1-A — POC Backend Technical Readiness Matrix

> **Read-only assessment. No gap below was modified, fixed, or worked around — this stage
> inventories only. No implementation, no runtime action, no deployment.**

```text
CONTEXT_ID:  AIAT-SYNC-20260803-01
Baseline:    canonical main c1db4cc
Objective:   ISOLATED FUNCTIONAL AI AGENT TEAM DELIVERY POC
```

Classification vocabulary (as required by §7):

```text
READY                   exists in production code, exercised, usable for the POC as-is
READY_WITH_CONSTRAINTS  exists and is usable, but with a material limitation the POC must accept
GAP_REQUIRING_POC0      does not exist or is not connected; POC.0 build work required
BLOCKED                 cannot proceed until a Product Owner decision or an upstream gap is resolved
```

## Matrix

| # | Capability | Classification | Evidence / constraint |
|---|---|---|---|
| 1 | goal intake | `READY_WITH_CONSTRAINTS` | Two entry points exist. `apps/communication-gateway` can hand a task to `stream.tasks` (feeds the agent pipeline). The operator-facing `POST /tasks` (Step 66B.1) accepts a goal but does **not** dispatch. Which one is "the" POC entry point is discrepancy **D-1**. |
| 2 | requirements | `READY` | `agents/requirement-agent/src/agent.py` (369 lines) consumes `stream.requirements`, produces structured requirements, records agent-execution + discussion rows. |
| 3 | work-item creation | `READY` | `shared/sdk/work_items/`, `shared/sdk/workspace_operator/work_item_mapper.py`. |
| 4 | task graph | `READY` | `shared/sdk/project_planning/task_graph.py`; rendered by the `TaskGraph` console page. Constraint: the console page renders the Path A task model (see D-1). |
| 5 | agent dispatch | `READY_WITH_CONSTRAINTS` | `apps/orchestrator/src/workflow.py::dispatch_node` -> `dispatch.py` -> `stream.tasks` works. Constraint: reachable only from Path B, not from the operator task API. |
| 6 | agent execution evidence | `READY` | Every agent writes an agent-execution row, an audit event, a notification, and an `agent_discussions` entry per message (`TaskExecutionStore`, `AGENT_DISCUSSIONS_TOTAL`). Surfaced by the `AgentExecutions` console page. |
| 7 | design artifact handoff | `READY_WITH_CONSTRAINTS` | `agents/design-review-agent/` + `shared/sdk/design_review/`; `DesignReview` console page. Constraint: review/evaluation of a design artifact, not generation of one. |
| 8 | backend artifact handoff | `GAP_REQUIRING_POC0` | `agents/backend-agent/` contains **.gitkeep only, 0 .py files**, and has no compose service. The development-agent produces code only from three deterministic templates. Discrepancy **D-2**. |
| 9 | frontend artifact handoff | `GAP_REQUIRING_POC0` | `agents/frontend-agent/` contains **.gitkeep only, 0 .py files**, and has no compose service. No frontend generation capability exists anywhere. Discrepancy **D-2**. |
| 10 | QA evidence | `READY` | `agents/qa-agent/src/agent.py` (745 lines); `QaCode` console page; QA evidence rows persisted. |
| 11 | approval checkpoints | `READY` | `apps/approval-engine/`, `shared/sdk/approval_policy/`, `apps/orchestrator/src/approval_policy_api.py`; workflow `dispatch_node` holds at `waiting_approval` when approval is required and not granted. |
| 12 | GitHub draft PR | `READY_WITH_CONSTRAINTS` | `apps/github-automation/` — **dry-run by default** (`GITHUB_DRY_RUN` defaults `"true"`); a real sandbox PR path exists behind `evaluate_real_github_sandbox_request` and was exercised in a controlled sandbox scope. POC must decide dry-run vs sandbox-real. |
| 13 | delivery package | `READY` | `shared/sdk/delivery_package/`, `agents/delivery-package-agent/` (218 lines), `DeliveryPackage` console page. |
| 14 | cost evidence | `READY_WITH_CONSTRAINTS` | `shared/sdk/llm_budget/` + `llm_usage_records`; `CostLlmGovernance` console page. Constraint: with the default mock provider, recorded cost is **zero**, so cost evidence is structurally present but numerically trivial until a real provider is used. |
| 15 | external operation evidence | `READY` | `/operations/real-integrations` and `/operations/safety` surfaces; `REAL_GITHUB_SANDBOX_PRS_TOTAL`; `shared/sdk/real_integration`; `shared/sdk/notifications/real_delivery_policy.py` classification recorded per event. |
| 16 | failure / retry / DLQ evidence | `READY_WITH_CONSTRAINTS` | `apps/retry-scheduler/` with bounded retry, backoff, and a terminal dead state, proven for the AUDIT destination. Constraint: **never exercised for the ORCHESTRATOR_COMMAND destination**, which has no consumer at all (G-4); and there is no operator-visible DLQ surface (G-11). |
| 17 | PO acceptance status | `READY_WITH_CONSTRAINTS` | Operator action/review machinery exists (`OperatorReviewPanel`, `OperatorActionHistory`, acceptance recorded as human review only, `production_executed` never set). Constraint: acceptance is bound to the fixed pseudo-identity `operator-test`, so it cannot distinguish two real humans (identity gap G-12). |
| 18 | reset / teardown | `READY` | `scripts/verify_environment_reset_test_handoff.py`, `verify_session_cleanup.py`, `verify_controlled_cleanup_review.py`; Compose stack is disposable and currently fully down. |

## Roll-up

```text
READY:                   9   (items 2, 3, 4, 6, 10, 11, 13, 15, 18)
READY_WITH_CONSTRAINTS:  7   (items 1, 5, 7, 12, 14, 16, 17)
GAP_REQUIRING_POC0:      2   (items 8, 9)
BLOCKED:                 0
                        ---
Total                   18
```

## Interpretation

```text
Nothing is classified BLOCKED. That is deliberate and accurate: no capability in this matrix is
prevented from proceeding by an unresolved upstream technical dependency. The two GAP items are
straightforward build work, not blocked work.

However, the POC's SHAPE is gated by three Product Owner decisions (D-1, D-2, D-3 in the
discrepancy register), not by technical blockers:

  D-1 decides what the operator entry point is -- and therefore whether item 1 and item 5 stay
      READY_WITH_CONSTRAINTS or require a connecting build.
  D-2 decides whether items 8 and 9 are in POC scope at all.
  D-3 decides whether "delivery" means template-driven demonstration output (achievable today) or
      LLM-generated software (requires deliberately relaxing an intentional safety control, with
      security review).

Until those three are answered, POC.0 scope cannot be fixed. This matrix does not answer them and
Claude Code has not assumed an answer to any of them.
```

## Honest summary of what a POC could demonstrate today

```text
Achievable with existing code, no new build:
  a goal entering via the workflow/communication-gateway path, flowing through
  intake -> requirements -> development (template output) -> qa -> devops, with per-hop agent
  execution rows, inter-agent discussion, audit evidence, approval checkpoints, retry/DLQ, a
  delivery package, a dry-run GitHub PR, cost records, and operator review -- all observable in
  the Admin Console.

NOT achievable without new build:
  driving that same flow from the operator-facing task surface an operator would naturally use;
  producing genuine backend or frontend software for an arbitrary goal; LLM-generated code or
  tests; observing BE3 resume/replay/production-approval from the console.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
