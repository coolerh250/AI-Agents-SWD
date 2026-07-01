# Staging Host Runtime Preparation Report (Step 64B.2A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **No AI Agents runtime was deployed in this stage. No `docker compose up`. No platform service started.**

Host-level runtime **preparation** of the staging target host, performed over key-based SSH
on 2026-07-01 under explicit operator authorization. This stage installs the container
runtime prerequisites only (Docker Engine + Docker Compose v2) and prepares the staging
directory. It does **not** bootstrap the AI Agents staging runtime: no orchestrator / Admin
Console / postgres / redis / vault / agent was started, no migration was run, no demo
workflow was executed.

## Target host
- **Target host:** `10.0.1.32` (hostname `agentai-swd-stage`)
- **Access method:** SSH, **key-based** (session ed25519 key `ai-agents-staging-10.0.1.32`,
  fingerprint `SHA256:pYdqIgihLdNgEfgPQ2h9sYlSc6dzO4O6xsKlmeQrwy8`). Login user `itadmin`.
- **Credential handling:** key-based only. The SSH **private key** stays on the operator
  workstation under `~/.ssh/ai-agents-staging/`; its contents are **never** printed,
  committed, or stored in the repo. **No password** was used or exposed. Passwordless `sudo`
  (already present on the host) was used for package install and service management.

## OS
- Ubuntu **24.04.4 LTS** (noble), kernel `6.8.0-124-generic`, `x86_64`.

## Installation method
- **Official Docker apt repository** (`https://download.docker.com/linux/ubuntu`, `noble`,
  `stable`, `arch=amd64`), signed by `/etc/apt/keyrings/docker.asc`.
- Packages installed: `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`,
  `docker-compose-plugin`. No unrelated packages installed. **No** Kubernetes / k3s / kind /
  ArgoCD / registry / cloud tooling installed.

## Docker version
- `Docker version 29.6.1, build 8900f1d`.

## Docker Compose version
- `Docker Compose version v5.2.0` (Compose v2 plugin — `docker compose`, not legacy
  `docker-compose`).

## Docker service state
- `systemctl is-active docker` → **active**.
- `systemctl is-enabled docker` → **enabled** (starts on boot).

## Docker group state
- `docker` group **present** (gid 988; created by the `docker-ce` package).

## itadmin docker access state
- `itadmin` **added** to the `docker` group (`usermod -aG docker itadmin`).
- Non-`sudo` `docker` access is **pending a reconnect** — the current SSH session predates the
  group change, so group membership is not yet effective in-session. `docker` currently works
  via `sudo`; a fresh SSH login (or `newgrp docker`) is required for non-`sudo` access. This is
  expected Linux group behaviour and must be noted before Step 64B.2B.

## Staging directory
- `/data` present (dedicated volume, ~93 GB free). Created **`/data/ai-agents-staging`**
  (owner `itadmin:itadmin`) as the staging volume base.

## hello-world validation result
- `docker run --rm hello-world` → **"Hello from Docker! This installation appears to be
  working correctly."** — **validation-only**; the container was removed (`--rm`) and the
  `hello-world` image was deleted afterward. This is not an AI Agents runtime deployment.

## Port 18000 state
- **Free** (no listener) — reconfirmed after installation. The Admin Console host port
  remains available for the future Step 64B.2B bring-up.

## Existing platform containers
- **None.** `docker ps -a` shows no orchestrator / postgres / redis / vault / agent / Admin
  Console container. No platform service was started in this stage.

## Remaining prerequisites (for Step 64B.2B)
See [staging-runtime-bootstrap-prerequisites-after-prep.md](staging-runtime-bootstrap-prerequisites-after-prep.md).
In summary: repo sync to the host, gitignored staging env generation, compose config
validation, volume mapping confirmation, access-mode confirmation, and operator decisions —
none performed here.

## Explicit safety statements
- **No AI Agents runtime was deployed** in this stage.
- **No `docker compose up` / `docker compose start` / platform `docker run`** was executed.
- **No production action**, no production deploy, no production sync, no production secret, no
  external write, no GitHub merge, no image push. `production_executed_true_count` remains 0.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false runtime-deployment=false docker-compose-up=false -->
