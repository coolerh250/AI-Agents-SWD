# Progress Log — AI-Agents-SWD

Updated at every development stage. Each entry records: execution time,
Git branch / commit hash, modified files, deployment target, test results,
issues & blockers, and next-step suggestions.

---

## Stage 1 — Environment, GitHub & Test Server Inventory

- **Execution time:** 2026-05-21 17:59 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `2f4058d` ("Initial commit"); this inventory record is committed on top of it.
- **Modified files:**
  - `source/progress.md` (new)
- **Deployment target:** none — inventory only, no deployment performed.
- **Test results:**

  **Local development environment**
  - Repo root: `…/Documents/VS Code/AIAgent-SWD`
  - Remote `origin`: `https://github.com/coolerh250/AI-Agents-SWD.git`
  - Branch `main`, working tree clean, up to date with `origin/main`
  - Latest commit: `2f4058dc32dfc5f88f32915c2c58fa96a0096f8c` — "Initial commit"
  - Content: `README.md`; empty directories `provisioning/cloud-init/` (untracked — git does not track empty directories)

  **GitHub**
  - `git push --dry-run origin main` → "Everything up-to-date" (exit 0)
  - Push capability: OK — credentials cached via Git Credential Manager

  **Test server 10.0.1.31**
  - SSH reachable via profile `aiagent-swd` (user `itadmin`, key-only authentication)
  - Host `aiagent-swd`, Ubuntu 24.04.4 LTS, kernel 6.8.0-101-generic
  - Tool inventory (no packages installed — inventory only):

    | Tool           | Status  | Version       |
    |----------------|---------|---------------|
    | git            | OK      | 2.43.0        |
    | docker         | MISSING | —             |
    | docker compose | MISSING | —             |
    | python3        | OK      | 3.12.3        |
    | curl           | OK      | 8.5.0         |

- **Issues & blockers:**
  - **BLOCKER:** `docker` and `docker compose` are not installed on the test server (10.0.1.31). Any container-based deployment is blocked until they are installed. Not installed in this stage, per the "inventory only / do not install packages" instruction.
  - Minor: `provisioning/cloud-init/` exists only as empty directories; intended contents not yet defined.

- **Next-step suggestions:**
  1. Decide whether deployment will be container-based. If yes, install Docker Engine + Compose plugin on 10.0.1.31 — this installs packages and needs explicit approval.
  2. Confirm the intended contents/purpose of `provisioning/cloud-init/`.
  3. Establish the deployment workflow on 10.0.1.31: `git clone` / `git pull` this repo, then deploy (per project rule 5).

---

## Stage 2 — Install Docker Test-Deployment Capability on 10.0.1.31

- **Execution / install time:** 2026-05-21 18:07:27–18:07:48 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `3cdb56b`; this record is committed on top of it.
- **Modified files:**
  - `source/progress.md` (Stage 2 entry appended)
  - No application or configuration files changed in the repo.
- **Deployment target:** test server `10.0.1.31` (`aiagent-swd`, Ubuntu 24.04.4 LTS) — Docker engine installed; **no application deployed** (per task constraint).
- **Install method:** Docker official Ubuntu apt repository (`https://download.docker.com/linux/ubuntu`, suite `noble stable`, signed by `/etc/apt/keyrings/docker.asc`). Packages installed: `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, `docker-compose-plugin` (+ dependencies `docker-ce-rootless-extras`, `pigz`).
- **Conflicting-package check (before install):** all absent — `docker.io`, `docker-compose`, `docker-compose-v2`, `docker-doc`, `podman-docker`, `containerd`, `runc`. No removals needed; clean install.
- **Test results:**
  - `docker --version` → `Docker version 29.5.2, build 79eb04c`
  - `docker compose version` → `Docker Compose version v5.1.4`
  - `systemctl status docker` → `active (running)`, unit enabled (auto-start on boot)
  - `docker run --rm hello-world` → **PASS** ("Hello from Docker!")
  - `itadmin` docker access in a fresh SSH session → `docker ps` works without `sudo`
- **docker group / re-login:**
  - `itadmin` added to group `docker` (gid 988) via `usermod -aG docker itadmin`.
  - New SSH logins pick up the group automatically — verified: `docker ps` runs without `sudo` in a fresh session.
  - The install-time shell did not gain the group immediately; any session opened before the install would need re-login (or `newgrp docker`). No action needed for new sessions.
- **Issues & blockers:** none — Docker is installed and fully functional.
- **Risks / notes:**
  - On first start `dockerd` logged benign `nftables ... No such file or directory` messages (no pre-existing rules to delete) — daemon initialized successfully; not an error.
  - No application deployed and no production resources created (per task constraints).
- **Next-step suggestions:**
  1. Define the application with its `Dockerfile` / `compose.yaml` in the repo.
  2. Establish the deploy flow on 10.0.1.31: `git pull` latest `main`, then `docker compose up` (per project rule 5).
  3. Confirm the intended contents of `provisioning/cloud-init/`.

---

## Stage 3 — Monorepo Base Skeleton (Step 2)

- **Execution time:** 2026-05-21 18:14–18:17 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `1ed9e98`. Step 2 produced two commits:
  - `4c973a1cb560d144bc0657ba107e8ae6fc090469` — monorepo skeleton (directories, `.gitkeep`, README, `.gitignore`)
  - this Stage 3 progress entry is committed on top.
- **Modified files:**
  - Added: `.gitignore`; 25 × `<directory>/.gitkeep` placeholders under `apps/`, `agents/`, `shared/`, `infra/`, `migrations/`, `scripts/`, `tests/`
  - Modified: `README.md` (expanded to the full project README); `source/progress.md` (this entry)
  - Deleted: none
- **Deployment target:** test server `10.0.1.31` — **pull verification only** (no application deployed, no `docker compose` started, no production resources created).
- **Test results:**
  - Directory skeleton: 26 directories present (25 created with `.gitkeep` + the pre-existing `source/`).
  - `README.md`: rewritten with project name, purpose, repository structure, local/test deployment principle, test server, production restriction, and no-secrets policy.
  - `.gitignore`: created (Python / Node / build artifacts / logs / env & local secrets / docker local volumes / OS cruft).
  - Commit `4c973a1` pushed to `origin/main` (27 files changed).
  - Test server: `git clone` into `/home/itadmin/AI-Agents-SWD`; HEAD `4c973a1` on `main`; all 26 directories verified present (`DIR_VERIFY: PASS`); `README.md`, `.gitignore`, `source/progress.md` present.
- **Issues & blockers:** none.
- **Risks / notes:**
  - All directories are empty placeholders (`.gitkeep` only) — no application code yet.
  - The pre-existing empty `provisioning/cloud-init/` is outside this skeleton and remains untracked (not part of Step 2 scope).
- **Next-step suggestions:**
  1. Begin implementing services/agents — start with `shared/` (sdk, models) so apps and agents have a dependency base.
  2. Add `infra/docker-compose/` definitions for local/test runs.
  3. Establish the deploy flow on 10.0.1.31: `git pull` → build → `docker compose up` (test only).

---

## Stage 4 — Docker Compose Local/Test Runtime (Step 3)

- **Execution time:** 2026-05-21 18:27 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `952a189`. Step 3 produced two commits:
  - `919630b8db3f73440ea4b2d06984835e4f0999da` — Docker Compose runtime + orchestrator placeholder
  - this Stage 4 progress entry is committed on top.
- **Modified files:**
  - Added: `infra/docker-compose/docker-compose.yml`, `apps/orchestrator/Dockerfile`, `apps/orchestrator/requirements.txt`, `apps/orchestrator/src/main.py`
  - Modified: `README.md` (local/test runtime instructions), `.gitignore` (ignore `.claude/`), `source/progress.md` (this entry)
  - Deleted: `apps/orchestrator/.gitkeep`, `infra/docker-compose/.gitkeep` (directories now contain real files)
- **Deployment target:** test server `10.0.1.31` — Docker Compose runtime validation (`up -d` of postgres, redis, vault, orchestrator). No application logic deployed, no production resources created.
- **Docker Compose config result:** `docker compose -f infra/docker-compose/docker-compose.yml config` → **valid** (exit 0); rendered project `aiagents-test` with 4 services. Local Docker is not installed on the dev machine, so config was validated on the test server.
- **Container status** (`docker compose ps`):
  - `aiagents-test-orchestrator-1` — Up (healthy) — `127.0.0.1:8000->8000`
  - `aiagents-test-postgres-1` — Up (healthy) — `127.0.0.1:5432->5432`
  - `aiagents-test-redis-1` — Up (healthy) — `127.0.0.1:6379->6379`
  - `aiagents-test-vault-1` — Up — `127.0.0.1:8200->8200` (no healthcheck defined)
- **Health check result:** `curl http://localhost:8000/health` → `{"service":"orchestrator","status":"ok"}` — **PASS**.
- **Logs summary:**
  - orchestrator — uvicorn startup complete; `GET /health` → `200 OK`.
  - postgres — PostgreSQL 16.14 initialised; "database system is ready to accept connections" (`trust` auth, expected warning).
  - redis — Redis 7.4.9 "Ready to accept connections" (benign kernel `vm.overcommit_memory` warning).
  - vault — dev mode; core unsealed; running. Vault dev mode prints an ephemeral root token / unseal key to its own container log — intentionally **not recorded here** (no-secrets rule); it is regenerated on every restart.
- **Image versions:** postgres 16.14, redis 7.4.9, hashicorp/vault 1.17.6; orchestrator built on `python:3.12-slim` with fastapi 0.136.1 + uvicorn 0.47.0.
- **Issues & blockers:** none — all four containers started and the orchestrator health check passed on the first deployment.
- **Risks / notes:**
  - Local Docker is not installed on the Windows dev machine; compose validation and image builds run on the test server only.
  - PostgreSQL uses `POSTGRES_HOST_AUTH_METHOD=trust` and Vault runs in dev mode — local/test-only choices, never for production.
  - Vault dev mode is in-memory (ephemeral); all data and tokens are lost on restart.
  - All service ports bind to `127.0.0.1` on the test server (not exposed to the wider network).
  - The runtime is left running on 10.0.1.31; stop it with `docker compose -f infra/docker-compose/docker-compose.yml down`.
