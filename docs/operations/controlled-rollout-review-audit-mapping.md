# Controlled Rollout Review Audit Mapping (Step 63A)

Source: [`infra/readiness/controlled-rollout-review-audit-mapping.yaml`](../../infra/readiness/controlled-rollout-review-audit-mapping.yaml).
SDK: `shared/sdk/controlled_rollout/audit.py`.

## Events
`controlled_rollout_review_generated`, `controlled_rollout_criteria_evaluated`,
`controlled_rollout_target_assessed`, `controlled_rollout_credentials_assessed`,
`controlled_rollout_gitops_assessed`, `controlled_rollout_approval_channel_assessed`,
`controlled_rollout_recommendation_created`, `controlled_rollout_operator_review_requested`,
`production_rollout_blocked`.

## Metadata
Always includes `actor`, `role`, `reason`, `review_id`, `recommendation`, and
`production_ready=false` / `production_approved=false` / `production_action_allowed=false` /
`production_executed=false`. Never includes a token, secret, kubeconfig, raw prompt,
chain-of-thought, or raw dump.
