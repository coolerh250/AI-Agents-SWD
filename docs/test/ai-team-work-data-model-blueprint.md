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

## 66B.1 implementation status (2026-07-09)

The `tasks` row above is **implemented**: table `operator_tasks` (migration
`029_operator_task_api_foundation.sql`), named to avoid colliding with the legacy vestigial `tasks`
table. Columns extend the proposal with `intake_planning_only`, `clarification_status`,
`delivery_status`, `correlation_id`, and a `production_effect`/environment CHECK restricting
`environment` to `test`/`staging` (defense in depth — no `production` value ever accepted). All
other rows (`task_participants`, `task_messages`, `clarification_requests`, `deliveries`, …) remain
proposals for their respective stages (66B.2+).

## Step 66C.1 implementation status (2026-07-10)

Two more rows from the proposal above are now **implemented**: `task_messages` and, under the name
**`operator_clarification_requests`** (not `clarification_requests` — a pre-existing, unrelated table
of that exact name already exists from the Discord requirement-agent pipeline,
`007_flexible_task_execution_loop.sql`; renamed to avoid the collision, discovered during live
deployment) — migration `030_workroom_clarification_foundation.sql`, additive only — no change to
`operator_tasks` or the legacy `clarification_requests`. `task_messages` extends the proposal with
`visibility`, `reply_to_message_id`, and `audit_ref`; `operator_clarification_requests` uses
`due_at`/`reminder_at` in place of the proposal's `expire_at`/implicit-24h naming, with the same
72h/24h values, plus `answered_at`/`answer_message_id`. `task_participants` (RBAC scoping is still handled entirely via
the `X-Task-Role` header + Requester-own-task check, not a separate participants table) and
`deliveries`/`delivery_reviews`/`delivery_actions`/`qa_rerun_requests`/`operator_action_items`/
`notification_events`/`web_research_*`/`role_permissions` remain proposals for their respective
stages (66C.2+/66D+).

## Step 66C.3 implementation status (2026-07-11)

**No new table and no new migration.** `task_messages.visibility` (already modeled since 66C.1) is
now actually enforced — `GET /tasks/{id}/workroom` filters by it server-side per caller role (G1).
The existing `audit_logs` table (Stage 19, `001_init_core_tables.sql`) is reused, not extended, by
the new `GET /tasks/{id}/audit-evidence` endpoint (G3) — it reads
`audit_logs.artifact_refs` and projects an allowlisted subset; no new column, no new table.
`operator_clarification_requests.status` transitions (`open` → `answered`) are now enforced with an
atomic `UPDATE ... WHERE status='open'` (G5) instead of a non-atomic read-then-write — a query-level
fix, not a schema change.

## Statement

The `tasks` model (66B.1) and the `task_messages`/`operator_clarification_requests` models (66C.1) are
implemented; the remaining models above are still proposals — nothing else implemented or migrated;
no runtime change beyond 66B.1/66C.1/66C.3 (query/logic changes only in 66C.3, no schema change); no
external action; no production action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
