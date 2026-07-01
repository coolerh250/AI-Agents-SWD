# Staging Runtime Bootstrap Readiness (Step 64B.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **No runtime deployment was performed in this stage.**

Readiness assessment for the staging **runtime bootstrap** (Step 64B.2), based on the
authenticated host preflight of `10.0.1.32` (`agentai-swd-stage`). See
[staging-host-preflight-report.md](staging-host-preflight-report.md).

## ready_for_runtime_bootstrap: **false**
The host is reachable, sized adequately, and reachable over key-based SSH, but **Docker
Engine + Docker Compose v2 are not installed**, so the compose staging stack cannot be
brought up yet.

## Readiness summary
| Prerequisite | State |
|---|---|
| SSH key-based access (`itadmin`) | ✅ established |
| OS (Ubuntu 24.04 LTS) | ✅ supported |
| CPU (16) / RAM (7.7 GiB) / disk (`/` 43 GB, `/data` 93 GB free) | ✅ adequate |
| Passwordless sudo | ✅ available |
| Port 18000 free (Admin Console) | ✅ free |
| **Docker Engine** | ❌ not installed |
| **Docker Compose v2** | ❌ not available |
| **Docker daemon running** | ❌ inactive |
| **`itadmin` in docker group** | ❌ no docker group |
| No swap configured | ⚠️ acceptable, monitor |

## Missing prerequisites
1. Docker Engine (not installed).
2. Docker Compose v2 plugin (not available).
3. Docker daemon enabled + running.
4. `docker` group membership for `itadmin` (or use `sudo` for docker) — currently absent.

## Required operator actions (before / during Step 64B.2)
1. **Authorize Docker installation** on `10.0.1.32` (passwordless sudo is available; Step
   64B.1 performed no install). Install `docker-ce` + `docker-compose-plugin` (or distro
   `docker.io` + `docker-compose-v2`).
2. Add `itadmin` to the `docker` group (or agree to run compose via `sudo`).
3. Confirm the intended data location (`/data` has 93 GB free and is a good home for staging
   volumes).
4. Confirm the access mode for the Admin Console (SSH port-forward recommended).
5. Confirm live GitHub / Slack / LLM integrations remain disabled in staging.

## Recommended access mode
Key-based SSH (already established) + **SSH local port-forward** for the Admin Console
(`ssh -i ~/.ssh/ai-agents-staging/staging_10_0_1_32 -L 18000:127.0.0.1:18000 itadmin@10.0.1.32`),
then browse `http://localhost:18000/admin`. Keeps `18000` off the LAN.

## Recommended port exposure
Keep staging host-port bindings on loopback (`127.0.0.1`) as in
`docker-compose.staging.yml`; expose to the operator only via SSH port-forward. No inbound
LAN port opened by default.

## Recommended next stage
**Step 64B.2 — Staging Runtime Bootstrap:** after explicit operator authorization, install
the Docker prerequisites, generate the gitignored staging env, bring up
`docker-compose.staging.yml` (project `aiagents-staging`), apply migrations, and run
non-production smoke checks. That stage — not this one — performs the (non-production)
runtime bring-up. No production action; `production_executed_true_count` remains 0.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false runtime-deployment=false ready-for-runtime-bootstrap=false -->
