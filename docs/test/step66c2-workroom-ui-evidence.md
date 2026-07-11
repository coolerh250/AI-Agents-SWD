# Step 66C.2 — Workroom UI Evidence

> **Evidence only. No production action. No external action.**

## 1. Local frontend test evidence (vitest, jsdom, no real backend)

`npm test` (`vitest run`) in `apps/admin-console/` — **79 tests / 12 files, all passing**
(58 pre-existing + 21 new in `src/__tests__/WorkroomUI.test.tsx`). `readOnlyGuard.test.ts` (3/3) and
`taskApiGuard.test.ts` (6/6) both still pass unmodified — `taskApiGuard.test.ts` automatically
covers the new `workroomClient.ts`/`workroomTypes.ts` files since it walks the whole `src/tasks/`
directory.

New test coverage (`WorkroomUI.test.tsx`):
- Task Detail renders the "Open Workroom" link pointing at `/tasks/{id}/workroom`.
- Workroom page renders the safety panel with `dispatch_enabled`/`resume_dispatch_enabled` from the
  API response.
- Test-role banner is shown on the Workroom page.
- Empty state ("No messages yet" / "No clarification requests") and error state ("Unable to load
  data…") render correctly.
- A readable RBAC error message (`not_own_task`) is shown.
- A normal message body renders as visible text.
- **A malicious-looking body (`<img src=x onerror=alert(1)>`) renders as literal text — no `<img>`
  DOM element is created** (`queryByRole("img")` / `document.querySelector("img")` both `null`).
- The clarification question renders with `textContent` exactly equal to the raw question string.
- The message composer requires a non-empty body, caps the textarea at 8000 characters, and posts
  with `X-Task-Actor`/`X-Task-Role` headers, refreshing the workroom on success.
- The answer form requires a non-empty answer, caps the textarea at 8000 characters, is hidden for
  an already-answered clarification, and posts with the required headers, refreshing on success.
- Static guards: no `dangerouslySetInnerHTML`, no generic `request(method,url)` helper, no
  token/credential/csrf/cookie reference, no external-integration endpoint reference.

## 2. Local build evidence

`npm run build` (`tsc -b && vite build`) — **success**, 94 modules transformed (up from 91 in
66B.2/66B.3), output `static/dist/index.html` + `assets/index-*.js` (245 kB / 73.6 kB gzip) +
`assets/index-*.css` (4.24 kB / 1.26 kB gzip). No TypeScript errors, no build warnings.

## 3. Live test-runtime validation (test host, `aiagents-test`)

See `step66c2-test-deployment-record.md` for the deployment steps and captured live results.

## 4. Statement

No workflow dispatch occurred. No workflow resume occurred. No external action occurred. No
production action occurred. production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