- **Next-step suggestions:**
  1. Implement orchestrator logic and shared libraries (`shared/sdk`, `shared/models`).
  2. Wire the orchestrator to postgres/redis once real functionality exists, using non-`trust` credentials supplied via env / a secrets manager.
  3. Add the remaining services and agents and extend the compose runtime.

---

## Stage 5 — PostgreSQL Migration & Redis Streams Initialization (Step 4)

- **Execution time:** 2026-05-21 21:43–21:45 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `97a1e86`. Step 4 produced three commits:
  - `b8ca097` — migration SQL + 3 runtime shell scripts
  - `d91c369` — fix: correct Redis stream enumeration in the runtime scripts
  - this Stage 5 progress entry is committed on top.
- **Modified files:**
  - Added: `migrations/001_init_core_tables.sql`, `scripts/init_redis_streams.sh`, `scripts/init_local_runtime.sh`, `scripts/check_runtime_state.sh` (the 3 scripts committed executable, mode 755)
  - Modified: `README.md` (database & streams initialization section); `source/progress.md` (this entry); `scripts/init_local_runtime.sh` and `scripts/check_runtime_state.sh` were further modified by the fix commit `d91c369`
  - Deleted: `migrations/.gitkeep`, `scripts/.gitkeep`
- **Deployment target:** test server `10.0.1.31` — database and Redis initialization validation (no application deployed, no production resources).
- **PostgreSQL migration result:** `migrations/001_init_core_tables.sql` applied via `psql -v ON_ERROR_STOP=1`. 8 core tables created — UUID primary keys; every table has `created_at`; `updated_at` on the 6 mutable tables; JSONB on `workflow_states.state` and `audit_logs.artifact_refs`; `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`.
- **PostgreSQL table list:** `agent_executions`, `approval_requests`, `audit_logs`, `deployment_records`, `incident_records`, `prompt_versions`, `tasks`, `workflow_states` — 8 tables (`public` schema count = 8).
- **Migration idempotency test:** migration re-run a second time → every object reported `already exists, skipping`, transaction committed, exit 0 — **PASS** (re-run does not fail).
- **Redis Streams init result:** `scripts/init_redis_streams.sh` created 10 consumer groups across 9 streams — **PASS**.
- **Redis stream / group list:** `stream.tasks` (orchestrator-group, intake-agent-group), `stream.requirements` (requirement-agent-group), `stream.development` (development-agent-group), `stream.qa` (qa-agent-group), `stream.deployments` (devops-agent-group), `stream.approvals` (approval-group), `stream.audit` (audit-group), `stream.notifications` (notification-group), `stream.incidents` (incident-group) — 9 streams, 10 groups.
- **Redis init idempotency test:** init re-run → all 10 groups reported `exists` (BUSYGROUP handled), exit 0 — **PASS** (re-run does not fail).
- **Runtime state check result** (`check_runtime_state.sh`): 4 containers Up (orchestrator/postgres/redis healthy, vault up); 8 PostgreSQL tables; 9 Redis streams / 10 consumer groups; orchestrator `/health` → `{"service":"orchestrator","status":"ok"}` — **PASS**.
- **Issues & blockers:** none outstanding.
- **Risks / notes:**
  - One bug was found and fixed during verification: a `docker compose exec` inside a `while read` pipe consumed the loop's stdin, so the stream check listed only the first stream. Fixed in commit `d91c369` (read the stream list into a variable, then iterate). Migration and stream creation were never affected — only the check display; re-verified with all 9 streams listed.
  - Local Docker is not installed on the dev machine; shell scripts were syntax-checked with `bash -n` locally; full validation ran on the test server.
  - PostgreSQL `trust` auth and Vault dev mode remain local/test-only choices, never for production.
- **Next-step suggestions:**
  1. Implement orchestrator logic and shared libraries that use the new schema and streams.
  2. Establish a migration versioning convention for future migrations (`002_*.sql`, ...).
  3. Add `updated_at` auto-update triggers if application code will not maintain that column.

---

## Stage 6 — Shared SDK & Base Agent (Step 5)

- **Execution time:** 2026-05-21 22:00–22:07 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `199e612`. Step 5 produced four commits:
  - `fe13fab` — shared SDK packages, tests, `pyproject.toml`, `requirements.txt`, `run_tests.sh`
  - `fca19ae` — type `AuditClient.event_bus` for mypy correctness
  - `795fb38` — apply black formatting
  - this Stage 6 progress entry is committed on top.
- **Modified files:**
  - Added: `shared/` SDK packages — `base_agent/base.py`, `event_bus/redis_streams.py`, `audit/client.py`, `policy/client.py`, `models/workflow.py`, `models/events.py`, `models/audit.py`, plus 7 `__init__.py`; `tests/` — 5 test files; `pyproject.toml`; `requirements.txt`; `scripts/run_tests.sh` (executable)
  - Modified: `README.md` (Shared SDK + Testing sections); `source/progress.md` (this entry)
  - Deleted: `shared/sdk/.gitkeep`, `shared/models/.gitkeep`, `tests/.gitkeep`
- **Deployment target:** test server `10.0.1.31` — SDK test validation (no application deployed, no production resources).
- **Test results:** `pytest` — **22 passed** (0.13s). `ruff check` — all checks passed. `black --check` — all 20 files clean. `mypy` — success, no issues in 14 source files.
  - BaseAgent (7 tests): abstract class cannot be instantiated directly; `DummyAgent` subclass instantiates and runs `receive_task`/`analyze`/`execute`; `request_approval` returns allowed for non-restricted and approval-required for restricted actions; `write_audit` and `report` work — PASS.
  - PolicyClient (4 tests): all 8 restricted actions blocked (`allowed=false`, `approval_required=true`); non-restricted and unknown actions allowed — PASS.
  - AuditClient (3 tests): `build_audit_event` produces a valid `AuditEvent` with all required fields; defaults applied; `write_audit_event` returns None without an event bus — PASS.
  - Redis Streams (4 tests): `REDIS_URL` env / default / explicit-override resolution; live publish→consume→ack cycle — PASS.
  - Pydantic models (4 tests): `WorkflowState`, `AgentEvent`, `TaskCreatedEvent`, `AuditEvent` build and JSON round-trip — PASS.
- **Redis integration result:** the integration test ran against the live test Redis (`REDIS_URL=redis://localhost:6379`): `ensure_group` (idempotent), `publish_event`, `consume_events`, and `ack_event` verified against a temporary `test.stream.*` stream which was deleted afterward — PASS.
- **Runtime state:** `check_runtime_state.sh` — 4 containers Up (orchestrator/postgres/redis healthy, vault up); 8 PostgreSQL tables; 9 Redis streams / 10 groups; orchestrator `/health` OK.
- **Issues & blockers:** none outstanding.
- **Risks / notes:**
  - The test server lacked `python3-venv`; it was installed (`apt-get install python3-venv python3.12-venv`) so the venv could be created, as required by the task's venv step.
  - The first test run flagged 4 files via `black --check` (line-wrapping at the 100-char limit); fixed in commit `795fb38` and re-verified fully green. `pytest`, `ruff`, and `mypy` passed from the first run.
  - Local Docker and Python dependencies are not installed on the dev machine; the local check was `py_compile` only; the full test run executed on the test server inside a venv.
  - No real LLM, GitHub, or Slack calls; no secrets committed; PostgreSQL `trust` auth and Vault dev mode remain local/test-only.
- **Next-step suggestions:**
  1. Implement a concrete agent (e.g. intake-agent) on top of `BaseAgent`.
  2. Wire the orchestrator to the SDK (event bus, audit, policy clients).
  3. Add a CI workflow that runs `scripts/run_tests.sh` automatically.

---

## Stage 7 — LangGraph Orchestrator Workflow Skeleton (Step 6)

- **Execution time:** 2026-05-21 22:17–22:20 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `5f46410`. Step 6 produced three commits:
  - `55a23b5` — LangGraph workflow skeleton, API endpoints, tests, Docker/compose updates
  - `d4813ca` — apply black formatting to workflow.py
  - this Stage 7 progress entry is committed on top.
- **Modified files:**
  - Added: `apps/orchestrator/src/workflow.py`, `tests/test_orchestrator_workflow.py`, `tests/test_orchestrator_api.py`, `.dockerignore`
  - Modified: `apps/orchestrator/src/main.py`, `apps/orchestrator/requirements.txt`, `apps/orchestrator/Dockerfile`, `infra/docker-compose/docker-compose.yml`, `pyproject.toml`, `requirements.txt`, `scripts/check_runtime_state.sh`, `scripts/run_tests.sh`, `README.md`, `source/progress.md`
  - Deleted: none
