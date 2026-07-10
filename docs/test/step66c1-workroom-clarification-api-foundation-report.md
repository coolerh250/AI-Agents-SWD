# Step 66C.1 — Agent Workroom & Clarification Data/API Foundation Report

> **66C.1 implemented Workroom / Clarification backend foundation only. No Workroom UI was
> implemented. No workflow dispatch occurred. No workflow resume occurred. No external action
> occurred. No production action occurred. production_executed_true_count=0.**

Builds the backend data model, API, RBAC, audit, and safety foundation for the Agent Workroom and
Clarification Layer, so Step 66C.2 can implement the Admin Console Workroom UI on top of it. Per the
Step 66B.3 security review (see `step66c1-rbac-audit-safety-record.md` §1), this stage was also
implemented against a security addendum covering message-body handling, XSS prevention (future UI
constraint), audit privacy, and RBAC denial audit.

## 1. Scope delivered

| # | Item | Status |
| --- | --- | --- |
| 1 | Task-level Agent Workroom messages | done — `task_messages` table + `TaskMessage` model |
| 2 | Human message creation | done — `POST /tasks/{id}/workroom/messages` |
| 3 | Agent/system message records | modeled (`sender_type: agent\|system\|audit`, `message_type` enum) — not produced by any agent in 66C.1 (no agent connector exists yet) |
| 4 | Clarification request creation | done — `POST /tasks/{id}/clarifications` |
| 5 | Clarification answer submission | done — `POST /tasks/{id}/clarifications/{id}/answer` |
| 6 | `clarification_needed` task state | done — set on clarification create |
| 7 | Resume-readiness state | done — `clarification_status: answered`, task returns to `intake_review`; `resume_dispatch_enabled=false` always |
| 8 | Message-to-task correlation | done — `task_messages.task_id` + `correlation_id` per message |
| 9 | Message-to-audit correlation | done — every mutating action's audit event carries the same `correlation_id`/`message_id`/`clarification_id` |
| 10 | RBAC and safety for workroom actions | done — see `step66c1-rbac-audit-safety-record.md` |

## 2. Data models (additive migration)

`migrations/030_workroom_clarification_foundation.sql` adds two new tables — no existing table
changed:

- **`task_messages`**: `id`, `task_id` (FK → `operator_tasks`), `correlation_id`, `sender_type`
  (`human`/`agent`/`system`/`audit`), `sender_id`, `sender_role`, `message_type` (10-value enum),
  `body` (TEXT, 1–8000 chars, CHECK-constrained), `visibility` (`task_participants`/`operators`/
  `audit_only`/`private_system`), `reply_to_message_id` (self-FK, optional), `audit_ref` (optional),
  `created_at`, `updated_at`.
- **`clarification_requests`**: `id`, `task_id` (FK), `question_message_id` (FK →
  `task_messages`), `status` (`open`/`answered`/`expired`/`canceled`), `question` (TEXT, 1–4000
  chars, CHECK-constrained), `requested_by_type`, `requested_by_id`, `assigned_to`, `due_at`
  (created + 72h), `reminder_at` (created + 24h), `answered_at`, `answer_message_id` (FK), timestamps.

Pydantic models: `shared/sdk/tasks/workroom_models.py` (`WorkroomMessageCreate`, `TaskMessage`,
`ClarificationCreate`, `ClarificationAnswerCreate`, `ClarificationRequest`, plus the length-limit
and reminder/due-hour constants).

Private per-agent channels are explicitly **not** implemented in 66C.1 (per spec §4.1).

## 3. APIs

New router `apps/orchestrator/src/workroom_api.py` (mounted alongside `task_api.py` in `main.py`,
same `/tasks` prefix, no path collisions):

- **`GET /tasks/{task_id}/workroom`** — returns `task_id`, `task_status`, `messages`,
  `clarification_requests`, `dispatch_enabled: false`, `resume_dispatch_enabled: false`.
- **`POST /tasks/{task_id}/workroom/messages`** — creates a `human_message`; 201 with the created
  message + `dispatch_enabled: false`.
- **`POST /tasks/{task_id}/clarifications`** — creates a `clarification_question` message +
  `clarification_requests` row; sets `task.status=clarification_needed`,
  `task.clarification_status=open`; 201 with the clarification + `task_status` +
  `dispatch_enabled`/`resume_dispatch_enabled: false`.
- **`POST /tasks/{task_id}/clarifications/{id}/answer`** — creates a `clarification_answer`
  message; sets `clarification.status=answered`, `task.status=intake_review`,
  `task.clarification_status=answered`; 200 with the updated clarification + `task_status` +
  `dispatch_enabled`/`resume_dispatch_enabled: false`.

**Design decision (spec explicitly allows either):** after a clarification is answered, task status
returns to **`intake_review`** (not a new `approved_for_execution_candidate` state, which does not
exist in the `TaskStatus` enum). This is the conservative choice — it puts the task back into the
same review queue it would have reached without a clarification detour, without granting any new
execution authority. Documented, not overclaimed.

**Reuse of the 66B.1/66B.3 auth model:** `workroom_api.py` does `import task_api` and calls
`task_api._authenticate(request)` / `task_api._audit(...)` / `task_api._store()` — a module
reference, not a `from ... import` copy — so the exact same fail-closed test-only auth gate,
audit publisher, and `operator_tasks` store apply to both routers. No new auth mechanism was added.

## 4. RBAC

See `step66c1-rbac-audit-safety-record.md` for the full matrix and security addendum. Summary: view
is all six roles (Requester scoped to own task); post-message excludes only
Security/Compliance Reviewer; create-clarification is PM/Eng Lead + Platform Admin + Agent Operator
only (Requester excluded by default, per spec); answer-clarification is Requester (own task) + PM/Eng
Lead + Platform Admin.

## 5. Audit

New decision types (`shared/sdk/tasks/audit_events.py`): `task_message_created`,
`clarification_requested`, `clarification_answered`, `task_workroom_rbac_denied`,
`clarification_rbac_denied`. New `safe_workroom_refs()` builder — **never** includes the raw
message/question/answer body, only its length and a SHA-256 hash (security addendum 3.5).

## 6. Safety

`dispatch_enabled: false` and `resume_dispatch_enabled: false` returned wherever applicable. No
workflow dispatch, no workflow resume, no external call anywhere in `workroom_api.py` (static source
tests confirm this). `GET /operations/safety` now also reports `task_workroom_enabled`,
`task_workroom_ui_enabled: false`, `task_workroom_dispatch_enabled: false`,
`task_workroom_resume_dispatch_enabled: false`, `task_workroom_external_integration_enabled: false`,
the two new RBAC-denial audit flags, and the three body/question/answer length limits.

## 7. No product scope expansion

Out of scope and **not touched**: Admin Console Workroom UI, real-time chat/websocket, agent
autonomous question generation, LLM-generated clarification, actual workflow resume, actual workflow
dispatch, Delivery Inbox, Accept/Reject/Request Changes, Re-run QA, Approvals UI, DLQ/Retry UI,
lifecycle notifications, Discord/Slack/Telegram messaging, GitHub write, web research connector,
production deployment.

## 8. Plain statements (for verifier)

- 66C.1 implemented Workroom / Clarification backend foundation only.
- No Workroom UI was implemented.
- No workflow dispatch occurred.
- No workflow resume occurred.
- No external action occurred.
- No production action occurred.
- production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
