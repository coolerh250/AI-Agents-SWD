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
