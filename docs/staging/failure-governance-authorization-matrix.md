# Failure / Governance Authorization Matrix (Step 65H.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only. Each execution sub-stage runs only under its named operator authorization.**

Maps each scenario group to the authorization required before execution. All **HIGH**-risk scenarios
require explicit per-sub-stage operator authorization.

## Authorization by sub-stage
| Sub-stage | Scenarios | Authorization required | Default external actions |
|---|---|---|---|
| 65H.2 — Approval & Governance | A1–A6, D1–D2, D4 | operator names which approval paths (required/granted/denied/expired/production-block) + external yes/no + max workflow count + UI validation | GitHub NO · Discord NO · LLM NO |
| 65H.3 — Cancel / Abort / Ignore-after-abort | B1–B6 | operator names which of cancel-before / cancel-during / abort-during / ignore-after-abort + external yes/no + max workflow count + UI validation | GitHub NO · Discord NO · LLM NO |
| 65H.4 — Retry / DLQ / Manual Replay | C1–C7, D3–D5 | operator names controlled-failure / retry / DLQ-creation / manual-replay / terminal-failure + max retry count + max replay count + external yes/no + UI validation | GitHub NO · Discord NO · LLM NO |
| 65H.5 — Operator Evidence Review | (review only) | operator gives the review/verdict | none |

## Default external-integration rule (Step 65H)
- **GitHub write: NO. Discord send: NO. LLM call: NO** — by default across all of 65H.
- If a specific scenario genuinely needs an external rail, the plan must document: **why** it is
  needed, **max count**, **target rail** (65D/65E/65F), **guardrail**, **reset requirement**, and it
  requires **separate authorization** naming that external action. Absent that, no external rail is
  used — 65H governance scenarios are exercised on controlled, non-external `workflow_state` objects
  and the audit/DLQ surfaces.

## Standing constraints (not overridable by any template)
- No production action / deploy / sync / secret. No production-effect dispatch. No merge/release/tag.
  No image push. No public exposure. No volume deletion. No full-stack restart. No auto-retry storm.
  No DLQ replay beyond the authorized count. No approval-state change outside the authorized test
  case. `production_executed_true_count` must remain 0.

## Rule
Claude Code does not self-authorize any HIGH-risk scenario and does not decide staging functional
acceptance. See [failure-governance-operator-authorization-templates.md](failure-governance-operator-authorization-templates.md).

## This stage's posture
Planning only. No scenario executed; no external write; no LLM call; no Discord send; no production
action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
