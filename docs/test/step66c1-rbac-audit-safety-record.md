# Step 66C.1 — RBAC / Audit / Safety Record (incl. Security Review Addendum)

> **Backend/API safety documentation only. No production action. No external action. No workflow
> dispatch. No workflow resume.**

## 1. Prior security review (Step 66B.3 / 66B.3-V)

Before Step 66C.1, the operator ran a security review over the 66B.3/66B.3-V commits (scope:
`task_api.py`, `shared/sdk/tasks/audit_events.py`/`safety.py`, `apps/admin-console/src/tasks/*`,
`TaskDetail.tsx`, tests, verifiers, docs). **Result: no HIGH or MEDIUM confidence vulnerabilities
identified.** Key observations carried forward into 66C.1's design:

1. DB access uses parameterized `asyncpg` placeholders — continued in `workroom_store.py`.
2. Missing actor / missing role / invalid role fail closed — reused unchanged via
   `task_api._authenticate`.
3. `TASK_API_TEST_AUTH_ENABLED` + `TASK_ROLES` allowlist remain the safety gates — unchanged.
4. Requester own-task scoping is enforced and tested — extended to workroom view/post/answer.
5. Audit events use fixed server-defined reason constants and opaque refs — extended with
   `safe_workroom_refs()`.
6. React JSX text interpolation is safe by default; no `dangerouslySetInnerHTML` — restated as a
   **mandatory 66C.2 UI constraint** (no UI exists yet in 66C.1).
7. `localStorage` stores only non-secret test actor/role labels — unaffected (no frontend touched).
8. No new external calls or dispatch paths added without explicit authorization — upheld; see §5.

## 2. RBAC (66C.1 scope: view workroom / post message / create clarification / answer clarification)

No project/team scoping model exists yet (documented gap carried over from 66A.3/66B) — the only
ownership scoping enforced is Requester-to-own-task, identical in shape to the existing
`task_api.py` pattern. All other roles are **unscoped by task ownership** in this stage; this is a
documented fallback, not overclaimed as full project/team RBAC.

| Capability | requester | pm_engineering_lead | reviewer_approver | platform_admin | agent_operator | security_compliance_reviewer |
| --- | --- | --- | --- | --- | --- | --- |
| View workroom (`GET .../workroom`) | ✔ (own only) | ✔ (all) | ✔ (all) | ✔ (all) | ✔ (all) | ✔ (all) |
| Post message (`POST .../workroom/messages`) | ✔ (own only) | ✔ | ✔ | ✔ | ✔ | ✖ |
| Create clarification (`POST .../clarifications`) | ✖ (default) | ✔ | ✖ | ✔ | ✔ | ✖ |
| Answer clarification (`POST .../clarifications/{id}/answer`) | ✔ (own only) | ✔ | ✖ | ✔ | ✖ | ✖ |

Enforced in `shared/sdk/tasks/workroom_rbac.py` (`can_view_workroom`, `can_post_message`,
`can_create_clarification`, `can_answer_clarification`) plus the own-task scoping checks
(`ctx.role == "requester" and task["created_by"] != ctx.actor`) in `workroom_api.py`, identical
pattern to `task_api.py`.

- Denied role → `403 role_cannot_view_workroom` / `role_cannot_post_message` /
  `role_cannot_create_clarification` / `role_cannot_answer_clarification`.
- Requester targeting another actor's task (view/post/answer) → `403 not_own_task`.
- Security/Compliance Reviewer can view but never mutates (post/create/answer all denied) —
  matches the spec's "view audit/safety messages; cannot mutate by default."

## 3. Audit

| Event | `decision_type` | Emitted on |
| --- | --- | --- |
| Workroom message created | `task_message_created` | every successful `POST .../workroom/messages` |
| Clarification requested | `clarification_requested` | every successful `POST .../clarifications` |
| Clarification answered | `clarification_answered` | every successful `POST .../clarifications/{id}/answer` |
| Workroom RBAC denial | `task_workroom_rbac_denied` | every 403 on view/post-message |
| Clarification RBAC denial | `clarification_rbac_denied` | every 403 on create/answer |

