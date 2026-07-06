# Controlled LLM Validation — Known Gaps (Step 65F)

> **Staging only — non-production only. No production action. No production data.**
> **Documentation only. No secret value appears here.**

## Gaps
1. **Stale hardcoded default model name.** `shared/sdk/llm/plan_only_provider.py`'s default Anthropic
   model (`claude-3-5-haiku`) is no longer a valid model id (`404 not_found_error` from the live
   API). Worked around this stage via the existing `ANTHROPIC_MODEL` env override (no source
   change); the hardcoded default itself was left unchanged (out of scope for a validation-only
   stage) and should be refreshed in a future maintenance pass.
2. **Preflight cost-estimator pricing gap.** The budget evaluator's preflight step fell back to a
   different model's pricing table (`claude-3-opus`) because the actual model used
   (`claude-haiku-4-5-20251001`) is not in its pricing table, so the preflight cost estimate
   ($0.00318) undershot the actual recorded cost ($0.03096). The **actual** cost was still
   correctly recorded post-call and the $1 cap was never at risk (`exceeded=false`), but the
   estimator's pricing table should be extended with current model names in a future stage.
3. **Two small diagnostic probes outside the audited path.** Disclosed in the validation report —
   made to identify the stale-model-name root cause before the one official call. Negligible cost
   (well under $0.01 combined), no sensitive content, no budget-policy/audit-trail involvement for
   those two probes specifically.
4. **No Admin Console surface exercised.** This call was invoked via the SDK inside the orchestrator
   container (matching the pre-existing Stage 35 pilot pattern, which itself notes "no orchestrator
   HTTP endpoint yet"), not through an Admin Console UI action. `/operations/llm/plan-only/{task_id}`
   was checked directly. Full Admin Console visibility of a live LLM interaction is in scope for
   65G (end-to-end workflow validation), not 65F.

## Governance consolidation (Step 65F-C)
Gap #3 above (diagnostic probes) has been formally consolidated: see
[step65f-llm-diagnostic-exception-record.md](step65f-llm-diagnostic-exception-record.md) and
[step65f-llm-guardrail-update.md](step65f-llm-guardrail-update.md). **Step 65F final status is
PASS_WITH_GAPS** (not a clean PASS) precisely because of this gap; future direct diagnostic
external calls are forbidden unless separately authorized.

## Non-gaps (done)
- Exactly one official, audited controlled LLM call; bounded by a $1-capped budget policy; no
  production data/secrets/personal data in the prompt; no GitHub write; no notification send; no
  workflow execution; `production_executed_true_count=0`; nothing left persistently enabled.

## Posture
Real (not mock) controlled LLM validation, with the above gaps tracked as non-blocking. No
production action; no external write beyond the one approved, bounded LLM API call.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=llm-controlled github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
