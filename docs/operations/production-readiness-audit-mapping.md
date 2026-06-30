# Production Readiness Audit Mapping (Step 62)

Source: [`infra/readiness/production-readiness-audit-mapping.yaml`](../../infra/readiness/production-readiness-audit-mapping.yaml).
SDK: `shared/sdk/production_readiness/audit.py`.

## Events
`production_readiness_report_generated`, `production_readiness_evidence_collected`,
`production_readiness_blocking_rules_evaluated`, `production_readiness_decision_created`,
`operator_review_package_created`, `operator_review_requested`, `production_action_blocked`.

## Metadata
Always includes `actor`, `role`, `reason`, `readiness_gate_id`, `decision_status`, and
`production_ready=false` / `production_approved=false` / `production_action_allowed=false` /
`production_executed=false`. Never includes a token, secret, kubeconfig, raw prompt,
chain-of-thought, or raw dump.
