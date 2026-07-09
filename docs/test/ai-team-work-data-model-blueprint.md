# AI Agents Team Work — Data Model Blueprint (Step 66A.3)

> **Blueprint / scope only. Proposed data-model additions — NOT implemented. No migration executed, no
> runtime change, no external action, no production action.**

Proposed additions to support the MVP. Each: purpose · key fields · relationships · retention/audit ·
migration required.

| Model | Purpose | Key fields | Relationships | Retention / audit | Migration? |
| --- | --- | --- | --- | --- | --- |
| `tasks` | operator-assigned task | id, title, type (D2/D14), state (lifecycle), owner, created_at, project_id | → work item / workflow | audited; retained | **yes** |
| `task_participants` | who is on a task + role scope | task_id, user_id, role, added_at | tasks ↔ users | audited | **yes** |
| `task_messages` | workroom messages (D9) | id, task_id, sender_type, message_type, body(redacted), correlation_id, created_at | → tasks, → audit | audit-linked retention | **yes** |
| `clarification_requests` | pause/notify/wait items (D4) | id, task_id, question, status, reminder_at(24h), expire_at(72h), extended_once | → tasks, → messages | audited | **yes** |
| `deliveries` | delivery package | id, task_id, summary refs, pr_link, cost_usage, risks, revision_no | → tasks | audited; retained | **yes** |
| `delivery_reviews` | review discussion/evidence | id, delivery_id, reviewer_id, note, created_at | → deliveries | audited | **yes** |
| `delivery_actions` | acceptance-gate actions (D5) | id, delivery_id, action, actor_id, change_size(D11), created_at | → deliveries | audited | **yes** |
| `qa_rerun_requests` | Re-run QA tracking (D12) | id, delivery_id, requester_id, seq(≤3), created_at | → deliveries | audited | **yes** |
| `operator_action_items` | Action Center queue items | id, queue, ref_id, status, risk, created_at | → approvals/dlq/incidents | audited | **yes** |
| `notification_events` | lifecycle notifications (D7) | id, event, target_channel, task_ref, read_state, redacted_body, created_at | → tasks | audited; no secrets | **yes** |
| `web_research_sources` | whitelist v0.1 (D10) | id, name, domain, status(approved/pending/blocked), added_by, reviewed_by | — | audited | **yes** |
| `web_research_requests` | governed search requests (future) | id, task_id, query, source_id, quota_used, status | → tasks, → sources | audited | yes (future) |
| `web_research_citations` | citations + timestamps (future) | id, request_id, url, retrieved_at, snippet_ref | → requests | audited; evidence | yes (future) |
| `role_permissions` | RBAC (D1) | role, capability, allowed | → users | audited | **yes** |

## Notes

- No secrets/tokens/customer data stored in message/notification bodies (redaction at write).
- `web_research_*` tables are **future** (connector not built); modeled now, populated later.
- `correlation_id` on `task_messages` ties workroom timeline ↔ audit events.
- Migrations are proposals; none executed in 66A.3.

## Statement

Data model blueprint only — nothing implemented or migrated; no runtime change; no external action; no
production action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
