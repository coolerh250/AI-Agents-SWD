# Verification & Regression Runner

Stage 41 — Verification Environment Hygiene & Regression Runner Hardening.

## Purpose

Every verify script in `scripts/verify_*.sh` must run in a **predictable, reproducible, auditable** environment. Before Stage 41, scripts that imported `shared.sdk.*` (which depends on `asyncpg`) would fail on host machines without the project virtualenv, producing `ModuleNotFoundError` and requiring a manual caveat in regression results.

This document describes the verification environment standard, how to set it up, and how to run and interpret the regression runner.

---

## Verification Environment Standard

All regression / verify scripts must conform to one of three modes:

### Mode A — Project Venv

- Uses `.venv/bin/python3` (created by `setup_verification_env.sh`).
- All SDK dependencies are installed from `requirements.txt` and `apps/orchestrator/requirements.txt`.
- Scripts source `scripts/lib/verify_env.sh` which prepends `.venv/bin` to `PATH` and exports `$PYTHON`.
- **When to use**: any script that imports `shared.sdk.*`, `asyncpg`, or other project packages.

### Mode B — Container Exec

- Uses `docker compose exec -T <service> python3 ...` to run Python inside a container.
- Suitable for scripts that need live DB / internal network access.
- No host Python dependency.

### Mode C — Pure Shell

- Uses only POSIX shell, `curl`, `jq`, `docker`, `psql` (via docker exec).
- No Python at all.
- **When to use**: scripts that only call HTTP endpoints or run psql queries.

---

## Dependency Manifest

Project-level packages are declared in:

- `requirements.txt` — top-level project dependencies (includes `asyncpg`, `httpx`, `pydantic`, `redis`, `pytest`, etc.)
- `apps/orchestrator/requirements.txt` — orchestrator-specific packages

These are the authoritative dependency sources. Never install global packages to fix verification failures.

---

## Setup

```bash
# First-time setup (or after requirements.txt changes)
./scripts/setup_verification_env.sh
```

This script:
1. Finds Python 3.10+ on the host.
2. Creates `.venv` at the repo root (`python3 -m venv .venv`).
3. Installs `requirements.txt` and `apps/orchestrator/requirements.txt` into the venv.
4. Runs `verify_environment_dependencies.sh` to confirm everything is ready.
5. Outputs `SETUP_VERIFICATION_ENV: PASS`.

Safe to run multiple times (idempotent).

---

## Dependency Check

```bash
./scripts/verify_environment_dependencies.sh
```

Checks:
- `.venv/bin/python3` exists and is usable.
- `asyncpg`, `httpx`, `pydantic`, `redis`, `pytest`, `langgraph` importable.
- `curl`, `jq`, `docker`, `docker compose` available.
- `psql` via host or `docker compose exec postgres`.
- `shared.sdk.audit_integrity`, `shared.sdk.approval_policy`, etc. importable.
- Host asyncpg caveat closed (asyncpg only in venv, not on bare host python).

Outputs `VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY: PASS` or `FAIL`.

---

## Shared Helper: `scripts/lib/verify_env.sh`

Source at the top of any verify script that uses Python:

```bash
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true
```

After sourcing:
- `$REPO_ROOT` — absolute path to repo root.
- `$VENV_PYTHON` — path to venv python3 (empty if no venv).
- `$PYTHON` — resolved python3 to use (venv if available, else system).
- `PATH` — `.venv/bin` prepended (bare `python3` resolves to venv).

Helper functions:
- `require_venv_python` — exits 1 with remediation message if no venv.
- `require_command CMD` — exits 1 if command not in PATH.
- `require_python_module MOD` — returns 0 if importable, 1 otherwise.
- `run_python ARGS...` — runs `$PYTHON` with given args.
- `run_in_service SVC CMD...` — runs `docker compose exec -T SVC CMD...`.
- `fail_with_marker MARKER MSG` — prints FAIL marker and exits 1.
- `skip_with_marker MARKER MSG` — prints SKIPPED-PASS.
- `detect_host_dependency_leak` — warns if asyncpg is on system python.
- `redact_env_values KEY...` — prints `KEY=***REDACTED***`.

---

## Regression Runner

