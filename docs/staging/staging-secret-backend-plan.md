# Staging Secret Backend Plan (Step 65B → 65C)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — no secret is created, updated, printed, or committed in this stage.**

Defines how staging sandbox credentials will be stored and referenced for the in-scope integrations,
replacing the current `mock-vault` posture at Step 65C. **No secret values appear in this document.**

## Secret backend target
- **Primary:** the existing staging secret path `infra/runtime/.env.staging.local` (gitignored,
  chmod 600) and/or the mock-vault file `infra/runtime/.mock-vault-secrets.local.json`, populated
  with **sandbox / non-production** references only.
- **Optional future:** a Vault-like staging secret store via `SECRET_PROVIDER=vault` (`VAULT_ADDR`,
  `VAULT_TOKEN` as *references*, never values) — deferred unless the operator requests it.
- **mock-vault replacement plan:** at 65C, add the sandbox references below to the staging secret
  path; keep `SECRET_PROVIDER=mock-vault` unless the operator opts into Vault. Reverting to
  fully-mocked = remove/rotate the references.

## Required secret references (names only — values provided out-of-band at 65C)
| Purpose | Reference name (env/flag) | Notes |
|---|---|---|
| GitHub sandbox token | `GITHUB_TOKEN` | sandbox repo, minimal scope |
| GitHub sandbox repo | `GITHUB_TEST_REPO` | non-production repo (name/URL) |
| GitHub enable flags | `RUN_REAL_GITHUB_TEST`, `GITHUB_DRY_RUN` | opt-in / dry-run kill switch |
| Notification webhook/token | `DISCORD_BOT_TOKEN` (or Slack webhook ref) | test channel only |
| Notification channel | `DISCORD_TEST_CHANNEL_ID` | staging test channel |
| Notification enable flag | `RUN_REAL_DISCORD_TEST` | opt-in kill switch |
| LLM API key | `LLM_API_KEY` (or `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) | non-production key |
| LLM provider / enable | `LLM_PROVIDER`, `RUN_REAL_LLM_TEST`, `ENABLE_REAL_LLM_NETWORK_CALL` | mock→live gate |
| LLM quota/budget config | LLM budget/limit config keys | bounded spend |

## Naming convention
- Reuse the platform's existing env/flag names above (no new secret schema) so `/operations/safety`
  keeps reflecting posture accurately. Sandbox references are distinguished by their **values**
  pointing at sandbox resources — never by embedding secrets in names.

## Secret owner / access / rotation
- **Owner:** the operator provides and owns the sandbox credentials; rotation owner named at 65C.
- **Access model:** injected via the staging secret path into the relevant services only; loopback
  runtime; no public exposure.
- **Rotation model:** rotate/revoke on demand; rotating a reference is also the kill switch.
- **Audit requirement:** record only *that* a reference is present (boolean/existence), never its
  value, mirroring `/operations/safety` booleans.

## Secret handling rules (mandatory)
- **No secret values may be committed.**
- **No secret values may be printed.**
- **No secret values may be copied into docs.**
- **Secrets must be staging-only and non-production.**
- `.env.staging.local` is never displayed; only existence/flags are reported.

## Fallback behavior
If a sandbox credential is absent or an enable flag is off, the integration falls back to
mock/disabled — the safe default — and `/operations/safety` shows the corresponding
`*_enabled=false`.

## Posture
Planning only. No secret created/updated/printed/committed, no integration enabled, no external
write, no runtime change, no production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
