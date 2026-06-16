# Off-host Backup Target (Stage 51)

## Mock off-host target

`shared/sdk/backup_dr/offhost_target.py` builds a **mock off-host target** — a
separate local directory (`/tmp/aiagents-offhost-backups`, override with
`BACKUP_DR_OFFHOST_DIR`) that stands in for a remote host. It is gitignored and
never committed.

`shared/sdk/backup_dr/offhost_transfer.py` copies the encrypted artifact to the
target and verifies the **readback checksum** (source SHA-256 == target
SHA-256). The off-host gap is closed when the transfer status is `verified`,
`readback_verified=true`, and `real_cloud_write_performed=false`.

## Readback verification

```bash
./scripts/verify_backup_offhost_target.sh   # BACKUP_OFFHOST_TARGET_VERIFY: PASS
```

## Future real S3 / GCS / Azure integration

When `BACKUP_DR_CLOUD_TARGET_TYPE` is `s3` / `gcs` / `azure`, the target is
recorded as `*_disabled` with `real_cloud_write_enabled=false`. No real cloud
client ships in this stage. A future stage can wire boto3 / GCS / Azure clients
behind the same `BackupOffhostTarget` abstraction without changing the
operations API surface.

## Real cloud disabled by default

- `real_cloud_write_enabled=false` and `real_cloud_write_performed=false`
  everywhere.
- `/operations/safety` exposes `backup_real_cloud_write_enabled` and
  `backup_real_cloud_write_performed` (both false).
- This is a carry-forward limitation: a real off-host cloud backup target is not
  enabled.
