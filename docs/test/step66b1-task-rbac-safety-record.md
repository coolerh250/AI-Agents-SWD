# Step 66B.1 — Task API RBAC & Safety Record

> **Backend/API safety documentation only. No production action. No external action.**

## 1. Auth model (fail-closed, test-only)

- Gate: `TASK_API_TEST_AUTH_ENABLED` must be exactly `"true"` (case-insensitive) or **every**
  endpoint returns `403 task_api_test_auth_disabled`. Unset/false → fail closed.
- Identity: `X-Task-Actor` header (free-text identity key, required, else `401 missing_actor`).
- Role: `X-Task-Role` header, must be one of the six roles below, else `401 invalid_role`.
- This is a **documented, deliberate stand-in** for a real identity/session model (see
  `step66b1-known-gaps.md`) — it does not weaken production safety because it is fail-closed and
  because no production deployment would ever set `TASK_API_TEST_AUTH_ENABLED=true`.

## 2. Roles (from `ai-team-work-rbac-blueprint.md`)

`requester`, `pm_engineering_lead`, `reviewer_approver`, `platform_admin`, `agent_operator`,
`security_compliance_reviewer`.

## 3. Capability matrix (66B.1 scope: create / view / submit)

| Capability | requester | pm_engineering_lead | reviewer_approver | platform_admin | agent_operator | security_compliance_reviewer |
| --- | --- | --- | --- | --- | --- | --- |
| Create task (`POST /tasks`) | ✔ | ✔ | ✖ | ✔ | ✖ | ✖ |
| View task (`GET /tasks`, `GET /tasks/{id}`) | ✔ (own only) | ✔ | ✔ | ✔ | ✔ | ✔ |
| Submit task (`POST /tasks/{id}/submit`) | ✔ (own only) | ✔ | ✖ | ✔ | ✖ | ✖ |

- Enforced in `shared/sdk/tasks/rbac.py` (`can_create`, `can_view`, `can_submit`) and the
  own-task scoping in `apps/orchestrator/src/task_api.py` (`ctx.role == "requester"` checks).
- Denied role → `403 role_cannot_create_task` / `role_cannot_view_tasks` / `role_cannot_submit_task`.
- Requester viewing/submitting another actor's task → `403 not_own_task`.

## 4. Audit events

| Event | `decision_type` | Emitted on |
| --- | --- | --- |
| Task created | `task_created` | every successful `POST /tasks` |
| Task submitted | `task_submitted` | every successful `POST /tasks/{id}/submit` |
| Policy block | `task_rejected_by_policy` | `production_effect=true` task forced to `blocked` (at create-with-submit or at submit) |

Each event's `artifact_refs` (`shared/sdk/tasks/audit_events.py::safe_task_refs`) carries only
opaque ids/labels/statuses: `task_id`, `correlation_id`, `actor`, `role`, `action`,
`production_effect`, `environment`, `status` — plus hard-`false` booleans
(`production_executed`, `workflow_dispatched`, `external_write_performed`,
`github_write_performed`, `discord_send_performed`, `llm_call_performed`). No secret, token, or
payload dump is ever included. Published via the existing `shared.sdk.audit.publisher` onto
`stream.audit` (best-effort; failures are suppressed so they never break the request).

## 5. `production_effect` handling (exact behavior)

| Request | Result |
| --- | --- |
| `production_effect=false` (default) | normal flow; `requires_approval` only set if explicitly requested |
| `production_effect=true`, `initial_status=draft` | task recorded as `draft`, `requires_approval=true` forced; no policy-block audit yet (nothing submitted) |
| `production_effect=true`, `initial_status=submitted` | task recorded directly as `blocked` (not `submitted`), `requires_approval=true`, `task_rejected_by_policy` audited |
| `POST /tasks/{id}/submit` on a `production_effect=true` task | status forced to `blocked` (never `intake_review`), `task_rejected_by_policy` audited |

In every case: **the task is recorded, never dispatched, never executed.** Response always
includes `"dispatch_enabled": false`.

## 6. `/operations/safety` integration

`shared/sdk/tasks/safety.py::tasks_safety_fields()` is spliced into `GET /operations/safety`
(`apps/orchestrator/src/operations.py`): `task_api_enabled`, `task_api_write_enabled`,
`task_api_test_auth_enabled` (reflects the env flag), and hard-`false`
`task_api_workflow_dispatch_enabled` / `task_api_production_effect_enabled` /
`task_api_external_integration_enabled` / `task_api_github_write_enabled` /
`task_api_discord_send_enabled` / `task_api_llm_call_enabled`.

## 7. Plain statements (for verifier)

- RBAC behavior documented.
- Audit events documented.
- production_effect safety documented.
- No workflow dispatch occurred.
- No external action occurred.
- No production action occurred.
- production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
