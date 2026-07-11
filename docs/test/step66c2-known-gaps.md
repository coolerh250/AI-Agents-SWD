# Step 66C.2 — Known Gaps

> **Documentation only. No production action.**

## Blocking (none)

No blocking gaps — 66C.2 PASS criteria met (see `step66c2-workroom-ui-report.md`). No
`dangerouslySetInnerHTML` is used anywhere in the workroom UI (verified statically).

## Non-blocking

1. **`createClarification()` is not implemented in the UI.** Per spec explicit allowance ("operator-
   facing create-clarification UI may be deferred if it complicates 66C.2"). Clarifications shown
   and answered by this UI are created via the `POST /tasks/{id}/clarifications` API directly (by an
   authorized role, e.g. `pm_engineering_lead`) — the live validation for this stage exercises that
   exact flow. Deferred to a future 66C sub-stage if the operator wants an in-UI create form.
2. **No real-time/websocket delivery.** The Workroom page loads once per navigation/refresh via
   `GET .../workroom`; there is no push/subscribe mechanism. Carried over from 66C.1 (out of scope
   there too).
3. **No rich markdown rendering.** Message bodies are plain text only, by design (security
   requirement, not a gap to close) — carried here for completeness, not as something to "fix."
4. **No file attachment support.** Out of scope per spec.
5. **No URL auto-linking.** Out of scope per spec — URLs in message bodies render as plain text, not
   clickable links, to avoid introducing an unreviewed `<a href>` construction path.
6. **No private per-agent channels.** Out of scope per spec (also out of scope for the 66C.1
   backend — `visibility` filtering, G1, is not implemented yet either).
7. **Message-visibility filtering not implemented (carried over from 66C.1, G1).** The Workroom UI
   shows every message the API returns; since the API itself does not yet filter by `visibility`
   (66C.1 gap G1, assigned to 66C.3), the UI has nothing to additionally filter either. Will be
   addressed together with the backend filtering in 66C.3.
8. **No per-task audit lookup surfaced (carried over from 66C.1, G3).** The UI does not (and cannot)
   show a full audit trail — see `step66c2-workroom-ui-security-record.md` §4. Assigned to 66C.3.
9. **RBAC is server-enforced only, not client-side hidden.** The answer form and message composer
   are always rendered (when a clarification is open); if the current simulated role lacks the
   capability, the action fails server-side and a readable error is shown. This matches the existing
   pattern from `TaskNew.tsx`/`TaskDetail.tsx` (66B.2/66B.3) — the server is the RBAC authority, the
   UI does not attempt to predict or hide based on role client-side.
10. **Answered-twice guard not covered by a dedicated UI test** (carried over from 66C.1, G5). The
    answer form is hidden once `status !== "open"`, so the UI cannot normally trigger this backend
    guard; a race (two tabs answering simultaneously) would surface the backend's `409` via the
    existing readable-error path but is not explicitly tested here. Assigned to 66C.3.

## Deferred to 66C.3

Message-visibility filtering (G1), per-task audit lookup surfaced in UI (G3), answered-twice guard
dedicated test (G5), any UI-side hardening that follows from the backend hardening in that stage.

## Deferred to 66C.4 / 66S / later stages

Clarification reminder/expiry scheduler + any UI surfacing of it (66C.4), real identity/session/CSRF
replacing the test-role banner (66S), Delivery Inbox / Approvals / DLQ-Retry UI / notifications
(66D+), in-UI clarification creation (future, if authorized).

## Statement

No production action occurred. No workflow dispatch occurred. No workflow resume occurred. No
external action occurred. Gaps above are all non-blocking for the 66C.2 PASS criteria.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
