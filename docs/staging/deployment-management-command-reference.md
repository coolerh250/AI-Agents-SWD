# Staging Deployment Management — Command Reference (Step 64F.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Reference only — commands are not executed by this document. Destructive commands require separate explicit authorization.**

Canonical commands for the `aiagents-staging` runtime on `10.0.1.32`. Run from the repo root
`/data/ai-agents-staging/AI-Agents-SWD`. Base invocation:

```
docker compose -p aiagents-staging \
  -f infra/docker-compose/docker-compose.staging.yml \
  --env-file infra/runtime/.env.staging.local <cmd>
```

## Read-only (routine)
| Purpose | Command |
|---|---|
| Service status | `docker compose … ps` |
| Health summary | `bash scripts/check_staging_runtime.sh` |
| Health probe | `curl -fsS http://127.0.0.1:18000/health` |
| Admin index | `curl -fsSI http://127.0.0.1:18000/admin` |
| Safety posture | `curl -fsS http://127.0.0.1:18000/operations/safety` |
| Logs | `docker compose … logs --tail 200 <service>` |

## Lifecycle (authorized)
| Purpose | Command |
|---|---|
| Start stack | `bash scripts/start_staging_runtime.sh` (`--rebuild` to build first) |
| Orchestrator rebuild | `docker compose … build orchestrator` |
| Orchestrator recreate | `docker compose … up -d orchestrator` |
| Orchestrator restart | `docker compose … restart orchestrator` |
| Single service restart | `docker compose … restart <service>` |
| Orchestrator stop | `docker compose … stop orchestrator` |
| Full-stack stop (keep volumes) | `bash scripts/stop_staging_runtime.sh` |

## Destructive (separate explicit authorization required)
| Purpose | Command | Note |
|---|---|---|
| Volume-deleting teardown | `bash scripts/stop_staging_runtime.sh --volumes` | deletes the 5 staging volumes |
| Compose down with volumes | `docker compose … down -v` | **forbidden** without explicit destructive-teardown authorization |
| Full rebuild | `docker compose … build` | only for dependency/base-image change; document why |

## Never (out of scope for staging operations)
`image push`, `registry login`, production deploy/sync/secret, live GitHub write, live
Slack/Discord send, live LLM call, public port exposure, DB reset, workflow re-run.

## Notes
- **Never print `infra/runtime/.env.staging.local`** or any secret.
- Host ports are loopback + `+10000` offset; operator access is via SSH `-L
  18000:127.0.0.1:18000` then `http://localhost:18000/admin` (navigate by tabs).
- No runtime change was performed to produce this reference; no production action;
  `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