```bash
# Full run with JSON report
./scripts/run_full_regression.sh --full --json-report

# Quick run (subset of scripts)
./scripts/run_full_regression.sh --quick --json-report

# Stop on first failure
./scripts/run_full_regression.sh --full --stop-on-fail

# Continue even on failures
./scripts/run_full_regression.sh --full --continue-on-fail --json-report
```

Output markers:
- `FULL_REGRESSION_VERIFY: PASS` — all scripts passed (or PASS_WITH_DOCUMENTED_GAPS + skipped_pass)
- `FULL_REGRESSION_VERIFY: PASS_WITH_DOCUMENTED_GAPS` — backup readiness has documented gaps, all else pass
- `FULL_REGRESSION_VERIFY: FAIL` — at least one disallowed failure

Report files:
- `source/regression-reports/regression_{timestamp}.json` — full report
- `source/regression-reports/regression_latest.json` — copy of latest
- `source/regression-reports/regression_latest_summary.json` — compact summary (read by `/operations/safety`)

---

## Result Classification

| Class | Meaning | Allowed? |
|-------|---------|----------|
| `pass` | Script exited 0 with PASS marker | ✅ Yes |
| `skipped_pass` | SKIPPED-PASS marker (e.g. no real LLM key) | ✅ Yes |
| `pass_with_gaps` | PASS_WITH_GAPS for backup readiness script | ✅ Yes (documented) |
| `pass_with_documented_gaps` | Overall run has only documented gaps | ✅ Yes |
| `fail` | Script exited non-zero, no known marker | ❌ No |
| `environment_failure` | `ModuleNotFoundError` or missing dependency | ❌ No |
| `regression_failure` | Audit integrity or direct-POST integrity FAIL | ❌ No |
| `safety_failure` | `production_executed != 0` | ❌ No (hard fail) |
| `unknown_failure` | Exit non-zero with no recognized marker | ❌ No |

---

## Known Allowed Gaps

Only `scripts/verify_backup_production_readiness.sh` may emit `PASS_WITH_GAPS`:

| Gap | Reason |
|-----|--------|
| `encryption_no_key` | `BACKUP_ENCRYPTION_KEY` not configured |
| `storage_not_off_host` | Backup storage is local-only |
| `schedule_dry_run_only` | Cron schedule is dry-run only |
| `migration_down_gaps` | Some migrations lack down scripts |

These are production blockers but not regression failures.

---

## Interpreting PASS_WITH_GAPS

A `PASS_WITH_DOCUMENTED_GAPS` overall result means:
- All verify scripts PASS or SKIPPED-PASS.
- `verify_backup_production_readiness.sh` returned `PASS_WITH_GAPS`.
- The gaps are the documented backup readiness blockers.
- This is the expected state until backup / DR gaps are resolved.

---

## Interpreting SKIPPED-PASS

Some scripts conditionally skip when external credentials are absent:
- `verify_real_llm_plan_only_pilot.sh` — skips if no `LLM_API_KEY`.
- `verify_real_discord_delivery_filter.sh` — may SKIPPED-PASS if no real Discord env.
- `verify_real_integration_pilot.sh` — SKIPPED-PASS if no real Discord + GitHub.

SKIPPED-PASS is an allowed outcome. The skip reason is in the key_marker.

---

## Troubleshooting `environment_failure`

If you see `ModuleNotFoundError: No module named 'asyncpg'`:

1. Run `./scripts/setup_verification_env.sh`.
2. Confirm `SETUP_VERIFICATION_ENV: PASS`.
3. Re-run `./scripts/verify_environment_dependencies.sh`.
4. Confirm `VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY: PASS`.
5. Re-run the failing verify script.

Do **not** install packages globally (`pip install asyncpg` without a venv).

---

## Production Safety Requirements

The regression runner enforces:
- `production_executed_true_count == 0`
- `real_incident_escalation_enabled == false`
- `incident_auto_remediation_enabled == false`
- No real Discord delivery of `verification.*` events
- No real LLM calls unless explicitly opt-in

---

## Preventing Secret Leaks

- `verify_env.sh` never prints secret values — only `KEY=(not set)` or `KEY=***REDACTED***`.
- Regression reports are scanned for token patterns in `verify_regression_runner_hardening.sh` Scenario E.
- Do not commit `.env` files or generated backup artifacts.

---

## Current Limitations

