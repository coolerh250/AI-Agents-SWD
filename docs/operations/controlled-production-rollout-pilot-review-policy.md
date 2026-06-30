# Controlled Production Rollout Pilot Review Policy (Step 63A)

Source: [`infra/readiness/controlled-production-rollout-pilot-review-policy.yaml`](../../infra/readiness/controlled-production-rollout-pilot-review-policy.yaml).

This is the go/no-go **REVIEW**, NOT the Step 63 rollout pilot itself. It collects the Step
62 readiness evidence, assesses the production rollout pilot prerequisites, identifies gaps,
builds an operator decision package, and produces a `go` / `conditional_go` / `no_go`
recommendation. It does NOT deploy, sync, merge, push, restore, or fail over.

## Invariants (all false)
`productionReady`, `allowsProductionAction`, `allowsProductionDeploy`, `allowsProductionSync`,
`allowsProductionRestore`, `allowsProductionFailover`, `operatorReviewIsApproval`,
`goRecommendationIsApproval`, `conditionalGoIsApproval`.

## Required guards (true)
`requiresExplicitOperatorApprovalForPilot`, `requiresSeparatePilotExecutionStage`,
`allowsOperatorReviewRequest`.

A Go / Conditional Go recommendation is **not** an approval and authorizes **no** production
action. A future pilot requires explicit operator approval in a separate stage. Claude Code
does not decide production readiness.
