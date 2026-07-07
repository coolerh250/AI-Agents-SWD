# Approval & Governance Path Validation Report (Step 65H.2)

> **Staging only — non-production only. No production action. No production secret. No production data.**
> **Controlled governance test on `workflow_state` objects only. No external GitHub / Discord / LLM action. No production action.**

Records the **real** controlled approval & governance path validation on staging `10.0.1.32`, under
operator authorization: three controlled workflows exercised the approval-required, approval-granted,
approval-denied, and production-block paths. No external integration was used.

## Overall result
- Overall result: **PASS_WITH_GAPS** — the four executable paths (required / granted / denied /
  production-block) all passed; the **approval expired / timeout** path is a tracked gap (no safe
  route — read-only confirmed, not executed). Operator UI validation pending.
- `production_executed_true_count=0` before, during, and after. **Claude Code does not decide staging
  functional acceptance.**

## Authorization compliance
| Item | Authorized | Actual |
|---|---|---|
| Controlled workflows | ≤ 3 | **3** |
| External actions (GitHub/Discord/LLM) | NO | **none** |
| Production action | forbidden | **none** |
| DB manipulation to fake expiry | forbidden | **none** |
| production_executed_true_count | 0 | **0** |

## Scenarios & results
### Workflow 1 — approval **required → granted → resume** (PASS)
- Task: `step65h2-wf1-granted-20260707015334`, `type=contract.action` (restricted, **non**-production).
- Required: policy-engine → `approval_required=true`, `risk_level=high` → `stage=waiting_approval`,
  `approval_status=pending`, `production_executed=false`, `dispatched=false`.
- Granted: `POST /approval/approve {request_id, decided_by=operator}` → approval-engine request
  `approved` → orchestrator `stream.approvals` listener auto-resumed the workflow.
- Result: `stage=completed`, `approval_status=approved`, `dispatched=true`,
  `production_executed=false`; the resumed workflow ran the mock 5-agent pipeline (intake →
  requirement → development → qa → devops); 23 audit events on the workflow timeline.

### Workflow 2 — approval **required → denied → terminal / not resumed** (PASS)
- Task: `step65h2-wf2-denied-20260707015430`, `type=contract.action`.
- Required → `waiting_approval` / `pending`.
- Denied: `POST /approval/reject` → approval-engine request `rejected` → workflow moved to
  `stage=rejected`, `approval_status=rejected` (terminal), **not resumed** (`dispatched=None`),
  `production_executed=false`. Stable across polls.

### Workflow 3 — **production block** (PASS)
- Task: `step65h2-wf3-prodblock-20260707015822`, `type=production.deploy` (a restricted **production**
  action).
- Result: `approval_required=true`, `risk_level=high` → `stage=waiting_approval`,
  `blocked_pending_approval`, `dispatched=false`, `production_executed=false`; **0** agent executions
  (never dispatched). It was **left unapproved** — approving + dispatching a production action is
  forbidden. `production_executed_true_count=0`.

### Approval **expired / timeout** (TRACKED GAP — not executed)
- Read-only inspection found **no safe expiry/timeout route** in the approval-engine or the resume
  engine (no expire endpoint, no timeout job). Per the operator's authorization, simulating expiry
  would require DB time manipulation / faking expiry, which is **forbidden** — so this path was
  **not executed** and is recorded as a **tracked gap**, not a failure. See
  [approval-governance-known-gaps.md](approval-governance-known-gaps.md).

## Mechanisms exercised (real)
- **policy-engine** `/policy/evaluate`: `action ∈ RESTRICTED_ACTIONS` → `approval_required=true`,
  `risk_level=high`.
- **approval-engine** `/approval/request` (pending) · `/approval/approve` · `/approval/reject`.
- **orchestrator** `_approval_listener` on `stream.approvals` → `ResumeEngine.on_approval_event` →
  resume-and-dispatch (approved) / terminal (rejected).
- **workflow graph** intake→requirement→policy→approval→audit→dispatch; a restricted, unapproved
  action stays at `waiting_approval` and is never dispatched (`production_executed=false` always).

## Safety
- `production_executed_true_count=0` throughout. No external write (all external flags stayed
  disabled — none were ever enabled). No runtime config change, no service recreate, no full-stack
  restart, no DB reset, no DB manipulation. Only 3 controlled workflows were created (≤3 authorized).

## Status
- Step 65H.2: **PASS_WITH_GAPS** (4 paths validated; expiry = tracked gap). Awaiting operator UI
  validation (see
  [approval-governance-operator-validation-request.md](approval-governance-operator-validation-request.md)).
  Not production readiness.

---
_Staging only — non-production only. No production action. No production secret. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
