# Backup / Restore / DR Verification (Step 61)

Combined: `scripts/verify_backup_restore_dr_operations_baseline.sh` →
`BACKUP_RESTORE_DR_OPERATIONS_BASELINE_VERIFY: PASS | BLOCKED | FAIL`.

It chains the Step 60 combined (Step 52–60 + tenant note), runs the three generators, then
the 12 Step 61 verifiers, the 13 targeted tests, and a live safety-posture assertion.

| Marker | Scope |
|---|---|
| `BACKUP_RESTORE_DR_POLICY_VERIFY` | policy toggles |
| `BACKUP_TARGET_INVENTORY_VERIFY` | target inventory |
| `BACKUP_ARTIFACT_CLASSIFICATION_VERIFY` | artifact classes |
| `CONTROLLED_CLEANUP_REVIEW_VERIFY` | cleanup review model/SDK |
| `RESTORE_PLAN_MODEL_VERIFY` | restore plan model |
| `NONPRODUCTION_RESTORE_VALIDATION_VERIFY` | restore validation |
| `DR_OPERATION_MODEL_VERIFY` | DR operation + readiness |
| `RECOVERY_EVIDENCE_PACKAGE_VERIFY` | recovery evidence |
| `BACKUP_RESTORE_DR_RUNTIME_VERIFY` | runtime artifacts |
| `BACKUP_RESTORE_DR_OPERATIONS_VISIBILITY_VERIFY` | live `/operations/dr/*` |
| `ADMIN_CONSOLE_BACKUP_DR_VERIFY` | Admin Console view |
| `BACKUP_RESTORE_DR_SAFETY_FIELDS_VERIFY` | live `/operations/safety` |
