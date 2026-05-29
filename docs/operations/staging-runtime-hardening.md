# Staging runtime hardening (Stage 24)

Stage 24 introduces a **staging-readiness baseline**. None of the
artefacts in this document promote the platform to production — they
record the gap and the tools you'd use to close it.

## Pre-conditions

Before you run any Stage 24 script, confirm:

* the local cluster on `10.0.1.31` is healthy (`docker compose ps`
  shows 22 services `running (healthy)`);
* `git status` is clean and `HEAD` points at the commit the team
  agreed to ship;
* you have shell-level access to the operator's secret store (Vault,
  1Password, or equivalent) — Stage 24 never reads secrets from disk.

## Environment configuration

Two templates live in `infra/runtime/`:

* [`env.schema.example`](../../infra/runtime/env.schema.example) —
  the canonical env shape. Lists every variable the platform reads,
  with placeholder values.
* [`env.staging.example`](../../infra/runtime/env.staging.example) —
  pins `APP_ENV=staging`, removes trust-auth tolerance, and leaves the
  Stage 22 / Stage 23 opt-in switches set to `false`.

**Never commit a populated copy of either file.** The repository's
`.gitignore` already excludes `.env`, `.env.*`, `*.env`, `secrets/`,
`*.secret`, `*.key`, `*.pem`, `*.p12`, and `credentials.json`. Stage 24
additionally ignores `backups/` and `*.dump` so a `pg_dump` archive
never accidentally ends up in a commit.

The validator's placeholder marker is the literal string
`PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE`. Any required field carrying
that marker is rejected by `validate_runtime_config.py --mode staging`.

## Postgres password

Local/test runs with `POSTGRES_HOST_AUTH_METHOD=trust` — fine for the
loopback-only cluster on `10.0.1.31`. Staging must drop the trust line
and require a real password. The Stage 24 template
[`docker-compose.staging.yml`](../../infra/docker-compose/docker-compose.staging.yml)
demonstrates the pattern:

```yaml
postgres:
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-aiagents_app}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set for staging}
    # POSTGRES_HOST_AUTH_METHOD intentionally absent — image defaults to scram-sha-256.
```

The `${VAR:?message}` form makes docker compose refuse to start when
the env var is empty.

## Avoiding trust auth

The Stage 24 validator runs three checks against `POSTGRES_HOST_AUTH_METHOD`:

| Mode               | Trust auth allowed?                |
| ------------------ | ---------------------------------- |
| `local`            | Yes (current cluster default).     |
| `staging`          | No — fails with `postgres_trust_auth_forbidden`. |
| `production-check` | No — fails the same way.           |

Run `./scripts/validate_runtime_config.sh --mode staging` against the
shell that will launch the staging cluster; the script reads the live
env and reports every placeholder + trust-auth violation.

## Vault dev mode

Local/test runs Vault with `server -dev`. Staging must point
`VAULT_ADDR` at a real Vault server. As an escape hatch the validator
accepts `ALLOW_VAULT_DEV_MODE_FOR_STAGING=true` (downgraded to a
**warning**, not a failure) so an operator can opt into a short
integration smoke without flipping production-grade Vault for it.
`production-check` rejects Vault dev mode unconditionally.

## Backup / restore

Two scripts and one verifier live under `scripts/`:

* [`backup_postgres.sh`](../../scripts/backup_postgres.sh) — writes a
  `pg_dump --format=custom` archive to `backups/aiagents-<ts>.dump`.
  The script uses the local cluster's trust-auth path; for staging
  the operator runs it with `PGPASSWORD` set in the shell.
* [`restore_postgres.sh`](../../scripts/restore_postgres.sh) —
  refuses unless `ALLOW_RESTORE=true` is exported AND a backup file
  is passed as the first positional argument. Refuses outright when
  `APP_ENV` is `production` / `production-check`.
* [`verify_backup_restore.sh`](../../scripts/verify_backup_restore.sh) —
  the Stage 24 backup/restore smoke. Takes a fresh `pg_dump`, asserts
  `pg_restore -l` parses the TOC, confirms the live DB's table count
  was untouched, and asserts the restore guard refuses without
  `ALLOW_RESTORE=true`. Ends with `BACKUP_RESTORE_VERIFY: PASS`.

The local cluster ships **no** backups — `backups/` is gitignored.
Each backup file lives only on the host that ran the script.

## Safety gate

Stage 24 adds a read-only gate:

```
./scripts/production_safety_gate.sh
```

It inspects:

* `deployment_records.production_executed=true OR environment='production'`;
* `workflow_states.execution_result->>'production_executed'='true'`;
* `/operations/safety.result` (must be `safe` or `warning`);
* `RUN_REAL_GITHUB_TEST` / `RUN_REAL_DISCORD_TEST` defaults;
* `/operations/safety.external_alert_receivers_present`;
* `/operations/safety.vault_mode_note` / `postgres_auth_note`.

The gate never writes. It exits `0` (PASS) when every counter is `0`
and the platform stays in sandbox-by-default. It exits `1` (FAIL)
otherwise — the script prints the offending counter so the operator
can drill in.

## Runtime health snapshot

```
./scripts/runtime_health_snapshot.sh
```

Writes a flat, regeneratable summary to `source/runtime-health.log`
(gitignored). The file carries `docker compose ps`,
`/operations/summary`, `/operations/safety`, Prometheus targets
up/down, stream lag, open incidents, DLQ counts, and the
`production_executed` counters. No secret value can appear in the
log; `verify_staging_hardening.sh` greps for token-shaped substrings
as a regression guard.

## Staging readiness checklist

This list is the Stage 24 baseline. Everything below MUST be true
before the team considers staging-ready:

* [ ] `infra/runtime/env.staging.example` is reviewed and the
      operator has a populated copy in their shell (not committed).
* [ ] `scripts/validate_runtime_config.sh --mode staging` PASSes
      against the staging shell.
* [ ] `scripts/verify_backup_restore.sh` PASSes against the staging
      Postgres.
* [ ] `scripts/production_safety_gate.sh` PASSes (all counters at `0`).
* [ ] `scripts/runtime_health_snapshot.sh` produced
      `source/runtime-health.log` with no token-shaped substring.
* [ ] `docker compose -f infra/docker-compose/docker-compose.staging.yml
      config` validates against the staging shell (do not actually
      start the staging cluster without operator + tenant sign-off).
* [ ] Vault is either real (`VAULT_ADDR` points outside the dev
      container) or the operator has documented why
      `ALLOW_VAULT_DEV_MODE_FOR_STAGING=true` is acceptable for the
      window in question.
* [ ] Alertmanager receivers are reviewed — the platform's null
      receiver is fine for local/test and staging, but documented for
      handoff.

## This is NOT production-ready

The Stage 24 baseline is a staging baseline. The following gaps
remain open and are tracked as observations (not roadmap commitments):

* Vault dev mode is still running in the test cluster.
* Postgres trust auth is still the local/test default.
* Alertmanager receivers are still `null-receiver` — no Slack,
  Discord, Telegram, PagerDuty, or email receiver is configured.
* The Stage 23 controlled-real GitHub flow and the Stage 22
  controlled-real Discord flow stay sandbox-by-default; neither is
  enabled by the Stage 24 baseline.
* No production deploy pipeline exists. The platform's
  `production_executed=true` counters remain `0`.

Stage 24 deliberately does not decide how to close these gaps — that
is the operator's call, escalated through whatever change-management
process the org uses.
