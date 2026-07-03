# Staging Deployment Management SOP (Step 64F.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **SOP design/documentation only — no runtime change was performed producing this document. Destructive commands require separate explicit operator authorization.**

Formal Deployment Management SOP for the staging AI Agents Platform on `10.0.1.32`. This is a
**staging** operations runbook — **not** production readiness and **not** a production rollout. The
formal product UI (accepted in Step 64E.4D) is the acceptance path; the Demo Evidence / Diagnostics
page is **not** the acceptance path. `production_executed_true_count` must remain **0**.

Commands below are **reference procedures**; running them is a separate, authorized operational
act governed by [deployment-management-authorization-matrix.md](deployment-management-authorization-matrix.md).

## A. Environment identity
- **Host:** `10.0.1.32` (SSH; key-based, interactive credentials never stored).
- **Repo path:** `/data/ai-agents-staging/AI-Agents-SWD`.
- **Compose file:** `infra/docker-compose/docker-compose.staging.yml`.
- **Env file:** `infra/runtime/.env.staging.local` (gitignored; **never print its contents**).
- **Compose project:** `aiagents-staging` (host ports offset `+10000`, loopback-only).
- **Canonical compose invocation:**
  `docker compose -p aiagents-staging -f infra/docker-compose/docker-compose.staging.yml --env-file infra/runtime/.env.staging.local <cmd>`
- **Admin URL access:** SSH local port-forward `-L 18000:127.0.0.1:18000`, then
  `http://localhost:18000/admin` — **navigate by the top-nav tabs** (SPA deep-link hard-refresh
  404s; see troubleshooting).
- **Services (22):** postgres, redis, vault (dev/mock), policy-engine, approval-engine,
  audit-service, notification-worker, discord-gateway, audit-worker, orchestrator,
  communication-gateway, github-automation, intake-agent, requirement-agent, development-agent,
  qa-agent, devops-agent, retry-scheduler, tempo, alertmanager, prometheus, grafana.
- **Data volumes (5, preserve unless destructive teardown authorized):**
  `postgres-staging-data`, `prometheus-staging-data`, `grafana-staging-data`,
  `tempo-staging-data`, `alertmanager-staging-data`.
- **Secret posture:** mock-vault by default (dev escape hatch); live GitHub/Discord/LLM
  disabled/mocked.
- Full command list: [deployment-management-command-reference.md](deployment-management-command-reference.md).

## B. Start procedure
- **Pre-checks:** clean `git status`; correct HEAD; env file present; `/data` free space.
- **Start command (canonical):** `bash scripts/start_staging_runtime.sh` (validates env, brings up
  the stack, waits for postgres+redis, applies migrations, inits Redis Streams, restarts consumers,
  prints the port map). Add `--rebuild` only when images must be rebuilt.
- **Expected services:** all 22 running; orchestrator healthy.
- **Post-start health checks:** `bash scripts/check_staging_runtime.sh`; `/health` 200; `/admin/`
  200; `/operations/safety` `production_executed_true_count=0`.
- **If start fails:** capture logs (§K), do not force volume deletion; re-run after fixing the
  reported cause; escalate per authorization matrix.

## C. Stop procedure
- **Orchestrator-only stop:** `docker compose … stop orchestrator` (leaves the rest running).
- **Full-stack stop (volume-preserving):** `bash scripts/stop_staging_runtime.sh` → `compose down
  --remove-orphans` (containers removed, **named volumes kept**).
- **`stop` vs `down`:** `stop` halts containers but keeps them; `down` removes containers/networks
  but (without `--volumes`) keeps named volumes.
- **`down -v` is forbidden** except under an explicit, separately-authorized **destructive
  teardown** (§H) — it deletes the staging DB and observability data.

## D. Restart procedure
- **Orchestrator-only restart:** `docker compose … restart orchestrator` (most common; used after
  an orchestrator-only redeploy).
- **Single service restart:** `docker compose … restart <service>`.
- **Full-stack restart:** `docker compose … restart` (only when broadly necessary; document the
  reason).
- **Health checks after restart:** `/health` 200; `check_staging_runtime.sh` PASS.
- **Operator notification:** notify the operator before/after any restart beyond orchestrator-only.

## E. Rebuild / redeploy procedure (orchestrator-only — the standard path)
1. **Repo sync:** `git fetch origin && git checkout main && git pull --ff-only origin main` (stop
   if the tree is dirty; no hard reset without authorization).
2. **Git clean-state check:** `git status --short` empty; record HEAD.
3. **Build:** `docker compose … build orchestrator` (in-image Vite build of the Admin Console).
4. **Recreate:** `docker compose … up -d orchestrator` (postgres/redis only health-waited).
5. **Validate:** `/health` 200; `/admin/` 200 (note the bundle hash); `/operations/safety`
   `production_executed_true_count=0`.
6. **Validate formal product pages** per [deployment-management-validation-plan.md](deployment-management-validation-plan.md)
   (Projects/Work Items `/delivery`, Agent Executions `/agent-executions`, Workflows/Task Graph
   `/task-graph`, QA/Code `/qa-code`, Audit/Evidence `/audit-evidence`, Safety Center `/safety`).
- **Full-stack rebuild** (`… build`) is only for a dependency/base-image change; document why and
  prefer orchestrator-only.

