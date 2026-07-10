# Step 66C.1 — Workroom API Evidence

> **Evidence only. No Workroom UI implemented. No workflow dispatch occurred. No workflow resume
> occurred. No external action occurred. No production action occurred.
> production_executed_true_count=0.**

## 1. `GET /tasks/{task_id}/workroom`

| Case | Result |
| --- | --- |
| Freshly created task, no messages/clarifications | `200`, `messages: []`, `clarification_requests: []`, `dispatch_enabled: false`, `resume_dispatch_enabled: false`, `task_status: "draft"` |
| Missing `X-Task-Actor` | `401 missing_actor` |
| Invalid `X-Task-Role` | `401 invalid_role` |
| Requester views own task's workroom | `200` |
| **Requester views another actor's workroom** | `403 not_own_task`, audited as `task_workroom_rbac_denied` |
| Platform Admin views any task's workroom | `200` (unscoped — see `step66c1-rbac-audit-safety-record.md` §2 for the documented fallback) |

Verified by `tests/test_step66c1_workroom_clarification_api.py`:
`test_get_workroom_empty_default`, `test_get_workroom_missing_actor_denied`,
`test_get_workroom_invalid_role_denied`, `test_requester_cannot_view_other_actor_workroom`,
`test_platform_admin_can_view_any_workroom`.

## 2. `POST /tasks/{task_id}/workroom/messages`

| Case | Result |
| --- | --- |
| Requester posts a message on own task | `201`, `message_type: "human_message"`, `sender_type: "human"`, `dispatch_enabled: false`; `task_message_created` audited |
| **Requester posts to another actor's task** | `403 not_own_task`, audited as `task_workroom_rbac_denied` |
| Body exceeds 8000 characters | `422` (Pydantic `Field(max_length=8000)`, defense in depth with the DB `CHECK` constraint) |
| Audit event for the message | Carries `body_length` + SHA-256 `body_hash` — **never** the raw body text |

Verified by `test_post_human_message_succeeds`, `test_requester_cannot_post_to_other_actor_task`,
`test_message_body_length_limit`, `test_message_audit_never_includes_raw_body`.

## 3. Message types and visibility

All 10 `message_type` values and all 4 `visibility` values from the Step 66C.1 spec are enforced by
the migration's `CHECK` constraints and the Pydantic `Literal` types. In 66C.1, only two message
types are actually produced by the API: `human_message` (via `POST .../messages`) and
`clarification_question`/`clarification_answer` (via the clarification endpoints, §... see
`step66c1-clarification-flow-evidence.md`). `agent_message`, `system_event`, `audit_event`,
`delivery_comment`, `request_changes_note`, `qa_result_note`, `approval_request_note` are modeled for
future stages (no agent connector, delivery flow, or QA flow exists yet to produce them) — not
fabricated, not yet exercised. All messages created in 66C.1 use `visibility: task_participants`
(the only value the API currently sets); the other three visibility values are modeled for future
per-audience filtering, not yet implemented.

## 4. Live test-runtime validation (10.0.1.31, `aiagents-test`)

See `step66c1-test-deployment-record.md` for the live curl-equivalent results.

## 5. Statement

66C.1 implemented Workroom / Clarification backend foundation only. No Workroom UI was implemented.
No workflow dispatch occurred. No workflow resume occurred. No external action occurred. No
production action occurred. production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
