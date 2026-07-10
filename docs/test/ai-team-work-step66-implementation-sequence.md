# AI Agents Team Work — Step 66 Implementation Sequence (Step 66A.3)

> **Blueprint / scope only. No implementation, no runtime change, no external action, no production
> action.** Each stage below needs its own explicit operator authorization + operator validation.

## 66B — Operator Task Assignment UI & Task API

- **Goal:** a manager can assign/create + track tasks from Console/API.
- **Scope:** `/tasks`, `/tasks/new` (task-type select, D14), `/tasks/{id}`; task API (`POST/GET /tasks`,
  submit); RBAC create/view (D1).
- **Out of scope:** workroom, delivery, channels beyond Console/API.
- **Dependencies:** existing intake path.
- **Backend:** `tasks`, `task_participants`, `role_permissions`; task endpoints.
- **Frontend:** task pages + role-aware nav.
- **Data model:** tasks, task_participants, role_permissions.
- **Tests:** task CRUD, RBAC create/view, submit transition.
- **Acceptance:** assign a task from UI; see it tracked; RBAC enforced.
- **Operator validation:** required (operator drives the UI).

## 66C — Agent Workroom & Clarification Layer

- **Goal:** chat-style workroom + pause/notify/wait/resume (D9, D4).
- **Scope:** `/tasks/{id}/workroom`; message types; clarification state machine + 24h/72h timeout
  (project-config, owner extend once); message↔audit correlation.
- **Out of scope:** deferred workroom features (voice, branching, per-agent rooms).
- **Dependencies:** 66B tasks.
- **Backend:** `task_messages`, `operator_clarification_requests` (implemented name — renamed from
  the originally proposed `clarification_requests` to avoid colliding with a pre-existing, unrelated
  table; see `step66c1-test-deployment-record.md`); workroom + clarification endpoints.
- **Frontend:** workroom UI, clarification reply.
- **Data model:** task_messages, operator_clarification_requests.
- **Tests:** message posting RBAC, clarification pause/resume, timeout→expired, owner extend once.
- **Acceptance:** converse with agents; answer a clarification; task resumes; timeout behaves.
- **Operator validation:** required.

### 66C sub-stage breakdown (operator-assigned, 2026-07-10, per 66C.1-V)

66C is delivered incrementally; each sub-stage still needs its own operator authorization +
validation:

- **66C.1 — Agent Workroom & Clarification Data/API Foundation.** Backend only, no UI. **Status:
  PASS, operator `READY_WITH_GAPS`** (see `step66c1-operator-api-validation-record.md`). Gaps
  G1 (visibility filtering), G2 (reminder/expiry scheduler), G3 (audit lookup), G5 (answered-twice
  test) carried forward — not blocking.
- **66C.2 — Admin Console Workroom UI.** Consumes the 66C.1 APIs; renders messages as plain text
  only (**no `dangerouslySetInnerHTML`**); shows the clarification question/answer;
  shows `dispatch_enabled=false`/`resume_dispatch_enabled=false`; shows the known visibility
  limitation (G1) if relevant.
- **66C.3 — Workroom Audit / Visibility / Edge-case Hardening.** Implements message visibility
  filtering (closes G1); adds a per-task audit lookup or task-scoped audit evidence endpoint (closes
  G3); adds an answered-twice guard + dedicated test (closes G5); strengthens RBAC evidence.
- **66C.4 — Clarification Reminder / Expiry Scheduler.** Implements the 24h reminder and 72h
  `clarification_expired` transition (closes G2); implements one owner extension; no external
  notification send unless separately authorized.

## 66D — Delivery Inbox & Acceptance Gate

- **Goal:** review + act on deliveries; close Step 65 gaps #6/#7.
- **Scope:** `/deliveries`, `/deliveries/{id}`, `/operator/approvals`, `/operator/dlq-retry`;
  acceptance actions (D5); Request-Changes classification (D11); Re-run-QA ≤3 (D12); replay Admin/
  Agent-Op only (D13).
- **Out of scope:** multi-channel intake, full notification center.
- **Dependencies:** 66B/66C; approval-engine + retry-scheduler (exist).
- **Backend:** `deliveries`, `delivery_reviews`, `delivery_actions`, `qa_rerun_requests`,
  `operator_action_items`; delivery + approvals + dlq endpoints.
