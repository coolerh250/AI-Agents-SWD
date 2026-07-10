# Step 66B.3 — RBAC / Audit / Safety Hardening Report

> **66B.3 hardened RBAC / audit / safety only. No workflow dispatch occurred. No external action
> occurred. No production action occurred. production_executed_true_count=0. Test-only role
> simulation is not production auth. Real identity/session/CSRF remains future work.**

Hardens the Step 66B.1 Task API Foundation and Step 66B.2 Admin Console Task Assignment UI with
clearer permission boundaries, stronger audit evidence, and improved safety UX, ahead of Step 66C
Agent Workroom. No product scope was expanded — no Workroom, Delivery Inbox, Accept/Reject/Request
Changes, Re-run QA, Approvals UI, DLQ/Retry UI, notifications, or connector work was added.

## 1. Scope delivered

| # | Item | Status |
| --- | --- | --- |
| 1 | Server-side RBAC enforcement documented against the 66A.3 blueprint | done — `step66b3-rbac-validation-evidence.md` |
| 2 | Permission matrix documentation (exact enforced subset, not overclaimed) | done — `ai-team-work-rbac-blueprint.md` §7 |
| 3 | Admin Console role simulation safety UX improvements | done — readable role labels, visible current-identity readout |
| 4 | Task audit evidence surface improvements | done — `task_rbac_denied` audit event on every RBAC denial |
| 5 | Task audit refs / correlation id in task detail | done — `correlation_id` already returned; `dispatch_enabled` now returned by `GET /tasks/{id}` too (previously create/submit only) |
| 6 | Policy/safety explanation for `production_effect=true` | done — UI copy + safety panel; backend behavior unchanged (already forced `blocked`) |
| 7 | Tests proving no workflow dispatch | done — static source checks + `dispatch_enabled` regression tests |
| 8 | Tests proving no external actions | done — static source checks (no GitHub/Discord/Slack/Telegram/LLM/web reference) |
| 9 | Safety regression tests for `production_executed_true_count=0` | done — live runtime validation (see `step66b3-safety-validation-record.md`) |
| 10 | Real identity/session/CSRF gap documentation | done — `step66b3-known-gaps.md`, carried forward from 66B.1/66B.2 |

## 2. RBAC hardening (backend)

- **Fail-closed auth split into three distinct codes** (`apps/orchestrator/src/task_api.py::_authenticate`):
  `missing_actor` (401), `missing_role` (401) — previously indistinguishable from `invalid_role` —
  and `invalid_role` (401). All three remain fail-closed; this is a readability improvement only, no
  behavior change to the fail-closed guarantee.
- **`task_rbac_denied` audit event** (new `shared/sdk/tasks/audit_events.py::DECISION_TASK_RBAC_DENIED`)
  is now emitted, via a new `_deny()` helper in `task_api.py`, on **every** 403: `role_cannot_create_task`,
  `role_cannot_view_tasks`, `role_cannot_submit_task`, `not_own_task` (on both `GET /tasks/{id}` and
  `POST /tasks/{id}/submit`). Previously these denials produced no audit trail at all.
- **`GET /tasks/{id}` now also returns `dispatch_enabled: false`**, matching create/submit — the UI no
  longer needs to hardcode this value; it reads it from the API response (still always `false`).
- Permission matrix is unchanged in substance from 66B.1 (create: requester/pm_engineering_lead/
  platform_admin; view: all six; submit: same as create; requester scoped to own tasks on view/submit) —
  see `step66b3-rbac-validation-evidence.md` for the live-validated exact behavior, and
  `ai-team-work-rbac-blueprint.md` §7 for the documented simplified-subset-vs-full-blueprint mapping.

## 3. Safety UI hardening (frontend)

- **Readable role labels**: the role dropdown (`TestRoleBanner`) now shows "PM / Engineering Lead",
  "Reviewer / Approver", "Security / Compliance Reviewer", etc. instead of raw snake_case role
  strings (`apps/admin-console/src/tasks/testRole.ts::TASK_ROLE_LABELS`).
  The underlying `<option value>` (sent as the `X-Task-Role` header) is unchanged.
- **Visible current-identity readout**: `TestRoleBanner` now shows `Current: <actor> as <role label>`
  (`data-testid="current-identity"`) so the operator can always see which simulated actor/role is
  currently active without inspecting the dropdown state.
- **Readable RBAC/auth error messages**: `taskClient.ts` now maps known backend `detail` codes
  (`missing_actor`, `missing_role`, `invalid_role`, `role_cannot_create_task`,
  `role_cannot_view_tasks`, `role_cannot_submit_task`, `not_own_task`, `task_not_found`,
  `task_api_test_auth_disabled`) to a short human-readable sentence, shown alongside the raw detail
  code (e.g. "Your simulated role cannot view tasks. (role_cannot_view_tasks)").
- **Safety panel on `/tasks/{id}`** (`data-testid="safety-panel"`): a concise summary of
  `Environment`, `production_effect`, `requires_approval`, `dispatch_enabled` (now data-driven from
  the API), `external_actions_enabled` (static `false`), `production_executed` (static `false`) — in
  addition to the existing full `KeyValueTable` dump and the `production_effect=true` warning banner.

## 4. No product scope expansion

Out of scope and **not touched**: real identity/session implementation, CSRF implementation, Agent
Workroom, clarification flow, Delivery Inbox, Accept/Reject/Request Changes, Re-run QA, Approvals UI,
DLQ/Retry UI, lifecycle notifications, Slack/Discord/Telegram intake, LLM, web research connector,
workflow dispatch, production deployment.

## 5. Plain statements (for verifier)

- 66B.3 hardened RBAC / audit / safety only.
- No workflow dispatch occurred.
- No external action occurred.
- No production action occurred.
- production_executed_true_count=0.
- Test-only role simulation is not production auth.
- Real identity/session/CSRF remains future work.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
