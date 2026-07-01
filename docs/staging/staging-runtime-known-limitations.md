# Staging Runtime Known Limitations (Step 64B.2B)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Known limitations / gaps of the Step 64B.2B staging runtime on `10.0.1.32`. None of these is a
production readiness sign-off; **Claude Code does not decide production readiness.**

## Secret storage
- **Vault runs in dev mode**; `SECRET_PROVIDER=mock-vault` (fixture
  `infra/runtime/.mock-vault-secrets.local.json`, gitignored). `ALLOW_VAULT_DEV_MODE_FOR_STAGING=true`
  is the documented staging escape hatch — **not a production-ready secret store**. The
  `/operations/safety` endpoint flags mock-vault as an escape hatch.

## GitHub / Discord / LLM integrations
- `github_has_token = true` reflects a **sandbox/mock** token from the mock-vault fixture, not
  a real credential. Live write gates are **off** (`github_external_write_enabled=false`,
  `real_github_test_enabled=false`), so no live GitHub write occurs.
- Discord: `discord_has_token=false`, `discord_external_send_enabled=false`,
  `discord_real_test_enabled=false` — no live send.
- LLM live calls disabled / mocked in staging.

## Host resource headroom
- Host has **no swap** and 7.7 GiB RAM; 22 containers run within it but headroom is limited —
  monitor memory under load (agent workflows).

## Transport
- **HTTP only (no TLS)** for the first staging demo (operator-accepted). TLS is a future
  option; not configured here.

## Not performed in this stage
- **Demo workflow NOT executed** — seeding + running the demo workflow is Step 64D.
- Admin Console mutation-page operator-session walkthrough is Step 64C.
- No production deploy / sync / secret / external write / GitHub merge / image push.

## Transient bring-up note
- The initial `docker compose up` hit a transient Docker Hub TLS-handshake timeout while
  pulling a base image (`grafana/tempo`); base images were re-pulled with retries and the
  bring-up then succeeded (`START_STAGING_RUNTIME: PASS`). No config change was required.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false runtime-deployment=staging-only live-integrations=disabled demo-workflow-executed=false -->
