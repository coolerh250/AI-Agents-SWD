# Controlled Notification Validation — Known Gaps (Step 65E)

> **Staging only — non-production only. No production action. No production notification.**
> **Documentation only. No secret value appears here.**

## Gaps
1. ~~Operator visual confirmation pending.~~ **RESOLVED** — the operator confirmed `VISIBLE`
   (seeing the message in `MySanbox` / `#general`). See
   [controlled-notification-operator-confirmation.md](controlled-notification-operator-confirmation.md).
2. **Mock-vault file left stale.** `infra/runtime/.mock-vault-secrets.local.json` still holds an
   old 36-char placeholder `DISCORD_BOT_TOKEN` / empty `DISCORD_TEST_CHANNEL_ID` from an earlier
   pilot stage. It was intentionally **not** overwritten (avoiding a wider blast radius on other
   services/tests that read it) — the validation instead used a scoped, temporary
   `SECRET_PROVIDER=env` override for the single recreate window. Left as a non-blocking gap; a
   future stage may choose to refresh or retire this file.
3. **`notification-worker`'s own real-Discord path was not exercised.** Only the discord-gateway's
   `/discord/real/test-message` endpoint was used. The stream-consumer (`notification-worker`)
   real-delivery path exists (`shared/sdk/notifications/real_delivery_policy.py`) but was
   intentionally left disabled/untouched this stage — it is in scope for 65G's end-to-end workflow
   validation, not 65E.
4. **Guild ID collection was reactive, not proactive.** `DISCORD_TEST_GUILD_ID` was not identified
   as a required input until the guard blocked on it mid-stage; it is a non-secret identifier and
   was provided immediately by the operator, but future integration-input checklists should include
   it up front.

## Non-gaps (done)
- Exactly one real, controlled `[STAGING]` send; no production channel; no DM; no spam; no secret
  in the message; notification flag + secret-provider override both reset;
  `production_executed_true_count=0`.

## Posture
Real (not mock) controlled notification validation, with the above gaps tracked as non-blocking
until the operator confirms visibility. No production action; no external write beyond the one
approved staging send.

---
_Staging only — non-production only. No production action. No production notification._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=notification-controlled github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
