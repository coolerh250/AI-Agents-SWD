# Controlled Staging External Integration Plan (Step 65B)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — no integration enabled, no secret created, no external write, no runtime change in this stage.**

Master plan for how the staging AI Agents Platform on `10.0.1.32` will safely connect to
**sandbox / non-production** external resources, to support the later Step 65C–65F validations. This
document is the umbrella; per-integration detail lives in the sibling plan docs.

## Operator-confirmed scope
- **Functional scope:** `FULL_DOMAIN_MATRIX` (all domains in
  [staging-functional-coverage-matrix.md](staging-functional-coverage-matrix.md)).
- **In-scope integrations:** GitHub sandbox repo · Notification staging channel · LLM staging key ·
  Staging secret backend.
- **Deferred:** Container registry sandbox · Cloud storage / Google Drive (see
  [deferred-integration-register.md](deferred-integration-register.md)).

## Current posture (read-only `/operations/safety`)
`production_executed_true_count=0`; `github_external_write_enabled=false`;
`discord_external_send_enabled=false`; `llm_external_call_enabled=false`; `secret_provider=mock-vault`.
Everything below is **planned**, not enabled.

## In-scope integrations (summary)
| Integration | Plan | Later step |
|---|---|---|
| Staging secret backend | [staging-secret-backend-plan.md](staging-secret-backend-plan.md) | 65C |
| GitHub sandbox repo | [github-sandbox-integration-plan.md](github-sandbox-integration-plan.md) | 65D |
| Notification staging channel | [notification-staging-channel-plan.md](notification-staging-channel-plan.md) | 65E |
| LLM staging key | [llm-staging-integration-plan.md](llm-staging-integration-plan.md) | 65F |

## Overall safety model
- **Sandbox / non-production only.** No production repo, channel, key, secret, or data — ever.
- **Default-off.** Every integration stays disabled/mocked until its step is explicitly authorized.
- **Least privilege.** Minimal scopes; bounded quotas; single controlled actions first.
- **No secret values anywhere in the repo/docs/logs.** Only reference *names* and *flags* are
  documented; values are provided out-of-band at 65C and stored in the staging secret backend only.
- **`production_executed_true_count` must remain 0** across all Step 65 work.

## Enable-flag model
Each integration is gated by existing safety flags (documented as *names* only), e.g. GitHub
(`RUN_REAL_GITHUB_TEST`, `GITHUB_DRY_RUN`, `GITHUB_TEST_REPO`), notification
(`RUN_REAL_DISCORD_TEST`, `DISCORD_TEST_CHANNEL_ID`), LLM (`RUN_REAL_LLM_TEST`,
`ENABLE_REAL_LLM_NETWORK_CALL`, `LLM_PROVIDER`). An integration is "live" only when its full set of
opt-in flags **and** a sandbox credential reference are present — mirroring the current
`*_external_*_enabled` gates.

## Kill-switch model
Every enabled integration has a documented disable path back to the fully-mocked posture: flip the
opt-in flag off (or set `GITHUB_DRY_RUN=true` / `LLM_PROVIDER=mock`) and/or remove/rotate the
sandbox credential reference. The `/operations/safety` endpoint is the single source of truth for
verifying an integration is off.

## Audit / evidence model
- Every controlled external action (65D/65E/65F/65G) is recorded with a sanitized evidence entry
  (what, where, when, result) — **never** the secret value or sensitive log content.
- Admin Console formal pages + `/operations/*` endpoints surface the resulting evidence for operator
  validation.
- Each step verifies `production_executed_true_count=0` before and after.

## Not-touching-production verification
Before and after any enablement: confirm the target is a sandbox resource (repo/channel/key), the
production flags stay false (`release_governance_allow_production_deploy`,
`github_external_write_enabled` to a production repo, etc.), and `production_executed_true_count=0`.

## Gates & user inputs
Authorization gates for 65C–65I → [external-integration-authorization-gates.md](external-integration-authorization-gates.md).
User inputs needed later → [external-integration-user-input-checklist.md](external-integration-user-input-checklist.md).
Risks → [external-integration-risk-register.md](external-integration-risk-register.md).

## Posture
Planning only. No integration enabled, no secret created, no external write, no workflow execution,
no runtime change, no production action; `production_executed_true_count=0`. This is not production
readiness. Claude Code does not enable integrations or decide staging functional acceptance.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
