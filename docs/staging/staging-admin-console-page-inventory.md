# Staging Admin Console Page Inventory (Step 64C)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Inventory of the staging Admin Console (`10.0.1.32`, `agentai-swd-stage`, commit `f43e163`).
Routes are from `apps/admin-console/src/App.tsx`; the SPA is served read-only at
`/admin/`. "Endpoint probe" is the result of a host-local `curl` against the primary backing
`/operations/*` route (200 = reachable). Pages marked "renders (deps not individually probed)"
load the SPA shell; their specific endpoints were not each probed in Step 64C.

## Expected page groups (spec §6) — all present
Overview/Dashboard, Projects/Work Items, Agent Executions, Operational Metrics, Release
Governance, Backup/DR, Production Readiness Gate, Controlled Rollout Review, Safety Posture,
Sandbox GitHub / External Integration Safety, Audit/Evidence.

## Routes
| Route | Page | Primary backing endpoint | Probe | Mutation |
|---|---|---|---|---|
| `/` | ExecutiveOverview | `/operations/summary` | **200** | read-only |
| `/projects` | Projects | `/operations/*` project reads | renders | read-only |
| `/projects/:projectId` | ProjectDetail | project detail reads | renders | read-only |
| `/task-graph` | TaskGraph | workflow/task reads | renders | read-only |
| `/design-review` | DesignReview | design review reads | renders | read-only |
| `/workspace` | WorkspaceExecution | agent execution reads | renders | read-only |
| `/mini-delivery` | MiniDeliveryPilot | delivery reads | renders | read-only |
| `/delivery-package` | DeliveryPackage | delivery package reads | renders | read-only |
| `/safety` | SafetyCenter | `/operations/safety` | **200** | read-only |
| `/regression` | RegressionStatus | regression reads | renders | read-only |
| `/cost-llm` | CostLlmGovernance | cost/LLM reads | renders | read-only |
| `/incidents` | Incidents | incident reads | renders | read-only |
| `/operator` | OperatorConsole | operator-action reads + gated POST | renders | **gated** |
| `/runtime` | RuntimeBaseline | `/operations/runtime/kubernetes/baseline` | **200** | read-only |
| `/identity` | IdentityPosture | `/operations/identity/posture` | **200** | read-only |
| `/secrets` | SecretPosture | `/operations/secrets/foundation` | **200** | read-only |
| `/security` | SecurityPosture | `/operations/security/foundation` | **200** | read-only |
| `/delivery` | MultiProjectDelivery | `/operations/delivery/*` | renders | read-only |
| `/metrics` | OperationalMetrics | `/operations/metrics/overview` | **200** | read-only |
| `/sandbox-github` | SandboxGithub | `/operations/github/sandbox-draft-pr/safety` | **200** | read-only |
| `/release-governance` | ReleaseGovernance | `/operations/release/overview` | **200** | read-only |
| `/backup-dr` | BackupDr | `/operations/dr/overview` | **200** | read-only |
| `/production-readiness` | ProductionReadiness | `/operations/readiness/overview` | **200** | read-only |
| `/controlled-rollout-review` | ControlledRolloutReview | `/operations/readiness/controlled-rollout/policy` | **200** | read-only |

## API dependency summary
- 13 read-only `/operations/*` endpoints probed on the host, **all returned 200**.
- Endpoints are GET reads; no probe mutated state.
- Mutation-capable operator flows (`/operator`, operator-review / release / rollout POSTs) are
  **gated**: operator actions are disabled in staging (`policy_blocked` /
  `operator_actions_disabled`), so no runtime/production state change is possible.

## Empty / error states
- No 5xx observed on probed endpoints. Freshly-bootstrapped staging DB means some pages will
  show **empty states** (no projects / no work items / no candidates yet) — expected; the demo
  workflow seed is Step 64D.
- `404` on non-existent sub-paths during discovery was expected (wrong guessed path), not a
  page failure.

## Safety
No public exposure; live integrations disabled/mocked; no production action;
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