- **Deployment target:** test server `10.0.1.31` — orchestrator workflow validation (no production resources; no production action executed).
- **WorkflowState schema:** TypedDict with 12 fields — `task_id`, `source`, `request`, `stage`, `artifacts`, `assigned_agents`, `approval_required`, `approval_status`, `retry_count`, `audit_refs`, `risk_level`, `execution_result`.
- **LangGraph nodes:** `intake → requirement → policy → approval → audit → final` (6 nodes; linear graph compiled via `langgraph` 1.2.0).
- **API endpoints:** `GET /health`, `POST /workflow/test`, `POST /workflow/policy-test`, `GET /workflow/schema`.
- **Unit/API test results:** `pytest` — **34 passed** (22 SDK/model tests + 12 new orchestrator tests). `ruff` — all checks passed. `black --check` — all 23 files clean. `mypy` — success, no issues in 14 source files.
- **Docker rebuild result:** orchestrator image rebuilt from the repo-root build context (so the `shared` package is importable in the container); `langgraph` 1.2.0 and dependencies installed; container recreated and healthy.
- **Runtime smoke test result** (`check_runtime_state.sh`): 4 containers Up; 8 PostgreSQL tables; 9 Redis streams / 10 groups; `/health` OK; `/workflow/schema` returns all 12 fields; NON_PROD_SMOKE PASS; PROD_APPROVAL_SMOKE PASS.
- **Policy / approval behavior:**
  - `/workflow/test` non-production (`dev.test`) → `stage: completed`, `approval_required: false`, `production_executed: false`.
  - `/workflow/test` `production.deploy` → `stage: waiting_approval`, `approval_required: true`, `approval_status: pending`, `risk_level: high`, `execution_result: blocked_pending_approval`, `production_executed: false`. **No production action was executed.**
- **Audit stream publish result:** `stream.audit` grew from 0 to 10 entries during verification — the workflow `audit_node` published audit events for both the non-production and the production.deploy runs. (Audit events carry task_id / agent / decision / summary only; no secrets or tokens.)
- **Issues & blockers:** none outstanding.
- **Risks / notes:**
  - The first test run flagged `workflow.py` via `black --check` (one dict line at 101 chars); fixed in commit `d4813ca` and re-verified fully green. `pytest`, `ruff`, and `mypy` passed from the first run.
  - The orchestrator build context is now the repository root; `.dockerignore` excludes `.venv`, caches, and `.git` from the image.
  - The workflow skeleton performs no LLM calls, no GitHub/Slack calls, and no production actions; `production.deploy` only reaches `waiting_approval`.
  - PostgreSQL `trust` auth, Vault dev mode, and the placeholder `DATABASE_URL` remain local/test-only.
- **Next-step suggestions:**
  1. Implement real approval handling (consume `stream.approvals` and resume the workflow).
  2. Connect the workflow to PostgreSQL (persist `workflow_states` rows).
  3. Implement concrete agents and dispatch tasks over the Redis Streams event bus.

---

## Stage 8 — Approval / Policy / Audit Service Split (Step 7)

- **Execution time:** 2026-05-22 09:55–10:09 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `f808124`. Step 7 produced two commits:
  - `a242ea95ff615297ec7119970ca6f4a0d90a1214` — governance service split, HTTP
    clients, orchestrator integration, migration, compose, tests, scripts, README
  - this Stage 8 progress entry is committed on top.
- **Modified files:**
  - Added: `apps/policy-engine/{src/main.py,Dockerfile,requirements.txt}`,
    `apps/approval-engine/{src/main.py,Dockerfile,requirements.txt}`,
    `apps/audit-service/{src/main.py,Dockerfile,requirements.txt}`,
    `shared/sdk/http_clients/{__init__.py,policy_http_client.py,approval_http_client.py,audit_http_client.py}`,
    `migrations/002_governance_tables.sql`,
    `tests/{conftest.py,test_policy_engine.py,test_approval_engine.py,test_audit_service.py,test_orchestrator_service_integration.py}`
  - Modified: `apps/orchestrator/src/{workflow.py,main.py}`,
    `apps/orchestrator/requirements.txt`, `infra/docker-compose/docker-compose.yml`,
    `requirements.txt`, `scripts/check_runtime_state.sh`,
    `scripts/init_local_runtime.sh`, `tests/{test_orchestrator_workflow.py,test_orchestrator_api.py}`,
    `README.md`, `source/progress.md`
  - Deleted: `apps/policy-engine/.gitkeep`, `apps/approval-engine/.gitkeep`,
    `apps/audit-service/.gitkeep`
- **Deployment target:** test server `10.0.1.31` — governance service validation
  (no production resources; no production action executed).
- **Service ports:** orchestrator `8000`, policy-engine `8001`, approval-engine
  `8002`, audit-service `8003` — all bound to `127.0.0.1`.
- **Service integration result:** the orchestrator workflow no longer uses local
  mock logic — `policy`, `approval`, and `audit` nodes call the governance
  services over HTTP via `PolicyHttpClient` / `ApprovalHttpClient` /
  `AuditHttpClient` (URLs from `POLICY_ENGINE_URL` / `APPROVAL_ENGINE_URL` /
  `AUDIT_SERVICE_URL`, localhost fallback). Verified end-to-end: the
  `production.deploy` smoke run created an `approval_requests` row with
  `requested_by = orchestrator` and an `audit_logs` row with `agent = orchestrator`.
- **PostgreSQL persistence result:** `migrations/002_governance_tables.sql` applied
  (11 × `ALTER TABLE`, 2 × `CREATE INDEX`) — idempotent, re-run safe. After
  verification: `approval_requests` = 11 rows, `audit_logs` = 15 rows.
  `production.deploy` task `step7-prod-001` persisted as
  `action = production.deploy`, `risk_level = high`, `status = pending`.
- **Redis stream result:** `stream.approvals` XLEN = 14, `stream.audit` XLEN = 31.
  approval-engine publishes `approval.requested` / `approval.approved` /
  `approval.rejected`; audit-service publishes `audit.recorded`.
- **Test results:** `run_tests.sh` — `pytest` **49 passed** (1.65s); `ruff` all
  checks passed; `black --check` 35 files clean; `mypy` no issues in 18 files.
  - policy-engine (4 tests): restricted actions → `approval_required: true`,
    `risk_level: high`; non-restricted → `allowed: true`, `risk_level: low` — PASS.
  - approval-engine (6 tests): health; request create → `pending`; get; approve →
    `approved`; reject → `rejected`; unknown id → 404 — PASS.
  - audit-service (3 tests): health; event insert → query by task_id with
    `artifact_refs` round-trip; unknown task → `count: 0` — PASS.
  - orchestrator integration (3 tests): non-production routes through the live
    services to `completed`; `production.deploy` creates a queryable
    `approval_requests` row; both Redis streams grow — PASS.
- **Runtime smoke test:** `check_runtime_state.sh` — 7 containers Up
  (orchestrator/policy/approval/audit/postgres/redis healthy, vault up); governance
  `/health` all PASS; APPROVAL_SMOKE PASS (request → approve); AUDIT_SMOKE PASS
  (insert → query). Orchestrator workflow smoke:
  - `step7-dev-001` (`dev.test`) → `stage: completed`, `approval_required: false`,
    `production_executed: false`.
  - `step7-prod-001` (`production.deploy`) → `stage: waiting_approval`,
    `approval_required: true`, `approval_status: pending`,
    `approval_request_id: dbb6cdbc-…`, `risk_level: high`,
    `execution_result: blocked_pending_approval`. **No production action executed.**
- **Issues & blockers:** none — all build, migration, test, and verification steps
  passed on the first run; no fix commit was required.
- **Risks / notes:**
  - The orchestrator HTTP clients fail safe: if the policy-engine is unreachable
    the workflow requires approval; if the approval/audit services are unreachable
    it degrades to a local reference. The dependency-bound tests skip gracefully
    when their service / database / Redis is not reachable.
  - `migrations/002` relaxes the `approval_requests.task_id` foreign key to `TEXT`
    so mock/test task ids are accepted; `audit_logs.action` is made nullable.
  - PostgreSQL `trust` auth and Vault dev mode remain local/test-only choices.
  - No real LLM / GitHub / Slack calls; no secrets committed; `production.deploy`
    only reaches `waiting_approval`.
- **Next-step suggestions:**
  1. Implement approval resumption — consume `stream.approvals` so an approved
     request resumes the blocked workflow.
  2. Persist `workflow_states` rows so workflow progress survives a restart.
  3. Add a communication-gateway service and wire notifications
     (`stream.notifications`).

---

## Stage 9 — Workflow Persistence & Resume Engine (Step 8)

- **Execution time:** 2026-05-22 12:55–13:09 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `3408c0f`. Step 8 produced two commits:
  - `fddd1cb5958338ef499999c2a0f250943abf4276` — workflow persistence layer,
    resume engine, approval-resume listener, persistence/replay API, migration,
    tests, runtime checks, README
  - this Stage 9 progress entry is committed on top.
- **Modified files:**
  - Added: `shared/sdk/workflow_store/{__init__.py,store.py}`,
    `apps/orchestrator/src/resume_engine.py`,
    `migrations/003_workflow_persistence.sql`,
    `tests/{test_workflow_store.py,test_resume_engine.py,test_workflow_persistence.py,test_approval_resume_flow.py}`
  - Modified: `apps/orchestrator/src/{workflow.py,main.py}`,
    `scripts/check_runtime_state.sh`, `README.md`, `source/progress.md`
  - Deleted: none
- **Deployment target:** test server `10.0.1.31` — workflow persistence / resume
  validation (no production resources; no production action executed).
- **Workflow persistence result:** `migrations/003_workflow_persistence.sql`
  applied (9 × `ALTER TABLE`, 2 × `CREATE INDEX`) — idempotent. `WorkflowStore`
  (asyncpg) writes one row per workflow into `workflow_states`; the workflow
  creates the row at start and updates it after every node transition. Verified:
  `GET /workflow/step8-prod-001` returns the full persisted state; the `state`
  JSONB column carries the complete LangGraph state.
- **Resume engine result:** `ResumeEngine.resume_workflow` transitions an
  approved `waiting_approval` workflow to `completed` — mock-safe: only
  bookkeeping is updated (`execution_result.resumed = true`,
  `production_executed = false`); no production action runs.
  `resume_approved_workflows` reconciles `waiting_approval` workflows against the
  approval-engine on startup.
- **Replay API result:** `GET /workflow/replay/step8-prod-001` returns the
  persisted state with `executed: false` — no workflow execution is triggered.
  `GET /workflow` lists all persisted workflows; `GET /workflow/{task_id}`
  returns one.
