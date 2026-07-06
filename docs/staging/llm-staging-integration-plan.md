# LLM Staging Integration Plan (Step 65B → 65F)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — no LLM call, no key use, no integration enabled in this stage.**

Plan for the controlled LLM integration to be validated at Step 65F. Currently `llm_provider=mock`,
`llm_external_call_enabled=false`.

## Provider & key
- **Provider:** `<LLM_PROVIDER_PLACEHOLDER>` (operator chooses at 65F; e.g. a non-production
  OpenAI/Anthropic account).
- **Key reference:** `LLM_API_KEY` (or `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) — a **non-production**
  key, stored in the staging secret backend only.

## Quota / limits
- **Quota / budget limit:** operator-defined bounded quota (existing LLM budget/cost-governance
  config); calls stop when exceeded.
- **Max tokens / per-run limit:** a small bounded per-call and per-run cap.

## Allowed actions (later Step 65F)
- A single controlled prompt call.
- A bounded E2E workflow call (65G).
- Record prompt/response **metadata** (not raw sensitive content) + cost/token estimate if
  available.

## Forbidden actions
- Use production data. Use a production key. Make unbounded calls. Take an automatic production
  action. Perform an external write based only on LLM output. Store secrets in a prompt.

## Audit / redaction
- **Prompt/response audit:** record metadata; redact PII/secrets; never log the key.
- Verify `production_executed_true_count=0`; LLM output never directly triggers a production action
  (human review + policy gates remain in force).

## Enable flags / kill switch / fallback
- Live only when `RUN_REAL_LLM_TEST=true` **and** `ENABLE_REAL_LLM_NETWORK_CALL=true` **and** a key
  reference is present and `LLM_PROVIDER` is set to the real provider.
- **Kill switch:** set `LLM_PROVIDER=mock` or `ENABLE_REAL_LLM_NETWORK_CALL=false` or revoke the key
  → **fallback to mock** behavior.

## Operator authorization
Required before 65F; the operator authorizes the key usage and quota, and confirms usage afterward.

## Step 65F outcome (real, not mock)
Validated: one official, audited, bounded Anthropic call (model `claude-haiku-4-5-20251001`, 708
tokens, actual cost $0.03096, well within the $1 cap) via the platform's existing Stage-35 plan-only
real-LLM rail; `plan_only=true`, `requires_human_review=true`, `production_executed=false`;
`production_executed_true_count=0`; nothing left persistently enabled (real-call flags were
ephemeral, scoped to one `docker compose exec` process only). See
[controlled-llm-validation-report.md](controlled-llm-validation-report.md).

## Posture
Step 65F executed (real, bounded call; nothing left enabled). No production data; no secret in
prompt; no runtime change beyond an ephemeral one-off exec; no production action;
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
