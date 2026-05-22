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
