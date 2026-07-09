# AI Agents Team Work — Frontend Page Map (Step 66A.3)

> **Blueprint / scope only. No UI implementation, no runtime change, no external action, no production
> action.**

MVP Admin Console page map. Each page: purpose · roles · data sources · actions · RBAC · audit ·
priority.

| Page | Purpose | Primary roles | Data sources | Actions | RBAC restriction | Audit | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/tasks` | list/track tasks | Requester (own), PM, Lead, Admin | `GET /tasks` | open, filter | own-scope for Requester | view logged | P0 |
| `/tasks/new` | assign/create task (task-type select, D14) | Requester, PM, Lead, Admin | task-type taxonomy | create, submit | create per RBAC | task.created/submitted | P0 |
| `/tasks/{id}` | task detail + state | task participants | `GET /tasks/{id}` | supplement reqs, cancel | own/role-scoped | actions logged | P0 |
| `/tasks/{id}/workroom` | chat-style Agent Workroom (D9) | participants | `GET workroom` | message, answer clarification | role-based msg visibility | msg↔audit corr id | P0 |
| `/deliveries` | Delivery Inbox | PM, Lead, Reviewer | `GET /deliveries` | open | review roles | view logged | P0 |
| `/deliveries/{id}` | delivery package + acceptance gate (D5) | PM, Lead, Reviewer | `GET /deliveries/{id}` | Accept/Reject/Request-Changes/Re-run-QA/Escalate/Archive | per RBAC + D12 limit | each action audited | P0 |
| `/operator/actions` | Operator Action Center (aggregated queues) | Admin, Agent Operator, Reviewer | action-center endpoints | triage, open item | role-scoped | view logged | P0 |
| `/operator/approvals` | Approvals UI (closes Step 65 gap #7) | Reviewer/Approver, Admin | approval-engine | approve, reject | approver/admin only | approval audited | **P0** |
| `/operator/dlq-retry` | DLQ / Retry UI (closes Step 65 gap #6) | Platform Admin, Agent Operator | retry-scheduler `/deadletter` | replay, inspect | **Admin/Agent-Op only (D13)** | replay audited | **P0** |
| `/operator/incidents` | incidents view | Admin, Agent Operator | incidents (`/admin/incidents`) | acknowledge, open | admin/agent-op | logged | P1 |
| `/notifications` | in-app notification center (D7) | all roles | `GET /notifications` | read, mark-read | own feed | read logged | P0 |
| `/settings/roles` | RBAC management | Platform Admin | role_permissions | assign roles | Admin only | change audited | P1 |
| `/settings/integrations` | integrations management | Platform Admin | integration config | configure (no secrets shown) | Admin only | change audited | P1 |
| `/settings/web-research-sources` | web-research whitelist mgmt (D10) | Platform Admin, Sec/Compliance (review) | web_research_sources | add/remove/approve source | Admin manage; Sec review | change audited | P1 |

## Navigation & visibility

- Role-aware navigation: pages/actions a role cannot use are hidden; server still enforces.
- Requester sees only own tasks + relevant workrooms + notifications.
- Operator surfaces (`/operator/*`) hidden from Requester/PM except where a specific capability applies.

## Statement

Frontend page map only — no page implemented, no runtime change, no external action, no production
action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
