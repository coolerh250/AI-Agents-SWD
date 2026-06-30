# Production Readiness Blocking Rules (Step 62)

Source: [`infra/readiness/production-readiness-blocking-rules.yaml`](../../infra/readiness/production-readiness-blocking-rules.yaml).
SDK: `shared/sdk/production_readiness/blocking_rules.py`.

Each rule has a `severity` and a live `currently_active` flag.

- **hard** — if active, the gate is `blocked_by_policy` (or fails). These are guards
  (production action requested, production_*_allowed, production_executed nonzero, missing
  required evidence) and are currently **inactive** (no production action is requested;
  counts are 0; all required markers PASS).
- **prerequisite** — if active, the gate is capped at `ready_for_operator_review` and can
  never be production_ready. These **are** active this stage (production environment not
  configured; runtime / GitOps non-production only; tenant isolation + external connectors
  not implemented; human approval pending).

A requested production action hard-blocks; `production_executed_true_count != 0` hard-fails.
The tenant strategy note is a future consideration, never an implemented capability.
