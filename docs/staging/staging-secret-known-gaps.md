# Staging Secret Known Gaps (Step 65C)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Tracks the credential items still pending. No secret value appears here.**

Items still pending after the Step 65C credential setup, to be provided by the operator out-of-band
before the relevant later step.

## Gap closure update (Step 65D-C)
Consolidated in [step65c-65d-gap-closure-map.md](step65c-65d-gap-closure-map.md):
1. **GitHub sandbox token — RESOLVED_BY_65D.** Exercised end-to-end by the real sandbox draft PR #15
   in `coolerh250/AI-Agents-SWD-sandbox`; reset to safe afterwards.
2. **Discord bot token + channel ID — PENDING_65E** (configured reference present / not yet
   validated).
3. **Anthropic LLM key — PENDING_65F** (configured reference present / not yet validated).

## Pending sandbox secret values (out-of-band, before their step)
1. **GitHub sandbox token** — confirm/set the sandbox-repo token in `GITHUB_TOKEN` (and point
   `GITHUB_TEST_REPO`/allowlist at the sandbox repo) before **65D**. The existing `GITHUB_TOKEN` is
   the earlier bootstrap value and must be confirmed as the sandbox token. **(Resolved by 65D.)**
2. **Discord bot token + channel ID** — set `DISCORD_TEST_CHANNEL_ID` (numeric ID for
   `MySanbox/#general`) and confirm `DISCORD_BOT_TOKEN` before **65E**.
3. **Anthropic LLM key** — set `ANTHROPIC_API_KEY` (or `LLM_API_KEY`), non-production, before
   **65F**.

## Runtime reload gap
- The env file references are provisioned but the orchestrator has **not** reloaded them (no restart
  authorized). A runtime reload/restart is a later explicit authorization; until then the running
  process uses the prior (also-safe) env.

## Non-gaps (done)
- Non-secret references + metadata provisioned; kill switches at safe defaults; file gitignored +
  chmod 600; secret-containing backup removed; `production_executed_true_count=0`; all external
  integrations disabled.

## Delivery rule (reminder)
Secret values are delivered **out-of-band** into `infra/runtime/.env.staging.local` on `10.0.1.32`
only — never pasted into chat, committed, or printed.

## Posture
Credential setup only. No integration enabled, no external write, no production action;
`production_executed_true_count=0`. Marked **PASS_WITH_GAPS** for the pending items above.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