- **Approval resume flow result:**
  - API path — `POST /workflow/resume/step8-prod-001` after approval →
    `stage: completed`, `resumed: true`, `production_executed: false`. An
    unapproved workflow returns `409`.
  - Redis path — the orchestrator opens consumer group
    `orchestrator-resume-group` on `stream.approvals` (`XREADGROUP BLOCK`, no
    polling). `step8-listener-001` was approved and the listener resumed it to
    `completed` within ~4s. The consumer group reported `entries-read: 42`,
    `pending: 0`, `lag: 0` — every approval event consumed and acked.
- **PostgreSQL workflow_states query:** 34 rows. `step8-prod-001` and
  `step8-listener-001` → `completed / approved`; `step8-dev-001` → `completed /
  not_required`; `smoke-prod` → `waiting_approval / pending`.
- **Redis approval event handling:** `stream.approvals` XLEN = 42,
  `stream.audit` XLEN = 69. Consumer group `orchestrator-resume-group` active
  with 1 consumer, fully caught up.
- **Restart survivability result:** `docker compose restart orchestrator` —
  orchestrator healthy after restart; `GET /workflow/replay/step8-prod-001` and
  `GET /workflow/replay/step8-listener-001` both still return the full persisted
  state. Workflow state is held in PostgreSQL, so nothing is lost on restart.
- **Test results:** `run_tests.sh` — `pytest` **69 passed** (5.61s); `ruff` all
  checks passed; `black --check` 42 files clean; `mypy` no issues in 20 files.
  - workflow store (5 tests): create/get/update/list/filter; append_artifact /
    append_audit_ref — PASS.
  - resume engine (6 tests): replay; unapproved/unknown → `ResumeError`;
    approved → `completed`; `on_approval_event` approved/rejected — PASS.
  - workflow persistence (4 tests): non-production and `waiting_approval`
    workflows persisted; full state stored; replay matches — PASS.
  - approval resume flow (5 tests): `on_approval_event` approve/reject; resume
    API rejects unapproved (409) and resumes approved; Redis listener resumes
    after approval — PASS.
- **Runtime smoke test:** `check_runtime_state.sh` — 7 containers Up;
  WORKFLOW_PERSISTENCE_SMOKE / WORKFLOW_REPLAY_SMOKE / APPROVAL_RESUME_SMOKE all
  PASS, alongside the existing health / approval / audit smoke tests.
- **Issues & blockers:** none — all build, migration, test, and verification
  steps passed on the first run; no fix commit was required.
- **Risks / notes:**
  - Persistence is best-effort inside the workflow: a database outage is logged
    and swallowed so the workflow still runs; resume/replay then require the
    database and surface `503` when it is unreachable.
  - Resume is mock-safe — a resumed `production.deploy` reaches `completed` with
    `production_executed: false`; no production action is ever executed.
  - The approval listener uses a Redis consumer group (`XREADGROUP BLOCK`); the
    startup scan recovers approvals that landed before the group existed.
  - PostgreSQL `trust` auth and Vault dev mode remain local/test-only.
- **Next-step suggestions:**
  1. Add a communication-gateway service and emit notifications on resume /
     reject (`stream.notifications`).
  2. Implement concrete agents that consume `stream.tasks` and report progress.
  3. Add workflow retry / failure handling and persist `retry_count`
     transitions.

---

## Stage 10 — Communication Gateway & Notification Flow (Step 9)

- **Execution time:** 2026-05-22 13:18–13:30 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `7bc219d`. Step 9 produced two commits:
  - `85292184040406f8a573242cd71457437aaacd67` — communication-gateway service,
    notification client, orchestrator notification publishing, docker-compose,
    tests, runtime checks, README
  - this Stage 10 progress entry is committed on top.
- **Modified files:**
  - Added: `apps/communication-gateway/{src/main.py,Dockerfile,requirements.txt}`,
    `shared/sdk/notifications/{__init__.py,client.py}`,
    `tests/{test_notification_client.py,test_communication_gateway.py,test_notification_flow.py}`
  - Modified: `apps/orchestrator/src/{workflow.py,resume_engine.py}`,
    `infra/docker-compose/docker-compose.yml`, `tests/conftest.py`,
    `scripts/check_runtime_state.sh`, `README.md`, `source/progress.md`
  - Deleted: `apps/communication-gateway/.gitkeep`
- **Deployment target:** test server `10.0.1.31` — communication-gateway /
  notification validation (no production resources; no production action executed).
- **Service ports:** orchestrator `8000`, policy-engine `8001`, approval-engine
  `8002`, audit-service `8003`, communication-gateway `8004` — all bound to
  `127.0.0.1`.
- **Service integration result:** `communication-gateway` (port 8004) is the
  entry point for mock intake and notifications. `POST /intake/mock` forwards to
  the orchestrator `POST /workflow/test`; `GET /tasks/{task_id}` proxies the
  orchestrator `GET /workflow/{task_id}`. The `ORCHESTRATOR_URL` and `REDIS_URL`
  are read from the environment. No real Slack / Discord / Telegram / GitHub /
  LLM calls are made.
- **Notification stream result:** notifications are published to the
  `stream.notifications` Redis stream via `NotificationClient`
  (`shared/sdk/notifications/client.py`). After verification `stream.notifications`
  XLEN = 47. Each notification carries `task_id`, `event_type`, `message`,
  `created_at`. `GET /notifications` reads recent entries with `XREVRANGE`.
- **Mock intake result:**
  - `/intake/mock` non-production (`step9-dev-001`, `dev.test`) → `stage:
    completed`, `approval_required: false`, `production_executed: false`.
  - `/intake/mock` `production.deploy` (`step9-prod-001`) → `stage:
    waiting_approval`, `approval_required: true`, `production_executed: false`.
    **No production action executed.**
  - `GET /tasks/step9-prod-001` returned the persisted workflow state.
- **Production approval notification result:** the orchestrator publishes a
  notification at every workflow outcome — verified `workflow.completed`
  (`step9-dev-001`), `workflow.waiting_approval` (`step9-prod-001`),
  `workflow.resumed` and `workflow.rejected` (resume-engine paths) all present in
  `stream.notifications`.
- **Test results:** `run_tests.sh` — `pytest` **80 passed** (6.45s); `ruff` all
  checks passed; `black --check` 48 files clean; `mypy` no issues in 22 files.
  - notification client (3 tests): build / publish+list / `send_notification`
    helper — PASS.
  - communication gateway (5 tests): health; mock intake non-production and
    `production.deploy`; `/tasks/{id}`; `/notifications/test` + `/notifications`
    — PASS.
  - notification flow (3 tests): intake completion publishes
    `workflow.completed`; `production.deploy` publishes `workflow.waiting_approval`
    with `production_executed: false`; `/notifications/test` reaches the stream —
    PASS.
- **Runtime smoke test:** `check_runtime_state.sh` — 8 containers Up;
  communication-gateway HEALTH PASS; INTAKE_NONPROD_SMOKE / INTAKE_PROD_SMOKE /
  NOTIFICATIONS_SMOKE all PASS, alongside the existing health / approval / audit /
  persistence / replay / resume smoke tests.
- **Issues & blockers:** none — all build, test, and verification steps passed on
  the first run; no fix commit was required.
- **Risks / notes:**
  - The communication-gateway is a mock entry point — it performs no real
    external messaging; `/notifications` only reads a Redis stream.
  - Notification publishing from the orchestrator is best-effort: a Redis outage
    is swallowed so the workflow still completes.
  - `production.deploy` continues to stop at `waiting_approval`; no production
    action is executed anywhere in the intake → notification path.
  - PostgreSQL `trust` auth and Vault dev mode remain local/test-only.
- **Next-step suggestions:**
  1. Implement concrete agents that consume `stream.tasks` and report progress
     back through the event bus.
  2. Add a notification consumer that turns `stream.notifications` events into
     real channel deliveries (Slack / Discord / Telegram) behind a feature flag.
  3. Add workflow retry / failure handling and persist `retry_count` transitions.

---

## Stage 11 — Concrete Agents: Intake Agent & Requirement Agent (Step 10)

- **Execution time:** 2026-05-22 13:43–13:55 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `d0e280b`. Step 10 produced two commits:
  - `bd6b34b0d31e02ae80a40978abfe0c91211950ca` — intake-agent and requirement-agent
    services, stream pipeline, gateway publish_to_stream, docker-compose, tests,
    runtime checks, README
  - this Stage 11 progress entry is committed on top.
- **Modified files:**
  - Added: `agents/intake-agent/{src/agent.py,src/main.py,Dockerfile,requirements.txt}`,
    `agents/requirement-agent/{src/agent.py,src/main.py,Dockerfile,requirements.txt}`,
    `tests/{test_intake_agent.py,test_requirement_agent.py,test_agent_stream_flow.py}`
  - Modified: `apps/communication-gateway/src/main.py`,
    `infra/docker-compose/docker-compose.yml`, `tests/conftest.py`,
    `scripts/check_runtime_state.sh`, `README.md`, `source/progress.md`
  - Deleted: `agents/intake-agent/.gitkeep`, `agents/requirement-agent/.gitkeep`
- **Deployment target:** test server `10.0.1.31` — agent stream-pipeline
  validation (no production resources; no production action executed).
- **Agent ports:** intake-agent `8010`, requirement-agent `8011` — both bound to
  `127.0.0.1`. (Platform services remain `8000`–`8004`.)
- **Agent service result:** both agents are standalone FastAPI services that
  subclass the shared `BaseAgent`, run a Redis Streams consumer-group loop in
  their lifespan, and expose `GET /health` and `GET /status`. After the flow run
  each agent's `/status` reported `running: true` with the processed count and
  the last task id (`step10-flow-001`).
