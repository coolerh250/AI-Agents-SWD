# Page Grouping — DESIGN-66UI.2

> Owner: Claude Design. Every current and near-term-planned page mapped to its new group, with
> visibility level, implementation status, and dependencies. Status/visibility describe the
> *round-1 nav shell*, not future work.

## Legend

- **Visibility level:** `all` (any authenticated role) · `role-scoped` (server-side RBAC decides
  contents/access; nav item may show for all but page enforces) · `operator/admin` · `governance`.
- **Implementation status:** `active` (existing route/page, reused unchanged) · `placeholder`
  (nav item present, opens compliant placeholder panel) · `hidden` (not in first-level nav).
- Routes shown are **existing, unchanged** targets unless marked `[new placeholder route]`.

## Overview

| Page | New group | Visibility | Status | Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| Dashboard | Overview | all | active | none | Reuses/extends `ExecutiveOverview.tsx` (`/`). Team-Work-oriented summary. Merge-vs-keep relative to Operational Metrics is an open PO question (Claude Code review §6.1). |
| Notifications | Overview | role-scoped | placeholder (in-app only) | external channels future | In-app 🔔 in top bar + page. Slack/Discord/Telegram = Coming later; must not imply external send is active. |

## Team Work

| Page | New group | Visibility | Status | Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| Task List | Team Work | role-scoped | active | none | `/tasks` (`TaskList.tsx`). `GET /tasks`. |
| Create Task | Team Work | role-scoped | active | none | `/tasks/new` (`TaskNew.tsx`). |
| Task Detail | Team Work | role-scoped | active | none | `/tasks/:id` (`TaskDetail.tsx`). `GET /tasks/{id}`. Contextual (opened from Task List). |
| Task Workroom | Team Work | role-scoped | active | none | `/tasks/:id/workroom` (`TaskWorkroom.tsx`). `GET/POST /tasks/{id}/workroom/messages`. Contextual. |
| Clarifications | Team Work | role-scoped | active | none | Section within Workroom. `POST /tasks/{id}/clarifications`, `.../answer`. |
| Reminder / Expiry | Team Work | role-scoped | placeholder | **Requires Step 66C.4** | No overdue badge / expiry state with real data until 66C.4 contract exists. |

## Deliveries

| Page | New group | Visibility | Status | Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| Delivery Package | Deliveries | role-scoped | active | none | `/delivery-package` (`DeliveryPackage.tsx`). Existing delivery evidence/package record. Placed here per Product Owner decision #2; the one active item in this group. Not merged with Delivery Inbox — final integration waits for the 66D contract. |
| Delivery Inbox | Deliveries | role-scoped | placeholder `[new placeholder route]` | **Requires Step 66D** | Human-acceptance entry point for task-linked deliveries. No Accept/Reject/etc. controls in placeholder. |
| Delivery Detail | Deliveries | role-scoped | placeholder `[new placeholder route]` | **Requires Step 66D** | Delivery review workspace (future Option-2 tab). Opens from Inbox. Placeholder only. |