Each event's `artifact_refs` (`shared/sdk/tasks/audit_events.py::safe_workroom_refs`) carries only
opaque ids/labels/statuses (`task_id`, `message_id`, `clarification_id`, `correlation_id`, `actor`,
`role`, `action`, `message_type`, `visibility`, `status`) plus hard-`false` safety booleans
(`production_executed`, `workflow_dispatched`, **`workflow_resumed`**, `external_write_performed`,
`github_write_performed`, `discord_send_performed`, `llm_call_performed`) — and, when a message body
is involved, `body_length` + a SHA-256 `body_hash`. **The raw body/question/answer text is never
included** — verified by `test_message_audit_never_includes_raw_body`.

Per-task audit lookup still does not exist (carried-over gap from 66B.1/66B.3) — `correlation_id`
remains the intended future join key; not fabricated.

## 4. Security addendum — controls implemented

### 4.1 SQL / persistence
All new queries in `workroom_store.py` use parameterized `asyncpg` placeholders (`$1`, `$2`, ...) —
no string-concatenated SQL, no dynamic unescaped fragments, no user input in SQL identifiers. The
migration is additive only (two new tables; no change to `operator_tasks` or any other table).

### 4.2 Message body safety
`task_messages.body`, `clarification_requests.question`, and clarification answers (also stored as
a `task_messages.body` row) are treated as **untrusted plain text**: stored as `TEXT`, never rendered
as HTML, never executed as markdown/template/script — there is no UI in 66C.1 to render them at all.
Length limits: message body / clarification answer ≤ **8000** characters, clarification question ≤
**4000** characters — enforced by Pydantic `Field(max_length=...)` (422 on violation) **and** by DB
`CHECK` constraints (defense in depth, in case a future direct-DB writer bypasses the API).

### 4.3 XSS prevention (mandatory 66C.2 UI constraint)
No UI is implemented in 66C.1, so there is no XSS attack surface yet. This is recorded here as a
**binding requirement for Step 66C.2**: no `dangerouslySetInnerHTML` for Workroom/clarification
display, no HTML injection path, no markdown-to-HTML rendering without separate review, no
user-controlled `className`/`style` injection. Render message/question/answer text as plain React
text content only.

### 4.4 RBAC / authorization
All required negative cases pass (see `step66c1-workroom-api-evidence.md` /
`step66c1-clarification-flow-evidence.md` for the full table): missing actor/role denied, invalid
role denied, Requester cannot view/post/answer on another actor's task, Requester cannot create a
clarification (default deny), unauthorized roles cannot create or answer a clarification,
Security/Compliance Reviewer cannot mutate.

### 4.5 Audit privacy
Confirmed: `safe_workroom_refs()` never includes the full message body, clarification answer,
secrets, tokens, headers, cookies, `.env` values, or a raw request payload dump — only opaque
ids/labels/statuses plus `body_length`/`body_hash`. Verified by
`test_message_audit_never_includes_raw_body`.

### 4.6 Denial audit
`task_workroom_rbac_denied` / `clarification_rbac_denied` are emitted on every relevant 403,
including view-denials, before the exception is raised. No fallback-suppression case was needed —
the audit ref for a view-denial only contains the task_id (already known to the caller, since they
supplied it in the URL) plus actor/role/reason, never task content, so there is no scenario where
emitting the denial audit itself would leak anything the caller doesn't already have.

### 4.7 No dispatch / no external side effects
`workroom_api.py` contains no call to a workflow dispatch/resume function and no
GitHub/Discord/Slack/Telegram/LLM/web-connector reference — verified statically by
`test_source_has_no_workflow_dispatch_or_resume_call` and
`test_source_has_no_external_integration_reference`. All relevant responses include
`dispatch_enabled: false` and (on the workroom/clarification endpoints) `resume_dispatch_enabled:
false`.

### 4.8 Test-auth boundary
Unchanged: `TASK_API_TEST_AUTH_ENABLED` + `X-Task-Actor`/`X-Task-Role` remain the fail-closed,
test-only stand-in reused from 66B.1/66B.3 — no new auth mechanism was introduced for the workroom
endpoints. Real identity/session/CSRF remains explicitly deferred future work (see
`step66c1-known-gaps.md`).

## 5. Plain statements (for verifier)

- 66C.1 implemented Workroom / Clarification backend foundation only.
- No Workroom UI was implemented.
- No workflow dispatch occurred.
- No workflow resume occurred.
- No external action occurred.
- No production action occurred.
- production_executed_true_count=0.
- Test-only role simulation is not production auth.
- Real identity/session/CSRF remains future work.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
