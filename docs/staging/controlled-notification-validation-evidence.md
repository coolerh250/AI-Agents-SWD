# Controlled Notification Validation — Evidence (Step 65E)

> **Staging only — non-production only. No production action. No production notification.**
> **Read-only evidence (masked). No secret value printed. No production channel. No DM.**

Evidence captured around the real Discord controlled-test-message send on `10.0.1.32`.

## Pre-send state (discord-gateway `GET /status`, port `18007`)
| Phase | has_token | real_test_enabled |
|---|---|---|
| Baseline (before any change) | false | false |
| After compose wiring + scoped `SECRET_PROVIDER=env` recreate | **true** | false |
| Guard dry-run (flag still false) | true | false → `409 run_real_discord_test_not_true` |
| After enabling `RUN_REAL_DISCORD_TEST=true` + recreate | **true** | **true** |
| After reset | false | false |

## Send result (real)
- `POST /discord/real/test-message` (discord-gateway, port `18007`) → **HTTP 200**.
- `sandbox=true`, `test_mode=true`, `external_sent=true`, `production_executed=false`.
- `message_id`: a real Discord snowflake ID returned by `discord.com` (not repeated here).
- `delivery_id`: `028c580c-2dcb-4b3d-89de-1ed3bb4efa58`.
- `task_id` / correlation id: `step65e-20260706040615`.
- `safety_guard_result.allowed=true`; `mode=controlled_test`.
- Target channel / guild: the configured `DISCORD_TEST_CHANNEL_ID` / `DISCORD_TEST_GUILD_ID`
  (masked — Discord snowflake identifiers, not credentials, but not repeated here for hygiene).
- Message prefix: `[STAGING]`. Message body included only safe metadata (environment=staging,
  stage=65E, purpose=controlled_notification_validation, `production_executed_true_count=0`,
  test_id, timestamp) — **no secret, no token, no `.env` content, no production data**.

## Delivery record (`GET /discord/deliveries/{task_id}`)
Two rows under the same `task_id` (both expected — one is the direct API-call delivery, one is the
async stream-consumer's own audit copy of the same logical event):
| delivery_id | status | external_sent | note |
|---|---|---|---|
| `028c580c-…` | `delivered` | **true** | the real send via `/discord/real/test-message` |
| `70781ec5-…` | `simulated` | false (`blocked_reason=real_mode_disabled`) | the stream-consumer path — `notification-worker` was **never recreated**, so it correctly stayed blocked; proves no double-send |
- `external_sent_count=1`, `simulated_count=1`, `failed_count=0`.

## Safety
- `/operations/safety` before / after: `production_executed_true_count=0`,
  `sandbox_github_draft_pr_live_mode_enabled=false`, `discord_external_send_enabled=false`,
  `llm_real_enabled=false`, `secret_provider=mock-vault` (orchestrator itself was never recreated,
  so this value never changed at the orchestrator layer).

## Credential handling
- The bot token was resolved by the container's own secret provider and used only in the Discord
  `Authorization` header; it was never printed, logged, or committed. The channel ID and guild ID
  are non-secret Discord identifiers; they were read from the env file into a shell variable and
  used directly in the request body without being echoed in full to any log or document. One
  nested field (`safety_guard_result.target_channel` / `target_guild`) echoed those identifiers in
  a single interactive diagnostic response during the run; they are not credentials (any channel/
  guild member can see them in the Discord UI) and are not reproduced in any document.

## Reset
- `RUN_REAL_DISCORD_TEST=false`, `SECRET_PROVIDER=mock-vault`; discord-gateway recreated;
  `/status` → `has_token=false`, `real_test_enabled=false` (matches the pre-validation baseline
  exactly).

## Status
Step 65E: **PASS**. Operator confirmed `VISIBLE`. `production_executed_true_count=0`. Not
production readiness.

---
_Staging only — non-production only. No production action. No production notification._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=notification-controlled github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
