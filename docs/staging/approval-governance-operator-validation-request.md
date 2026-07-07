# Approval & Governance — Operator Validation Request (Step 65H.2)

> **Staging only — non-production only. No production action. No production data.**
> **Claude Code does not decide staging functional acceptance. This document requests the operator's UI validation.**

Step 65H.2 completed technically; API evidence is captured. The operator must confirm the evidence on
the **formal** Admin Console pages (not `/demo-evidence`).

## Formal-page checklist
| Page | Look for | Expected |
|---|---|---|
| `/task-graph` | WF1 `step65h2-wf1-granted-…` | `approval_status=approved`, stage `completed` |
| `/task-graph` | WF2 `step65h2-wf2-denied-…` | `approval_status=rejected`, stage `rejected` (terminal) |
| `/task-graph` | WF3 `step65h2-wf3-prodblock-…` | `approval_status=pending`, stage `waiting_approval` (blocked) |
| `/agent-executions` | WF1 vs WF3 | WF1 = 5 completed hops; WF3 = 0 (never dispatched) |
| `/audit-evidence` | the three task ids | approval/workflow audit events; WF1 timeline ~23 events; chain intact |
| `/delivery` | (supporting) | no production-effect dispatch |
| `/safety` | production-executed counter | `production_executed_true_count=0`; external integrations disabled; `hard_policy_enforced=true` |
| `/metrics` | (supporting) | metrics reflect the scenarios; no external side effect |

## Required operator response
Record one of:
- **VISIBLE** — the approval-granted / denied / production-block evidence is visible on the formal
  pages.
- **NOT_VISIBLE** — evidence not visible.
- **PARTIAL_WITH_GAPS** — some visible; note which are missing.

## Note on the expired path
The approval **expired / timeout** path was **not** executed (no safe route; recorded as a tracked
gap per your authorization). No operator action is needed for it beyond acknowledging the tracked
gap.

## Rule
Claude Code must not self-accept this validation or decide staging functional acceptance (that is the
Step 65I operator verdict). Until the operator responds, Step 65H.2 remains **PASS_WITH_GAPS** with
operator UI validation pending.

## Status
Step 65H.2: awaiting operator UI validation. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
