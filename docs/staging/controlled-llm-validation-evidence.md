# Controlled LLM Validation — Evidence (Step 65F)

> **Staging only — non-production only. No production action. No production data.**
> **Read-only evidence (metadata-only). No secret value printed. No raw sensitive content.**

Evidence captured around the real, bounded Anthropic controlled call on `10.0.1.32`.

## Prompt (safe to record — no sensitive content)
```
You are validating a staging AI Agents platform integration. Reply with exactly one sentence
confirming this is a staging LLM connectivity test. Do not include secrets, credentials, code, or
external actions.
```
This was passed as the plan-only contract's `task_summary` / `TASK_SUMMARY` free-text appendix. The
provider's fixed system prompt (unchanged, pre-existing) additionally instructs the model to return
JSON (`summary`, `proposed_steps`, `assumptions`, …) and to never produce code or patches.

## Call metadata
| Field | Value |
|---|---|
| test id / correlation id | `step65f-llm-validation-1783315465` |
| provider | `external_anthropic` |
| model | `claude-haiku-4-5-20251001` |
| status | `ok` |
| prompt tokens | 369 |
| completion tokens | 339 |
| total tokens | 708 |
| actual cost (USD) | `0.03096` |
| interaction_id | `d56cc96d-8ba4-491a-a31c-98c4ce59b3c6` |
| proposal_id | `659b09c8-9c5e-4f57-a32e-070dc7f05973` |
| usage_id | `b4bf19c5-feae-4cd2-babe-b87b248999e4` |
| budget policy_id (created, then deactivated) | `08684db6-e109-4714-b583-96e985bcd207` |

## Redacted response summary
> "Planning validation of staging AI Agents platform integration connectivity test."

`confidence=0.85`; `requires_human_review=true` (always forced by the provider); `safety_allowed=true`
with 0 violations. The model's `assumptions` field explicitly recorded: "Staging environment is
isolated from production", "This is a connectivity validation task only", "No actual deployments or
credentials are involved" — confirming the model correctly understood the staging-only, no-action
scope of the prompt.

## Plan-only invariants (`GET /operations/llm/plan-only/{task_id}`)
- `real_llm_used: true`
- `plan_only: true`
- `requires_human_review: true`
- `production_executed: false`
- One `interactions` row, one `plan_only_proposals` row, one `usage_records` row, budget events
  recorded against the policy above.

## No side effects
- `code_workspaces` rows for this task_id: **0**.
- `code_change_artifacts` rows for this task_id: **0**.
- No GitHub write, no notification send, no workflow execution occurred as part of this call.

## Deviation disclosed (see report for full context)
- Two small diagnostic probes (outside the audited path, no budget policy attached) were made first
  to locate a stale hardcoded default model name (`claude-3-5-haiku` → `404 not_found_error`): one
  0-token failed probe, one ~17-token `"Reply with the word OK"` confirmation probe. Combined
  additional cost: negligible (well under $0.01). Only the one official, audited, budget-gated call
  documented above is treated as "the Step 65F controlled LLM call."

## Credential handling
- `ANTHROPIC_API_KEY` was read from the gitignored, chmod-600 staging env file into a shell
  variable on the host and passed only as an ephemeral `docker compose exec -e` value to the
  one-off Python process; it was used only in the Anthropic `x-api-key` header and was **never
  printed, logged, or committed**.

## Status
Step 65F: **PASS**. `production_executed_true_count=0`. Not production readiness.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=llm-controlled github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
