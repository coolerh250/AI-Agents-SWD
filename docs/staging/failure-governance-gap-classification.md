# Failure & Governance — Gap Classification (Step 65H.5)

> **Staging only — non-production only. No production action. No production data.**
> **Documentation only. No secret value appears here.**

Classifies every remaining Step 65H gap for the Step 65I acceptance decision. Classes:
**BLOCKING** · **ACCEPTABLE_FOR_STAGING** · **OPERATOR_UX_GAP** · **POST-STAGING_BACKLOG** ·
**REQUIRES_PRODUCT_FIX_BEFORE_PRODUCTION**.

## Classification
| Gap | Source | Class | Rationale / recommendation |
|---|---|---|---|
| Approval **expiry / timeout** path not executed | 65H.2 | **ACCEPTABLE_FOR_STAGING** + **REQUIRES_PRODUCT_FIX_BEFORE_PRODUCTION** | No safe expiry route; DB manipulation forbidden. Acceptable for staging (the required/granted/denied paths are validated). Before production, add a safe approval-TTL / expiry mechanism (+ `expired` status) so the timeout path can be validated non-destructively. |
| Raw late-**stream**-event injection not executed | 65H.3 | **ACCEPTABLE_FOR_STAGING** | The late-event-ignored behavior is validated at the API level (HTTP 409 terminal-state protection). The raw-stream variant needs unsafe injection (forbidden). Low residual risk; the terminal-state guard is proven. |
| Cancel-during does not un-dispatch in-flight agent events | 65H.3 | **ACCEPTABLE_FOR_STAGING** (async characteristic) | Documented behavior of the async pipeline; the workflow still terminates to `canceled` with `production_executed=false`. Not a safety issue. Optional future enhancement: cooperative cancellation for in-flight events. |
| **No DLQ / Retry Admin Console page** | 65H.4 (operator-flagged) | **OPERATOR_UX_GAP** + **POST-STAGING_BACKLOG** (recommend before production) | DLQ is an operator-facing failure indicator but is backend-API-only. Terminal failures surface indirectly (Incidents / Task Graph `failed` / Audit-Evidence). **Recommendation:** add a first-class DLQ / Retry Admin Console page (queue depth, per-entry reason, controlled manual replay) before production operations. |
| No dedicated **`/approvals`** Admin Console page | 65H.1/65H.2 | **OPERATOR_UX_GAP** | Approval state is validated on `/task-graph` (`approval_status`) + `/audit-evidence` (+ approval-decisions API). A dedicated approvals view is a UX nicety, not blocking. |
| Stream-mode intake creates no `workflow_state` on `/task-graph` | 65G.2 (context) | **ACCEPTABLE_FOR_STAGING** | Documented; agent-executions carry the pipeline evidence. Optional future enhancement. |

## Blocking summary
- **BLOCKING gaps for staging functional acceptance: NONE.** All Step 65H gaps are either
  acceptable-for-staging tracked gaps or operator-UX / product-backlog items to carry into the Step
  65I acceptance decision and pre-production planning.

## Production-readiness note
- **REQUIRES_PRODUCT_FIX_BEFORE_PRODUCTION:** approval expiry/timeout mechanism; DLQ/Retry operator
  console (strongly recommended). These are **not** in scope for the Step 65 staging validation and
  are **not** decided by Claude Code — they are flagged for the operator's pre-production planning.

## This stage's posture
Documentation only. No new scenario executed; no external action; no production action.
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
