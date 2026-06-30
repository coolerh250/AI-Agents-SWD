# Backup Target Inventory (Step 61)

Source: [`infra/dr/backup-target-inventory.yaml`](../../infra/dr/backup-target-inventory.yaml).

Declarative inventory of what the platform can back up as governance evidence. Every
target is annotated with classification + handling flags. The inventory itself contains
**no** secret, token, kubeconfig, raw dump, or customer data.

## Per-target fields
`source`, `classification`, `contains_secret`, `contains_customer_data`,
`contains_runtime_state`, `contains_audit_evidence`, `backup_allowed`,
`restore_allowed_nonprod`, `restore_allowed_production`, `retention_class`,
`cleanup_allowed`.

## Invariants
- `restore_allowed_production` is **false** for every target.
- A target flagged `contains_secret` is never `backup_allowed` (secrets are redacted /
  excluded / secret-managed).
- `contains_customer_data` is false for every target.
- kind / ArgoCD cluster runtime state is `backup_allowed: false` (never backed up here).
