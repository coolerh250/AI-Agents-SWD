# Delivery Package Operations (Stage 49)

Operations API surface for the Delivery Package & Acceptance Gate. All
endpoints are read-only except the single controlled build endpoint and the
(disabled-by-default) operator action endpoints.

## Build (controlled-only write)

```
POST /operations/mini-delivery-pilots/{pilot_id}/delivery-package/build
```

Builds a formal delivery package from a completed mini delivery pilot. Returns
the `DeliveryPackageResult` (package id, gate status/decision, readiness, safety
flags). Never calls an LLM, writes GitHub, opens a PR, deploys, or delivers
externally.

## Package reads

```
GET /operations/delivery-packages
GET /operations/delivery-packages/{package_id}
GET /operations/delivery-packages/{package_id}/sections
GET /operations/delivery-packages/{package_id}/artifacts
GET /operations/delivery-packages/{package_id}/report
GET /operations/delivery-packages/{package_id}/handoff-summaries
GET /operations/delivery-packages/{package_id}/readiness
GET /operations/projects/{project_id}/delivery-packages
GET /operations/projects/{project_id}/latest-delivery-package
```

## Acceptance gate reads

```
GET /operations/delivery-packages/{package_id}/acceptance-gate
GET /operations/delivery-packages/{package_id}/acceptance-checks
GET /operations/delivery-packages/{package_id}/acceptance-checklist
GET /operations/projects/{project_id}/acceptance-gates
```

## Operator review

```
GET  /operations/delivery-packages/{package_id}/operator-review
POST /operations/delivery-packages/{package_id}/operator-review/accept           (disabled)
POST /operations/delivery-packages/{package_id}/operator-review/reject           (disabled)
POST /operations/delivery-packages/{package_id}/operator-review/request-changes  (disabled)
```

Operator action POSTs return `action_disabled` / `policy_blocked` unless
`ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS=true`. They never auto-accept.

## /operations/safety fields

`delivery_package_enabled`, `delivery_package_controlled_only`,
`delivery_package_real_llm_enabled`, `delivery_package_github_write_enabled`,
`delivery_package_pr_creation_enabled`, `delivery_package_deploy_enabled`,
`delivery_package_external_delivery_enabled`,
`delivery_package_auto_accept_enabled`,
`delivery_package_operator_actions_enabled`, `latest_delivery_package_status`,
`latest_delivery_package_id`, `latest_acceptance_gate_status`,
`latest_acceptance_gate_decision`,
`latest_acceptance_gate_blocking_findings_count`,
`latest_delivery_readiness_status`, `latest_human_acceptance_status`,
`latest_delivery_package_sections_ready_count`,
`latest_delivery_package_sections_missing_count`,
`delivery_package_ready_for_admin_console`.

Expected controlled-only posture: all `*_enabled` real-write flags false,
`latest_human_acceptance_status=pending`, `production_executed_true_count=0`.

## Feature flags (orchestrator + agent)

`ENABLE_DELIVERY_PACKAGE` (default true), `DELIVERY_PACKAGE_CONTROLLED_ONLY`
(true), `DELIVERY_PACKAGE_TEMPLATE_MODE` (true),
`ENABLE_DELIVERY_PACKAGE_REAL_LLM` / `_GITHUB_WRITE` / `_PR_CREATION` /
`_DEPLOY` / `_EXTERNAL_DELIVERY` / `_AUTO_ACCEPT` / `_OPERATOR_ACTIONS` (all
default false).

## Ports

delivery-package-agent: `8020` (project-planner 8016, design-review 8017,
workspace-operator 8018, mini-delivery-pilot 8019, orchestrator 8000).
