# Staging Secret Reference Map (Step 65C)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Reference names + non-secret metadata only — NO secret value appears in this document.**

Maps the staging sandbox credential **references** (names) and non-secret metadata. Values live only
in the gitignored `infra/runtime/.env.staging.local` on `10.0.1.32`, entered out-of-band.

## GitHub sandbox
- **Token reference:** `GITHUB_TOKEN` (sandbox; value out-of-band). Sandbox-specific token to be
  confirmed/set out-of-band before 65D.
- **Repo (non-secret):** `GITHUB_SANDBOX_REPO` = `https://github.com/coolerh250/AI-Agents-SWD-sandbox.git`
  (public sandbox repo, non-production).
- **Allowlist (non-secret):** `GITHUB_ALLOWED_REPO` = `coolerh250/AI-Agents-SWD-sandbox`;
  `GITHUB_FORBID_PROTECTED_BRANCH=true`.

## Notification (Discord)
- **Token reference:** `DISCORD_BOT_TOKEN` (value out-of-band).
- **Channel reference:** `DISCORD_TEST_CHANNEL_ID` (numeric ID pending out-of-band); operator
  channel = server `MySanbox`, channel `#general` (non-secret metadata).
- **Platform (non-secret):** `NOTIFICATION_PLATFORM=discord`; `NOTIFICATION_MESSAGE_PREFIX=[STAGING]`.

## LLM (Anthropic)
- **Key reference:** `ANTHROPIC_API_KEY` (or `LLM_API_KEY`) — non-production staging key, value
  out-of-band.
- **Provider (non-secret):** `LLM_STAGING_PROVIDER=anthropic`; current `LLM_PROVIDER=mock` (safe
  default); quota `LLM_MAX_COST_PER_RUN=1` (operator-defined bounded limit = 1 USD per run).

## Secret backend / ownership (non-secret)
- **Backend:** env-file (`infra/runtime/.env.staging.local`, gitignored, chmod 600).
- **`SECRET_PROVIDER`:** mock-vault (unchanged); references injected via the env file.
- **`SECRET_OWNER`:** Zachary. **`SECRET_ROTATION_OWNER`:** Zachary. **`SECRET_AUDIT_REQUIRED`:**
  true.

## Rules
- No secret **value** is listed here or anywhere in the repo/docs/logs — only reference names +
  non-secret metadata.
- Secret values are staging-only, non-production, and entered out-of-band into the env file.

## Posture
Reference map only. No integration enabled, no external write, no production action;
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
