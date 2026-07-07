# Failure / Governance Execution Split (Step 65H.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — 65H.2–65H.5 are not executed in this stage.**

Step 65H is split into controlled sub-stages, each under its own explicit operator authorization.

## Sub-stages
| Sub-stage | Title | Scenarios | Output |
|---|---|---|---|
| **65H.1** | Failure / Recovery / Governance Validation Plan (this stage) | — (planning) | plan + matrix + templates |
| **65H.2** | Approval & Governance Path Validation | A1–A6, D1–D2, D4 | approval required/granted/denied/expired + production-block evidence |
| **65H.3** | Cancel / Abort / Ignore-after-abort Validation | B1–B6 | cancel/abort/ignore-after-abort evidence |
| **65H.4** | Retry / DLQ / Manual Replay Validation | C1–C7, D3–D5 | retry/DLQ/terminal + kill-switch evidence |
| **65H.5** | Failure & Governance Operator Evidence Review | (review) | operator evidence review + verdict input |

## Ordering & gating
- 65H.2 → 65H.3 → 65H.4 → 65H.5, each gated on the operator returning that sub-stage's authorization
  template (see
  [failure-governance-operator-authorization-templates.md](failure-governance-operator-authorization-templates.md)).
- Each execution sub-stage: read-only pre-checks → authorized scenarios (controlled, non-external by
  default) → capture formal-page evidence → reset to safe → operator UI validation.
- **65H.1 executes none of them** — it only produces the plan.

## Default posture per sub-stage
- External integrations **off** by default (GitHub/Discord/LLM = NO). `production_executed_true_count`
  stays 0. HIGH-risk scenarios require explicit authorization. Reset to safe after each sub-stage.

## Acceptance
- Staging functional acceptance is **not** decided by Claude Code. After 65H.5, the operator gives
  the Step 65I acceptance verdict for the whole Step 65 track.

## This stage's posture
Planning only. No scenario executed; no external write; no LLM call; no Discord send; no production
action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
