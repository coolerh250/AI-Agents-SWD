# Backup Schedule & Retention (Stage 51, dry-run only)

## Schedule spec

`shared/sdk/backup_dr/schedule_builder.py` generates schedule specs:

- `build_cron_spec()` — cron expression (default `0 2 * * *`).
- `build_systemd_timer_spec()` — `OnCalendar` timer spec.
- `build_kubernetes_cronjob_spec()` + `render_kubernetes_cronjob_yaml()` — a
  Kubernetes CronJob YAML with `suspend: true` (never applied to a cluster).

## Dry-run validation

The command preview is validated (must reference a controlled backup script and
must not contain a production marker) and the cron expression is shape-checked.
On success `dry_run_validated=true`.

```bash
./scripts/verify_backup_schedule_dry_run.sh   # BACKUP_SCHEDULE_DRY_RUN_VERIFY: PASS
```

## Production schedule disabled

`enabled=false` and `production_schedule_enabled=false` on every spec. No real
cron / systemd timer / Kubernetes CronJob is installed or applied. The schedule
gap is closed when a spec is dry-run validated **and** the production schedule is
disabled. (Carry-forward limitation: production schedule not enabled.)

## Retention policy

`shared/sdk/backup_dr/retention_policy.py` builds a retention policy
(`keep_last` / `keep_daily` / `keep_weekly` / `keep_monthly`) with
`delete_enabled=false`, `dry_run_only=true`.

## Dry-run cleanup (no deletion)

`compute_retention_dry_run()` reports which artifacts a future enabled run
*would* delete (`candidate_delete_count`) but performs no deletion
(`actual_delete_count=0`, `delete_enabled=false`).

```bash
./scripts/verify_backup_retention_policy.sh   # BACKUP_RETENTION_POLICY_VERIFY: PASS
```