- **Redis stream flow result:** verified end-to-end —
  `stream.tasks → intake-agent → stream.requirements → requirement-agent →
  stream.development`. For `step10-flow-001`: `stream.requirements` carried a
  `task.intake_completed` event (`normalized_by: intake-agent`);
  `stream.development` carried a `requirement.completed` event with a
  `requirement_spec` artifact (`produced_by: requirement-agent`). The chain
  reached `stream.development` within ~2s.
- **Audit / notification result:** both agents wrote to `stream.audit` —
  `intake-agent` (`decision_type: intake`) and `requirement-agent`
  (`decision_type: requirement`) — and published to `stream.notifications` —
  `agent.intake_completed` and `requirement.completed`. Final stream lengths:
  `stream.tasks` 5, `stream.requirements` 5, `stream.development` 5,
  `stream.audit` 159, `stream.notifications` 101.
- **Test results:** `run_tests.sh` — `pytest` **91 passed** (8.74s); `ruff` all
  checks passed; `black --check` 55 files clean; `mypy` no issues in 22 files.
  - intake-agent (4 tests): health; status; `receive_task` normalization;
    `analyze` request-type extraction — PASS.
  - requirement-agent (4 tests): health; status; `receive_task`; `analyze`
    summary — PASS.
  - agent stream flow (3 tests): intake-agent forwards to `stream.requirements`;
    requirement-agent emits `requirement.completed` to `stream.development`;
    both agents write audit events and publish notifications — PASS.
- **Runtime smoke test:** `check_runtime_state.sh` — 10 containers Up; intake-agent
  and requirement-agent HEALTH PASS; AGENT_STREAM_FLOW_SMOKE PASS
  (`stream.requirements` and `stream.development` both grew), alongside the
  existing health / approval / audit / persistence / replay / resume / gateway /
  notification smoke tests.
- **Issues & blockers:** none — all build, test, and verification steps passed on
  the first run; no fix commit was required.
- **Risks / notes:**
  - The agents perform no LLM / GitHub / Slack calls; the `requirement_spec` is a
    mock artifact (`mock: true`). No production action is executed.
  - Each agent runs a Redis consumer group (`XREADGROUP BLOCK`) — no polling; a
    bad message is logged and skipped so the loop keeps running.
  - The communication-gateway `/intake/mock` keeps its default orchestrator mode;
    `publish_to_stream: true` is opt-in for the agent pipeline.
  - PostgreSQL `trust` auth and Vault dev mode remain local/test-only.
- **Next-step suggestions:**
  1. Add the development / QA / DevOps agents to extend the pipeline
     (`stream.development → stream.qa → stream.deployments`).
  2. Wire the orchestrator workflow to dispatch real tasks onto `stream.tasks`
     instead of running every stage in-process.
  3. Persist agent executions to the `agent_executions` table for traceability.

---

## Stage 12 — Agent Execution Persistence & Development / QA / DevOps Pipeline (Step 11)

- **Execution time:** 2026-05-22 14:10–14:22 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `977c53d`. Step 11 produced two commits:
  - `6dbfd8458ea17c3bc4f8213ea539dd5c35402df3` — agent execution persistence,
    StreamAgent base, development/QA/DevOps agents, migration, gateway endpoint,
    compose, tests, runtime checks, README
  - this Stage 12 progress entry is committed on top.
- **Modified files:**
  - Added: `migrations/004_agent_execution_persistence.sql`,
    `shared/sdk/agent_execution/{__init__.py,store.py}`,
    `shared/sdk/base_agent/stream_agent.py`,
    `agents/development-agent/`, `agents/qa-agent/`, `agents/devops-agent/`
    (each `src/agent.py`, `src/main.py`, `Dockerfile`, `requirements.txt`),
    `tests/{test_agent_execution_store.py,test_development_agent.py,test_qa_agent.py,test_devops_agent.py,test_full_agent_pipeline.py}`
  - Modified: `agents/intake-agent/{src/agent.py,requirements.txt}`,
    `agents/requirement-agent/{src/agent.py,requirements.txt}`,
    `apps/communication-gateway/{src/main.py,requirements.txt}`,
    `infra/docker-compose/docker-compose.yml`, `tests/conftest.py`,
    `tests/{test_intake_agent.py,test_requirement_agent.py}`,
    `scripts/check_runtime_state.sh`, `README.md`, `source/progress.md`
  - Deleted: `agents/qa-agent/.gitkeep`, `agents/devops-agent/.gitkeep`
- **Deployment target:** test server `10.0.1.31` — agent pipeline + execution
  persistence validation (no production resources; no production deploy executed).
- **Agent ports:** intake-agent `8010`, requirement-agent `8011`,
  development-agent `8012`, qa-agent `8013`, devops-agent `8014` — all bound to
  `127.0.0.1`.
- **Agent service result:** intake-agent and requirement-agent were refactored
  onto the new shared `StreamAgent` base; development-agent, qa-agent, and
  devops-agent were added. All five subclass `StreamAgent` (a `BaseAgent`), run a
  Redis consumer-group loop, and expose `GET /health` and `GET /status`. After
  the pipeline run each `/status` reported `running: true`, `failed_count: 0`,
  and the last task id.
- **Redis stream flow result:** verified end-to-end —
  `stream.tasks → intake-agent → stream.requirements → requirement-agent →
  stream.development → development-agent → stream.qa → qa-agent →
  stream.deployments → devops-agent`. Task `step11-flow-001` reached
  `stream.deployments` within ~2s. Final stream lengths: tasks / requirements /
  development / qa / deployments all 13; `stream.audit` 253;
  `stream.notifications` 200.
- **Execution persistence result:** `migrations/004_agent_execution_persistence.sql`
  applied (idempotent). `AgentExecutionStore` (asyncpg) records one
  `agent_executions` row per message. For `step11-flow-001` all five agents
  (intake / requirement / development / qa / devops) have a `completed` row with
  `started_at` and `completed_at` set. `GET /executions?task_id=step11-flow-001`
  returned 5 executions; `GET /executions?agent=devops-agent&status=completed`
  filtered correctly.
- **Deployment mock result:** the devops-agent wrote one `deployment_records`
  row for `step11-flow-001` — `environment: test`, `status: simulated`,
  `production_executed: false`, `mock: true`. **No production deployment was
  performed and no Kubernetes / cloud / GitHub API was called.**
- **Audit / notification result:** every agent wrote an audit event to
  `stream.audit` and published a notification to `stream.notifications`
  (`agent.intake_completed`, `requirement.completed`, `development.completed`,
  `qa.completed`, `devops.deployment_simulated`).
- **Test results:** `run_tests.sh` — `pytest` **106 passed** (12.99s); `ruff`
  all checks passed; `black --check` 69 files clean; `mypy` no issues in 25 files.
  - agent execution store (5 tests): create / complete / fail / update+get /
    list with filters — PASS.
  - development / qa / devops agents (3 tests each): health; status; the mock
    artifact builder — PASS.
  - full agent pipeline (3 tests): task reaches `stream.qa` and
    `stream.deployments`; all five agents record `completed` executions; the
    devops execution metadata is mock-safe (`production_executed: false`) — PASS.
- **Runtime smoke test:** `check_runtime_state.sh` — 13 containers Up; all five
  agents HEALTH PASS; FULL_PIPELINE_SMOKE PASS; AGENT_EXECUTIONS_SMOKE PASS
  (5 completed rows); DEPLOYMENT_RECORD_SMOKE PASS — alongside the existing
  health / approval / audit / persistence / replay / resume / gateway /
  notification smoke tests.
- **Issues & blockers:** none — all build, migration, test, and verification
  steps passed on the first run; no fix commit was required.
- **Risks / notes:**
  - The agents make no LLM / GitHub / Slack / Kubernetes / cloud calls; every
    artifact (`code_change`, `test_report`, `deployment_record`) is a mock
    (`mock: true`). The devops-agent never deploys to production.
  - Execution / audit / notification writes are best-effort: a database or Redis
    outage is swallowed so the consumer loop keeps running.
  - PostgreSQL `trust` auth and Vault dev mode remain local/test-only.
- **Next-step suggestions:**
  1. Wire the orchestrator workflow to dispatch real tasks onto `stream.tasks`
     so the LangGraph workflow and the agent pipeline are one flow.
  2. Add retry / dead-letter handling for messages an agent fails to process.
  3. Surface `agent_executions` and `deployment_records` in an observability
     dashboard or a consolidated status endpoint.

---

## Stage 13 — Orchestrator-to-Agent Unified Workflow Dispatch (Step 12)

- **Execution time:** 2026-05-24 07:59–08:02 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `2bbf8f7`. Step 12 produces
  two commits:
  - `f61cdd805e2c5da3448333549d344aa76bae7bcf` — orchestrator dispatch refactor,
    workflow event consumer, progress API, event correlation, dead-letter
    foundation, 4 new test files, 8 updated test files, runtime scripts, README
  - this Stage 13 progress entry is committed on top.
- **Modified files:**
  - Added: `apps/orchestrator/src/{dispatch.py,progress.py,workflow_events.py}`,
    `tests/{test_orchestrator_dispatch.py,test_workflow_progress.py,test_event_correlation.py,test_deadletter_foundation.py}`
  - Modified: `apps/orchestrator/src/{main.py,workflow.py,resume_engine.py}`,
    `shared/sdk/event_bus/redis_streams.py`,
    `shared/sdk/base_agent/stream_agent.py`,
    `agents/{intake-agent,requirement-agent,development-agent,qa-agent,devops-agent}/src/agent.py`,
    `scripts/{check_runtime_state.sh,init_redis_streams.sh}`,
    `tests/{test_orchestrator_workflow.py,test_orchestrator_api.py,test_workflow_persistence.py,test_orchestrator_service_integration.py,test_notification_flow.py,test_resume_engine.py,test_approval_resume_flow.py,test_communication_gateway.py}`,
    `README.md`, `source/progress.md`
