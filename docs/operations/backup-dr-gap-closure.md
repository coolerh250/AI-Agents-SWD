# Backup / DR Gap Closure (Stage 51 / Step 49)

## Purpose

Close the four long-standing Backup / DR documented gaps with a **verifiable,
auditable, recoverable, reportable** readiness baseline that extends the Stage
36 backup/restore design (`shared/sdk/backup`). This advances backup readiness
from `PASS_WITH_GAPS` to `PASS_WITH_NON_PRODUCTION_LIMITATIONS`.

This is **NOT** production backup, **NOT** real cloud backup, **NOT** real
production restore, and does **NOT** enable a real production schedule.

## Closed gaps

| Gap                     | Closure (test baseline)                                              |
| ----------------------- | ------------------------------------------------------------------- |
| `encryption_no_key`     | test-only key file (chmod 600, gitignored) + manifest `key_id` label |
| `storage_not_off_host`  | encrypted artifact copied to a mock off-host target + readback verified |
| `schedule_dry_run_only` | cron / systemd / k8s schedule specs generated + dry-run validated   |
| `migration_down_gaps`   | every migration classified in the rollback catalog (no `unknown`)   |

`migration_down_gap_closed` does **not** require every migration to be
reversible — it requires every migration to be classified
(reversible / forward_only / manual_rollback_required) with rollback notes for
non-reversible ones, and zero `unknown`.

## Remaining non-production limitations (carry-forward)

- real production secret store not integrated
- real off-host cloud target (S3 / GCS / Azure) not enabled
- production schedule not enabled (cron / systemd / Kubernetes CronJob)
- production restore not executed
- Kubernetes CronJob not applied

## Safety constraints

- No production backup / restore. No real cloud bucket write. No real schedule.
- No raw key / secret / token persisted to DB, manifest, report, or repo.
- `production_executed` stays false; `production_executed_true_count` stays 0.
- `backup_dr.*` / `backup.*` / `restore.*` / `dr.*` notifications are
  default-denied for real external delivery.

## Verification commands

```bash
./scripts/setup_backup_dr_test_key.sh
./scripts/run_encrypted_backup.sh
./scripts/verify_backup_encryption.sh
./scripts/verify_backup_offhost_target.sh
./scripts/verify_backup_restore_drill.sh
./scripts/verify_backup_schedule_dry_run.sh
./scripts/verify_backup_retention_policy.sh
./scripts/verify_migration_rollback_catalog.sh
./scripts/verify_backup_dr_gap_closure.sh      # orchestrates all of the above
./scripts/verify_backup_production_readiness.sh # -> PASS_WITH_NON_PRODUCTION_LIMITATIONS
```

Operations (read-only): `GET /operations/backup-dr/readiness/latest`,
`/report/latest`, `/migration-rollback-catalog`, `/operations/safety`.

## Production readiness caveat

Closing these gaps establishes a controlled test baseline only. Claude Code does
NOT declare production readiness — production readiness is an operator decision
that additionally requires the real production substrate (secret store, cloud
target, schedule, restore rehearsal) listed under non-production limitations.
