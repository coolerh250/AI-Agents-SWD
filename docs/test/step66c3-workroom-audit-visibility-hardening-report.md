# Step 66C.3 — Workroom Audit / Visibility / Edge-case Hardening Report

> **66C.3 hardens the Step 66C.1/66C.2 Workroom and Clarification capabilities only. No workflow
> dispatch occurred. No workflow resume occurred. No external action occurred. No production action
> occurred. production_executed_true_count=0.**
>
> **Final status: `PASS, operator VISIBLE`.** Operator confirmed all 12 items in the Step 66C.3-V
> validation record. See `step66c3-operator-validation-record.md`. Step 66C.4 is READY_TO_START.

Closes three non-blocking gaps carried forward from Step 66C.1-V operator validation
(`step66c1-operator-api-validation-record.md` §5): **G1** (message visibility filtering), **G3**
(per-task audit lookup endpoint), **G5** (answered-twice guard dedicated test).

## 1. Scope delivered

| # | Item | Status |
| --- | --- | --- |
| 1 | Server-side message visibility filtering (G1) | done — `shared/sdk/tasks/workroom_rbac.py::filter_messages_by_visibility` |
| 2 | Task-scoped audit evidence endpoint (G3) | done — `GET /tasks/{task_id}/audit-evidence` |
| 3 | Answered-twice guard hardened + dedicated tests (G5) | done — atomic DB-level claim, `409 clarification_already_answered` |
| 4 | Workroom UI respects visibility-filtered results | done — UI renders only what the API returns, plus a visibility note |
| 5 | Workroom UI displays audit evidence | done — new Audit Evidence section, safe metadata only |
| 6 | Plain-text rendering / no-`dangerouslySetInnerHTML` preserved | done — no new rendering path introduced |
| 7 | No-dispatch / no-resume safety preserved | done — unchanged, always `false` |
| 8 | Deployed to test runtime | done — orchestrator-only rebuild, no migration |
| 9 | Operator validation request prepared | done — `step66c3-operator-validation-request.md` |

## 2. G1 — Message visibility filtering

**Root cause / prior state.** 66C.1/66C.2 always created messages with `visibility:
task_participants` and `GET .../workroom` returned every message regardless of caller role — the
visibility model was schema-modeled but not enforced.

**Fix.** `shared/sdk/tasks/workroom_rbac.py` adds `_VISIBILITY_ROLES` (a role-allowlist per
`visibility` value), `visible_message(role, visibility)`, and `filter_messages_by_visibility(messages,
role)`. `GET /tasks/{task_id}/workroom` (`apps/orchestrator/src/workroom_api.py::get_workroom`) now
calls `filter_messages_by_visibility` on every response — **server-side, not frontend-only**. Any
`visibility` value not explicitly listed in `_VISIBILITY_ROLES` is fail-closed (visible to nobody),
so an unrecognized future value can never accidentally leak. See
`step66c3-message-visibility-evidence.md` for the enforced matrix and test evidence.

## 3. G3 — Per-task audit lookup / evidence endpoint

**New endpoint.** `GET /tasks/{task_id}/audit-evidence` reads `shared.sdk.audit.store.AuditStore
.get_audit_logs(task_id)` (the existing `audit_logs` table, unchanged — Stage 19's
`stream.audit` → `audit-worker` → `audit_logs` pipeline is reused, not duplicated) and projects each
row through an **allowlist** (`_AUDIT_EVIDENCE_REF_FIELDS`) before returning it — never a raw
message/answer body, request payload, header, cookie, token, or secret. RBAC:
`platform_admin`/`agent_operator`/`security_compliance_reviewer`/`pm_engineering_lead` allowed;
`requester`/`reviewer_approver` denied by default (conservative, documented choice — see
`step66c3-task-audit-evidence-endpoint-record.md`).

## 4. G5 — Answered-twice guard

**Root cause found.** The 66C.1 `answer_clarification` store method did an unconditional `UPDATE ...
SET status='answered' ... WHERE id=$1` with **no `status='open'` guard in the WHERE clause** — the
API layer's pre-check (`if clarification["status"] != "open": raise 409`) was read-then-write, not
atomic, so two concurrent answer requests could both pass the pre-check and both succeed, creating
two answer messages and two `clarification_answered` audit events.

**Fix.** `shared/sdk/tasks/workroom_store.py::claim_clarification_answer` now does an atomic
`UPDATE ... WHERE id=$1 AND status='open' RETURNING *` — Postgres row-level locking means only one
concurrent request can ever match. `apps/orchestrator/src/workroom_api.py::answer_clarification`
calls this claim **before** creating the answer message or emitting the audit event, so a lost race
has zero side effects. The stable error code is `409 clarification_already_answered`. See
`step66c3-answered-twice-guard-record.md`.

## 5. Frontend

- **Visibility note.** `MessageList` in `TaskWorkroom.tsx` shows: *"Some operator-only or audit-only
  messages may be hidden based on your role."* The UI never re-filters — it only renders what the API
  already returned.
- **Audit Evidence section.** A new `AuditEvidenceSection` component fetches
  `GET /tasks/{id}/audit-evidence` independently of the main workroom load. On `403` it shows *"Audit
  evidence is restricted for your current role."* (not a hard page error — the rest of the workroom
  still renders). On success it renders only the safe fields (`event_type`, `actor`/`role`,
  `created_at`, `status`, `body_length`/`body_hash`) via plain React text interpolation.
- **Answered-twice readable error.** `workroomClient.ts` maps `clarification_already_answered` to
  *"This clarification has already been answered."*, shown in the existing answer-form error slot.

## 6. Plain statements (for verifier)

- G1 message visibility filtering: implemented, server-side.
- G3 per-task audit evidence endpoint: implemented.
- G5 answered-twice guard: implemented, atomic, dedicated tests.
- No raw message body exposed through audit evidence.
- No workflow dispatch occurred.
- No workflow resume occurred.
- No external action occurred.
- No production action occurred.
- production_executed_true_count=0.

## 7. Step 66C.3-V operator validation (2026-07-11)

Operator confirmed **`VISIBLE`** against all 12 items in
`step66c3-operator-validation-request.md`. **G1, G3, and G5 are fixed.** Step 66C.3 final status:
**`PASS, operator VISIBLE`**. Step 66C.4 is READY_TO_START. See
`step66c3-operator-validation-record.md`.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
