# Release Risk Summary Model (Step 54.4)

Source: [`infra/security/release-risk-summary-model.yaml`](../../infra/security/release-risk-summary-model.yaml)

Defines what a release risk summary aggregates (delivery package, security asset
inventory, secret/SAST/dependency scan summaries, SBOM, image policy, Dockerfile
security, threat model status, QA, human acceptance, secret/identity/runtime/backup/
rollback readiness, production blockers, approval requirements).

**A summary is NOT an approval.** Status enum: `not_ready`,
`ready_for_non_production_review`, `ready_for_operator_review`, `blocked`.
`production_ready` / `production_approved` are **forbidden statuses**. The model
produces neither a production nor a deployment approval; human approval is still
required. `productionReady: false`, `productionGateIntegrated: false`.

## Verify
`python scripts/verify_release_risk_summary_model.py` →
`RELEASE_RISK_SUMMARY_MODEL_VERIFY: PASS`. API:
`GET /operations/security/release-risk/model`.
