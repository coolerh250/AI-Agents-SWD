# Staging Admin Console Plan (Step 64A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

How the Admin Console is exposed to an operator in staging.

## Access method
Served by the orchestrator at `/admin` (Vite build mounted via `StaticFiles`, static
fallback otherwise). Staging URL: `http://10.0.1.32:18000/admin`, reached directly or via SSH
local port-forward (see [staging-access-plan.md](staging-access-plan.md)).

## Pages to expose (minimum viewable)
- Overview / Dashboard (`/`)
- Projects / Work Items (`/projects`, `/task-graph`)
- Agent Executions (`/workspace`)
- Operational Metrics (`/metrics`)
- Release Governance (`/release-governance`)
- Backup / DR (`/backup-dr`)
- Production Readiness Gate (`/production-readiness`)
- Controlled Rollout Review (`/controlled-rollout-review`)
- Safety Posture (`/safety`)

## Expected route list (current Admin Console)
`/`, `/projects`, `/projects/:id`, `/task-graph`, `/design-review`, `/workspace`,
`/mini-delivery`, `/delivery-package`, `/safety`, `/regression`, `/cost-llm`, `/incidents`,
`/operator`, `/runtime`, `/identity`, `/secrets`, `/security`, `/delivery`, `/metrics`,
`/sandbox-github`, `/release-governance`, `/backup-dr`, `/production-readiness`,
`/controlled-rollout-review`.

## API dependencies
Read-only `GET /operations/*` (admin-console / metrics / release / dr / readiness /
controlled-rollout / safety) + `/health`, all served by the orchestrator at `:18000`.

## Operator session method
Read-only pages need no session. Controlled mutations (operator console, review requests)
reuse the existing operator auth + CSRF + audit (non-production session model). No production
auth / IdP is introduced.

## Known gaps
- First demo over HTTP (no TLS) — operator to confirm acceptable.
- Operator-session bootstrap for mutation pages in staging to be confirmed in Step 64C.
- Demo data must be seeded (Step 64D) for the Projects / Agent Executions pages to show
  meaningful content.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
