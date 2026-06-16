# Encrypted Backup Runbook (Stage 51, test baseline)

## Key source

- Test-only key file at `.runtime/backup-test-key` (chmod 600), created by
  `scripts/setup_backup_dr_test_key.sh`. The path is **gitignored**.
- Alternatives recognised as metadata only: `mock_vault` (`BACKUP_DR_MOCK_VAULT_REF`)
  and `env_reference` (`BACKUP_DR_ENCRYPTION_ENV_REF`).
- A real production secret store is **not** integrated (carry-forward limitation).

## No raw key storage

The raw key value is **never** written to the database, the manifest, the
readiness report, the audit log, or the repo. Only a `key_id` label
(`sha256(key)[:12]`) is recorded. The key only enters `openssl`'s address space
via `-pass env:...`.

## Backup command

```bash
./scripts/run_encrypted_backup.sh          # test environment only
```

Steps: `pg_dump -Fc` (via the postgres container) → `.runtime/backup-dr/<key>.dump`
→ `openssl enc -aes-256-cbc -pbkdf2 -iter 200000` → `<key>.enc`. Refuses
`environment=production`.

## Manifest

`shared/sdk/backup_dr/manifest_builder.py` builds a secret-free manifest:
`backup_key`, `source_database`, `schema_migration_count`, `table_count`,
`row_count_summary`, `artifact_checksum_sha256`,
`encrypted_artifact_checksum_sha256`, `encryption_algorithm`,
`encryption_key_id`, `production_executed=false`. `manifest_contains_secret()`
asserts no password/token/private-key leaks.

## Checksum

SHA-256 over both plain and encrypted artifacts (reuses
`shared/sdk/backup/checksum.py`).

## Encryption verification

```bash
./scripts/verify_backup_encryption.sh   # BACKUP_ENCRYPTION_VERIFY: PASS
```

## Restore preparation

Decrypt with `openssl enc -d ... -pass env:...`, then `pg_restore` into an
**isolated** drill database — see `restore-drill-runbook.md`.
