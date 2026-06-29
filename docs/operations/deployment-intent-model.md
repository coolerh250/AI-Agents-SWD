# Release Governance — Deployment Intent Model (Step 60)

- Model: `infra/release/deployment-intent-model.yaml`
- SDK: `shared/sdk/release_governance/deployment_intent.py`
- Verifier: `scripts/verify_deployment_intent_model.py` → `DEPLOYMENT_INTENT_MODEL_VERIFY`

A deployment intent records an *intention* against a release candidate. It **never
executes a deployment**.

## Requested actions (allowed)
`validate_only`, `prepare_nonproduction`, `request_operator_review`.

## Forbidden actions (blocked)
`deploy_production`, `sync_production`, `merge_pr`, `push_image`, `create_release`,
`create_tag`.

## Behaviour
- A production target is **blocked** (`production_environment_forbidden`).
- A forbidden / unknown action is **blocked**.
- `validate_only` / `prepare_nonproduction` validate without executing anything.
- `request_operator_review` sets `requires_human_approval` — which is **not** an
  approval granted.
- Every intent result carries `production_executed=false`, `deploy_performed=false`,
  `argocd_sync_performed=false`, `merge_performed=false`, `image_push_performed=false`.