- `asyncpg` requires the project venv to be set up before running verify scripts. Run `./scripts/setup_verification_env.sh` once per host.
- Some verify scripts (backup, audit) require running containers (`docker compose up -d`).
- `check_runtime_state.sh` may hang at Stage 30 LLM section on some hosts; Stage 41 smokes (115-124) can be run separately.
- Host asyncpg caveat is now closed (Stage 41). Previous regressions showing `ModuleNotFoundError` are resolved by venv setup.

---

## Operations API

After a full regression run, `/operations/safety` exposes:

```json
{
  "verification_environment_ready": true,
  "verification_runner_available": true,
  "latest_full_regression_status": "pass",
  "latest_full_regression_at": "2026-06-13T12:05:00Z",
  "latest_full_regression_report_path": "source/regression-reports/regression_20260613.json",
  "verification_dependency_failures": [],
  "verification_known_gaps": ["encryption_no_key", "storage_not_off_host"],
  "verification_environment_caveats": [],
  "verification_host_dependency_caveat_closed": true
}
```

If no regression has been run: `"latest_full_regression_status": "unknown"`.

## Stage 45 — Project planner verify (additive)

`scripts/verify_project_planner_task_graph.sh` is a standalone verifier (like
`verify_audit_touching_serialization.sh`): its Scenario F runs
`run_full_regression.sh --full` itself, so it is **not** part of the runner's
own verify list (that would recurse). Run it directly in the regression
sequence. Marker: `PROJECT_PLANNER_TASK_GRAPH_VERIFY: PASS`.

`check_runtime_state.sh` smokes 153–164 cover the project planner / task graph
surfaces (template, brief, graph build, dependency validation, acceptance,
assignment policy, operations API, planning-only safety, denylist, audit
integrity, no-secret-leak).

## Stage 46 — Design review verify (additive)

`scripts/verify_agent_discussion_design_review.sh` is a standalone verifier: its
Scenario G runs `verify_project_planner_task_graph.sh` (which itself runs
`run_full_regression.sh --full`), so it is **not** part of the runner's own
verify list. Run it directly in the regression sequence. Marker:
`AGENT_DISCUSSION_DESIGN_REVIEW_VERIFY: PASS`.

`check_runtime_state.sh` smokes 165–177 cover the agent discussion / design
review surfaces (service health, session/contribution builders, FastAPI Todo
review, gate evaluation, acceptance coverage, operations API, planning-only
safety, denylist, audit integrity, no-secret-leak, no-chain-of-thought).

## Stage 47 — Real repo workspace operator verify (additive)

`scripts/verify_real_repo_workspace_operator.sh` is a standalone verifier: its
Scenario H runs `verify_agent_discussion_design_review.sh` (which transitively
runs `verify_project_planner_task_graph.sh` and `run_full_regression.sh
--full`), so it is **not** part of the runner's own verify list. Run it
directly in the regression sequence. Scenario G waits for audit/notification
convergence (bounded verify-chain loop) before reading the chain, to avoid the
Stage 44 eventual-consistency false failure. Marker:
`REAL_REPO_WORKSPACE_OPERATOR_VERIFY: PASS`.

`check_runtime_state.sh` smokes 178–192 cover the workspace operator surfaces
(service health, workspace-root allowlist, FastAPI Todo generation, file
manifest, pytest/static-check runners, diff summary, artifacts, work-item
links, operations API, controlled-only safety, denylist, audit integrity,
no-secret-leak, no-repo-write).

## Stage 48 — Mini delivery pilot verify (additive)

`scripts/verify_mini_project_delivery_pilot.sh` is a standalone verifier: its
Scenario H reuses `verify_real_repo_workspace_operator.sh` (which transitively
runs `verify_agent_discussion_design_review.sh` →
`verify_project_planner_task_graph.sh` → `run_full_regression.sh --full`), so
it is **not** part of the runner's own verify list. Run it directly in the
regression sequence. Scenario G waits for audit/notification convergence
(bounded verify-chain loop, 60s client timeout) before reading the chain.
Marker: `MINI_PROJECT_DELIVERY_PILOT_VERIFY: PASS`.