- **Deployment target:** test server `10.0.1.31` — unified dispatch + agent
  pipeline + progress / correlation / dead-letter validation. **No production
  resources were created and no production deployment was executed.**
- **Workflow dispatch result:** the orchestrator workflow's terminal node is
  now `dispatch_node` (`apps/orchestrator/src/workflow.py`). It publishes
  `task.created` (`task_id`, `workflow_id`, `request`, `source`,
  `requested_at`) to `stream.tasks` and sets `stage: dispatched`,
  `execution_result.status: awaiting_agents`. The smoke responses confirm it:
  `smoke-dev` reached `stage: dispatched` with
  `execution_result.dispatched: true, production_executed: false, mock: true`;
  `smoke-prod` (production.deploy) stayed at `waiting_approval` with
  `execution_result.dispatched: false` — **a restricted action is not
  dispatched until it is approved**. An approved restricted action is
  dispatched by the resume engine (`smoke-resume-3896681` reached
  `stage: completed` via the agent pipeline after the approval listener
  resumed it).
- **Agent completion integration:** the orchestrator opens a Redis consumer
  group `orchestrator-workflow-group` on `stream.development`, `stream.qa`,
  `stream.deployments`, and `stream.devops`
  (`apps/orchestrator/src/workflow_events.py`).
  `requirement.completed` / `development.completed` / `qa.completed` move the
  workflow to `in_progress`; `devops.deployment_simulated` moves it to
  `completed` and writes `deployment_record_id` into `execution_result`. End
  to end: `smoke-e2e-3896681` went
  `gateway → /workflow/test → dispatched → agent pipeline →
  devops.deployment_simulated → workflow.stage: completed`, with
  `deployment_record_id: 14f74894-972f-4d42-bbad-ed57a5849c71`.
- **Workflow progress result:** `GET /workflow/progress/{task_id}` returns
  `current_stage`, `completed_agents`, `pending_agents`, `failed_agents`,
  `execution_status` (`waiting_approval` / `dispatched` / `in_progress` /
  `completed` / `failed`), `approval_status`, `workflow_id`, and timestamps
  including per-agent `started_at`/`completed_at`
  (`apps/orchestrator/src/progress.py`). PROGRESS_API_SMOKE for
  `smoke-e2e-3896681` returned `execution_status: completed`,
  `completed_agents: [intake-agent, requirement-agent, development-agent,
  qa-agent, devops-agent]`, `pending_agents: []`.
- **Event correlation result:** every pipeline message carries `task_id` **and**
  `workflow_id` via `StreamAgent.correlation_ids`. The persisted state for
  `smoke-e2e-3896681` carries `workflow_id: wf-d13dba799e01`, the
  `devops.deployment_simulated` event in `stream.devops` carries the same
  workflow_id, and the deployment_records `metadata` JSONB carries it too.
- **Dead-letter foundation result:** `shared/sdk/event_bus/redis_streams.py`
  adds `retry_count` / `max_retries` metadata, `with_incremented_retry`,
  `is_retry_exhausted`, `build_dead_letter_event`, and `publish_dead_letter`.
  `StreamAgent._handle_failure` re-publishes a failed message with
  `retry_count + 1`; once `retry_count >= max_retries` it routes the event to
  `stream.deadletter` instead. DEADLETTER_SMOKE grew `stream.deadletter` from
  2 to 3.
- **Deployment correlation result:** the devops-agent's
  `_persist_deployment_record` now `INSERT ... RETURNING id`; the
  `devops.deployment_simulated` event carries `deployment_record_id` and
  `workflow_id`; the orchestrator's workflow-event consumer persists the
  `deployment_record_id` into `workflow_states.execution_result`
  (`smoke-e2e-3896681` ended with
  `execution_result.deployment_record_id: 14f74894-972f-4d42-bbad-ed57a5849c71`).
- **Test results:** `run_tests.sh` on the server — `pytest` **128 passed**
  (20.11s); `ruff check` all checks passed; `black --check` 76 files clean;
  `mypy shared/` no issues in 25 source files.
  - New pytest files: `test_orchestrator_dispatch.py` (3 tests: non-prod
    publishes `task.created`; production.deploy is not dispatched without
    approval; approved production.deploy is dispatched);
    `test_workflow_progress.py` (8 tests: 6 pure unit tests for
    `build_progress` + 2 API tests); `test_event_correlation.py` (3 tests:
    2 pure unit tests + 1 end-to-end workflow_id propagation);
    `test_deadletter_foundation.py` (8 tests: 5 pure unit tests +
    `publish_dead_letter` integration + retry re-enqueue + exhausted-retry
    dead-letter routing).
  - Locally (Windows, no infra): 65 passed, 63 skipped, 0 failures. On the
    test server (full stack): 128 passed, 0 skipped, 0 failures.
- **Runtime smoke test:** `check_runtime_state.sh` on the server — 13
  containers Up (healthy); all health endpoints PASS; the existing
  HEALTH / NON_PROD / PROD_APPROVAL / APPROVAL / AUDIT / WORKFLOW_PERSISTENCE /
  WORKFLOW_REPLAY / APPROVAL_RESUME / INTAKE_NONPROD / INTAKE_PROD /
  NOTIFICATIONS / FULL_PIPELINE / AGENT_EXECUTIONS / DEPLOYMENT_RECORD smokes
  PASS, and the **new** DISPATCH / DISPATCH_TO_COMPLETED / PROGRESS_API /
  DEADLETTER smokes all PASS. The Redis groups list grew to include
  `orchestrator-workflow-group` on the four pipeline streams and a
  `deadletter-group` on `stream.deadletter`.
- **workflow_states query (recent):** `smoke-e2e-3896681` reached `completed`
  with `agent_progress` for all four downstream agents and
  `deployment_record_id`; `smoke-gw-prod` and `smoke-prod` stayed at
  `waiting_approval` with `dispatched: false`; `smoke-resume-3896681` reached
  `completed` (`resumed: true`, `dispatched: true`). No row records
  `production_executed: true`.
- **deployment_records correlation:** `smoke-e2e-3896681` /
  `smoke-pipeline-3896681` / `smoke-gw-dev` / `smoke-resume-3896681` /
  `smoke-persist-3896681` each have `environment=test`, `status=simulated`,
  and the `metadata` JSONB carries `task_id`, `workflow_id`, and
  `production_executed: false`. **No production deployment was performed and
  no Kubernetes / cloud / GitHub API was called.**
- **Issues & blockers:** none — all build, test, and verification steps
  passed on the first run; no fix commit was required.
- **Risks / notes:**
  - The agents make no LLM / GitHub / Slack / Kubernetes / cloud calls; every
    artifact (`requirement_spec`, `code_change`, `test_report`,
    `deployment_record`) is a mock (`mock: true`). An approved
    `production.deploy` is dispatched to the agents which only simulate the
    deployment — `production_executed: false` everywhere.
  - The retry / dead-letter foundation re-publishes a failed message to the
    same input stream up to `max_retries` times before routing it to
    `stream.deadletter`; there is no separate retry scheduler or backoff.
    Poison messages can therefore loop fast — the bound is `max_retries`
    (default 3).
  - The orchestrator's workflow-event consumer correlates events by
    `task_id`. Tasks placed on `stream.tasks` directly by the gateway's
    `publish_to_stream: true` mode have no persisted workflow row; the
    consumer ignores them (no error).
  - PostgreSQL `trust` auth and Vault dev mode remain local/test-only.
- **Next-step suggestions:**
  1. Implement a proper retry scheduler / DLQ replayer that reads
     `stream.deadletter`, inspects failures, and either re-queues or surfaces
     them in an operator view.
  2. Add tracing / metrics across the orchestrator workflow, the agent
     pipeline, and the workflow-event consumer so the unified flow has a
     single timeline view.
  3. Add a workflow cancel / abort path so a queued workflow can be stopped
     before the agents pick it up.

---

## Stage 14 — Retry Scheduler, DLQ Replayer & Workflow Cancelation (Step 13)

- **Execution time:** 2026-05-25 09:16–09:21 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `256f3fd`. Step 13 produces
  three commits:
  - `05a4e87982a119e7b9c56197eba52bc05e197dc1` — retry-scheduler service,
    DLQ replayer, orchestrator cancel/abort + ignore-after-abort,
    development-agent controlled failure, 5 new test files, 8 updated test
    files, runtime scripts, docker-compose, README.
  - `07f48f5` — smoke fix: cancel / abort smokes target `production.deploy`
    workflows so the cancel POST is not raced by the agent pipeline (the unit
    tests already covered the deterministic transitions against a seeded
    store).
  - this Stage 14 progress entry is committed on top.
- **Modified files:**
  - Added: `apps/retry-scheduler/{Dockerfile,requirements.txt,src/main.py,src/scheduler.py}`,
    `tests/{test_retry_scheduler.py,test_workflow_cancelation.py,test_workflow_abort.py,test_dlq_replay.py,test_failure_retry_flow.py}`
  - Modified: `apps/orchestrator/src/{main.py,workflow_events.py,progress.py}`,
    `shared/sdk/event_bus/redis_streams.py`,
    `shared/sdk/base_agent/stream_agent.py`,
    `agents/{requirement-agent,development-agent}/src/agent.py`,
    `infra/docker-compose/docker-compose.yml`,
    `scripts/{init_redis_streams.sh,check_runtime_state.sh}`,
    `tests/{conftest.py,test_deadletter_foundation.py}`,
    `README.md`, `source/progress.md`
- **Deployment target:** test server `10.0.1.31` — retry / DLQ /
  cancel / abort / controlled-failure validation. **No production resources
  were created and no production deployment was executed.**
