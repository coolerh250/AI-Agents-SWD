# Runtime configuration baseline (Stage 24)

Stage 24 introduces a single source of truth for the platform's runtime
environment shape. Three artefacts live in this directory:

* `env.schema.example` — the canonical list of env vars the platform
  reads, with placeholder values. This file is for documentation; the
  shell that launches the cluster is expected to supply real values.
* `env.staging.example` — a staging-flavoured copy that pins
  `APP_ENV=staging` and removes the trust-auth tolerance.
* `runtime-config.schema.json` — the JSON Schema fragment
  `scripts/validate_runtime_config.py` reads, including the per-mode
  rule table (`x-mode-rules`).

## Local/test vs staging differences

| Topic                                | local / test (`docker-compose.yml`)               | staging (`docker-compose.staging.yml` + env.staging.example) |
| ------------------------------------ | ------------------------------------------------- | ------------------------------------------------------------ |
| Postgres auth                        | `POSTGRES_HOST_AUTH_METHOD=trust` (no password)   | `POSTGRES_PASSWORD` required; no trust auth                  |
| Vault                                | `server -dev` (in-memory unseal)                  | Real Vault required unless `ALLOW_VAULT_DEV_MODE_FOR_STAGING=true` |
| Alertmanager receivers               | `null-receiver` only                              | `null-receiver` allowed; webhook receivers documented but disabled |
| GitHub real test (Stage 23 endpoint) | sandbox-only by default                           | sandbox-only by default; opt-in path unchanged               |
| Discord real test (Stage 22 worker)  | sandbox-only by default                           | sandbox-only by default; opt-in path unchanged               |
| DB volume                            | `postgres-data` (test data)                       | `postgres-staging-data` (separate volume)                    |
| Service exposure                     | `127.0.0.1:<port>` (local-only)                   | unchanged — staging stays loopback-bound                     |

## Values that MUST NOT be committed

The repository's `.gitignore` already excludes `.env`, `.env.*`, `*.env`,
`secrets/`, `*.secret`, `*.key`, `*.pem`, `*.p12`, and `credentials.json`.
**On top of that**, the following keys must never appear in any file
under version control with a real value — only the literal string
`PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE`:

* `POSTGRES_PASSWORD`
* `VAULT_TOKEN`
* `GITHUB_TOKEN`
* `DISCORD_BOT_TOKEN`
* `ALERTMANAGER_WEBHOOK_URL`

`scripts/validate_runtime_config.py --mode staging` and
`scripts/verify_staging_hardening.sh` both grep for the placeholder
marker on the staging template and on `infra/runtime/env.schema.example`
to guarantee no real secret slipped in.

## Modes

The validator accepts `--mode local`, `--mode staging`, and
`--mode production-check`. See `runtime-config.schema.json
.x-mode-rules` for the canonical per-mode rule table.

## How this interacts with the existing local/test compose

Nothing in `docker-compose.yml` changes. Stage 24 is **additive**: it
adds a sibling staging template and a validator that can run against
either the current loopback cluster (local mode) or a future staging
deployment (staging mode). The local cluster on `10.0.1.31` keeps its
trust-auth + Vault-dev-mode + null-receiver posture and remains
local/test only.
