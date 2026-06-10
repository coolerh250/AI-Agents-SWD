# Validation Pilot Run (Step "Validation Pilot Run")

This document describes the controlled pilot procedure used to verify
that the platform is fit for an external validation environment. It
is NOT a production-readiness statement. The pilot uses the existing
gateway intake / sandbox paths and the deterministic agent pipeline
plus the existing `verify_*.sh` regression suite for deeper
capabilities.

> **Test cluster only.** The pilot must not target production
> resources. No real production GitHub write, no PR merge, no branch
> protection change, no production deploy, no real LLM call by
> default. Real Discord / GitHub / LLM paths require explicit
> operator opt-in env, otherwise the corresponding pilot path is
> reported `SKIPPED: PASS`.

## What the pilot proves

* Tasks can be **assigned via the gateway intake path** (sandbox
  `/intake/mock` on `communication-gateway`, optionally real Discord
  when env is present).
* The **agent pipeline completes** for `delivery_task` scenarios:
  intake-agent -> requirement-agent -> development-agent -> qa-agent ->
  devops-agent, plus the github-automation service producing a
  **dry-run PR** (no real GitHub write).
* The **deterministic execution-mode classifier**
  (`shared/sdk/task_execution::classify_execution_mode`) routes
  scenarios to `simple_task`, `delivery_task`, or
  `needs_clarification`.
* **Operations**, **audit**, and **notification** surfaces are
  populated for every task. `/operations/workflows/{task_id}` returns
  the workflow with deployment record + audit refs;
  `/audit/events?task_id=...` returns the per-task audit timeline;
  `/deliveries?task_id=...` returns the per-task notification
  deliveries.
* **Production safety counters** stay at zero:
  `deployment_records production_executed=true` = 0,
  `workflow_states execution_result->>'production_executed'='true'`
  = 0.
* Deeper capabilities (controlled code generation, QA findings +
  auto-fix, human approval policy, LLM plan-only) are exercised by
  the existing `verify_*.sh` regression scripts that the pilot
  re-runs in full.

## Scenario matrix

| Scenario | Trigger | Verified path |
|----------|---------|----------------|
| A: Simple Task | description without dev keywords + non-`dev.*` request_type | `simple_task`, no workspace, agent pipeline short-circuits |
| B: Docs Delivery | description mentioning "docs / API / endpoint" + `dev.request` request_type | `delivery_task`, full pipeline, GitHub dry-run PR |
| C: API Demo | description mentioning "API / endpoint / test" + `dev.request` request_type | `delivery_task`, full pipeline, GitHub dry-run PR |
| D: Clarification | description containing `TBD` / `?` / short text | `needs_clarification`, work item stays at dispatched, no PR |
| E: Policy Block | description mentioning `.env` / `infra/` | inline mock workflow completes safely; the dedicated `verify_controlled_code_generation.sh` script exercises the policy block path during regression |
| F: Human Approval | description requesting per-path delegated approval | inline mock workflow completes safely; `verify_flexible_human_approval_policy.sh` exercises per-action / per-feature / delegated lifecycles during regression |
| G: LLM Plan-Only | description requesting a development plan only | `plan_only=True`; real LLM SKIPPED when env absent (`REAL_LLM_PLAN_ONLY_SKIPPED: PASS`) |
| H: QA Auto-Fix | description requesting an API + matching pytest | inline mock workflow completes safely; `verify_qa_auto_fix_loop.sh` exercises QA findings + auto-fix during regression |

The pilot intentionally drives the **inline mock workflow** for breadth
(8 scenarios in seconds) and relies on the **regression verify
scripts** for depth on capabilities that require their own multi-step
setup (controlled code workspace, QA findings, human approval policy,
LLM plan-only with redaction).

## Pilot mode resolution

The pilot driver consults `scripts/check_real_integration_inputs.sh`
and `scripts/check_llm_runtime_inputs.sh` to pick its mode:

* `DISCORD_REAL_EXECUTED` -- `DISCORD_BOT_TOKEN`,
  `DISCORD_TEST_CHANNEL_ID`, `DISCORD_TEST_GUILD_ID`, and
  `RUN_REAL_DISCORD_TEST=true` are all set; messages may target
  `DISCORD_TEST_CHANNEL_ID`. Otherwise `DISCORD_SKIPPED`.
* `GITHUB_REAL_EXECUTED` -- `GITHUB_TOKEN`, `GITHUB_TEST_REPO`, and
  `RUN_REAL_GITHUB_TEST=true` are all set; only `GITHUB_TEST_REPO`
  is touched. Otherwise `GITHUB_SKIPPED`.
* `LLM_REAL_PLAN_ONLY_EXECUTED` -- the provider key + `RUN_REAL_LLM_TEST=true`
  + `ENABLE_REAL_LLM_NETWORK_CALL=true` are all set; only
  `generate_development_plan` is allowed. Otherwise `LLM_SKIPPED`.

Each `SKIPPED` mode is a `PASS` outcome, not a failure.

## Driving the pilot

