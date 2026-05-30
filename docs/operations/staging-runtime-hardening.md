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

---

# Stage 25 — Staging bring-up & end-to-end validation

Stage 25 turns the Stage 24 baseline into a runnable parallel cluster.
The local/test stack stays untouched on its existing host ports; the
staging stack uses docker compose project name `aiagents-staging`,
host ports offset by **+10000**, separate volumes, and password Postgres.

## How to generate a staging env

```
./scripts/generate_staging_env.sh
```

* Reads `infra/runtime/env.staging.example`.
* Writes `infra/runtime/.env.staging.local` (gitignored, chmod 600).
* Substitutes a random base64 `POSTGRES_PASSWORD` (32 chars).
* Leaves every other secret-shaped field as the literal
  `PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE` so the validator catches
  half-configured envs.
* Refuses to overwrite an existing file unless `ALLOW_OVERWRITE=true`.

## How to start the staging runtime

```
./scripts/start_staging_runtime.sh          # uses existing images
./scripts/start_staging_runtime.sh --rebuild # docker compose build first
```

Sequence:

1. Generate the env file if missing.
2. Enable `ALLOW_VAULT_DEV_MODE_FOR_STAGING=true` in the env file (the
   documented Stage 25 escape hatch — see "known limitations" below).
3. Run `./scripts/validate_runtime_config.sh --mode staging
   --env-file infra/runtime/.env.staging.local`. Refuse to proceed
   unless `RUNTIME_CONFIG_VALIDATION: PASS`.
4. `docker compose -p aiagents-staging -f
   infra/docker-compose/docker-compose.staging.yml --env-file
   infra/runtime/.env.staging.local up -d`.
5. Wait for staging Postgres + Redis.
6. Apply every migration in `migrations/*.sql` against the staging DB
   under the `aiagents_app` user.
7. Initialise Redis Streams consumer groups.
8. Restart consumer services so they pick up the new tables.
9. Print the staging port map.

## How to stop the staging runtime

```
./scripts/stop_staging_runtime.sh             # keep volumes
./scripts/stop_staging_runtime.sh --volumes   # purge staging volumes
```

`docker compose down` is invoked under the same project name. The
script falls back to a noop `POSTGRES_PASSWORD` when the env file is
missing so a "I'm not sure what state staging is in" tear-down still
works.

## How to check staging DB auth

```
./scripts/check_staging_runtime.sh
```

* Lists `docker compose ps` for the staging project.
* Hits `/health` on every staging service via its +10000 host port.
* Confirms `POSTGRES_HOST_AUTH_METHOD` is unset inside the staging
  Postgres container (proves trust auth is disabled).
* Confirms the staging Postgres connection works under the
  `aiagents_app` password user via `psql`.

The script never echoes the password — it only reads it from the env
file.

## How to run staging end-to-end validation

```
./scripts/verify_staging_runtime.sh
```

Runs 12 checks in sequence. The default behaviour is to tear staging
DOWN after the final assertion so the test cluster doesn't carry
two 22-service stacks at once. Pass `--keep-running` to leave the
staging stack up for manual inspection.

The e2e workflow seeds a `dev.test` task through the staging
discord-gateway (port 18007), waits for the orchestrator (port 18000)
to mark it `completed`, then asserts the workflow view, audit
timeline, notification deliveries, and `/operations/safety` all
carry the expected sandbox-only shape. `production_executed` must
remain `0` for both stacks throughout.

## How to produce a staging runtime health snapshot

```
./scripts/runtime_health_snapshot.sh --env staging
cat source/runtime-health-staging.log
```

The flag toggles the script to:

* read the staging compose project + env file;
* hit the staging orchestrator + Prometheus on +10000 host ports;
* query the staging Postgres under `aiagents_app`;
* write to `source/runtime-health-staging.log` (gitignored).

The file must contain no token-shaped substring (the verify script
greps for one as a regression guard).

## How to run staging backup / restore

```
./scripts/verify_staging_backup_restore.sh
```

* Takes a fresh `pg_dump --format=custom` of the staging DB via
  password auth.
* Verifies `pg_restore -l` parses the archive's TOC.
* Asserts the staging DB's table count is unchanged.
* Asserts `scripts/restore_postgres.sh` refuses without
  `ALLOW_RESTORE=true`.
* Samples the local/test DB's table count BEFORE and AFTER to
  guarantee the staging operation never touched the `aiagents-test`
  data plane.

The dump file lands under `backups/` (gitignored).

## Known limitations

* **Vault dev mode.** The Stage 25 staging compose still ships the
  `hashicorp/vault:1.17 server -dev` container. The validator's
  `staging` mode rejects this unless
  `ALLOW_VAULT_DEV_MODE_FOR_STAGING=true` is set — `start_staging_runtime.sh`
  enables that escape hatch automatically so the bring-up doesn't
  block on it. A real staging deployment must point `VAULT_ADDR` at
  an external Vault server before production hand-off.
* **Alertmanager null receiver.** Unchanged — neither stack contacts
  a real off-host notifier.
* **Real GitHub / Discord tests.** Sandbox-only by default. The
  Stage 22 / Stage 23 opt-in gates are unchanged.
* **Resource use.** Running both stacks (44 containers) doubles the
  test cluster's memory + CPU footprint. The default `verify_staging
  _runtime.sh --down` path mitigates this; operators that pass
  `--keep-running` should monitor the host.
* **Local/test data plane.** The staging bring-up uses a separate
  Postgres volume + a separate Redis container so it cannot, even
  by accident, corrupt the existing `aiagents-test` data plane. The
  backup verifier samples local/test table counts before + after as
  an explicit regression guard.
* **No production deploy.** Staging bring-up is not production
  bring-up. The platform's `production_executed=true` counter MUST
  stay at `0` for both stacks throughout.
