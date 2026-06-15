# Workspace Operator Operations (Stage 47)

Operator-facing reference for the controlled Real Repo Workspace Operator.

## Service

* `workspace-operator-agent` (port 8018) consumes
  `stream.workspace_execution` and reports to `stream.workspace_events`.
* The orchestrator (port 8000) exposes the operations API and, after a
  non-blocked design review, publishes `project.workspace_execution_requested`
  when `ENABLE_WORKSPACE_OPERATOR=true` and
  `WORKSPACE_OPERATOR_CONTROLLED_ONLY=true`.

## Feature flags (all default to the safe value)

| Flag | Default | Meaning |
| ---- | ------- | ------- |
| `ENABLE_WORKSPACE_OPERATOR` | `true` | operator active |
| `WORKSPACE_OPERATOR_CONTROLLED_ONLY` | `true` | controlled workspace only |
| `WORKSPACE_OPERATOR_TEMPLATE_MODE` | `true` | deterministic templates |
| `ENABLE_WORKSPACE_OPERATOR_REAL_LLM` | `false` | never call a real LLM |
| `ENABLE_WORKSPACE_OPERATOR_GITHUB_WRITE` | `false` | never write GitHub / PR |
| `ENABLE_WORKSPACE_OPERATOR_REPO_WRITE` | `false` | never write the repo root |
| `ENABLE_WORKSPACE_OPERATOR_DEPLOY` | `false` | never deploy |
| `ENABLE_WORKSPACE_OPERATOR_WORK_ITEM_DISPATCH` | `false` | never dispatch work items |
| `WORKSPACE_OPERATOR_ALLOWED_ROOTS` | `/tmp/aiagents-workspaces` | allowlisted roots |

## Operations API

| Method | Path | Notes |
| ------ | ---- | ----- |
| POST | `/operations/projects/{id}/workspace/execute` | controlled-only write |
| GET | `/operations/workspaces` | list (optional `?project_id=`) |
| GET | `/operations/workspaces/{id}` | one workspace |
| GET | `/operations/workspaces/{id}/files` | file metadata |
| GET | `/operations/workspaces/{id}/operations` | step log |
| GET | `/operations/workspaces/{id}/test-runs` | pytest/ruff/compileall |
| GET | `/operations/workspaces/{id}/diff-summary` | diff counts |
| GET | `/operations/workspaces/{id}/artifacts` | artifact refs |
| GET | `/operations/workspaces/{id}/report` | full report |
| GET | `/operations/projects/{id}/work-item-execution-links` | links |
| GET | `/operations/projects/{id}/workspace-summary` | latest summary |

## /operations/safety fields

`workspace_operator_enabled`, `workspace_operator_controlled_only`,
`workspace_operator_real_llm_enabled`, `workspace_operator_github_write_enabled`,
`workspace_operator_repo_write_enabled`, `workspace_operator_deploy_enabled`,
`latest_workspace_execution_status`, `latest_workspace_id`,
`latest_workspace_tests_status`, `latest_workspace_static_check_status`,
`latest_workspace_generated_files_count`, `latest_workspace_safety_status`,
`workspace_generation_pilot_ready`.

## Verification

`scripts/verify_real_repo_workspace_operator.sh` runs Scenarios A–H and emits
`REAL_REPO_WORKSPACE_OPERATOR_VERIFY: PASS`. Runtime smokes 178–192 live in
`scripts/check_runtime_state.sh`. Both wait for audit/notification convergence
before reading the audit chain (Stage 44 eventual-consistency note).
