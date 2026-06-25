# Release Risk Scoring Policy (Step 54.4)

Source: [`infra/security/release-risk-scoring-policy.yaml`](../../infra/security/release-risk-scoring-policy.yaml)

Modeled, **not enforced**. Score range 0–100; severity weights critical=100,
high=40, medium=15, low=5. Blockers: a confirmed secret leak or a critical finding
is a `critical_blocker`; missing SBOM / image digest / threat model, and production
identity/secret-store/runtime not ready are `not_ready`.

Interpretation (all true): the score is **not** an approval; a low score is **not**
production ready; missing required evidence **forces** `not_ready`; the production
gate **remains disabled**. `productionReady: false`, `productionGateEnabled: false`.

## Verify
`python scripts/verify_release_risk_summary_model.py` (also checks the scoring
policy); `tests/test_release_risk_scoring_policy.py`.
