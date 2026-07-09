# AI Agents Team Work — Operator Action Center Blueprint (Step 66A.3)

> **Blueprint / scope only. No implementation, no runtime change, no external action, no production
> action.**
> **D8: Approvals UI and DLQ/Retry UI are both P0 — closing the Step 65 operator-flagged gaps.**

## 1. Queues

| Queue | Data source | UI columns | Detail view | Actions | RBAC | Risk | Audit | Notification | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Pending approvals** | approval-engine `/approval/*` | request, type, requester, age | request context + policy | approve, reject | Reviewer/Approver, Admin | med | approval.decided | approval required/granted/denied | **P0** |
| **Clarification requests** | clarification_requests | task, question, age | thread | open workroom, reply | task roles | low | clarification.* | clarification needed | P0 |
| **Delivery ready** | deliveries | delivery, task, risk | package | open delivery | PM/Lead/Reviewer | low | delivery.ready | delivery ready | P0 |
| **Request changes** | delivery_actions | task, size, requester | change note | open task | PM/Lead/Reviewer | low | delivery.changes_requested | request changes | P1 |
| **Failed workflows** | orchestrator/incidents | task, stage, error class | trace | open, escalate | Admin/Agent-Op | med | task.failed | task failed | P1 |
| **DLQ / retry queue** | retry-scheduler `/deadletter` | entry, reason class, retry count, last error class | entry detail | **replay**, inspect | **Admin/Agent-Op only (D13)** | **high** | dlq.replayed | DLQ created | **P0** |
| **Incidents** | `/admin/incidents` | id, severity, status | incident detail | acknowledge | Admin/Agent-Op | med | incident.* | incident raised | P1 |
| **Blocked production-effect tasks** | policy-engine RESTRICTED_ACTIONS | task, action, reason | policy detail | review (no prod exec) | Reviewer/Admin | high | policy.blocked | approval required | P1 |
| **Integration health issues** | `/operations/safety` + gateways | integration, status | health detail | open settings | Platform Admin | med | integration.health | health alert | P2 |

## 2. Step 65 gap closure (explicit)

- **DLQ / Retry queue (P0)** closes operator-flagged gap **#6** — DLQ indicators had no admin page.
  Shows which tasks failed terminally and why (reason class, retry count, last error class — never
  secrets), with a **governed manual replay** (Admin / Agent Operator only, audited), backed by the
  existing retry-scheduler APIs.
- **Pending approvals queue (P0)** closes gap **#7** — the missing `/approvals` page — via the existing
  approval-engine APIs.

## 3. Cross-cutting

Each item shows what needs attention, who can act, the governed action(s), a link-back to the work
item, and the audit trail. Replay and approval actions are server-enforced by role; all emit audit +
notification; `production_executed_true_count=0` preserved (no queue action performs production effect).

## Statement

Operator Action Center blueprint only — no implementation, no runtime change, no external action, no
production action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
