# Staging Runtime Stop & Restart Notes (Step 64B.2B)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Operator commands to inspect, restart, and stop the staging runtime on `10.0.1.32`
(`agentai-swd-stage`, repo `/data/ai-agents-staging/AI-Agents-SWD`). The runtime was **left
running** after Step 64B.2B; these commands are documented, not executed as a teardown.

All commands run from the repo root on the host, over key-based SSH.

```bash
cd /data/ai-agents-staging/AI-Agents-SWD
COMPOSE="docker compose -p aiagents-staging -f infra/docker-compose/docker-compose.staging.yml --env-file infra/runtime/.env.staging.local"
```

## Status
```bash
$COMPOSE ps
```

## Logs (troubleshooting)
```bash
$COMPOSE logs --tail=100
$COMPOSE logs --tail=100 orchestrator
```

## Restart
```bash
$COMPOSE restart               # all services
$COMPOSE restart orchestrator  # single service
```

## Stop / start (preserve volumes + data)
```bash
$COMPOSE stop
$COMPOSE start
```

## Bring down (remove containers, KEEP volumes)
```bash
$COMPOSE down
```

Alternatively use the committed helper:
```bash
bash scripts/stop_staging_runtime.sh
```

## Bring back up
```bash
bash scripts/start_staging_runtime.sh
```

## Not authorized here
- **Do NOT run `docker compose down -v`** (that deletes staging volumes) unless the operator
  explicitly authorizes it — the staging Postgres / Redis / Grafana / Prometheus / Tempo /
  Alertmanager data volumes must be preserved.
- No production teardown; this affects only the `aiagents-staging` project on `10.0.1.32`.
- No production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false runtime-deployment=staging-only live-integrations=disabled demo-workflow-executed=false -->
