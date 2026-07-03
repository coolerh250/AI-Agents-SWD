# Notification Staging Channel Plan (Step 65B → 65E)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — no notification sent, no token use, no integration enabled in this stage.**

Plan for the controlled notification integration to be validated at Step 65E. Currently disabled
(`discord_has_token=false`, `discord_external_send_enabled=false`).

## Channel
- **Type:** Slack **or** Discord (operator chooses at 65E; other platforms out of scope).
- **Channel:** `<STAGING_TEST_CHANNEL>` placeholder — a **test** channel / webhook in a test
  workspace (never a production channel or a real user DM).
- **Credential reference:** `DISCORD_BOT_TOKEN` + `DISCORD_TEST_CHANNEL_ID` (or a Slack webhook
  reference), stored in the staging secret backend only.

## Conventions
- **Message prefix:** `[STAGING]` on every message.
- **Allowed message types:** E2E workflow status; controlled test notification.
- **Rate limit:** at most a small bounded number of messages per validation run (no repeated
  sends).

## Allowed actions (later Step 65E)
- Send one controlled `[STAGING]` notification to the test channel.
- Send a status notification for the E2E staging workflow (65G).
- Record the delivery result.

## Forbidden actions
- Send to a production channel. Send a DM to a real user. Send a customer-facing notification. Send
  repeated / spam messages. Include secrets or sensitive logs in a message.

## Enable flags / kill switch
- Live only when `RUN_REAL_DISCORD_TEST=true` **and** `DISCORD_TEST_CHANNEL_ID` + token reference are
  present.
- **Kill switch:** set `RUN_REAL_DISCORD_TEST=false` or remove/rotate the token → returns to
  disabled.

## Required audit / evidence
- Record channel reference, message type, and delivery result (sanitized); no secret in logs.
- Verify `production_executed_true_count=0` and that the channel is the test channel.

## Operator authorization + confirmation
Required before 65E sends anything; the operator authorizes the send and confirms the test-channel
delivery afterward.

## Posture
Planning only. No notification sent, no token use, no integration enabled, no external write, no
runtime change, no production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
