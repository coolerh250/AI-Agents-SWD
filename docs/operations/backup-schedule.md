# Backup Schedule (Stage 36)

Stage 36 ships a **dry-run-by-default** scheduling baseline. The cron
line is rendered and inspected; nothing is installed unless an operator
opts in.

## Install (operator-opt-in)

```bash
INSTALL_BACKUP_SCHEDULE=true ./scripts/install_backup_cron.sh
# marker: BACKUP_SCHEDULE_INSTALLED: PASS
```

The default schedule is `0 2 * * *` (daily 02:00 UTC). Override with
`BACKUP_SCHEDULE_CRON='<cron expression>'`. The installed entry looks
like:

```
0 2 * * * cd /home/itadmin/AI-Agents-SWD && \
  ./scripts/backup_postgres_encrypted.sh \
  >> source/runtime-health/backup_schedule.log 2>&1
```

## Dry-run (default)

```bash
./scripts/install_backup_cron.sh
# prints the proposed cron line and exits with BACKUP_SCHEDULE_DRY_RUN: PASS
```

The dry-run path is what CI / verify scripts run; it confirms the entry
**would** install without actually touching the operator's crontab.

## Uninstall

```bash
./scripts/uninstall_backup_cron.sh
# marker: BACKUP_SCHEDULE_UNINSTALLED: PASS
```

Idempotent. Strips any line referencing
`backup_postgres_encrypted.sh`.

## Schedule log

Encrypted-backup output for the scheduled run lands in
`source/runtime-health/backup_schedule.log`. The directory is committed
but the `.log` files are gitignored. Never write secrets to this log.

## Limitations

* The schedule is a single host crontab. A multi-host production setup
  would move this to `systemd-timer` or an orchestrated scheduler
  (Argo CronWorkflow / K8s CronJob). Stage 36 does NOT ship that.
* The schedule does NOT off-host upload by default. Operators must
  configure `BACKUP_STORAGE_MODE` + credentials (and accept that the
  S3 path is "wired but not implemented" until a future stage).
* Stage 36 does NOT trigger an automatic restore drill after each
  backup. The drill must be invoked explicitly via
  `scripts/run_restore_drill.sh`.

## Carry-forward limitations (from earlier stages)

* HMAC key rotation / key map loader (Step 33).
* audit-service direct POST immediate integrity gap (Step 33).

Both are still open and are NOT remediated by the schedule.
