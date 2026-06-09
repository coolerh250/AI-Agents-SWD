# Backup / Restore / Disaster Recovery (Stage 36)

This runbook describes the Stage 36 production-readiness baseline for
PostgreSQL backup, encrypted off-host storage, restore drill, integrity
verification, RTO / RPO measurement, scheduled backup, and the disaster
recovery operator playbook.

> **Production gate:** Stage 36 is **NOT** a production deploy. The
> tooling described here brings the *capability* up to production
> readiness; the platform itself is still operated only against
> 10.0.1.31 / aiagents-test. The operations endpoints + safety fields
> surface the current gaps so an operator can see, at a glance, what is
> still missing before going live.

## Architecture

```
docker compose / postgres  ->  scripts/backup_postgres_encrypted.sh
                                     |
                                     +-->  ./backups/aiagents-<ts>.dump.enc
                                     +-->  ./backups/backup_manifest_<id>.json
                                     |
                                     +-->  (optional) off-host upload
                                              local-filesystem   (real)
                                              s3-compatible      (skipped — wired, not implemented)
                                              disabled
                                     |
                                     +-->  scripts/run_restore_drill.sh
                                              CREATE DATABASE aiagents_restore_drill_<ts>
                                              decrypt -> pg_restore -> verify
                                              source/dr-reports/dr_report_<ts>.json
                                              source/dr-reports/dr_report_latest.json
                                              (optional KEEP_RESTORE_DRILL_DB=true)
                                              else DROP DATABASE
```

## Encrypted backup

`scripts/backup_postgres_encrypted.sh` produces a `pg_dump --format=custom`
archive and pipes it into `openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000`.
The key value is passed to openssl via `-pass env:BACKUP_ENCRYPTION_KEY`
so it never appears on stdout, stderr, or the command line.

Key source resolution (no key value is ever logged):

| `BACKUP_ENCRYPTION_KEY` env | `BACKUP_KEY_SOURCE` | Result                | Production-ready |
|-----------------------------|---------------------|-----------------------|------------------|
| present                     | (any / unset)       | `env`                 | yes              |
| absent                      | `test-only-generated` | ephemeral /tmp keyfile (chmod 600) | no       |
| absent                      | unset / other       | `missing` -- backup fails (production-check) | no       |

The script writes a manifest beside the artifact:

```json
{
  "backup_id": "bkp-<ts>-<rand>",
  "created_at": "2026-06-09T...",
  "environment": "local|test|staging",
  "source_database": "aiagents",
  "source_host": "postgres",
  "pg_version": "16.x",
  "backup_format": "pg_dump-custom",
  "backup_file": "backups/aiagents-<ts>.dump.enc",
  "backup_size_bytes": 12345,
  "checksum_sha256": "...",
  "encrypted": true,
  "encryption_mode": "openssl-aes-256-cbc",
  "encryption_key_id": "<sha256(key)[:8]>",
  "compression": "pg_dump-custom-zlib",
  "off_host_uploaded": false,
  "off_host_uri": null,
  "schema_version": "1.0",
  "included_tables": ["audit_logs", "audit_integrity_records", ...],
  "row_count_summary": {"audit_logs": 226572, ...},
  "audit_chain_latest_hash": "...",
  "created_by": "scripts/backup_postgres_encrypted.sh",
  "production_executed": false
}
```

## Checksum

`shared/sdk/backup/checksum.py::compute_sha256` streams the artifact in
1 MiB chunks and returns a lower-case hex digest. `verify_sha256` re-runs
the digest and compares against the manifest. The drill walks both sides
before pg_restore.

## Off-host storage

`scripts/upload_backup_artifact.sh` + `shared/sdk/backup/storage.py`
implement a pluggable interface:

* `local-filesystem` (default) -- copies the artifact under
  `BACKUP_STORAGE_BUCKET/<prefix>/<filename>`. **Real upload.**
* `s3-compatible-placeholder` -- the interface is wired but Stage 36
  does **NOT** ship a real S3 client. With credentials present, the
  script emits `BACKUP_UPLOAD: SKIPPED s3_upload_not_implemented` so an
  operator cannot mistake "wired" for "uploaded". Without credentials
  the script emits `BACKUP_UPLOAD: SKIPPED credential_missing`.
* `disabled` -- explicit opt-out.

The interface never returns a credential value.

## Restore drill

`scripts/run_restore_drill.sh` is the canonical drill:

