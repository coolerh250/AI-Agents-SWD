# Production Readiness Checklist Model (Step 62)

Source: [`infra/readiness/production-readiness-checklist-model.yaml`](../../infra/readiness/production-readiness-checklist-model.yaml).

17 readiness categories (identity, secret_management, security_supply_chain,
runtime_kubernetes, gitops_argocd, multi_project_delivery, operational_metrics,
sandbox_github, release_governance, backup_restore_dr, audit_integrity, approval_governance,
rollback, observability, incident_response, documentation, operator_review). Each maps to an
existing platform evidence source.

## Per-category fields
`required`, `evidence_source`, `status`, `blocking_if_missing`,
`production_ready_claim_allowed` (always **false**).

A missing required category blocks readiness. A non-production PASS is **not** a
production-ready claim; no category may ever produce a production approval.
