# Production Rollout Preflight Model (Step 62)

Source: [`infra/readiness/production-rollout-preflight-model.yaml`](../../infra/readiness/production-rollout-preflight-model.yaml).
SDK: `shared/sdk/production_readiness/preflight.py`.

Preflight checks (identity / secrets / security / release / rollback / dr / monitoring /
approval / production_cluster / production_gitops / change_window) are **modeled and
evaluated only**.

- `rolloutExecutionEnabled: false`
- `rolloutStatus: not_started`
- `rolloutTriggeredThisStage: false`

This stage never triggers a rollout. No preflight check claims production readiness.
