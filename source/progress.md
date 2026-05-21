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
