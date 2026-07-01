# Staging Runtime Bootstrap Prerequisites — After Host Preparation (Step 64B.2A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **No AI Agents runtime deployed in this stage. No `docker compose up`.**

Prerequisite state for the staging **runtime bootstrap** (Step 64B.2B) *after* the Step
64B.2A host preparation on `10.0.1.32` (`agentai-swd-stage`). See
[staging-host-runtime-preparation-report.md](staging-host-runtime-preparation-report.md).

## Host runtime prerequisites — now satisfied
| Prerequisite | Before (64B.1) | After (64B.2A) |
|---|---|---|
| Docker Engine installed | ❌ absent | ✅ `29.6.1` installed |
| Docker Compose v2 plugin | ❌ absent | ✅ `v5.2.0` (`docker compose`) |
| Docker daemon running | ❌ inactive | ✅ active + enabled |
| `docker` group | ❌ none | ✅ present; `itadmin` added (effective after reconnect) |
| Staging volume base | ❌ absent | ✅ `/data/ai-agents-staging` created |
| Port 18000 free | ✅ free | ✅ free |
| CPU / RAM / disk | ✅ adequate | ✅ adequate |

**host_runtime_prerequisites_prepared: true.**

## ready_for_runtime_bootstrap: **false**
The **host container runtime** is prepared, but the full runtime bootstrap (Step 64B.2B) is
**not yet ready**: the repository is not synced to the host, the gitignored staging env is not
generated, and the compose config is not yet validated on the host. Those are Step 64B.2B
prerequisites — none was performed here, and this stage started no service.

## Remaining prerequisites (for Step 64B.2B)
1. **Repo sync** — clone / sync `origin/main` to `10.0.1.32` (e.g. `/data/ai-agents-staging`
   or a working checkout). Not done in 64B.2A.
2. **Staging env file** — generate a gitignored `.env.staging.local` via
   `scripts/generate_staging_env.sh` on the host (POSTGRES_PASSWORD etc. generated locally,
   never committed / printed). Not done in 64B.2A.
3. **Compose config validation** — `docker compose -f docker-compose.staging.yml config`
   (read-only validation, no bring-up). Not done in 64B.2A.
4. **Volume mapping** — confirm staging volumes map under `/data/ai-agents-staging`.
5. **Access mode** — SSH local port-forward `-L 18000:127.0.0.1:18000` → `http://localhost:18000/admin`.
6. **Reconnect** — reconnect so `itadmin`'s `docker` group membership is effective (or use `sudo`).

## Operator decisions still open
- Docker-group (post-reconnect) vs `sudo` for compose in 64B.2B.
- Confirm HTTP (no TLS) acceptable for the first staging demo.
- Confirm live GitHub / Slack / LLM integrations remain **disabled / mocked** in staging.
- Confirm staging data retention / teardown preference.

## Safety
No AI Agents runtime deployed; no `docker compose up`; no production action / deploy / sync /
secret; no external write; no GitHub merge; no image push. `production_executed_true_count`
remains 0. **Claude Code does not decide production readiness.**

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false runtime-deployment=false docker-compose-up=false ready-for-runtime-bootstrap=false -->