> **DeliveryPackage placement resolved (Product Owner decision #2).** `DeliveryPackage.tsx` sits in
> the **Deliveries** group as the existing delivery evidence/package record, distinct from and
> **not merged with** the 66D Delivery Inbox/Detail. Final integration between the legacy package
> record and the 66D task-linked flow waits for Claude Code's 66D API/data contract. See
> `product-owner-decision-record.md`.

## Operator Center

| Page | New group | Visibility | Status | Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| Operator Console | Operator Center | operator/admin | active | none | `/operator` (`OperatorConsole.tsx`). Existing controlled/audited mutations unchanged. |
| Incidents | Operator Center | operator/admin | active | none | `/incidents` (`Incidents.tsx`). |
| Agent Executions | Operator Center | operator/admin | active | none | `/agent-executions` (`AgentExecutions.tsx`). Agent execution health/failures. |
| Approvals | Operator Center | role-scoped (Reviewer/Approver) | placeholder `[new placeholder route]` | **Requires Step 66D** | Separate page (not a tab of Operator Console — resolved in `design-brief.md`). No approve/reject controls in placeholder. |
| DLQ / Retry | Operator Center | operator/admin | placeholder `[new placeholder route]` | **Requires Step 66D** | Separate page. No retry/replay controls in placeholder. |
| (Unified Action Center) | Operator Center | operator/admin | future (not in round 1) | **Requires 66D + 66C.4** | Aggregates DLQ + overdue + incidents + approvals. Blocked on both contracts (`codex-readiness-boundary.md` §3). |

## Governance

| Page | New group | Visibility | Status | Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| Safety Center | Governance | governance | active | none | `/safety` (`SafetyCenter.tsx`). Shows `dispatch_enabled`, `resume_dispatch_enabled`, `production_executed_true_count`, external-integration state — all server-computed. |
| Audit Evidence | Governance | governance (RBAC-restricted) | active | none | `/audit-evidence` (`AuditEvidence.tsx`). Safe metadata only; readable restricted message for denied roles; never raw body. `GET /tasks/{id}/audit-evidence`. |

## Platform Ops (grouping only — no page redesign this round)

| Page | New group | Visibility | Status | Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| Operational Metrics | Platform Ops | operator/admin | active | none | `/metrics` (`OperationalMetrics.tsx`). |
| Projects | Platform Ops | role-scoped | active | none | `/projects` (`Projects.tsx`) + Project Detail `/projects/:id`. Pre-Step-66 project model. |
| Projects / Work Items | Platform Ops | role-scoped | active | none | `/delivery` (`MultiProjectDelivery.tsx`). Legacy multi-project delivery model. |
| Workflows / Task Graph | Platform Ops | role-scoped | active | none | `/task-graph` (`TaskGraph.tsx`). Candidate future home for the read-only Lifecycle Pipeline view (deferred; needs contract). |
| QA / Code | Platform Ops | role-scoped | active | none | `/qa-code` (`QaCode.tsx`). Relationship to future Delivery Detail QA evidence to be reconciled at 66D. |
| Design Review | Platform Ops | role-scoped | active | none | `/design-review`. |
| Workspace Execution | Platform Ops | role-scoped | active | none | `/workspace`. |
| Mini Delivery Pilot | Platform Ops | role-scoped | active | none | `/mini-delivery`. |
| Regression | Platform Ops | operator/admin | active | none | `/regression`. |
| Cost / LLM | Platform Ops | operator/admin | active | none | `/cost-llm`. |
| Runtime Baseline | Platform Ops | operator/admin | active | none | `/runtime`. Read-only posture. |
| Identity Posture | Platform Ops | governance/admin | active | none | `/identity`. Read-only; real identity/session = 66S (Settings). |
| Secret Posture | Platform Ops | governance/admin | active | none | `/secrets`. Read-only; no secret values. |
| Security / Supply Chain | Platform Ops | governance/admin | active | none | `/security`. Read-only posture. |
| Sandbox GitHub Draft PR | Platform Ops | operator/admin | active | none | `/sandbox-github`. Sandbox-only; no live GitHub write. |
| Release Governance | Platform Ops | operator/admin | active | none | `/release-governance`. Read-only; production blocked. |
| Backup / Restore / DR | Platform Ops | operator/admin | active | none | `/backup-dr`. Read-only; no execute. |
| Production Readiness Gate | Platform Ops | operator/admin | active | none | `/production-readiness`. Read-only; not a production approval. |
| Controlled Rollout Review | Platform Ops | operator/admin | active | none | `/controlled-rollout-review`. Read-only go/no-go review. |

## Settings

| Page | New group | Visibility | Status | Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| Roles & Permissions | Settings | admin | placeholder `[new placeholder route]` | **Requires Step 66S** | RBAC model exists in docs; no admin UI yet. |
| Integrations | Settings | admin | placeholder `[new placeholder route]` | Coming later | GitHub/Discord/Slack/Telegram/LLM/web connectors. Must show each as not-connected/disabled; no send. |
| Web Research Sources | Settings | admin | placeholder `[new placeholder route]` | Coming later | Whitelist source management. |
| Approval Policy | Settings | admin | placeholder `[new placeholder route]` | Coming later | Policy concepts exist in docs; no UI. |
| Identity / Session | Settings | admin | placeholder `[new placeholder route]` | **Requires Step 66S** | Real identity/session/CSRF; today only read-only posture exists under Platform Ops. |

## Not in first-level nav

| Page | Disposition | Notes |
| --- | --- | --- |
| Diagnostics (Demo Evidence) | hidden | `/demo-evidence` remains reachable by direct route only; excluded from primary nav per its existing "developer diagnostic only — NOT a staging acceptance path" annotation in `Nav.tsx`. |

## Rollup

- **First-level items:** 28 flat → **7 groups**.
- **Active (existing routes preserved, regrouped):** Dashboard + 5 Team Work + 1 Deliveries
  (Delivery Package) + 3 Operator Center + 2 Governance + 19 Platform Ops ≈ **31 existing route
  targets, all unchanged**.
- **Placeholders (new placeholder routes):** Delivery Inbox, Delivery Detail, Approvals, DLQ/Retry,
  Reminder/Expiry (section), Roles & Permissions, Integrations, Web Research Sources, Approval
  Policy, Identity/Session, Notifications (in-app only).
- **Hidden:** Diagnostics (Demo Evidence).

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
