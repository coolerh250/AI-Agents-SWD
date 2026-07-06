# E2E Staging Integration Guardrails (Step 65G.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only. Carries forward the Step 65F-C guardrail.**

Integration guardrails for Step 65G.2. Every real external call must go through its
platform-controlled rail; the pipeline's native mock/dry-run integration points must **not** be used
for real external artifacts (see
[e2e-staging-workflow-readiness-report.md](e2e-staging-workflow-readiness-report.md)).

## GitHub — controlled sandbox draft-PR rail only (65D)
- **Allowed (if separately authorized in 65G.2):** sandbox repo `coolerh250/AI-Agents-SWD-sandbox`
  only; staging branch only; **draft PR** only; evidence file only; audit/evidence record.
- **Forbidden:** main-repo write; production/customer-repo write; protected-branch direct push;
  merge; release; tag; deploy.
- **Rail:** `POST /operations/github/sandbox-draft-pr` (allowlist + live gate + audit). The
  devops-agent's native dry-run `/demo-pr` path must **not** be switched to a real write.

## Discord — controlled discord-gateway rail only (65E)
- **Allowed (if separately authorized in 65G.2):** exactly **one** staging workflow notification;
  target `MySanbox / #general` only; `[STAGING]` prefix; audit/evidence record.
- **Forbidden:** production channel; DM; spam / repeated sends; secret or sensitive-log content in
  the message.
- **Rail:** `POST /discord/real/test-message` (guard + audit). The notification-worker stream path
  must stay simulated by default.

## LLM — platform budget/audit rail only (65F)
- **Allowed (if separately authorized in 65G.2):** bounded LLM calls through the platform
  budget/audit rail only (`RealLLMPlanOnlyProvider` + `BudgetPolicyEvaluator` + interaction/usage
  stores); Anthropic staging key only; budget cap enforced; metadata/evidence recorded.
- **Forbidden:** **direct diagnostic Anthropic call**; untracked external call; production key;
  production data; secrets in prompt; customer data in prompt; unbounded retry.
- **Rail:** the Step-65F plan-only rail with a `max_cost` budget policy in `block` mode.

## Cross-cutting rule (from Step 65F-C)
- **Direct diagnostic external calls are forbidden unless separately authorized in advance.** If a
  wire-level issue must be diagnosed by calling an external API directly, **stop and request explicit
  operator authorization first** (naming the call, its content, and its expected cost). Prefer
  non-network diagnosis (source/env/guard-dry-run) first.
- Every real external call in 65G.2 must be visible in the relevant platform audit/evidence surface
  (sandbox draft-PR safety record / notification delivery record / LLM interaction+usage store).

## This stage's posture
Planning only. No GitHub write, no Discord send, no LLM call, no workflow execution, no production
action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
