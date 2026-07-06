# Step 65F → Step 65G Precondition Update (Step 65F-C)

> **Staging only — non-production only. No production action. No production secret.**
> **Documentation only — no LLM call, no external write, no workflow execution in this stage.**

Carries the Step 65F guardrail update (see
[step65f-llm-guardrail-update.md](step65f-llm-guardrail-update.md)) forward as an explicit
precondition set for Step 65G (End-to-End Staging Workflow Validation).

## Step 65G preconditions (added by this stage)
Before Step 65G's end-to-end workflow run is authorized and executed, the following must hold:
- **All GitHub writes** exercised during the E2E run go through the controlled GitHub sandbox
  draft-PR rail (allowlist + live gate + audit trail) — no direct GitHub API calls outside that
  rail.
- **All notifications** exercised during the E2E run go through the controlled discord-gateway
  real-send rail (guard + audit trail) — no direct Discord API calls outside that rail.
- **All LLM calls** exercised during the E2E run go through the platform's budget/audit rail
  (`RealLLMPlanOnlyProvider` + `BudgetPolicyEvaluator` + interaction/proposal/usage stores) — no
  direct provider API calls outside that rail.
- **No direct diagnostic external calls** of any kind (GitHub, Discord, or LLM) without separate,
  explicit, prior operator authorization naming the call, its content, and its expected cost.
- **No extra probes** beyond what the operator has explicitly authorized for the run.
- **No untracked external calls** — every real network call made during 65G must be visible in the
  relevant platform audit/evidence surface (sandbox draft-PR safety record, notification delivery
  record, or LLM interaction/usage store).
- **No production action** — unchanged from every prior Step 65 stage.

## Status
- Step 65G status: **READY_AFTER_GUARDRAIL_CONSOLIDATION.** The above preconditions apply to the
  65G run once the operator authorizes it; Claude Code does not decide staging functional
  acceptance.

## No new external call in this stage
This is a documentation update only. No LLM call, no GitHub write, no notification send, no
workflow execution, no runtime change. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