- **Frontend:** inbox, delivery detail, approvals page, DLQ/retry page.
- **Data model:** deliveries, delivery_reviews, delivery_actions, qa_rerun_requests.
- **Tests:** each action + RBAC; small/major classification; Re-run-QA >3 blocked; non-admin replay
  blocked.
- **Acceptance:** Accept/Reject/Request-Changes/Re-run-QA a delivery; approvals + DLQ operable.
- **Operator validation:** required.

## 66E — Fixed Software Delivery Team Integration

- **Goal:** wire assign → fixed team (intake→…→devops) → delivery, end to end.
- **Scope:** connect task/workroom/delivery to the validated 5-agent pipeline (D6); task-type routing
  (software/docs/platform first-class; others → intake/planning).
- **Out of scope:** custom/AI-suggested teams; non-software specialized pipelines.
- **Dependencies:** 66B–66D.
- **Backend:** orchestration glue; delivery package assembly from pipeline output.
- **Frontend:** progress surfaced in workroom.
- **Data model:** links tasks↔work items↔workflows.
- **Tests:** E2E fixed-team run (mock/dry-run), delivery assembly.
- **Acceptance:** assigned task runs the fixed team and produces a reviewable delivery; prod_exec=0.
- **Operator validation:** required.

## 66F — Multi-channel Intake Foundation

- **Goal:** intake from more channels (D3).
- **Scope:** Admin+API confirmed; **Discord intake first, then Slack**; Telegram later; identity→role
  mapping.
- **Out of scope:** Telegram P0; Slack P0.
- **Dependencies:** 66B; Discord rail (exists).
- **Backend:** channel intake adapters; identity mapping.
- **Frontend:** channel settings.
- **Data model:** identity mapping.
- **Tests:** channel intake → task; identity→role; unmapped rejected.
- **Acceptance:** create a task via Discord (controlled); mapped to role + audited.
- **Operator validation:** required (any real send needs separate auth).

## 66G — Lifecycle Notification & Operator Action Center

- **Goal:** unified notifications + full Action Center (D7, D8).
- **Scope:** `/notifications`, `/operator/actions` (all queues); Console P0 + Discord P1 routing;
  redaction.
- **Out of scope:** Slack/Telegram notify (later).
- **Dependencies:** 66B–66E.
- **Backend:** `notification_events`; action-center aggregation.
- **Frontend:** notification center, action center.
- **Data model:** notification_events, operator_action_items.
- **Tests:** event routing, redaction, queue population, RBAC.
- **Acceptance:** lifecycle events notified (no secrets); Action Center aggregates all queues.
- **Operator validation:** required.

## 66H — AI Team Work E2E Pilot

- **Goal:** full manager journey pilot on the test runtime (controlled).
- **Scope:** assign → agents work → workroom → clarification → delivery → accept/request-changes →
  notifications → action center; all mock/dry-run; prod_exec=0.
- **Out of scope:** production; live external writes without per-step auth; web research (no connector).
- **Dependencies:** 66B–66G.
- **Tests:** full E2E; governance (RBAC, replay, limits, timeout).
- **Acceptance:** operator completes the end-to-end journey with operator-visible evidence.
- **Operator validation:** required — operator decides product acceptance (not Claude Code).

## 66S — Identity / Session / CSRF / Project RBAC Foundation (operator-assigned, 2026-07-10)

- **Goal:** replace the fail-closed test-only header role simulation (`TASK_API_TEST_AUTH_ENABLED` +
  `X-Task-Actor`/`X-Task-Role`, carried since 66B.1) with a real identity/session model before any
  broader-than-test deployment.
- **Scope:** real identity/session model; CSRF protection; project/team RBAC scoping (closes **G4**
  from 66C.1-V — the only-Requester-is-scoped fallback used throughout 66B/66C).
- **Out of scope:** production deployment itself (this stage only builds the foundation for it).
- **Dependencies:** none blocking — can run in parallel with 66C.2–66H, but must land before any
  production or broader-audience deployment of the Task API / Workroom.
- **Tests:** real session issuance/expiry, CSRF token validation, project/team-scoped RBAC checks
  (Requester/PM/Reviewer/Admin/Agent-Op/Sec-Compliance all re-verified under project scoping).
- **Acceptance:** the test-only header simulation is fully replaced; no regression in the RBAC
  matrices already validated for 66B/66C.
- **Operator validation:** required.

## Statement

Implementation sequence blueprint only — nothing implemented; no runtime change; no external action;
no production action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
