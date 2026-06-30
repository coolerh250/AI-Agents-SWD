# Non-production Restore Validation Model (Step 61)

Source: [`infra/dr/nonproduction-restore-validation-model.yaml`](../../infra/dr/nonproduction-restore-validation-model.yaml).
SDK: `shared/sdk/backup_restore_dr/restore_validation.py`.
Runner: `scripts/run_nonproduction_restore_validation.py`.

Validation is safe and non-destructive. Validation types: `manifest_integrity_check`,
`schema_validation`, `redaction_validation`, `artifact_freshness_check`, `restore_dry_run`,
`nonproduction_copy_restore`, `post_restore_consistency_check`.

## Invariants
- Never overwrites an active Postgres / Redis.
- Never uses production data; never writes a production namespace.
- Never triggers an ArgoCD sync; by default never mutates the kind cluster.
- A production target is blocked; an arbitrary restore path is rejected.
- Validation failure is reported, never hidden.
