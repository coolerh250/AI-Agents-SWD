# Controlled Rollout Go / No-Go Criteria (Step 63A)

Source: [`infra/readiness/controlled-rollout-go-no-go-criteria.yaml`](../../infra/readiness/controlled-rollout-go-no-go-criteria.yaml).

16 criteria, each with a `status` (met / missing / insufficient) and a `hard` flag.
Outcomes: `go` / `conditional_go` / `no_go`.

A missing **hard** criterion (production target / credentials / GitOps app / approval
channel / operator owner) forces `no_go`. At this stage those hard gates are missing, so the
expected outcome is `no_go`. No outcome ever authorizes a production action.