```bash
# 1. Resolve pilot mode + verify baseline.
./scripts/check_real_integration_inputs.sh
./scripts/check_llm_runtime_inputs.sh
./scripts/check_runtime_state.sh
./scripts/verify_operations_view.sh
./scripts/verify_unified_audit.sh
./scripts/verify_platform_observability.sh
./scripts/verify_backup_drill.sh
./scripts/verify_backup_production_readiness.sh

# 2. Drive 8 scenarios (idempotent; tasks are timestamped).
PILOT_TS="$(date -u +%Y%m%d%H%M%S)"
# (driver script generates 8 tasks via /intake/mock; see report below)

# 3. Generate the pilot report.
PILOT_TS="$PILOT_TS" \
PILOT_DIR=/tmp/pilot \
REPO_ROOT=/home/itadmin/AI-Agents-SWD \
  python3 scripts/build_validation_pilot_report.py

# 4. Re-run full regression suite.
./scripts/run_tests.sh
for s in check_runtime_state verify_backup_drill \
         verify_backup_production_readiness verify_llm_cost_governance \
         verify_real_llm_plan_only_pilot verify_tamper_evident_audit \
         verify_real_discord_delivery_filter verify_real_integration_pilot \
         verify_notification_delivery verify_operations_view \
         verify_unified_audit verify_platform_observability \
         verify_flexible_human_approval_policy verify_llm_proposal_promotion \
         verify_qa_auto_fix_loop verify_controlled_code_generation; do
  ./scripts/${s}.sh
done
```

## Reports

* `source/pilot-reports/validation_pilot_<ts>.json` -- per-pilot
  snapshot.
* `source/pilot-reports/validation_pilot_latest.json` -- always the
  most recent.

Report fields include `pilot_id`, `started_at`, `completed_at`,
`git_commit`, `pilot_mode`, `total_tasks`, `passed_tasks`,
`failed_tasks`, `tasks[]` (each with task_id, scenario,
execution_mode, final_stage, github_result, qa_result,
approval_result, llm_result, audit_present, notification_present,
operations_present, production_executed, result, notes),
`production_safety_counts`, `backup_readiness_status`,
`backup_readiness_gaps`, `known_gaps`, `recommendation`, and
`future_stage_candidates`.

Reports MUST NOT carry any credential, token, or backup artifact.
Generated backup artifacts under `backups/` are gitignored.

## Pilot assessment

The pilot reports one of:

* **Controlled external task assignment viable: YES** when every
  scenario lands a deterministic verdict (`PASS`, `PASS_via_regression`,
  or `PASS_SKIPPED` for unavailable real-integration paths).
* **Controlled external task assignment viable: NO** when any
  scenario returns FAIL after retries.

Operator-decided production readiness is NOT a pilot output. The
pilot only states whether the **validation environment** is fit
for wider exposure.

## Future stage candidates (observation only)

The pilot intentionally lists future-stage candidates so an operator
can prioritise them. **Claude Code does not pick the next stage.**

* **LLM Model Routing & Agent Model Policy** -- scope below.
* Backup / DR gap closure (S3 client + scheduled backup + migration
  `*_down.sql` files + production encryption key).
* Audit HMAC key rotation / key map loader (Step 33 carry-forward).
* audit-service direct POST integrity gap closure (Step 33 carry-forward).
* Kubernetes / Helm / ArgoCD runtime baseline.
* Incident response runbook / external alert receiver.

### LLM Model Routing & Agent Model Policy (future stage scope)

This stage is **not implemented** in the current platform. When it
is implemented it MUST cover at minimum:

* **per-agent model policy** -- the orchestrator (not the agent)
  decides which provider / model an agent uses, based on the agent's
  declared capability needs.
* **task-risk based model routing** -- low-risk tasks may flow to
  cheaper / smaller models; high-risk tasks demand a vetted, more
  capable model with stricter guardrails.
* **budget-aware model selection** -- the Model Router consults the
  Stage 35 LLM budget governance before each call so a route that
  would exceed the per-day / per-month cap is blocked or
  downgraded.
* **provider fallback** -- if the primary provider is unhealthy or
  rate-limited, fall back to a vetted secondary; the fallback is
  audited and counted.
* **schema compatibility check** -- the router asserts that the
  selected model implements the prompt + tool schema the agent
  needs; mismatches block the call.
* **human approval override** -- specific routes (e.g., production
  patch generation) require a Stage 31 human approval policy hit
  before the router commits.
* **model usage audit** -- every routed call writes an
  `llm_model_routed` (or equivalent) decision_type with provider,
  model_name, route_reason, budget_remaining, and the agent
  capability request.
* **agents may NOT pick a real model autonomously** -- the
  development-agent / qa-agent / etc. emit a *capability request*
  (e.g. "generate a development plan for a delivery_task with
  high-risk surface"); the Model Router / Policy picks the actual
  provider + model + parameters. An agent that bypasses the router
  is rejected at the SDK boundary.
* **agents only submit a capability request** -- the SDK exposes
  `request_model_capability(...)` (or equivalent) and refuses any
  call that hard-codes a model name.

These items are **observations only**; the next stage is
operator-decided.

## Carry-forward limitations

* Step 33 -- HMAC key rotation / key map loader (still open).
* Step 33 -- audit-service direct POST `/audit/events` immediate
  integrity gap (still open).
* Stage 36 -- backup readiness gaps (`encryption_no_key`,
  `storage_not_off_host`, `schedule_dry_run_only`,
  `migration_down_gaps`).

The pilot does NOT remediate any of these.