`check_runtime_state.sh` smokes 193–210 cover the mini delivery pilot surfaces
(service health, controlled pilot run, project/design-review/workspace links,
acceptance evaluation, QA evidence, safety evidence, mini delivery report,
artifacts, operations API, controlled-only safety, denylist, audit integrity,
no-secret-leak, no-chain-of-thought, no-GitHub-write, no-deploy).

## Stage 49 — Delivery package & acceptance gate verify (additive)

`scripts/verify_delivery_package_acceptance_gate.sh` is a standalone verifier:
its Scenario I reuses `verify_mini_project_delivery_pilot.sh` (which transitively
runs the workspace / design-review / planner verifies and
`run_full_regression.sh --full`), so it is **not** part of the runner's own
verify list. Run it directly in the regression sequence. Scenario H waits for
audit/notification convergence (bounded verify-chain loop, 60s client timeout)
before reading the chain. Marker:
`DELIVERY_PACKAGE_ACCEPTANCE_GATE_VERIFY: PASS`.

`check_runtime_state.sh` smokes 211–229 cover the delivery package surfaces
(service health, package build, sections, artifacts, acceptance gate run +
checks, operator-acceptance pending, handoff summaries, readiness snapshot,
operations API, controlled-only safety, operator-actions-disabled, denylist,
audit integrity, no-secret-leak, no-chain-of-thought, no-GitHub-write,
no-deploy, ready-for-admin-console).

## Stage 50 — Admin Console v0 verify (additive)

`scripts/verify_admin_console_v0.sh` is a standalone verifier: its Scenario G
reuses `verify_delivery_package_acceptance_gate.sh` (which transitively runs the
mini pilot / workspace / design / planner verifies and
`run_full_regression.sh --full`), so it is **not** part of the runner's own
verify list. Run it directly. npm is **optional**: Scenarios A/E run the
frontend typecheck/build/test when npm is present, else fall back to
deterministic source-level checks (the served zero-build `/admin` fallback keeps
the runtime checks meaningful). A missing Node toolchain must NOT fail the
backend regression. Marker: `ADMIN_CONSOLE_V0_VERIFY: PASS`.

`check_runtime_state.sh` smokes 230–242 cover the admin console surfaces
(`/admin` serve, build inputs, static serve, the six aggregate endpoints,
read-only guard, no-secret-leak, no-chain-of-thought, no-operator-action,
no-write-API).

## Stage 51 — Backup / DR gap closure verify (in the runner)

`scripts/verify_backup_dr_gap_closure.sh` (marker
`BACKUP_DR_GAP_CLOSURE_VERIFY: PASS`) closes the four backup/DR gaps at a
controlled test baseline (encryption, off-host transfer + readback, restore
drill, schedule/retention dry-run, migration rollback catalog, readiness). It is
chained into `run_full_regression.sh --full` **before**
`verify_backup_production_readiness.sh`, so the readiness gate reads the fresh
`source/dr-reports/backup_dr_readiness_latest.json` snapshot and now reports
`BACKUP_PRODUCTION_READINESS_VERIFY: PASS_WITH_NON_PRODUCTION_LIMITATIONS`
instead of the original `PASS_WITH_GAPS gaps=encryption_no_key,...`.

The runner gained a new allowed PASS class,
`pass_with_non_production_limitations`: it is **not** a failure and **not** a
documented gap. When the only non-`pass` results are non-production limitations,
the overall marker is `FULL_REGRESSION_VERIFY:
PASS_WITH_NON_PRODUCTION_LIMITATIONS`. The original four backup gaps no longer
produce `PASS_WITH_DOCUMENTED_GAPS`. `regression_fail` / `env_fail` /
`safety_fail` must remain 0; verifier strictness is unchanged (a still-open gap
or a real failure is still reported as such).

`check_runtime_state.sh` smokes 243–256 cover the backup/DR surfaces
(encryption, manifest, off-host, restore drill, schedule, retention, migration
catalog, readiness, operations API, notification denylist, audit integrity,
no-secret-leak, no-production-action, no-artifact-tracked). The standalone
sub-verifiers (`verify_backup_encryption.sh`, `verify_backup_offhost_target.sh`,
`verify_backup_restore_drill.sh`, `verify_backup_schedule_dry_run.sh`,
`verify_backup_retention_policy.sh`, `verify_migration_rollback_catalog.sh`) each
emit their own `..._VERIFY: PASS` marker and are also runnable directly.
