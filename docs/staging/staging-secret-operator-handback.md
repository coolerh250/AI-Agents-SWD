# Staging Secret Operator Handback (Step 65C)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Handback instructions for the operator. Do NOT paste secret values into chat, repo, docs, or logs.**

What the operator (owner: **Zachary**) provides out-of-band before each later step. All values go
**only** into `infra/runtime/.env.staging.local` on `10.0.1.32` (gitignored, chmod 600).

## Out-of-band entry method
On the staging host, edit the gitignored env file directly (never via chat/repo):
```
# on 10.0.1.32, as itadmin — example key names only, values entered by the operator
#   GITHUB_TOKEN=<sandbox token>
#   DISCORD_BOT_TOKEN=<bot token>   DISCORD_TEST_CHANNEL_ID=<numeric id>
#   ANTHROPIC_API_KEY=<non-prod key>
```
Keep the file `chmod 600`; do not commit; do not print. (The lines above are placeholders — no real
value is shown here.)

## Handback checklist
- [ ] **Before 65D:** confirm/set the **GitHub sandbox token** (`GITHUB_TOKEN`) for
      `coolerh250/AI-Agents-SWD-sandbox`; keep `GITHUB_DRY_RUN=true` until 65D authorizes the write.
- [ ] **Before 65E:** set `DISCORD_TEST_CHANNEL_ID` (numeric ID for `MySanbox/#general`) and confirm
      `DISCORD_BOT_TOKEN`; keep `RUN_REAL_DISCORD_TEST=false` until 65E authorizes the send.
- [ ] **Before 65F:** set `ANTHROPIC_API_KEY` (non-production); keep `LLM_PROVIDER=mock` and
      `ENABLE_REAL_LLM_NETWORK_CALL=false` until 65F authorizes the bounded call.
- [ ] Rotation owner (**Zachary**) rotates/revokes on demand; rotating a value is also the kill
      switch.

## Enablement stays operator-gated
No integration is enabled by this handback. Each of 65D/65E/65F flips its enable flag **only** under
a separate explicit operator authorization, and a runtime reload/restart is separately authorized.

## Posture
Handback / documentation only. No integration enabled, no external write, no production action;
`production_executed_true_count=0`. No secret value appears in this document.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
