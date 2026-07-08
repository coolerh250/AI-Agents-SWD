# Staging Functional Acceptance — Gap Register (Step 65I)

> **Staging only — non-production only. No production action. No production data.**
> **Documentation only. No secret value appears here.**

Every remaining Step 65 gap, classified for the operator's acceptance decision. Classes:
**ACCEPTED_STAGING_GAP** · **OPERATOR_UX_GAP** · **PRODUCTION_READINESS_GAP** · **DEFERRED_SCOPE** ·
**NON_BLOCKING_TECHNICAL_CHARACTERISTIC**.

Columns: **Blocks staging acceptance?** · **Blocks production readiness?** · **Owner** · **Next
action**.

| # | Gap | Class | Blocks staging | Blocks production | Owner | Next action |
|---|---|---|---|---|---|---|
| 1 | **LLM governance gap** — 2 diagnostic probes bypassed the budget/audit rail before 65F-C; guardrail updated | ACCEPTED_STAGING_GAP | **no** | no | platform / dev | Guardrail already added (65F-C); keep enforcing "all real calls via controlled rail" |
| 2 | **Approval expiry / timeout** — no safe route; DB manipulation forbidden; not executed | ACCEPTED_STAGING_GAP + PRODUCTION_READINESS_GAP | **no** | **yes** | platform / dev | Add a safe approval-TTL/expiry mechanism (+ `expired` status) before production; then validate |
| 3 | **Raw late-stream-event injection** — unsafe injection forbidden; API-level terminal protection validated | ACCEPTED_STAGING_GAP | **no** | no | QA | Optional: a safe test harness to inject terminal-state stream events |
| 4 | **Cancel-during in-flight events** — workflow stays `canceled`, `production_executed=false` | NON_BLOCKING_TECHNICAL_CHARACTERISTIC | **no** | no | platform / dev | Optional: cooperative cancellation for already-dispatched agent events |
| 5 | **Stream-mode intake creates no `workflow_state`** — `/task-graph` empty for stream intakes | NON_BLOCKING_TECHNICAL_CHARACTERISTIC | **no** | no | platform / dev | Optional: register a workflow for real stream-mode intakes so `/task-graph` shows a trace |
| 6 | **No DLQ / Retry Admin Console page** — DLQ evidence backend-API-only (operator-flagged) | OPERATOR_UX_GAP + PRODUCTION_READINESS_GAP (recommended) | **no** | **recommended before prod** | frontend / product | Add a first-class DLQ / Retry Admin Console page (queue depth, per-entry reason, governed manual replay) |
| 7 | **No dedicated `/approvals` Admin Console page** | OPERATOR_UX_GAP | **no** | no | frontend / product | Optional approvals view (nice-to-have) |
| 8 | **comm-gateway `/intake/mock/project-work-item` PyYAML missing** — HTTP 500 in staging | NON_BLOCKING_TECHNICAL_CHARACTERISTIC | **no** | no | platform / dev | Add PyYAML to the communication-gateway image (or lazy import) |
| 9 | **Sandbox rail branch/title naming** differs from the original spec suggestion | NON_BLOCKING_TECHNICAL_CHARACTERISTIC | **no** | no | platform / dev | Accept the validated Step-59 naming, or align naming in a future pass |
| 10 | **Container registry sandbox** not validated | DEFERRED_SCOPE | **no** | out of scope | operator / platform | Validate if/when registry integration is scoped in |
| 11 | **Cloud storage / Google Drive** not validated | DEFERRED_SCOPE | **no** | out of scope | operator / platform | Validate if/when scoped in |

## Blocking summary
- **Gaps blocking staging functional acceptance: NONE.**
- **Gaps to resolve before production (not staging blockers):** #2 (approval expiry mechanism), #6
  (DLQ/Retry operator console, recommended); tracked as PRODUCTION_READINESS_GAP for the operator's
  pre-production planning. Claude Code does not decide production readiness.

## This stage's posture
Documentation only. No new workflow executed; no external action; no production action.
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
