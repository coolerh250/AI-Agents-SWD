# Controlled Rollout Pilot Scope Model (Step 63A)

Source: [`infra/readiness/controlled-rollout-pilot-scope-model.yaml`](../../infra/readiness/controlled-rollout-pilot-scope-model.yaml).

Defines the strict scope a future pilot would be limited to: single service, single
environment, single operator, manual approval, manual rollback, no auto-promotion, no
external customer traffic unless explicitly approved, no uncontrolled data migration. The
blast radius (single non-production service reference) and rollback trigger (manual
operator-initiated) are describable. If scope cannot be bounded, the recommendation is
`no_go`. This stage only models the scope; it never executes a pilot.
