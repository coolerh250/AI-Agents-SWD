# Step 66C.2-R — Clarification UI Evidence

> **Evidence only. No production action. No external action.**

## 1. Local frontend test evidence (vitest, jsdom, no real backend)

`npm test` (`vitest run`) in `apps/admin-console/` — **87 tests / 12 files, all passing**
(58 pre-existing + 29 in `src/__tests__/WorkroomUI.test.tsx`, up from 21). `readOnlyGuard.test.ts`
(3/3) and `taskApiGuard.test.ts` (6/6) both still pass unmodified — `taskApiGuard.test.ts`
automatically covers the updated `workroomClient.ts` (new `createClarification()` method) since it
walks the whole `src/tasks/` directory.

New test coverage added in this remediation (`WorkroomUI.test.tsx`, describe blocks
`"Step 66C.2-R -- Create Clarification"` and `"Step 66C.2-R -- malicious text in clarifications"`):
- The Create Clarification form renders in the Clarifications section
  (`data-testid="workroom-create-clarification"`).
- **Send Message never becomes a clarification** — posting a normal message calls only
  `POST /tasks/{id}/workroom/messages`; the request URL is asserted to not contain `/clarifications`.
- Create Clarification requires a non-empty question before submitting.
- The clarification question textarea is capped at 4000 characters
  (`maxLength={CLARIFICATION_QUESTION_MAX_LENGTH}`).
- Creating a clarification calls `POST /tasks/{id}/clarifications` with the required
  `X-Task-Actor`/`X-Task-Role` headers and a JSON body `{ question, assigned_to }`; after the
  refresh that follows, the newly-created clarification is shown with `status: "open"` and its
  answer form visible.
- A readable RBAC error (`role_cannot_create_clarification` → "Your simulated role cannot create a
  clarification request.") is shown when the server rejects the create call.
- **A malicious-looking clarification question** (`<img src=x onerror=alert(1)>`) renders as literal
  text (`textContent` equals the raw string) — no `<img>` DOM element is created
  (`queryByRole("img")` / `document.querySelector("img")` both `null`).
- **A malicious-looking clarification-answer message** (`message_type: "clarification_answer"`,
  same payload) renders as literal text via the existing message list — same two assertions.

All pre-existing 66C.2 test coverage (plain-text rendering, message composer, answer form, static
security guardrails: no `dangerouslySetInnerHTML`, no token/credential/csrf/cookie, no generic
`request()` helper, no external-integration endpoint reference) remains unchanged and passing.

## 2. Local build evidence

`npm run build` (`tsc -b && vite build`) — **success**, 94 modules transformed (unchanged count —
no new source files were added, only existing files were extended). Output
`static/dist/index.html` + `assets/index-*.js` (247.5 kB / 74.0 kB gzip, up from 245 kB / 73.6 kB)
+ `assets/index-*.css` (4.63 kB / 1.30 kB gzip, up from 4.24 kB / 1.26 kB). No TypeScript errors, no
build warnings.

## 3. Live test-runtime validation (test host, `aiagents-test`)

See `step66c2-test-deployment-record.md` §5 (updated in this remediation) for the deployment steps
and captured live results, including the full create-clarification-from-UI-request-pattern →
`clarification_needed` → answer-from-UI-request-pattern → `answered` flow.

## 4. Statement

No workflow dispatch occurred. No workflow resume occurred. No external action occurred. No
production action occurred. production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
