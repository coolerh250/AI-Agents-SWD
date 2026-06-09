# Restore Drill Runbook (Stage 36)

Operator playbook for running the encrypted restore drill against the
isolated `aiagents_restore_drill_<ts>` database.

> **Test cluster only.** The drill must never target the primary
> `aiagents` database. The shell scripts + `shared/sdk/backup/restore.py`
> refuse any DB name that is not prefixed with
> `aiagents_restore_drill_`.

## Prerequisites

* `docker compose -f infra/docker-compose/docker-compose.yml ps` shows
  the `postgres` service running.
* You are running from the repo root on a host with `openssl`,
  `python3`, `crontab` (for the schedule check), and `pg_dump` reachable
  via the postgres container.
* (Optional) `BACKUP_ENCRYPTION_KEY` set if you want to exercise the
  env-key path; otherwise the drill auto-generates a test-only keyfile
  under `/tmp` (chmod 600, shredded at the end of the drill).

## Steps

```bash
# 1. Run the drill (creates encrypted backup + manifest + restore + verify).
./scripts/run_restore_drill.sh

# 2. Inspect the report.
cat source/dr-reports/dr_report_latest.json | python3 -m json.tool

# 3. (Optional) keep the restore DB for manual inspection.
KEEP_RESTORE_DRILL_DB=true ./scripts/run_restore_drill.sh

# 4. Cleanup leftover restore drill DBs manually:
docker compose -f infra/docker-compose/docker-compose.yml exec -T postgres \
  psql -U postgres -d postgres -c "
    DO $$
    DECLARE r record;
    BEGIN
      FOR r IN SELECT datname FROM pg_database
               WHERE datname LIKE 'aiagents_restore_drill_%' LOOP
        EXECUTE 'DROP DATABASE ' || quote_ident(r.datname);
      END LOOP;
    END $$;
  "
```

## Expected markers

* `BACKUP_POSTGRES_ENCRYPTED: PASS` -- pg_dump + openssl + manifest OK.
* `BACKUP_UPLOAD: SKIPPED s3_upload_not_implemented` -- expected when
  the S3 mode is wired without a real client; or `PASS uri=...` for
  local-filesystem mode.
* `RESTORE_DRILL: PASS` -- the drill restored into the isolated DB,
  verified counts, walked the audit chain, and dropped the isolated DB.
* `BACKUP_DRILL_VERIFY: PASS` -- the top-level wrapper succeeded.

## Failure triage

| Marker | Likely cause | Operator action |
|--------|--------------|-----------------|
| `RESTORE_DRILL: FAIL backup_step_failed` | pg_dump RC != 0 | check `docker compose logs postgres` |
| `RESTORE_DRILL: FAIL checksum_mismatch` | artifact corrupted in transit | re-run the drill |
| `RESTORE_DRILL: FAIL create_database_failed` | restore DB name collision | drop the residual DB then retry |
| `RESTORE_DRILL: FAIL pg_restore_rc=...` | dump produced against newer pg_version | upgrade the postgres image to match |
| `RESTORE_DRILL: FAIL audit_integrity_mismatches=<N>` | chain link discontinuity in the backed-up data | re-run `backfill_audit_integrity.sh` before the next backup |
| `BACKUP_DRILL_VERIFY: FAIL missing_dr_report_latest` | drill exited before writing the report | inspect `/tmp/aiagents-drill-*.log` |

## Carry-forward limitations

* The drill verifies chain *structure* (each record's `prev_record_hash`
  equals the previous record's `record_hash`). For full cryptographic
  re-verification the operator runs `verify_tamper_evident_audit.sh`
  against the live audit-service.
* HMAC key rotation and the audit-service direct-POST integrity gap
  (Step 33) are NOT remediated by the drill; the drill simply re-asserts
  the chain that exists in the dump.