1. Create encrypted backup + manifest.
2. Recompute checksum and compare against the manifest.
3. Optional off-host upload (skipped without credentials).
4. `CREATE DATABASE aiagents_restore_drill_<ts>` -- the name is
   enforced by `shared/sdk/backup/restore.py::isolated_restore_db_name`.
   The drill refuses to target `aiagents`, `postgres`, `template0`,
   or `template1`.
5. Decrypt the artifact inside the postgres container (key piped via
   `-e BACKUP_ENCRYPTION_KEY=...`).
6. `pg_restore --no-owner --clean --if-exists --exit-on-error` into the
   isolated DB.
7. Row counts for `audit_logs`, `audit_integrity_records`,
   `workflow_states`, `deployment_records`,
   `notification_deliveries`, `llm_interactions`, `llm_budget_events`.
8. Structural audit integrity verify on the isolated DB (walks the
   `audit_integrity_records` chain and counts prev-hash discontinuities).
9. `DROP DATABASE aiagents_restore_drill_<ts>` unless
   `KEEP_RESTORE_DRILL_DB=true`.
10. Write `source/dr-reports/dr_report_<ts>.json` + `dr_report_latest.json`.
11. Marker `RESTORE_DRILL: PASS` or `FAIL`.

## Isolated restore DB rule

* Refuses any DB name that is not prefixed with
  `aiagents_restore_drill_`.
* Refuses to drop a DB that is not prefixed with
  `aiagents_restore_drill_`.
* The drill NEVER restores into the primary `aiagents` DB.

## RTO / RPO measurement

`scripts/measure_backup_rto_rpo.sh` reads the latest DR report +
manifest and prints:

```
RTO_RPO_SUMMARY_BEGIN
backup_duration_seconds=...
restore_duration_seconds=...
total_drill_duration_seconds=...
estimated_rto_seconds=...
estimated_rpo_seconds=...
rpo_status=manual_only
audit_integrity_status=passed
latest_dr_report=source/dr-reports/dr_report_<ts>.json
latest_manifest=backups/backup_manifest_<id>.json
RTO_RPO_SUMMARY_END
```

* **RTO** = `total_drill_duration_seconds` from the latest DR report.
* **RPO** = current-time minus the latest backup's `created_at`. If no
  scheduled backup is configured, `rpo_status=manual_only`.

## Scheduled backup baseline

`scripts/install_backup_cron.sh` is **dry-run by default**:

```
0 2 * * * cd <repo> && ./scripts/backup_postgres_encrypted.sh \
    >> source/runtime-health/backup_schedule.log 2>&1
```

Setting `INSTALL_BACKUP_SCHEDULE=true` installs the entry; otherwise the
script prints the proposed cron line and exits with
`BACKUP_SCHEDULE_DRY_RUN: PASS`. `scripts/uninstall_backup_cron.sh`
removes any matching entry. Stage 36 does **NOT** auto-install the
schedule.

## Migration down-script inventory

`scripts/check_migration_down_scripts.sh` scans `migrations/*.sql` and
reports which `*_down.sql` files are missing. Stage 36 does NOT require
every migration to have a down script; the report exists so an operator
can triage rollback risk. Markers:

* `MIGRATION_DOWN_SCRIPT_INVENTORY: PASS` -- every migration has a down.
* `MIGRATION_DOWN_SCRIPT_INVENTORY: PASS_WITH_GAPS gaps=<N>` -- some are
  missing; the gap list is printed.

## Production readiness

`scripts/verify_backup_production_readiness.sh` aggregates the six
pillars (encryption, off-host, schedule, DR report, migration down,
runbook) and emits:

* `BACKUP_PRODUCTION_READINESS: PASS` -- no gaps.
* `BACKUP_PRODUCTION_READINESS: PASS_WITH_GAPS gaps=<csv>` -- one or
  more pillars are not production-grade. Default test-cluster state is
  PASS_WITH_GAPS because off-host S3 is not implemented + the cron is
  dry-run-only.

## Audit decision types

Stage 36 reserves the following `decision_type` values in `audit_logs`:

* `backup_created`
* `backup_encrypted`
* `backup_uploaded`
* `backup_upload_skipped`
* `restore_drill_started`
* `restore_drill_passed`
* `restore_drill_failed`
* `backup_integrity_verified`
* `migration_down_inventory_completed`

`artifact_refs` may include `backup_id`, `manifest_path`,
`checksum_sha256`, `encrypted`, `off_host_uploaded`, `restore_drill_id`,
`rto_seconds`, `rpo_seconds`, and `production_executed=false`. The
records NEVER carry encryption-key value, storage credential value, or
database password.

