# Step 66C.2 — Workroom UI Security Record

> **66C.2 implemented Admin Console Workroom UI only. Messages are rendered as plain text only. No
> dangerouslySetInnerHTML is allowed. No workflow dispatch occurred. No workflow resume occurred.
> No external action occurred. No production action occurred. production_executed_true_count=0.**

These are the Step 66C.2 blocking security requirements (spec §5) and how each is satisfied.

## 1. Plain text rendering only

Message bodies (`TaskMessage.body`) and clarification questions/answers
(`ClarificationRequest.question`, answer submissions) are rendered exclusively via React's ordinary
text-content interpolation — `{m.body}`, `{clarification.question}` — in
`apps/admin-console/src/pages/TaskWorkroom.tsx`. React escapes text-content interpolation by
default, so no HTML tag, script, iframe, object, or embed in a message body is ever parsed as
markup; it renders as literal visible text.

**No dangerouslySetInnerHTML is allowed** — and none is used anywhere in the workroom page or
client. Verified by a static source-grep test
(`apps/admin-console/src/__tests__/WorkroomUI.test.tsx::"never uses dangerouslySetInnerHTML in the
workroom page or client"`), which reads `TaskWorkroom.tsx`, `workroomClient.ts`, and
`workroomTypes.ts` and asserts the literal string is absent from all three.

No markdown-to-HTML rendering library is used. No URL auto-linking is performed — URLs in message
bodies render as plain text, not as clickable `<a>` tags (deferred per spec, out of scope for
66C.2).

## 2. XSS guard tests

`apps/admin-console/src/__tests__/WorkroomUI.test.tsx` includes:

- **Static guard**: no `dangerouslySetInnerHTML` in `TaskWorkroom.tsx` / `workroomClient.ts` /
  `workroomTypes.ts` (see §1).
- **Behavioral guard**: a workroom message with body
  `<img src=x onerror=alert(1)>` is rendered — the test asserts (a) the literal string appears as
  visible text content (`screen.getByText(...)`), and (b) **no actual `<img>` DOM element exists**
  (`screen.queryByRole("img")` and `document.querySelector("img")` are both `null`), proving the
  markup was never parsed/executed, only displayed as text.
- **Clarification answer guard**: the clarification question is asserted to render with `textContent`
  exactly equal to the raw question string (no HTML interpretation).

## 3. Input limits

Both limits match the Step 66C.1 backend exactly
(`shared/sdk/tasks/workroom_models.py::MESSAGE_BODY_MAX_LENGTH` /
`CLARIFICATION_ANSWER_MAX_LENGTH`, both `8000`):

- **Human message**: max **8000** characters — enforced client-side via the composer's `<textarea
  maxLength={8000}>` (hard browser-level cap) and a pre-submit client validation that shows a
  readable field error if somehow exceeded (defense in depth); the backend's own `422` on
  violation is additionally surfaced through the readable-error mapping if it occurs.
- **Clarification answer**: max **8000** characters — identical pattern (`maxLength={8000}` on the
  answer `<textarea>`, plus client + server validation).
- If the backend returns a validation error (`422` or any other non-2xx), `WorkroomApiError`
  surfaces a readable message via `workroomClient.ts`'s `READABLE_ERRORS` map (mirrors
  `taskClient.ts`'s Step 66B.3 pattern), shown in the composer/answer-form's inline error state.

Verified by `WorkroomUI.test.tsx`: `"rejects a body over the 8000-character limit client-side"`,
`"caps the answer textarea at 8000 characters"`.

## 4. Audit privacy reminder

The Workroom UI does **not** expose raw audit payloads. What it shows: `audit_ref` (opaque, if
present on a message — currently always `null`, no code path sets it yet), `correlation_id` (in the
underlying message object, not separately surfaced in the UI copy), `message_id`/`clarification_id`
(as the React `key` and internal reference, not prominently displayed as "audit evidence"). The UI
never implies a full audit-trail lookup exists — there is no "View Audit Log" button or similar
affordance, consistent with the still-open `step66c1-known-gaps.md` gap **G3** (no per-task audit
lookup endpoint exists yet on the backend either).

## 5. Test-only auth boundary (unchanged)

`workroomClient.ts` reuses `testRole.ts`'s `{actor, role}` label exactly like `taskClient.ts` — no
token, session identifier, cookie, or CSRF value is ever read, stored, or sent. Verified by
`WorkroomUI.test.tsx`: `"workroom client never touches a token / credential / csrf / cookie value"`
and `"workroom client exposes no generic request(method,url) helper"`. The pre-existing
`taskApiGuard.test.ts` (which walks the entire `src/tasks/` directory) automatically covers
`workroomClient.ts` and `workroomTypes.ts` without any change to that guard test.

## 6. No external call

`workroomClient.ts` only ever calls `${API_BASE}/tasks/...` — no GitHub/Discord/Slack/Telegram/
LLM/web endpoint reference exists in the file. Verified by
`WorkroomUI.test.tsx::"workroom client does not call external integration endpoints"`.

## 7. Plain statements (for verifier)

- 66C.2 implemented Admin Console Workroom UI only.
- Messages are rendered as plain text only.
- No dangerouslySetInnerHTML is allowed.
- No workflow dispatch occurred.
- No workflow resume occurred.
- No external action occurred.
- No production action occurred.
- production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
