# Production Deployment Readiness Gate Runtime (Step 62)

The host-side generator `scripts/generate_production_readiness_gate_report.py` produces a
redacted report at `.runtime/readiness/production-readiness-gate-report.json` (gitignored —
never committed). It collects evidence availability + known limitations, evaluates the
blocking rules and production prerequisites, builds the operator review package, and
produces a readiness decision.

It NEVER deploys, syncs, merges, pushes, restores, or fails over. `production_ready` /
`production_approval` / `production_action_allowed` are always false, and it confirms
`production_executed_true_count == 0` (read from the live `/operations/safety` when
available). The live posture is exposed read-only at `/operations/readiness/*` and
`/operations/safety`. The single controlled write (`POST
/operations/readiness/operator-review-requests`) creates an operator review request only
(auth + CSRF + reason + audit) and is not a production approval.

## Next phase
Step 63A (Stage 65A) adds the non-production [controlled rollout go/no-go review](controlled-production-rollout-pilot-review-policy.md) (`/operations/readiness/controlled-rollout/*`), which consumes this readiness gate result as input and produces a go/conditional_go/no_go recommendation that is never an approval.