## F. Upgrade procedure
1. **Pre-upgrade evidence capture:** record current HEAD, bundle hash, `check_staging_runtime.sh`
   output, `/operations/safety`.
2. **Identify target commit** on `origin/main` (or a tag) and its change scope.
3. **Test/QA gate:** the change must have passed the test/QA gate (frontend typecheck/tests/build;
   backend pytest; verifiers) **before** staging redeploy — no staging acceptance on an unvalidated
   build.
4. **Staging redeploy:** the §E orchestrator-only path (or full rebuild if required).
5. **Post-upgrade validation:** §J health/safety + formal-page validation.
6. **Operator re-review trigger:** if the upgrade changes operator-visible behavior, request an
   operator re-review before treating it as accepted.
7. **Rollback decision point:** if validation fails or the operator rejects, roll back per §G.

## G. Rollback procedure (document only — do not execute here)
- **When allowed:** post-upgrade validation failure, operator rejection, or a safety regression.
- **Identify previous known-good commit:** from `git log` / the pre-upgrade evidence capture.
- **Rebuild previous image:** `git checkout <good-commit>` → `docker compose … build orchestrator`
  → `up -d orchestrator` (orchestrator-only; no volume deletion).
- **Validate after rollback:** §J health/safety + formal-page validation; confirm
  `production_executed_true_count=0`.
- **Record:** rolled-back-from/to commits, reason, validation result, operator notification.

## H. Teardown procedure (document only — do not execute here)
- **Non-destructive stop:** `stop` / `down --remove-orphans` (containers removed, **volumes
  kept**).
- **Volume-preserving teardown:** `bash scripts/stop_staging_runtime.sh` (default).
- **Volume-deleting (destructive) teardown:** `bash scripts/stop_staging_runtime.sh --volumes`
  (equivalent to `down --volumes`) — **deletes** the 5 named volumes (staging DB + observability
  data).
- **Destructive teardown requires separate explicit operator authorization** and a recorded
  reason; it is never part of a routine restart/redeploy.

## I. Restore procedure (document only — do not execute here)
- **Preconditions:** authorized destructive event or fresh environment; a validated backup exists.
- **Backup source:** the staging backup/DR artifacts (see backup/DR docs); never a production
  secret store.
- **Restore target:** the `aiagents-staging` volumes / DB on `10.0.1.32`.
- **Validation:** post-restore `check_staging_runtime.sh` PASS; DB integrity checks; formal-page
  validation; `/operations/safety` `production_executed_true_count=0`.
- **Data integrity checks + operator sign-off** are required before the restored environment is
  treated as usable.

## J. Health and safety validation
- **Runtime:** `/health` 200; `/admin` 307 → `/admin/` 200; `bash scripts/check_staging_runtime.sh`
  PASS.
- **Safety:** `/operations/safety` → `production_executed_true_count=0`; live GitHub/Discord/LLM
  external flags `false` (disabled/mocked) unless a controlled external-integration phase is
  separately authorized.
- **Formal product UI:** each formal page surfaces its evidence (see validation plan); the Demo
  Evidence / Diagnostics page is **not** the acceptance path.
- All checks are **GET/HEAD** only.

## K. Troubleshooting
See [deployment-management-troubleshooting-guide.md](deployment-management-troubleshooting-guide.md).
Covers: Admin Console unreachable; stale Vite bundle; orchestrator unhealthy; postgres/redis
dependency issues; safety warning; SPA deep-link 404; missing evidence in formal pages. Log
collection: `docker compose … logs --tail <n> <service>` (no secrets in shared logs).

## L. Authorization matrix
See [deployment-management-authorization-matrix.md](deployment-management-authorization-matrix.md).
Read-only checks are routine; orchestrator restart / rebuild-redeploy require operator
authorization; full-stack restart, rollback, teardown, restore, external-integration enablement,
and any production deploy require **explicit** authorization (destructive/production actions
require separate explicit sign-off and are out of scope for routine staging operations).

## Rehearsed in Steps 64F.2 / 64F.3
- **64F.2** — the restart (§D, orchestrator-only) and health/safety validation (§J) procedures were
  exercised on `10.0.1.32`: orchestrator recovered healthy, all formal-evidence endpoints
  unchanged, `production_executed_true_count=0`, no data loss. See
  [deployment-management-rehearsal-report.md](deployment-management-rehearsal-report.md).
- **64F.3** — the rebuild/redeploy (§E, git ff-only sync → orchestrator-only `build` + `up -d`) and
  validation (§J) procedures were exercised: build succeeded, orchestrator recovered healthy,
  formal-evidence endpoints unchanged, `production_executed_true_count=0`, no data loss. See
  [deployment-management-rebuild-redeploy-rehearsal-report.md](deployment-management-rebuild-redeploy-rehearsal-report.md).

## Status
- Step 64E: **PASS**. Step 64F: **REHEARSAL_COMPLETED** (SOP designed in 64F.1, restart+validation
  rehearsed in 64F.2).
- **This is staging deployment management, not production readiness and not a production rollout.**
- No runtime change in this stage; no production action; `production_executed_true_count=0`.
- Destructive commands (`down -v`, volume deletion, teardown, restore, rollback) require separate
  explicit authorization. Demo Evidence / Diagnostics is not the staging acceptance path; the
  formal product UI remains the acceptance path.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
