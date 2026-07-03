# Staging Integration Readiness Assessment (Step 65A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Read-only assessment / documentation only — no integration enabled, no secret created in this stage.**

Current external-integration posture and what each needs before a controlled staging validation.
All integrations are currently **disabled or mocked**; enabling any is a later, explicitly
operator-authorized step.

## Current posture (from `/operations/safety`, read-only)
- `production_executed_true_count = 0`
- `github_has_token = true` (mock/sandbox), `github_default_dry_run = true`,
  `github_external_write_enabled = false`
- `discord_has_token = false`, `discord_external_send_enabled = false`
- `llm_provider = mock`, `llm_external_call_enabled = false`
- `secret_provider = mock-vault`, `mock_vault_enabled = true`

## Per-integration readiness
### GitHub sandbox (→ 65D)
- **Current:** dry-run/mock; sandbox draft-PR endpoints exist (`/operations/github/sandbox-draft-pr/*`).
- **Sandbox resource:** a non-production GitHub repo (never a production repo).
- **Credentials:** a sandbox GitHub token (minimal scope), stored in the staging secret store only.
- **Kill switch:** integration-enable flag / `GITHUB_DRY_RUN=true` / revoke token.
- **Allowed:** controlled writes to the sandbox repo (draft PRs). **Forbidden:** production repo
  writes, merges to protected branches, image push.
- **Audit:** record every sandbox interaction; no secret in logs.
- **Operator authorization:** required before enabling.

### Notification (Slack/Discord) (→ 65E)
- **Current:** disabled (no token).
- **Sandbox resource:** a test channel / webhook (test workspace).
- **Credentials:** sandbox webhook/token in the staging secret store.
- **Kill switch:** notification-enable flag / revoke webhook.
- **Allowed:** test notifications to the test channel. **Forbidden:** production channels / real
  users.
- **Audit:** record test-channel delivery. **Operator authorization:** required.

### LLM (→ 65F)
- **Current:** `llm_provider=mock`; no live call.
- **Sandbox resource:** a non-production LLM key with a bounded quota.
- **Credentials:** non-prod key in the staging secret store; bounded spend.
- **Kill switch:** LLM-live flag / revoke key.
- **Allowed:** bounded live calls for the demo workflow. **Forbidden:** production keys, unbounded
  spend, sending production/customer data.
- **Audit:** record live calls within quota. **Operator authorization:** required.

### Secret backend (→ 65C)
- **Current:** `mock-vault`.
- **Resource:** a staging secret store / injection path (gitignored env or Vault-like).
- **Rule:** sandbox/non-production credentials only; never committed/printed/logged; **no production
  secrets**.
- **Kill switch:** remove/rotate credentials to return to fully-mocked posture.
- **Operator authorization:** required.

### Container registry sandbox (→ 65B/65D)
- **Current:** not set up; **no image push** anywhere.
- **Resource:** a sandbox registry (if in scope).
- **Forbidden until scoped + authorized:** registry login, image push.

## Cross-cutting requirements
- Where credentials must be stored: the **staging secret store only** (existence recorded, never
  values).
- Kill switches: every enabled integration must have a documented disable path back to mock.
- Audit evidence: every controlled external action must be recorded (sanitized).
- Sandbox/non-production only: staging must not use production secrets or production data.

## Posture
Read-only assessment only. No integration enabled, no secret created, no external write, no
production action; `production_executed_true_count=0`. Enabling any integration is a later,
explicitly operator-authorized step (65C–65F).

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
