# Staging Docker Installation Notes (Step 64B.2A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Container runtime prepared only — no AI Agents runtime deployed, no `docker compose up`.**

Reproducible notes for the Docker Engine + Docker Compose v2 installation performed on the
staging target host `10.0.1.32` (`agentai-swd-stage`, Ubuntu 24.04.4 LTS) over key-based SSH,
using passwordless `sudo`. Commands are recorded for auditability; **no credential, password,
private key, token, or kubeconfig value appears here.**

## Method
Official Docker apt repository for Ubuntu (`download.docker.com`). No unrelated packages; no
Kubernetes / k3s / kind / ArgoCD / registry / cloud tooling.

## Steps performed (on 10.0.1.32)
1. **Reachability check** — `curl` of `https://download.docker.com/linux/ubuntu/gpg` → HTTP 200.
2. **Prerequisites** — `apt-get update`; `apt-get install -y ca-certificates curl`.
3. **GPG key** —
   ```
   sudo install -m 0755 -d /etc/apt/keyrings
   sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
   sudo chmod a+r /etc/apt/keyrings/docker.asc
   ```
4. **Apt source** — added `/etc/apt/sources.list.d/docker.list`:
   ```
   deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable
   ```
   then `apt-get update`.
5. **Install** —
   ```
   sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   ```
6. **Service** — `sudo systemctl enable --now docker` → active + enabled.
7. **Group** — `docker` group present (created by package); `sudo usermod -aG docker itadmin`.
8. **Staging dir** — `sudo mkdir -p /data/ai-agents-staging`; `sudo chown itadmin:itadmin /data/ai-agents-staging`.
9. **Validation** — `docker --version`; `docker compose version`; `docker ps`;
   `docker run --rm hello-world` (validation-only, image removed afterward); port 18000 recheck.

## Recorded results
| Item | Result |
|---|---|
| `docker --version` | `Docker version 29.6.1, build 8900f1d` |
| `docker compose version` | `Docker Compose version v5.2.0` |
| `systemctl is-active docker` | `active` |
| `systemctl is-enabled docker` | `enabled` |
| `docker` group | present (gid 988) |
| `itadmin` in `docker` group | yes (effective after reconnect) |
| `docker ps` | empty (no containers) |
| `docker run --rm hello-world` | "Hello from Docker!" (validation-only, image removed) |
| `/data/ai-agents-staging` | created, `itadmin:itadmin` |
| Port 18000 | free |

## Reconnect note
The current SSH session predates the `docker` group change, so non-`sudo` `docker` access is
**pending a reconnect** (fresh SSH login or `newgrp docker`). Until then, `docker` runs via
`sudo`. Step 64B.2B should reconnect before relying on non-`sudo` `docker`.

## Not done in this stage
No `docker compose up`, no platform `docker pull`/`docker run` for AI Agents services, no
orchestrator / Admin Console / postgres / redis / vault / agent, no migration, no demo
workflow, no registry login, no image push, no production action.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false runtime-deployment=false docker-compose-up=false -->
