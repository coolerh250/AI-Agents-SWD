# Controlled LLM Validation Report (Step 65F)

> **Staging only — non-production only. No production action. No production secret. No production data.**
> **Only one controlled staging LLM call was made (via the platform's audited plan-only path). No production data was used.**

Records the **real** (not mock) controlled LLM validation on staging `10.0.1.32`, under operator
authorization: one bounded Anthropic call was made through the platform's existing Stage-35
plan-only real-LLM rail (`shared/sdk/llm/plan_only_provider.py::RealLLMPlanOnlyProvider`), gated by
a budget policy capped at $1, with a safe, non-production, staging-connectivity-only prompt.

## Overall result
- Overall result: **PASS_WITH_GAPS** (corrected in Step 65F-C — see
  [step65f-llm-validation-final-status.md](step65f-llm-validation-final-status.md)). The **official
  audited call** succeeded (`preflight allowed`, `safety_allowed=true`, 0 violations),
  `plan_only=true`, `requires_human_review=true`, `production_executed=false`; no workspace or
  code-change artifact was created; the LLM real-call flags were never made persistent (see §Runtime
  scope) so there was nothing to leave enabled. The **governance** result is PASS_WITH_GAPS because
  two diagnostic probes (disclosed below) bypassed the platform's budget/audit rail before the
  official call — see
  [step65f-llm-diagnostic-exception-record.md](step65f-llm-diagnostic-exception-record.md).
- `production_executed_true_count=0` throughout.

## What was validated (real)
- **Control path:** the existing Stage-35 controlled-real-LLM guard
  (`real_llm_plan_only_guard`) — `RUN_REAL_LLM_TEST=true`, `ENABLE_REAL_LLM_NETWORK_CALL=true`,
  provider `external_anthropic`, matching API key present, `interaction_type=development_plan`,
  explicit `allow_real=True` opt-in — all required simultaneously.
- **Budget gate:** a bounded budget policy (`max_cost_per_task_usd=1.00`,
  `max_cost_per_day_usd=1.00`, `max_cost_per_month_usd=1.00`, `enforcement_mode=block`) was created
  before the call and the preflight check returned `allowed`.
- **Real call:** exactly **one** audited Anthropic Messages API call, provider `external_anthropic`,
  model `claude-haiku-4-5-20251001`, `max_tokens=1024`, prompt confirming a staging connectivity
  test only (see [-evidence.md](controlled-llm-validation-evidence.md) for the exact text — it
  contains no secrets, production data, or personal data).
- **Result:** `interaction_id`, `proposal_id`, `usage_id` recorded; tokens `369` prompt + `339`
  completion = `708` total; **actual cost `$0.03096`** — well within the $1 cap.

## Changes required to make it work (no code change — env-only)
1. **Stale default model name.** The provider's hardcoded default model (`claude-3-5-haiku`) is no
   longer a valid Anthropic model id — the first probe returned `HTTP 404 not_found_error: model:
   claude-3-5-haiku`. **Fix:** the provider already supports an `ANTHROPIC_MODEL` env override; it
   was set (ephemerally, for this call only) to `claude-haiku-4-5-20251001`, a current model. No
   source change was required or made.
2. **No persistent env change needed.** Rather than editing `docker-compose.staging.yml` or the host
   env file (as 65D/65E required), the real-call flags (`RUN_REAL_LLM_TEST`,
   `ENABLE_REAL_LLM_NETWORK_CALL`, `LLM_PROVIDER=external_anthropic`, `ANTHROPIC_MODEL`,
   `ANTHROPIC_API_KEY`) were injected **only into the one-off `docker compose exec`
   process** via `-e` flags, scoped to the single Python invocation. The long-running orchestrator
   process's own environment was never touched, so `/operations/safety`'s `llm_provider`/
   `llm_real_enabled` fields read `mock`/`false` before, during, and after — there is nothing to
   "reset" at the container-env layer.

## Findings resolved during validation (disclosed transparently)
- **Two small diagnostic probes preceded the one official call**, made directly via `httpx` (outside
  the audited SDK path, no budget policy attached) to identify the stale-model-name root cause: one
  `404` probe (no tokens billed — Anthropic rejects before generation) and one 17-token
  confirmation probe (`"Reply with the word OK"` → `"OK"`, cost effectively sub-cent). This is a
  disclosed deviation from a strict single-call count — total additional spend was negligible
  (well under $0.01) and no production/sensitive content was involved. Only **one** call went
  through the platform's official audited plan-only path with budget-policy gating, interaction/
  proposal/usage recording, and safety-policy evaluation — that is the call this report treats as
  "the Step 65F controlled LLM call."
- **Preflight cost estimator used a fallback pricing model** (`claude-3-opus`) because
  `claude-haiku-4-5-20251001` was not in the estimator's pricing table, so the preflight estimate
  (`$0.00318`) undershot the actual recorded cost (`$0.03096`). The **actual** cost was still
  correctly recorded and the budget-enforcement check (`record_usage`) reported `exceeded=false` —
  the $1 cap was never at risk. Tracked as a non-blocking known gap.

## Safety
- `production_executed_true_count=0` before, during, and after.
- No GitHub write, no notification send, no workflow execution, no production action.
- `plan_only=true`, `requires_human_review=true`, `production_executed=false` (from
  `/operations/llm/plan-only/{task_id}`); 0 rows in `code_workspaces` / `code_change_artifacts` for
  the task id — the call never produced a patch or touched a workspace.
- The budget policy created for this validation was deactivated (`status=inactive`) after the call.

## Status
- Step 65F: **PASS_WITH_GAPS** (final, per Step 65F-C) — the official audited LLM call is
  technically **PASS**; the disclosed diagnostic-probe deviation makes the overall governance
  result PASS_WITH_GAPS, not a clean PASS. Reset posture confirmed. This is not production
  readiness.

---
_Staging only — non-production only. No production action. No production secret. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=llm-controlled github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
