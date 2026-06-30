# Production Readiness Gate Policy (Step 62)

Source: [`infra/readiness/production-readiness-gate-policy.yaml`](../../infra/readiness/production-readiness-gate-policy.yaml).

A controlled, **non-production** readiness gate that integrates the completed Step 52–61
evidence into a readiness decision + operator review package. It is NOT a production
deployment: no deploy / sync / merge / push / restore / failover.

## Permanently blocked / false
`productionReady`, `allowProductionDeploy`, `allowProductionSync`, `allowProductionRestore`,
`allowProductionFailover`, `allowAutoPromotion`, `allowGitHubMerge`, `allowImagePush`,
`allowRegistryLogin`, `currentStageAllowsProductionAction`.

## Required guards (true)
`requireHumanApprovalBeforeProduction`, `requireExplicitProductionRolloutPhase`.

Readiness visibility is **not** production ready. The gate never approves production; a
production rollout requires a future explicit phase. Claude Code does not decide production
readiness.