## Notification events

The notification-worker reserves these event types:

* `backup.created`
* `backup.upload_skipped`
* `restore_drill.passed`
* `restore_drill.failed`
* `backup.integrity_verified`

All five are **default-blocked** by Stage 33's real-Discord delivery
policy (`backup.*` + `restore_drill.*` in the denylist). An operator
who wants any of them externalised must add the specific event_type to
the allowlist *and* the originating publisher must include the
`metadata.real_delivery=true` marker.

## Metrics

* `backup_created_total{environment, storage_mode, encrypted}`
* `backup_encrypted_total{mode}`
* `backup_upload_skipped_total{mode, reason}`
* `backup_upload_success_total{mode}`
* `restore_drill_runs_total{status}`
* `restore_drill_failed_total{reason}`
* `backup_duration_seconds` (Histogram)
* `restore_duration_seconds` (Histogram)
* `backup_artifact_size_bytes` (Histogram)
* `backup_rto_seconds` (Histogram)
* `backup_rpo_seconds` (Histogram)

Spans:

* `backup.create`, `backup.encrypt`, `backup.checksum`, `backup.upload`,
  `backup.download`, `restore.drill_start`, `restore.restore_db`,
  `restore.verify_counts`, `restore.audit_integrity_verify`,
  `restore.cleanup`.

## Operations endpoints

* `GET /operations/backup/status`
* `GET /operations/backup/reports`
* `GET /operations/backup/reports/latest`

Plus Stage 36 safety fields under `/operations/safety`:
`backup_encryption_enabled`, `backup_encryption_production_ready`,
`backup_off_host_enabled`, `backup_storage_mode`,
`latest_restore_drill_status`, `backup_production_ready`,
`backup_gaps`, `migration_down_scripts_complete`, `dr_runbook_present`.

`/operations/summary` carries a compact `backup_summary` block with
`latest_backup_at`, `latest_backup_id`, `latest_restore_drill_status`,
`rto_seconds`, `rpo_seconds`, `off_host_uploaded`, `encryption_enabled`,
`encryption_production_ready`, `storage_mode`, `production_executed`.

## Cleanup procedure

```bash
# Remove the most recent generated artifacts (gitignored anyway).
rm -f backups/aiagents-*.dump backups/aiagents-*.dump.enc \
       backups/backup_manifest_bkp-*.json
# Remove leftover restore drill DBs (paranoid -- the drill cleans up itself).
docker compose -f infra/docker-compose/docker-compose.yml exec -T postgres \
  psql -U postgres -d postgres -c "
    DO $$
    DECLARE r record;
    BEGIN
      FOR r IN SELECT datname FROM pg_database WHERE datname LIKE 'aiagents_restore_drill_%' LOOP
        EXECUTE 'DROP DATABASE ' || quote_ident(r.datname);
      END LOOP;
    END $$;
  "
```

## Disaster recovery operator steps

1. Confirm the latest backup manifest + DR report are recent:
   `GET /operations/backup/status` (or read
   `source/dr-reports/dr_report_latest.json` directly).
2. Pick the artifact to restore from (`latest_backup_manifest.backup_file`).
3. Run `scripts/run_restore_drill.sh` against an isolated DB first to
   confirm the restore path is healthy.
4. To actually restore over the primary DB:
   * Stop the orchestrator + agent services (so they do not write
     during restore).
   * `ALLOW_RESTORE=true scripts/restore_postgres.sh <decrypted_path>`
     (the Stage 24 restore guard) -- this is the **only** path
     authorised to mutate the primary `aiagents` catalog and it still
     refuses to run against `APP_ENV=production`.
   * Re-run `verify_tamper_evident_audit.sh` after restore so the
     audit chain is re-verified end-to-end.
5. Bring services back online.

## Carry-forward limitations (from earlier stages)

* **HMAC key rotation / key map loader** (Step 33). Stage 36 does NOT
  implement key map / rotation. Operators must keep the active key
  stable and run `backfill_audit_integrity.sh` after any key change.
* **audit-service direct POST integrity gap** (Step 33). The
  audit-service's direct `POST /audit/events` writer bypasses the
  audit-worker, so integrity records for that row appear only after
  the next `backfill_audit_integrity.sh` run.

Both are explicitly NOT remediated in Stage 36 and remain on the
production-blocker list.
