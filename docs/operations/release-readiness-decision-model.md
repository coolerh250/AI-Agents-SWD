# Release Governance — Readiness Decision Model (Step 60)

- Model: `infra/release/release-readiness-decision-model.yaml`
- SDK: `shared/sdk/release_governance/readiness.py`
- Verifier: `scripts/verify_release_readiness_decision.py` → `RELEASE_READINESS_DECISION_VERIFY`

Readiness is a **governance judgement**, not a production approval. `production_ready` is
always false in Step 60.

## Decisions
`not_ready`, `ready_for_operator_review`, `blocked_by_missing_evidence`,
`blocked_by_security`, `blocked_by_policy`, `accepted_nonproduction`.

## Must block when
production target requested · missing security evidence · missing rollback plan ·
missing audit linkage · production approval missing · sandbox PR not reviewed/merged ·
runtime unavailable for target · GitOps unhealthy · policy violation.

## Invariants
- `production_ready` always false.
- Readiness is governance, not production approval.
- A human-review request is **not** a human approval.