- **Retry scheduler result:** `apps/retry-scheduler/` runs as a 14th service
  on `127.0.0.1:8015` (`/health: ok`). It consumes `stream.deadletter` via
  the `retry-scheduler-group` consumer group and, for each event, sleeps
  `retry_after_seconds` (capped at 60s) before re-publishing the original
  event back to `original_stream` as `event: retry.requeued`. After the smoke
  run the `/status` endpoint reported
  `running: true, input_stream: stream.deadletter, group: retry-scheduler-group,
  requeued_count: 10, terminal_failure_count: 4`. No busy polling — the
  consume loop blocks on `XREADGROUP` and each scheduled requeue is an
  `asyncio.sleep`.
- **DLQ replay result:** `GET /deadletter` (paginated by `count`) returned
  five most-recent entries, each carrying the spec-aligned fields
  `original_stream`, `failure_reason`, `retry_count`, `max_retries`,
  `retry_after_seconds`, `failed_at`, and `original_event`.
  `POST /deadletter/replay/{message_id}` republished the entry as
  `event: retry.manual_replay` to the recorded `original_stream`
  (DLQ_REPLAY_SMOKE: `replayed=True stream=test.replay.smoke before=0
  after=2`). The terminal path
  (`retry_count > max_retries`) routes to `stream.deadletter.terminal` as
  `retry.terminal_failure` instead of requeueing.
- **Workflow cancel result:** `POST /workflow/cancel/{task_id}` on a
  `production.deploy` workflow at `waiting_approval` returned
  `{"stage": "canceled", "execution_result": {"status": "canceled",
  "cancel_reason": "runtime smoke", "production_executed": false, ...}}`.
  The persisted state JSONB carries `canceled_at` and `cancel_reason`. An
  already-terminal workflow (completed / canceled / aborted / rejected) is
  refused with 409 (`test_workflow_cancelation.py::test_cancel_completed_workflow_returns_409`).
  WORKFLOW_CANCEL_SMOKE: PASS.
- **Workflow abort result:** `POST /workflow/abort/{task_id}` returned the
  same shape with `stage: aborted`, `aborted_at`, `abort_reason: "runtime
  smoke abort"`, `production_executed: false`. WORKFLOW_ABORT_SMOKE: PASS.
- **Ignored event handling result:** the orchestrator's workflow-event
  consumer checks the workflow's current stage before applying an agent
  event; if the workflow is already `aborted` or `canceled` it skips the
  update, writes an `audit_logs` row
  (`decision_type: workflow_event_ignored`), and publishes a
  `workflow.event_ignored` notification.
  `tests/test_workflow_abort.py::test_workflow_event_consumer_ignores_events_for_aborted_workflow`
  and `..._canceled_workflow` cover both branches.
- **Failure simulation result:** the development-agent honors
  `request.simulate_failure: true` and raises a `SimulatedFailure` inside
  `handle()` — the consumer loop never crashes (the
  `_handle_failure` path retries and then dead-letters). End to end on the
  server: `smoke-fail-$$ → in-stream retries → DLQ (retry_count=3) → retry
  scheduler requeue → another failure (retry_count=4) → DLQ → terminal_failure
  (retry_count=4 > max_retries=3)`. FAILURE_SIMULATION_SMOKE:
  `dl_retry_count=4 terminal_retry_count=4 → PASS`.
- **Deadletter query:** `stream.deadletter xlen: 17`,
  `stream.deadletter.terminal xlen: 5`. A representative entry from
  `GET /deadletter` carries `task_id: smoke-fail-1733371`,
  `workflow_id: wf-smoke-fail-1733371`,
  `original_stream: stream.development`,
  `failure_reason: development-agent simulated failure for smoke-fail-1733371
  (request.simulate_failure)`, `retry_count: 4, max_retries: 3,
  retry_after_seconds: 1.0`, and the original retry.requeued payload
  embedded in `original_event`.
- **Docker compose ps:** 14 containers Up (healthy) — postgres, redis,
  vault, policy-engine, approval-engine, audit-service, orchestrator,
  communication-gateway, intake-agent, requirement-agent, development-agent,
  qa-agent, devops-agent, **retry-scheduler** — all bound to `127.0.0.1`.
- **Test results:** `run_tests.sh` on the server — `pytest` **153 passed**
  (26.56s, 0 skipped, 0 failures); `ruff check` all checks passed;
  `black --check` 83 files clean; `mypy shared/` no issues in 25 source
  files.
  - New pytest files: `test_retry_scheduler.py` (12 tests — 5 pure unit
    tests for `_is_terminal`, `_retry_delay`, `_original_stream`,
    `_build_requeue_event`, `_build_terminal_event` + 2 TestClient tests +
    5 Redis integration tests covering requeue, terminal, list);
    `test_workflow_cancelation.py` (4 tests — cancel, unknown 404,
    completed 409, default reason);
    `test_workflow_abort.py` (4 tests — abort, unknown 404,
    event-ignored-after-aborted, event-ignored-after-canceled);
    `test_dlq_replay.py` (4 tests — list endpoint shape, 404 path,
    integration replay, unknown KeyError);
    `test_failure_retry_flow.py` (3 tests — DLQ reached, terminal_failure
    reached, retry_count progression).
  - Locally (Windows, no infra): the same suite gives the same pure-unit /
    TestClient tests pass; redis/db/service tests skip. On the server the
    full suite is green.
- **Runtime smoke test:** `check_runtime_state.sh` on the server — 14
  containers Up; **all 22 smokes PASS** (HEALTH, NON_PROD, PROD_APPROVAL,
  governance HEALTH × 3, APPROVAL, AUDIT, WORKFLOW_PERSISTENCE,
  WORKFLOW_REPLAY, APPROVAL_RESUME, communication-gateway HEALTH,
  INTAKE_NONPROD, INTAKE_PROD, NOTIFICATIONS, 5× agent HEALTH +
  retry-scheduler HEALTH, FULL_PIPELINE, AGENT_EXECUTIONS,
  DEPLOYMENT_RECORD, DISPATCH, DISPATCH_TO_COMPLETED, PROGRESS_API,
  DEADLETTER, **DLQ_LIST**, **DLQ_REPLAY**, **WORKFLOW_CANCEL**,
  **WORKFLOW_ABORT**, **FAILURE_SIMULATION**). The Redis groups list now
  shows `retry-scheduler-group` on `stream.deadletter` and a separate
  `terminal-failure-group` on `stream.deadletter.terminal`.
- **source/progress.md latest:** this Stage 14 entry. The previous
  next-step suggestion to add a retry scheduler / DLQ replayer (Stage 13)
  and the suggestion to add a workflow cancel/abort path (Stage 13) are
  now implemented and validated.
- **Issues & blockers:** the initial smoke run hit a race in the cancel /
  abort smokes — the agent pipeline drove the `dev.test` workflow to
  `completed` before the smoke's POST arrived, so cancel / abort got 409.
  Fixed in commit `07f48f5` by switching the smoke to `production.deploy`
  (which stays at `waiting_approval` indefinitely). The unit tests under
  `test_workflow_cancelation.py` and `test_workflow_abort.py` were
  unaffected because they seed the workflow row directly.
- **Risks / notes:**
  - The retry scheduler re-publishes to the original input stream
    immediately (within `retry_after_seconds`). A poison message that
    always fails will cycle through retries quickly until the scheduler
    publishes a `terminal_failure` event — work is bounded by
    `max_retries` but the system burns audit / notification / DLQ entries
    while iterating.
  - The terminal_failure event lives on its own stream
    (`stream.deadletter.terminal`) and is **not** yet consumed by the
    orchestrator. A failed workflow's `workflow_states.stage` therefore
    stays at `in_progress` (it never reaches a workflow-level `failed`
    state automatically). An operator can `POST /workflow/cancel` or
    `POST /workflow/abort` to bring it to a terminal stage.
  - The DLQ manual replay (`POST /deadletter/replay/{message_id}`) ignores
    `retry_count` — it republishes the original_event as
    `retry.manual_replay`. It is the operator's explicit recovery path; if
    the underlying defect is not yet fixed the replay will simply DLQ
    again.
  - Same as prior stages: no LLM / GitHub / Slack / Kubernetes / cloud
    calls; `production_executed: false` everywhere; PostgreSQL `trust`
    auth and Vault dev mode remain local/test-only.
- **Next-step suggestions:**
  1. Surface terminal_failure events back into `workflow_states` — when the
     scheduler emits `retry.terminal_failure` for a `task_id` that owns a
     workflow row, transition that row to `stage: failed` so the workflow
     has a clear terminal state without operator intervention.
  2. Add exponential backoff to `retry_after_seconds` and / or a retry
     policy per agent so a flaky agent does not burn its retry budget
     instantly.
  3. Provide a `/workflow/replay/{task_id}` end-to-end path that pairs a
     workflow with a DLQ replay (find the most recent DLQ entry for the
     task, edit the payload, and replay).

---

## Stage 15 — Observability, Metrics & Distributed Tracing (Step 14)

- **Execution time:** 2026-05-25 12:00–12:08 (UTC+8, Asia/Taipei)
- **Git branch / commit:** branch `main`; base commit `9b96dea`. Step 14 produces
  three commits:
  - `0d58f343b...` — observability SDK, tracing/metrics wiring in every
    service, workflow timeline, Prometheus + Grafana stack, four new test
    files.
  - `957016fa...` — runtime fix: tolerant grep on `/api/health` and
    GF_ANALYTICS_* env vars so Grafana stays offline (no grafana.com calls).
  - this Stage 15 progress entry is committed on top.
