# Step 65F — LLM Diagnostic Exception Record (Step 65F-C)

> **Staging only — non-production only. No production action. No production secret. No production data.**
> **Documentation / reconciliation / guardrail update only — no LLM call, no GitHub write, no notification send, no workflow execution, no runtime change in this stage.**

Formal exception record for the two diagnostic Anthropic probes disclosed in the Step 65F
completion report. This stage performs no new external call of any kind.

## Official audited call (unaffected — see also
[step65f-llm-validation-final-status.md](step65f-llm-validation-final-status.md))
The Step 65F **official audited LLM validation succeeded** through the platform's controlled
budget/audit rail. This exception record does not change that result — it formalizes the
governance treatment of the two diagnostic probes that preceded it.

## Diagnostic exception
- **Diagnostic probe count:** 2.
- **Purpose:** to diagnose an outdated/stale hardcoded default Anthropic model name
  (`claude-3-5-haiku`, which Anthropic rejected with `404 not_found_error`) before running the one
  official, audited call.
- **Path used:** both probes were made via a direct `httpx` call to the Anthropic Messages API,
  **bypassing** the platform's budget policy, interaction/proposal/usage store, and safety-policy
  evaluation (i.e., outside the `RealLLMPlanOnlyProvider` / budget-audit rail used for the official
  call).
- **Content:** probe 1 — a copy of the plan-only request body with the stale model name (rejected
  by Anthropic before generation, 0 tokens billed). Probe 2 — a minimal literal prompt, `"Reply
  with the word OK."` (13 input tokens, 4 output tokens), used only to confirm the corrected model
  id (`claude-haiku-4-5-20251001`) was valid.
- **Sensitive content:** **none.** No secrets, no production data, no customer data, no personal
  data were included in either probe.
- **Cost:** negligible — probe 1 was rejected before generation (no cost); probe 2 was a 17-token
  round trip (well under $0.01). Both were within the same $1 per-run cap the operator authorized
  for this stage, but neither was recorded against the formal budget policy or the interaction/
  usage audit trail, because they did not go through the controlled rail.
- **Acceptability:** **not acceptable as standard practice.** Direct diagnostic external calls that
  bypass the platform's controlled rail are a governance gap, even when content is safe and cost is
  negligible — they are untracked, unaudited, and not subject to the budget-policy enforcement that
  governs every other real-integration call in this project (GitHub sandbox writes, Discord sends,
  and the official LLM call all go through their platform-controlled rails).

## Governance disposition
- The probes are **disclosed exceptions**, not concealed activity — they were reported in full in
  the original Step 65F completion report and are formalized here.
- They **do not** invalidate the official audited call's technical success.
- They **do** mean Step 65F cannot be marked a clean **PASS** — it is corrected to
  **PASS_WITH_GAPS** (governance gap), while the official call's technical result remains **PASS**.
  See [step65f-llm-validation-final-status.md](step65f-llm-validation-final-status.md).
- Future direct diagnostic external calls of this kind are **forbidden unless separately
  authorized** by the operator before the call is made — see
  [step65f-llm-guardrail-update.md](step65f-llm-guardrail-update.md).

## No new external call in this stage
This consolidation stage is documentation-only: no LLM call, no Anthropic API call, no GitHub
write, no notification send, no workflow execution, and no runtime/config change were performed
while producing this record. `production_executed_true_count=0`.

## Status
Step 65F-C: diagnostic exception formally recorded. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
