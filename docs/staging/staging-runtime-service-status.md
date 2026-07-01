# Staging Runtime Service Status (Step 64B.2B)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Service status captured from `docker compose -p aiagents-staging … ps` on `10.0.1.32`
(`agentai-swd-stage`) shortly after the Step 64B.2B bring-up (deployed commit `f43e163`).

## Summary
- **22 / 22 containers running.** 21 report `healthy`; `vault` runs in dev mode (no
  healthcheck defined) and is `running`.

## Container states
| Service (container) | State | Health |
|---|---|---|
| orchestrator | running | healthy |
| policy-engine | running | healthy |
| approval-engine | running | healthy |
| audit-service | running | healthy |
| audit-worker | running | healthy |
| communication-gateway | running | healthy |
| github-automation | running | healthy |
| discord-gateway | running | healthy |
| notification-worker | running | healthy |
| intake-agent | running | healthy |
| requirement-agent | running | healthy |
| development-agent | running | healthy |
| qa-agent | running | healthy |
| devops-agent | running | healthy |
| retry-scheduler | running | healthy |
| postgres | running | healthy |
| redis | running | healthy |
| vault | running | dev mode (no healthcheck) |
| prometheus | running | healthy |
| grafana | running | healthy |
| alertmanager | running | healthy |
| tempo | running | healthy |

## Host port map (loopback only, `+10000` offset)
| Service | Host bind | Container port |
|---|---|---|
| orchestrator (Admin Console `/admin`) | `127.0.0.1:18000` | 8000 |
| policy-engine | `127.0.0.1:18001` | 8001 |
| approval-engine | `127.0.0.1:18002` | 8002 |
| audit-service | `127.0.0.1:18003` | 8003 |
| communication-gateway | `127.0.0.1:18004` | 8004 |
| github-automation | `127.0.0.1:18005` | 8005 |
| audit-worker | `127.0.0.1:18006` | 8006 |
| discord-gateway | `127.0.0.1:18007` | 8007 |
| notification-worker | `127.0.0.1:18008` | 8008 |
| intake/requirement/development/qa/devops-agent | `127.0.0.1:18010–18014` | 8010–8014 |
| retry-scheduler | `127.0.0.1:18015` | 8015 |
| postgres | `127.0.0.1:15432` | 5432 |
| redis | `127.0.0.1:16379` | 6379 |
| vault (dev) | `127.0.0.1:18200` | 8200 |
| prometheus | `127.0.0.1:19090` | 9090 |
| grafana | `127.0.0.1:13000` | 3000 |
| alertmanager | `127.0.0.1:19093` | 9093 |
| tempo | `127.0.0.1:13200 / 14317 / 14318` | 3200 / 4317 / 4318 |

All bindings are loopback-only; nothing is exposed on the LAN. Operator access is via SSH
local port-forward — see [staging-admin-console-access-evidence.md](staging-admin-console-access-evidence.md).

## Data / migrations
- All `migrations/*.sql` applied idempotently against the staging Postgres.
- Redis Streams consumer groups initialised; consumer services restarted after migration.

## Safety
No production action; no production secret; no external write; live integrations disabled /
mocked; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false runtime-deployment=staging-only live-integrations=disabled demo-workflow-executed=false -->
