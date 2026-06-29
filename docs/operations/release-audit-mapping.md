# Release Governance — Audit Mapping (Step 60)

- Model: `infra/release/release-audit-mapping.yaml`
- SDK: `shared/sdk/release_governance/audit.py`

Every release governance operation emits an audit event. The orchestrator write
endpoints additionally record an operator-action audit entry (reusing the Step 52 audit
chain).

## Events
`release_candidate_created`, `release_evidence_collected`, `release_readiness_evaluated`,
`deployment_intent_created`, `deployment_intent_blocked`,
`release_operator_review_requested`, `release_candidate_archived`.

## Required metadata
`actor`, `role`, `reason`, `project_id`, `candidate_id`, `deployment_intent_id`,
`target_environment`, `policy_decision`, and `production_executed` (always `false`).

## Forbidden metadata
`token`, `secret`, `raw prompt`, `chain-of-thought` — stripped by
`shared/sdk/release_governance/redaction.py` before the metadata leaves the SDK.
