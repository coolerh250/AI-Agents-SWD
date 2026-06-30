# Staging Service Inventory (Step 64A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Inventory of services in `infra/docker-compose/docker-compose.staging.yml` (project
`aiagents-staging`). Host ports use the `+10000` offset; internal container ports are
unchanged. **Staging target host: `10.0.1.32` · Access: SSH.** SSH credentials are
interactive only and are never stored, never committed, never printed. This is an inventory
only — no service is started in Step 64A.

| Service | Path / image | Internal port | Host port | Health | Depends on | Required for staging | Mock allowed | Notes |
|---|---|---|---|---|---|---|---|---|
| postgres | `postgres:16` | 5432 | 15432 | pg_isready | — | **yes** | no | staging password required (gitignored env) |
| redis | `redis:7` | 6379 | 16379 | redis ping | — | **yes** | no | streams + state |
| vault | `hashicorp/vault:1.17` | 8200 | 18200 | — | — | yes | yes | dev mode (staging limitation) |
| orchestrator | `apps/orchestrator` | 8000 | 18000 | `GET /health` | postgres, redis | **yes** | no | serves Admin Console at `/admin`; `/operations/*` |
| policy-engine | `services/policy-engine` | 8001 | 18001 | health | postgres | **yes** | no | governance |
| approval-engine | `services/approval-engine` | 8002 | 18002 | health | postgres | **yes** | no | approval governance |
| audit-service | `services/audit-service` | 8003 | 18003 | health | postgres | **yes** | no | audit integrity |
| communication-gateway | `services/communication-gateway` | 8004 | 18004 | health | redis | yes | partial | external sends disabled in staging |
| github-automation | `services/github-automation` | 8005 | 18005 | health | — | no | **yes** | sandbox/dry-run only; no merge/push |
| audit-worker | worker | 8006 | 18006 | — | redis | yes | no | audit stream consumer |
| discord-gateway | gateway | 8007 | 18007 | — | redis | no | **yes** | external send disabled |
| notification-worker | worker | 8008 | 18008 | — | redis | yes | partial | no external send by default |
| intake / requirement / development / qa / devops agents | agent services | 8010–8014 | 18010–18014 | — | redis, orchestrator | yes (for demo) | **yes** | LLM live disabled; mock for demo |
| project-planner / design-review / workspace-operator agents | agent services | 8016–8018 | 18016–18018 | — | orchestrator | yes (for demo) | **yes** | mockable for walkthrough |
| **Admin Console** | `apps/admin-console` (Vite build) | served by orchestrator | `18000/admin` | via orchestrator | orchestrator | **yes** | no | static bundle mounted at `/admin`; React app + static fallback |

## Known gaps
- No dedicated **demo-project seed** script yet (SaaS User Management demo) → to build in
  Step 64D (see [staging-demo-workflow-plan.md](staging-demo-workflow-plan.md)).
- Vault runs in dev mode (staging limitation; not production-grade secret storage).
- LLM / GitHub / Slack live integrations disabled → agent stages mockable for the demo.
- Whether Docker / Compose exist on `10.0.1.32` is an open prerequisite (operator to confirm;
  see [staging-information-request.md](staging-information-request.md)).

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
