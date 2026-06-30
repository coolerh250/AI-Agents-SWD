# Readiness Evidence Inventory (Step 62)

Source: [`infra/readiness/readiness-evidence-inventory.yaml`](../../infra/readiness/readiness-evidence-inventory.yaml).

Inventory of the Step 52–61 evidence the readiness gate consumes, plus the tenant strategy
note, audit integrity, approval controls, and known limitations.

## Per-item fields
`source`, `freshness` (live / live_or_stale / documentation_only), `availability`,
`redaction`, `production_scope` (always **false**), `nonproduction_only` (true),
`blocking_limitations`.

All `production_scope` is false at this stage; runtime / GitOps evidence is non-production
only. Missing evidence is never reported as clean. The inventory contains no secret.
