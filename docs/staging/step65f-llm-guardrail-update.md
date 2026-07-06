# Step 65F — LLM Guardrail Update (Step 65F-C)

> **Staging only — non-production only. No production action. No production secret. No production data.**
> **Guardrail / documentation update only — no LLM call, no external write, no workflow execution in this stage.**

Updates the future validation guardrails in response to the Step 65F diagnostic-probe exception
(see [step65f-llm-diagnostic-exception-record.md](step65f-llm-diagnostic-exception-record.md)).
Applies to every subsequent controlled real-integration validation stage (65G onward).

## Updated rules
1. **All real external calls in staging validation must go through the platform-controlled
   budget/audit/evidence rail** for that integration — the GitHub sandbox draft-PR rail for GitHub,
   the discord-gateway controlled-real-send rail for notifications, and the
   `RealLLMPlanOnlyProvider` budget-gated rail for LLM calls. No exceptions for "just a quick
   diagnostic check."
2. **Direct diagnostic external calls are forbidden unless separately authorized.** If a wire-level
   issue (e.g., a stale model name, a malformed endpoint, an auth error) needs to be diagnosed by
   calling the external API directly rather than through the platform rail, **stop and request
   explicit operator authorization first**, naming the diagnostic call, its content, and its
   expected cost, before making it.
3. **"Exactly one call" counts every external network call, not just the official audited one.**
   The per-stage call budget the operator authorizes (e.g., "exactly one controlled call") applies
   to the total number of real network calls made to that provider during the stage — official and
   diagnostic alike — unless the operator has explicitly authorized additional diagnostic calls in
   advance.
4. **Root-cause diagnosis should prefer non-network methods first**: reading source code, checking
   environment variable presence/shape, reviewing provider documentation/changelogs, or a
   read-only guard dry-run (as used in 65D/65E) that is rejected locally without ever reaching the
   external network — before resorting to a live diagnostic call.

## Why this matters
The Step 65F official call was correctly bounded, budget-gated, and fully audited. The two
diagnostic probes that preceded it were safe in content and negligible in cost, but they were
**untracked** — outside the same budget policy, interaction store, and safety-policy evaluation that
make every other real-integration call in this project auditable. A governance model that allows
"safe-looking" unaudited calls as an implicit exception erodes the guarantee that *every* real
external call is accounted for, which is the actual safety property Step 65 is validating.

## Application to Step 65G
See [step65f-to-step65g-precondition-update.md](step65f-to-step65g-precondition-update.md) for how
this guardrail is carried forward as an explicit precondition for Step 65G.

## No new external call in this stage
This is a guardrail/documentation update only. No LLM call, no GitHub write, no notification send,
no workflow execution, no runtime change. `production_executed_true_count=0`.

## Status
Step 65F-C: guardrail update recorded. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