- **Modified files:**
  - Added: `shared/sdk/observability/{__init__.py,tracing.py,metrics.py,correlation.py}`,
    `apps/orchestrator/src/progress.py` updates,
    `infra/observability/{prometheus.yml,grafana/provisioning/datasources/prometheus.yml,grafana/provisioning/dashboards/dashboards.yml,grafana/dashboards/aiagents.json}`,
    `tests/{test_metrics.py,test_tracing.py,test_observability_stack.py,test_workflow_timeline.py}`
  - Modified: every service's `requirements.txt` (`prometheus_client`,
    `opentelemetry-api`, `opentelemetry-sdk`), root `requirements.txt`
    (+ exporter + 3 instrumentation packages),
    every service's `main.py` (`setup_tracing(...)` +
    `install_metrics_endpoint(app)`),
    `shared/sdk/base_agent/stream_agent.py` (correlation_ids carries
    trace_id + emits agent metrics),
    `shared/sdk/event_bus/redis_streams.py` (DEADLETTER_TOTAL),
    `shared/sdk/notifications/client.py` (NOTIFICATION_TOTAL),
    `apps/orchestrator/src/{main.py,workflow.py,dispatch.py,workflow_events.py,resume_engine.py,progress.py}`,
    `apps/retry-scheduler/src/scheduler.py` (RETRY_TOTAL),
    `infra/docker-compose/docker-compose.yml` (+ prometheus + grafana),
    `scripts/check_runtime_state.sh` (6 observability smokes),
    `tests/test_event_correlation.py` (correlation now 4 fields),
    `README.md`, `source/progress.md`
- **Deployment target:** test server `10.0.1.31` — distributed tracing,
  Prometheus / Grafana, workflow timeline validation. **No production
  resources were created and no cloud observability SaaS was contacted.**
- **Tracing result:** every service initializes OpenTelemetry tracing at
  startup (`shared/sdk/observability/tracing.py::setup_tracing`).
  `inject_trace_context` / `extract_trace_context` carry a workflow-scope
  `trace_id` (128-bit hex) and a per-stage `span_id` (64-bit hex) through
  every Redis event. Without an OTLP collector configured the SDK keeps the
  ids local — no real cloud observability SaaS is contacted. The dispatch
  event now carries `task_id`, `workflow_id`, `trace_id`, `span_id`, and
  every agent's outbound message carries the same four fields
  (`StreamAgent.correlation_ids → correlation_payload`).
- **Metrics endpoint result:** every FastAPI service exposes
  `GET /metrics` in the Prometheus text format
  (`install_metrics_endpoint(app)`).
  Orchestrator `/metrics` smoke output starts with
  `# HELP workflow_total Workflows dispatched...` and `workflow_total{status="..."}`,
  followed by `workflow_completed_total`, `workflow_failed_total`,
  `workflow_duration_seconds_bucket{...}`, `agent_execution_total{...}`,
  `agent_latency_seconds_bucket{...}`, `deadletter_total{...}`,
  `retry_total{...}`, `notification_total{...}`. METRICS_ENDPOINT_SMOKE:
  PASS.
- **Prometheus scrape result:** prometheus 2.55.1 on
  `127.0.0.1:9090`. `/api/v1/targets` lists every service with
  `health=up` — orchestrator, policy-engine, approval-engine, audit-service,
  communication-gateway, intake-agent, requirement-agent, development-agent,
  qa-agent, devops-agent, retry-scheduler. PROMETHEUS_HEALTH: PASS,
  PROMETHEUS_TARGETS_SMOKE: PASS. `/api/v1/query?query=sum(workflow_total)`
  returns a value > 0 after the runtime smoke completes.
- **Grafana provisioning result:** grafana 11.3.0 on `127.0.0.1:3000`.
  Anonymous Admin access enabled for the local/test runtime. The
  AI Agents SWD Platform dashboard is auto-provisioned in the
  `AI Agents SWD` folder with 8 panels (workflow totals, failed by reason,
  deadletter total, agent execution rate, agent latency p95, workflow
  duration p95, retry / deadletter activity).
  GRAFANA_HEALTH: PASS (after the regex fix in commit `957016f`).
  All four GF_ANALYTICS_* env vars are now set to false so Grafana never
  contacts grafana.com.
- **Workflow timeline result:** `GET /workflow/progress/{task_id}` now also
  returns `traces` (`{trace_id, workflow_id}`), `agent_timeline`
  (chronological per-agent `started_at` / `completed_at` / `duration_ms`),
  and `retry_timeline` (DLQ entries observed for the task). The new
  `GET /workflow/timeline/{task_id}` returns the same timelines as a
  condensed view, suitable for a dashboard. WORKFLOW_TIMELINE_SMOKE: PASS
  on the smoke task `smoke-e2e-$$` after it completed through the agent
  pipeline.
- **Trace propagation result:** the smoke published a `task.created` event
  to `stream.tasks` with `trace_id=ff...ff` and verified the matching
  `devops.deployment_simulated` event on `stream.devops` carried both
  `trace_id=[0-9a-f]{32}` and a fresh `span_id=[0-9a-f]{16}` per hop.
  TRACE_PROPAGATION_SMOKE: PASS.
- **Docker compose ps:** 16 containers Up (healthy) — postgres, redis,
  vault, policy-engine, approval-engine, audit-service, orchestrator,
  communication-gateway, intake-agent, requirement-agent, development-agent,
  qa-agent, devops-agent, retry-scheduler, **prometheus**, **grafana** —
  all bound to `127.0.0.1`.
- **Test results:** `run_tests.sh` on the server — `pytest` **183 passed**
  (26.83s, 0 skipped, 0 failures); `ruff check` all checks passed;
  `black --check` 91 files clean; `mypy shared/` no issues in 29 source
  files.
  - New pytest files: `test_metrics.py` (5 tests — metric registry,
    counter / histogram observation, /metrics endpoint shape, install
    helper); `test_tracing.py` (9 tests — `setup_tracing` idempotency,
    `generate_trace_id` / `generate_span_id` format, inject / extract
    roundtrip, parent trace_id propagation, span_id refreshed per hop);
    `test_observability_stack.py` (9 tests — Prometheus config covers all
    11 services, Grafana provisioning files exist and reference
    `prometheus:9090`, dashboard JSON references all platform metrics,
    docker-compose binds 127.0.0.1:9090 and 127.0.0.1:3000, plus 3
    skip-guarded smoke tests against the live stack);
    `test_workflow_timeline.py` (8 tests — `build_agent_timeline` ordering
    + missing timestamps, `build_retry_timeline` skips invalid entries,
    API tests via `await workflow_progress` / `await workflow_timeline`).
  - Locally (Windows, no infra): 97 passed, 85 skipped, 0 failures. On the
    test server (full stack): 183 passed, 0 skipped, 0 failures.
- **Runtime smoke test:** `check_runtime_state.sh` — 16 containers Up; **all
  33 smokes PASS** including the existing 27 from Step 13 plus the new
  **PROMETHEUS_HEALTH**, **GRAFANA_HEALTH**, **PROMETHEUS_TARGETS_SMOKE**,
  **METRICS_ENDPOINT_SMOKE**, **TRACE_PROPAGATION_SMOKE**, and
  **WORKFLOW_TIMELINE_SMOKE**.
- **source/progress.md latest:** this Stage 15 entry. The previous Stage 13
  next-step suggestion to "add tracing / metrics across the orchestrator
  workflow, the agent pipeline, and the workflow-event consumer so the
  unified flow has a single timeline view" is now implemented and
  validated.
- **Issues & blockers:** the first verification run hit two non-blocking
  glitches that were fixed in commit `957016f`:
  1. `GRAFANA_HEALTH` smoke used a no-whitespace regex
     (`"database":"ok"`); Grafana returns `"database": "ok"`. Switched to
     a tolerant POSIX regex.
  2. Grafana 11.3.0 auto-pulled the `grafana-lokiexplore-app` plugin from
     grafana.com at startup. Disabled by `GF_ANALYTICS_REPORTING_ENABLED`,
     `GF_ANALYTICS_CHECK_FOR_UPDATES`,
     `GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES`, and `GF_INSTALL_PLUGINS=""`
     — required by the "no real cloud observability SaaS" constraint.
  Both fixes were applied, pushed, and re-verified — all six observability
  smokes PASS.
- **Risks / notes:**
  - The `OTLPSpanExporter` ships in `opentelemetry-exporter-otlp` (root
    requirements only) and is conditional on
    `OTEL_EXPORTER_OTLP_ENDPOINT` being set. The local/test runtime does
    not set it, so traces are recorded in-process and dropped on flush —
    enough to validate id propagation, but not enough to view the
    distributed trace in a Tempo / Jaeger UI.
  - Grafana anonymous access (`GF_AUTH_ANONYMOUS_ENABLED: true`) is
    appropriate only for the local/test environment — never for
    production.
  - Per-service instrumentation packages (`opentelemetry-instrumentation-{fastapi,redis,asyncpg}`)
    are in the root `requirements.txt` only. Service images install
    `opentelemetry-api` / `opentelemetry-sdk` / `prometheus_client`; the
    instrumentation packages are not yet wired into the FastAPI / Redis /
    asyncpg call sites — the present coverage is the custom trace_id
    propagation through Redis events and Prometheus counters / histograms.
  - Same as prior stages: no LLM / GitHub / Slack / Kubernetes / cloud
    calls; PostgreSQL `trust` auth and Vault dev mode remain
    local/test-only.
- **Next-step suggestions:**
  1. Add a Tempo / Jaeger sidecar to the compose stack and point
     `OTEL_EXPORTER_OTLP_ENDPOINT` at it so traces render as a span graph
     in Grafana's Tempo / Traces UI.
  2. Wire the instrumentation packages (FastAPI, Redis, asyncpg) into
     each service so per-request HTTP and per-XADD Redis spans are emitted
     automatically — currently only the manual workflow / agent spans
     exist.
  3. Add alert rules (`alerts.rules.yml`) targeting `workflow_failed_total
     > N` and `agent_execution_failures_total > M`; provision an
     Alertmanager so the same operator who runs `/workflow/cancel` sees
     a Grafana alert before the failure spreads.
