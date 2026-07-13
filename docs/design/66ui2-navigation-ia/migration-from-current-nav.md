# Migration From Current Nav — DESIGN-66UI.2

> Owner: Claude Design. Item-by-item migration from the current 28-item flat `Nav.tsx` to the new
> 7-group IA. This is the mapping Codex would follow (once authorized) to regroup the menu **without
> changing any route target**.

## Current nav (baseline)

`apps/admin-console/src/components/Nav.tsx` today = 28 flat `NavLink` items, no grouping:
`Executive Overview, Tasks, Projects, Projects/Work Items (/delivery), Agent Executions,
Workflows/Task Graph, QA/Code, Audit/Evidence, Design Review, Workspace Execution, Mini Delivery
Pilot, Delivery Package, Safety Center, Regression, Cost/LLM, Incidents, Operator Console, Runtime
Baseline, Identity Posture, Secret Posture, Security/Supply Chain, Operational Metrics, Sandbox
GitHub Draft PR, Release Governance, Backup/Restore/DR, Production Readiness Gate, Controlled
Rollout Review, Diagnostics (Demo Evidence)`.

## Migration table (existing item → new group)

| Current nav label | Route (unchanged) | New group | Disposition |
| --- | --- | --- | --- |
| Executive Overview | `/` | Overview | Becomes **Dashboard** (route preserved; label refined). |
| Tasks | `/tasks` | Team Work | Preserved; raised into Team Work group. |
| Audit / Evidence | `/audit-evidence` | Governance | Preserved; moved to Governance. |
| Safety Center | `/safety` | Governance | Preserved; moved to Governance. |
| Operator Console | `/operator` | Operator Center | Preserved. |
| Incidents | `/incidents` | Operator Center | Preserved. |
| Agent Executions | `/agent-executions` | Operator Center | Preserved. |
| Operational Metrics | `/metrics` | Platform Ops | Preserved; moved under Platform Ops. |
| Projects | `/projects` | Platform Ops | Preserved; moved under Platform Ops. |
| Projects / Work Items | `/delivery` | Platform Ops | Preserved; moved under Platform Ops. |
| Workflows / Task Graph | `/task-graph` | Platform Ops | Preserved; future read-only pipeline home (deferred). |
| QA / Code | `/qa-code` | Platform Ops | Preserved. |
| Design Review | `/design-review` | Platform Ops | Preserved. |
| Workspace Execution | `/workspace` | Platform Ops | Preserved. |
| Mini Delivery Pilot | `/mini-delivery` | Platform Ops | Preserved. |
| Delivery Package | `/delivery-package` | Platform Ops | Preserved; stays legacy evidence record (not merged into Deliveries). |
| Regression | `/regression` | Platform Ops | Preserved. |
| Cost / LLM | `/cost-llm` | Platform Ops | Preserved. |
| Runtime Baseline | `/runtime` | Platform Ops | Preserved. |
| Identity Posture | `/identity` | Platform Ops | Preserved (read-only posture). |
| Secret Posture | `/secrets` | Platform Ops | Preserved. |
| Security / Supply Chain | `/security` | Platform Ops | Preserved. |
| Sandbox GitHub Draft PR | `/sandbox-github` | Platform Ops | Preserved. |
| Release Governance | `/release-governance` | Platform Ops | Preserved. |
| Backup / Restore / DR | `/backup-dr` | Platform Ops | Preserved. |
| Production Readiness Gate | `/production-readiness` | Platform Ops | Preserved. |
| Controlled Rollout Review | `/controlled-rollout-review` | Platform Ops | Preserved. |
| Diagnostics (Demo Evidence) | `/demo-evidence` | (none) | **Removed from first-level nav**; direct-route access only. |

## New items that do not exist today (added as placeholders)

| New nav label | New group | Placeholder state |
| --- | --- | --- |
| Notifications (in-app) | Overview | in-app only; external channels Coming later |
| Reminder / Expiry (Workroom section) | Team Work | Requires Step 66C.4 |
| Delivery Inbox | Deliveries | Requires Step 66D |
| Delivery Detail | Deliveries | Requires Step 66D |
| Approvals | Operator Center | Requires Step 66D |
| DLQ / Retry | Operator Center | Requires Step 66D |
| Roles & Permissions | Settings | Requires Step 66S |
| Integrations | Settings | Coming later |
| Web Research Sources | Settings | Coming later |
| Approval Policy | Settings | Coming later |
| Identity / Session | Settings | Requires Step 66S (read-only posture exists under Platform Ops) |

## Answering the required migration questions

- **Which existing nav items move to which group:** see the migration table above — every one of the
  28 items is accounted for.
- **Which keep their existing route:** **all of them.** No route target changes in this round; this
  is a menu-grouping change only. Task Detail/Workroom remain contextual sub-routes of a task, as
  today.
- **Which need a future route:** the placeholder items above will each need a real route + page when
  their gating stage (66D / 66C.4 / 66S) ships; in round 1 they are `[new placeholder route]`
  targets pointing at compliant placeholder panels.
- **Which are just placeholders:** Notifications (in-app only), Reminder/Expiry, Delivery Inbox,
  Delivery Detail, Approvals, DLQ/Retry, and all four Settings items + Identity/Session.
- **Which should not appear at the first level:** Diagnostics (Demo Evidence) — dev-only, excluded
  from primary nav; and all contextual task sub-items (Task Detail, Task Workroom) which appear only
  once a task is opened, not as standing top-level links.

## Migration is reversible and low-risk

Because no route target or page component changes, this migration is a pure `Nav.tsx` restructure
plus new placeholder routes. It can be shipped, validated, and — if needed — reverted without
touching any business logic, backend, or existing page (`frontend-implementation-boundary.md` §2).

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
