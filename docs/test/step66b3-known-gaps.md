# Step 66B.3 — Known Gaps

> **Documentation only for this list. No production action.**

## Blocking (none)

No blocking gaps — 66B.3 PASS criteria met (see `step66b3-rbac-audit-safety-hardening-report.md`).

## Non-blocking

1. **No per-task audit lookup endpoint.** `GET /tasks/{id}` does not join to the audit trail; there
   is no `GET /tasks/{id}/audit` (or equivalent) in this stage. `correlation_id` is returned as the
   intended future join key. Documented rather than fabricated (see
   `step66b3-audit-evidence-record.md` §3).
2. **`role_cannot_view_tasks` is currently unreachable in practice.** All six roles are in
   `_VIEW_ROLES` (`shared/sdk/tasks/rbac.py`), so `can_view()` never returns `False` today — the
   `_deny(ctx, "get"/"list", "role_cannot_view_tasks")` code path exists for forward-compatibility
   (e.g. if a future role is added that cannot view) but has no live trigger. Not a functional gap;
   documented for clarity.
3. **Role-change mid-page still does not auto-refetch** (carried over from 66B.2) — the new
   current-identity readout reflects the *persisted* selection immediately, but an already-loaded
   `AsyncView` (e.g. a loaded task list) does not automatically re-fetch under the new role.
4. **Readable role labels are UI-display-only.** The `X-Task-Role` header value sent to the backend
   is unchanged (raw snake_case); `TASK_ROLE_LABELS` only affects what the operator sees in the
   dropdown/current-identity text.
5. **Readable RBAC error messages cover a fixed, hand-maintained list** (`READABLE_ERRORS` in
   `taskClient.ts`). Any future backend `detail` code not added to this map falls back to the raw
   code + HTTP status, same as before 66B.3 — not a regression, just an incomplete-by-design mapping.
6. **Safety panel is presentation-only.** It re-displays fields already present in the full
   `KeyValueTable` dump (plus two static `false` constants) for at-a-glance scanning — it introduces
   no new backend data.

## Real identity/session/CSRF (future work)

Carried forward from 66B.1/66B.2, restated for this hardening stage: there is **no real production
identity/session model and no CSRF protection** for the Task API. `TASK_API_TEST_AUTH_ENABLED` +
`X-Task-Actor`/`X-Task-Role` headers are a documented, fail-closed, test-only stand-in. A real
identity/session model (and CSRF once a real session/cookie exists) remains explicitly deferred —
timing not yet scheduled. This does not weaken production safety today: the gate fails closed, and
no production deployment would ever set `TASK_API_TEST_AUTH_ENABLED=true`.

## Deferred to 66C / later stages

Agent Workroom (66C), Clarification replies (66C), Delivery Inbox (66D), Accept/Reject/Request
Changes/Re-run QA (66D), Approvals UI (66D/66G), DLQ/Retry UI (66D/66G), lifecycle notifications
(66G), Slack/Discord/Telegram intake (66F), real identity/session model + CSRF (timing TBD),
per-task audit lookup endpoint (timing TBD).

## Statement

No production action occurred. No workflow dispatch occurred. No external action occurred. Gaps
above are all non-blocking for the 66B.3 PASS criteria.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
