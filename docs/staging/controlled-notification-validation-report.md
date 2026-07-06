# Controlled Notification Validation Report (Step 65E)

> **Staging only — non-production only. No production action. No production secret. No production notification.**
> **Exactly one controlled staging notification was sent. No production notification was sent. No DM was sent.**

Records the **real** (not mock) controlled notification validation on staging `10.0.1.32`, under
operator authorization: one `[STAGING]`-prefixed test message was sent to the operator's
**non-production** Discord test channel (`MySanbox` / `#general`) through the platform's existing
controlled real-Discord path.

## Overall result
- Overall result: **PASS** — the technical send succeeded (`external_sent=true`,
  `status=delivered`, guard `allowed=true`), staging was reset to safe, and the operator confirmed
  **VISIBLE** — the message was seen in `MySanbox` / `#general`.
- `production_executed_true_count=0` throughout. Notification send flag reset to disabled.

## What was validated (real)
- **Control path:** the existing Stage-32 controlled-real-Discord guard
  (`shared/sdk/real_integration/discord.py::evaluate_real_discord_request`) on the discord-gateway's
  `POST /discord/real/test-message` endpoint — token present, opt-in flag, test guild, test channel,
  `mode=controlled_test`, `production_executed=False` all required simultaneously.
- **Real send:** exactly **one** message posted to `discord.com` via the bot token, to the
  configured `DISCORD_TEST_CHANNEL_ID` (masked in all docs) in the configured test guild (masked).
- **Result:** HTTP 200, `external_sent=true`, `production_executed=false`, `message_id` returned by
  Discord, `delivery_id` recorded, `safety_guard_result.allowed=true`.

## Changes required to make it work (committed)
1. **Compose env wiring** (`2052dff`): `discord-gateway`'s compose environment block wired only
   `DISCORD_BOT_TOKEN` + `RUN_REAL_DISCORD_TEST` — missing `DISCORD_TEST_CHANNEL_ID` /
   `DISCORD_TEST_GUILD_ID` / `DISCORD_ALLOWED_ROLE_ID` (same class of gap found in 65D's GitHub
   wiring). Added the missing vars with safe empty defaults.
2. **Missing operator input:** `DISCORD_TEST_GUILD_ID` (the Discord Guild/Server ID for `MySanbox`)
   had never been collected — the guard requires it. The operator provided it directly (a
   non-secret numeric server identifier, not a credential) and it was added to
   `infra/runtime/.env.staging.local` on the host.
3. **Secret-provider routing gap (not committed — runtime-only, reset after):** with
   `SECRET_PROVIDER=mock-vault`, the discord-gateway client resolves its token through
   `MockVaultSecretProvider`, which reads a **separate** file
   (`infra/runtime/.mock-vault-secrets.local.json`) still holding a stale 36-char placeholder token
   from an earlier pilot stage — not the real 72-char sandbox token in `.env.staging.local`.
   Overwriting that shared mock-vault file (used by other services/tests) was avoided; instead
   `SECRET_PROVIDER=env` was set **only for the validation window**, and **only the discord-gateway
   container** was recreated to pick it up — every other running container was left untouched. Reset
   to `mock-vault` and the container recreated again after the send.

## Findings resolved during validation
- Guard dry-run (flag off) correctly returned `409 run_real_discord_test_not_true` before
  enablement, confirming the token was resolvable and the block was live.
- After enabling, the real send succeeded on the first attempt; no retry was needed.
- The stream-consumer delivery path (`notification-worker`, the Stage-33 "autospam" surface) was
  **not** touched or recreated during this window and correctly recorded its own copy of the event
  as `simulated` / `blocked_reason=real_mode_disabled` — confirming **no double-send** occurred.

## Safety
- `production_executed_true_count=0` before, during, and after.
- Only the discord-gateway container was recreated (twice: enable, then reset); no other service was
  restarted. No GitHub write, no LLM call, no workflow execution, no production action.
- Notification send flag reset to `false`; `SECRET_PROVIDER` reset to `mock-vault`; discord-gateway
  `/status` returned to the exact pre-validation state (`has_token=false`, `real_test_enabled=false`).

## Status
- Step 65E: **PASS** (real send validated technically; operator confirmed `VISIBLE`). Step 65F
  (LLM) still pending its own authorization. This is not production readiness.

---
_Staging only — non-production only. No production action. No production secret. No production notification._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=notification-controlled github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
