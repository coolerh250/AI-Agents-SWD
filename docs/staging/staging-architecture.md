# Staging Architecture (Step 64A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

This is the architecture plan for a **rebuildable, demonstrable, operable** staging
environment for the AI Agents platform. Step 64A is **planning + inventory only** — it does
NOT deploy a staging runtime, start services, or run any production action.

## Staging target
- **Staging target host:** `10.0.1.32`
- **Access method:** SSH
- **Credential handling:** interactive only — requested from the operator at connect time,
  never stored, never committed, never printed.
- **Deployment source / repo reference:** `10.0.1.31` (current repo / source server) or
  GitHub `origin/main`, depending on the final Step 64B plan.

## Recommended architecture
**Recommended: Option A — Docker Compose Staging** (reusing the existing committed
`infra/docker-compose/docker-compose.staging.yml`, Stage 25), deployed to `10.0.1.32`.

Rationale: the platform already ships a self-contained 22-service staging compose with a
`+10000` host-port offset and isolated volumes/network. It is the fastest path to let an
administrator *see and operate* the system, is trivially rebuildable, and maps cleanly to a
deployment SOP. It is explicitly **not** production Kubernetes.

## Option comparison
| Option | Use | Pros | Cons | Rank |
|---|---|---|---|---|
| **A — Docker Compose** | Fastest operator-visible system | low effort, rebuildable, SOP-friendly, already committed | not production K8s | **1 (recommended)** |
| **B — kind / k3s** | Closer to Kubernetes runtime | validates namespace / Helm / Service / Ingress | higher build + troubleshooting cost | 2 (Step 64 later / future) |
| **C — Production-like** | Pre-production rehearsal | validates GitOps / Ingress / TLS / monitoring | needs more environment info + authorization | 3 (future, out of scope) |

## Service topology (Option A)
- **Data plane:** `postgres:16`, `redis:7`, `vault` (dev mode — staging limitation).
- **Core API:** `orchestrator` (FastAPI, container `8000` → host `18000`) — also serves the
  Admin Console static bundle at `/admin`.
- **Governance/services:** `policy-engine` (8001), `approval-engine` (8002),
  `audit-service` (8003), `communication-gateway` (8004), plus workers and agent services.
- All host bindings are offset `+10000` and bound to loopback by default.

## Network access pattern
Operator reaches the Admin Console at `http://10.0.1.32:18000/admin` either directly (if the
port is exposed on the staging host LAN) or via SSH local port-forward
(`ssh -L 18000:127.0.0.1:18000 <user>@10.0.1.32`). See
[staging-access-plan.md](staging-access-plan.md).

## Data flow
Operator → Admin Console (`/admin`, served by orchestrator) → orchestrator read-only
`/operations/*` endpoints → Postgres / Redis. Agent workflow events flow through Redis
Streams + the governance/audit services. No external write occurs by default (GitHub / Slack
/ LLM live integrations remain disabled in staging).

## Staging vs production boundary
- Staging is **non-production**. A kind cluster or this compose stack is **not** production;
  the non-production ArgoCD is **not** production ArgoCD.
- No production target, no production secret, no production deploy, no production ArgoCD sync.
- Step 62 readiness decision (`ready_for_operator_review`) and Step 63A recommendation
  (`no_go`) are unchanged; staging does not make the platform production ready.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
