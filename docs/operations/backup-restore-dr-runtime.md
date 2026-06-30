# Backup / Restore / DR Runtime (Step 61)

Host-side generators produce redacted runtime artifacts under `.runtime/backup-dr/`
(gitignored — never committed):

- `scripts/generate_backup_dr_runtime_inventory.py` →
  `.runtime/backup-dr/backup-dr-runtime-inventory.json`
- `scripts/generate_controlled_cleanup_review.py` →
  `.runtime/backup-dr/controlled-cleanup-review.json`
- `scripts/run_nonproduction_restore_validation.py` →
  `.runtime/backup-dr/nonproduction-restore-validation-result.json`

The inventory walks only allowlisted roots, reports metadata (path / size / age /
classification) and never reads file contents. None of the artifacts execute a cleanup or
restore, overwrite active runtime, sync ArgoCD, or mutate the kind cluster. The live
posture is exposed read-only at `/operations/dr/*` and `/operations/safety`.
