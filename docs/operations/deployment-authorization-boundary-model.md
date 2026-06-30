# Deployment Authorization Boundary Model (Step 62)

Source: [`infra/readiness/deployment-authorization-boundary-model.yaml`](../../infra/readiness/deployment-authorization-boundary-model.yaml).
SDK: `shared/sdk/production_readiness/authorization.py`.

## May authorize
- readiness review package
- operator review request
- production rollout planning

## May NOT authorize
production deploy, production sync, production restore, production failover, PR merge, image
push, release creation, tag creation, registry login, auto promotion.

An operator review request is **not** a production approval
(`operatorReviewRequestIsApproval: false`); production rollout planning is **not** rollout
execution.
