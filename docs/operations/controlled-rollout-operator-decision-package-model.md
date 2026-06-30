# Controlled Rollout Operator Decision Package Model (Step 63A)

Source: [`infra/readiness/controlled-rollout-operator-decision-package-model.yaml`](../../infra/readiness/controlled-rollout-operator-decision-package-model.yaml).
SDK: `shared/sdk/controlled_rollout/decision_package.py`.

A redacted package assembled for a human operator: summary, readiness gate result, go/no-go
criteria, production target / credential / GitOps / approval-channel / rollback-DR
assessments, pilot scope, risk register, missing items, required operator decisions, and the
recommendation.

## Invariants
- The recommendation it carries is **not** an approval (`recommendationIsApproval: false`).
- `production_ready` / `production_approval` / `production_action_allowed` always false.
- No secret, token, kubeconfig, chain-of-thought, or raw dump (forbidden keys redacted).
