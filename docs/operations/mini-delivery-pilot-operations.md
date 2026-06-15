# Mini Delivery Pilot Operations (Stage 48)

Operator-facing reference for the controlled Mini Project Delivery Pilot.

## Service

* `mini-delivery-pilot-agent` (port 8019) consumes `stream.delivery_pilot` and
  reports to `stream.delivery_pilot_events`.
* The orchestrator (port 8000) exposes the operations API and consumes
  `stream.delivery_pilot_events` (workflow stages
  `mini_delivery_pilot_completed` / `mini_delivery_pilot_failed`).

## Feature flags (all default to the safe value)

| Flag | Default | Meaning |
| ---- | ------- | ------- |
| `ENABLE_MINI_DELIVERY_PILOT` | `true` | pilot active |
| `MINI_DELIVERY_PILOT_CONTROLLED_ONLY` | `true` | controlled-only |
| `MINI_DELIVERY_PILOT_TEMPLATE_MODE` | `true` | deterministic template |
| `ENABLE_MINI_DELIVERY_REAL_LLM` | `false` | never call a real LLM |
| `ENABLE_MINI_DELIVERY_GITHUB_WRITE` | `false` | never write GitHub |
| `ENABLE_MINI_DELIVERY_PR_CREATION` | `false` | never create a PR |
| `ENABLE_MINI_DELIVERY_DEPLOY` | `false` | never deploy |
| `ENABLE_MINI_DELIVERY_EXTERNAL_DELIVERY` | `false` | never deliver externally |

## Operations API

| Method | Path | Notes |
| ------ | ---- | ----- |
| POST | `/operations/mini-delivery-pilots/run` | controlled-only write |
| GET | `/operations/mini-delivery-pilots` | list (optional `?project_id=`) |
| GET | `/operations/mini-delivery-pilots/{id}` | one pilot |
| GET | `/operations/mini-delivery-pilots/{id}/steps` | step timeline |
| GET | `/operations/mini-delivery-pilots/{id}/acceptance-evaluations` | + summary |
| GET | `/operations/mini-delivery-pilots/{id}/qa-report` | QA evidence |
| GET | `/operations/mini-delivery-pilots/{id}/safety-report` | safety evidence |
| GET | `/operations/mini-delivery-pilots/{id}/report` | mini delivery report |
| GET | `/operations/mini-delivery-pilots/{id}/artifacts` | artifact refs |
| GET | `/operations/mini-delivery-pilots/{id}/timeline` | pilot + steps |
| GET | `/operations/projects/{id}/mini-delivery-pilots` | per-project list |
| GET | `/operations/projects/{id}/latest-mini-delivery-pilot` | latest pilot |

## /operations/safety fields

`mini_delivery_pilot_enabled`, `mini_delivery_pilot_controlled_only`,
`mini_delivery_real_llm_enabled`, `mini_delivery_github_write_enabled`,
`mini_delivery_pr_creation_enabled`, `mini_delivery_deploy_enabled`,
`mini_delivery_external_delivery_enabled`, `latest_mini_delivery_pilot_status`,
`latest_mini_delivery_pilot_id`, `latest_mini_delivery_acceptance_total`,
`latest_mini_delivery_acceptance_satisfied`,
`latest_mini_delivery_acceptance_failed`,
`latest_mini_delivery_acceptance_pending`, `latest_mini_delivery_qa_status`,
`latest_mini_delivery_safety_status`,
`mini_delivery_pilot_ready_for_delivery_package`.

## Verification

`scripts/verify_mini_project_delivery_pilot.sh` runs Scenarios A–H and emits
`MINI_PROJECT_DELIVERY_PILOT_VERIFY: PASS`. Scenario H reuses
`verify_real_repo_workspace_operator.sh` (which transitively runs the design
review verify + full regression) as the single regression gate. Runtime smokes
193–210 live in `scripts/check_runtime_state.sh`. Audit-chain reads use a
bounded convergence wait (Stage 44/47 eventual-consistency note) with a 60s
client timeout.
