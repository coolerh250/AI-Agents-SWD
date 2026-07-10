# Step 66B.3 — Audit Evidence Record

> **66B.3 hardened RBAC / audit / safety only. No workflow dispatch occurred. No external action
> occurred. No production action occurred. production_executed_true_count=0.**

## 1. Audit events (updated set)

| Event | `decision_type` | Emitted on | Since |
| --- | --- | --- | --- |
| Task created | `task_created` | every successful `POST /tasks` | 66B.1 |
| Task submitted | `task_submitted` | every successful `POST /tasks/{id}/submit` | 66B.1 |
| Policy block | `task_rejected_by_policy` | `production_effect=true` task forced to `blocked` | 66B.1 |
| **RBAC denial** | **`task_rbac_denied`** | **every 403**: `role_cannot_create_task`, `role_cannot_view_tasks`, `role_cannot_submit_task`, `not_own_task` (on `GET /tasks/{id}` and `POST /tasks/{id}/submit`) | **66B.3 (new)** |

Previously (66B.1/66B.2), a denied RBAC attempt produced **no audit record at all** — only the HTTP
403 response. This was a documented but unaddressed audit-evidence gap. Step 66B.3 closes it: every
403 now goes through a new `_deny()` helper (`apps/orchestrator/src/task_api.py`) that publishes a
`task_rbac_denied` audit event **before** raising the `HTTPException`, then raises exactly the same
HTTP status/detail as before (no behavior change to the API response itself).

## 2. `task_rbac_denied` evidence content

Uses the same `safe_task_refs()` builder as every other task audit event — opaque ids/labels/statuses
only, plus hard-`false` safety booleans:

```
{
  "production_executed": false,
  "workflow_dispatched": false,
  "external_write_performed": false,
  "github_write_performed": false,
  "discord_send_performed": false,
  "llm_call_performed": false,
  "task_id": "<uuid, if applicable>",
  "actor": "<requesting actor>",
  "role": "<requesting role>",
  "action": "create" | "list" | "get" | "submit",
  "status": "<denial reason, e.g. not_own_task>"
}
```

No token, secret, or payload dump is ever included — verified by
`tests/test_step66b3_rbac_audit_safety.py::test_audit_refs_never_carry_secret_shaped_content`.

## 3. Task detail evidence surface

`GET /tasks/{id}` returns: `id`, `correlation_id`, `production_effect`, `requires_approval`,
`environment`, `status`, `created_by`, `owner`, `created_at`, `updated_at`, and (as of 66B.3)
`dispatch_enabled: false` — all of which the Admin Console's Task Detail page renders (full
`KeyValueTable` dump plus the new concise safety panel, see `step66b3-safety-validation-record.md`).

**Known gap (documented, not fabricated):** there is **no direct "show me the audit trail for this
task_id" lookup endpoint**. Audit events are published to the `stream.audit` Redis stream
(`shared/sdk/audit/publisher.py`) but there is no per-task audit query API in this stage. The
`correlation_id` field is the intended future join key once such a lookup exists. This gap is
carried forward, not newly introduced — see `step66b3-known-gaps.md`.

## 4. Full audit event coverage confirmed by test

`tests/test_step66b3_rbac_audit_safety.py`: `test_task_created_audit_event`,
`test_task_submitted_audit_event`, `test_task_rejected_by_policy_audit_event`,
`test_task_rbac_denied_audit_event` — all four `TASK_DECISION_TYPES`
(`shared/sdk/tasks/audit_events.py`) are now exercised by at least one test.

## 5. Statement

No workflow dispatch occurred. No external action occurred. No production action occurred.
production_executed_true_count=0. Test-only role simulation is not production auth. Real
identity/session/CSRF remains future work.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
