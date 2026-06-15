# Operator Acceptance Review (Stage 49)

## Pending human review model

Every delivery package build creates an `operator_acceptance_reviews` row with
`review_status = pending`. The automated acceptance gate can only resolve to
`ready_for_operator_review` / `controlled_only_complete` — it **never**
auto-marks human acceptance. `delivery_packages.human_acceptance_status` stays
`pending` until a real human acts (in a future stage).

## Accept / reject / request-changes endpoints (disabled by default)

The operations API scaffolds the operator action endpoints:

- `POST /operations/delivery-packages/{id}/operator-review/accept`
- `POST /operations/delivery-packages/{id}/operator-review/reject`
- `POST /operations/delivery-packages/{id}/operator-review/request-changes`

They are **disabled by default**
(`ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS=false`). When disabled they return:

```json
{"status": "action_disabled", "policy": "policy_blocked",
 "human_acceptance_status": "pending", "production_executed": false}
```

They do **not** mutate the package or the review row. Scaffolded ≠ implemented:
these endpoints are not a completed Admin Console v1 operator-action flow.

## Future Admin Console v1 operator action flow

A later stage (Step 50, Admin Console v1) will enable real operator actions:

1. Operator authenticates and is authorised for the project.
2. Operator reviews the acceptance checklist + handoff summaries.
3. Operator accepts / rejects / requests changes; the action is recorded on the
   review row and the package `human_acceptance_status` is updated.
4. The action is audited and (optionally) notified — still default-denied for
   real external channels.

## Policy / approval / audit requirements before enabling actions

Before `ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS=true` is acceptable:

- An approval policy gates who may accept on behalf of which project.
- Every operator action is written to the tamper-evident audit chain.
- Acceptance does **not** trigger production deploy / PR / external delivery by
  itself; those remain separately gated and default-off.
- `production_executed=true` count must still remain 0 unless a separate,
  explicitly-approved production stage is reached.
