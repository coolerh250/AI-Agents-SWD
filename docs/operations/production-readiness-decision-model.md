# Production Readiness Decision Model (Step 62)

Source: [`infra/readiness/production-readiness-decision-model.yaml`](../../infra/readiness/production-readiness-decision-model.yaml).
SDK: `shared/sdk/production_readiness/decision.py`.

## Statuses
`not_ready`, `blocked_by_missing_evidence`, `blocked_by_policy`,
`blocked_by_production_prerequisites`, `ready_for_operator_review`,
`operator_review_requested`.

## Evaluation order
1. A requested production action or `production_executed != 0` → `blocked_by_policy`.
2. A missing required-evidence marker → `blocked_by_missing_evidence`.
3. Evidence complete but production prerequisites missing → `ready_for_operator_review`
   (the maximum attainable decision this stage).

The decision is NEVER `production_ready` and NEVER a production approval; `production_ready`
/ `production_approved` / `production_action_allowed` are always false.
