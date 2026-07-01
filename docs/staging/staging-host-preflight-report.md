# Staging Host Preflight Report (Step 64B.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **No runtime deployment was performed in this stage.**

Authenticated **read-only** inventory of the staging target host, collected over key-based
SSH on 2026-07-01. No service was started, nothing was installed, no host configuration was
changed, no production resource was created.

## Target host
- **Target host:** `10.0.1.32` (hostname `agentai-swd-stage`)
- **Access method:** SSH, **key-based** (session-generated ed25519 key
  `ai-agents-staging-10.0.1.32`, fingerprint `SHA256:pYdqIgihLdNgEfgPQ2h9sYlSc6dzO4O6xsKlmeQrwy8`).
- **Credential handling:** interactive / key-based only. The SSH **private key** stays on the
  operator workstation under `~/.ssh/ai-agents-staging/` and its contents are **never**
  printed, committed, or stored in the repo. No password was used or exposed (the
  non-interactive shell cannot use a password without leaking it). The operator installed the
  **public** key into `itadmin@10.0.1.32`'s `authorized_keys`.
- **Login user:** `itadmin` (uid 1000; member of `sudo`).

## OS
- Ubuntu **24.04.4 LTS** (noble), kernel `6.8.0-124-generic`, `x86_64`.

## CPU
- **16** logical CPUs (`nproc=16`). Load average ~0.00 (idle).

## Memory
- **7.7 GiB** total, ~6.7 GiB free, ~7.1 GiB available. **Swap: 0 B** (no swap configured).

## Disk
- `/` (`ubuntu--vg-ubuntu--lv`): **48 GB**, 43 GB available (8% used).
- `/data` (`/dev/sdb`): **98 GB**, ~93 GB available (1% used) — dedicated data volume.
- `/boot`: 1.8 GB.

## Network
- Interface `ens33`: **10.0.1.32/24**, MAC `00:0c:29:cb:56:7a`.
- Default route via **10.0.1.254** (`ens33`); local subnet `10.0.1.0/24`.

## Docker version
- **Docker: NOT INSTALLED.**

## Docker Compose version
- **Docker Compose v2: NOT AVAILABLE.**

## Docker daemon state
- **inactive** (no daemon running; `docker ps` not accessible).

## docker group access
- **`docker_group_access=false`** — `itadmin` is not in a `docker` group (none exists yet).

## sudo availability
- **`sudo_nopasswd_available=true`** — passwordless sudo is available for `itadmin`.

## Listening ports
- `tcp/22` (SSH, `0.0.0.0` + `[::]`).
- `tcp/udp 53` on `127.0.0.53` / `127.0.0.54` (systemd-resolved, loopback only).
- **No application ports listening.** The planned Admin Console port `18000` is free.

## Existing containers
- None (Docker not installed / daemon inactive).

## Risk notes
- **Prerequisite gap:** Docker Engine + Docker Compose v2 are not installed → the staging
  compose stack cannot be brought up until they are installed (Step 64B.2). No install was
  performed in this stage.
- No swap configured; 7.7 GiB RAM is adequate for the compose stack but leaves limited
  headroom under load — monitor during Step 64B.2.
- SSH `22` is exposed on `0.0.0.0`; key-based auth is in use. Prefer SSH local port-forward
  for the Admin Console (keep `18000` off the LAN) — see
  [staging-access-plan.md](staging-access-plan.md).
- `sudo` is passwordless — Step 64B.2 Docker install is possible but requires explicit
  operator authorization; Step 64B.1 performs no install.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false runtime-deployment=false -->
