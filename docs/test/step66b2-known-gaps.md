# Step 66B.2 — Known Gaps

> **Documentation only. No production action.**

## Blocking (none)

No blocking gaps — 66B.2 PASS criteria met (see completion report). Operator validation: VISIBLE
(Zachary, 2026-07-09; see `step66b2-operator-ui-validation-record.md`).

## Non-blocking

0. **UI wording note (operator-confirmed, not a gap).** The `/tasks/new` page is labeled
   **"Create Task"**, not "New". Operator confirmed during validation this is an acceptable, clearer
   wording and explicitly **not a functional gap** — recorded here for completeness only, not as an
   open item.

1. **No real identity/session model.** Carried over from 66B.1 — RBAC uses the fail-closed
   test-only header simulation; the UI's `TestRoleBanner` is a stand-in until a real
   identity/session model exists.
2. **No CSRF.** Out of scope per the 66B.2 spec (no cookie-based session to protect yet). Will be
   needed once a real session model lands.
3. **Role change mid-page does not auto-refetch.** `TestRoleBanner` persists the new
   `{actor, role}` to `localStorage` immediately, so the **next** API call uses it — but an
   already-mounted `AsyncView` (e.g. a loaded task list) does not automatically re-fetch. Navigating
   or reloading applies the new role. Documented in the banner's own copy.
4. **Filters on `/tasks` remount `AsyncView` via a `key` trick**, not a dedicated re-fetch hook —
   functionally correct (confirmed by tests) but a lighter-weight pattern than a proper data-fetching
   hook. Acceptable for MVP scope; revisit if the pattern is reused elsewhere.
5. **No pagination on `/tasks`.** The list page renders whatever `GET /tasks` returns; large task
   counts are not paginated. Not a concern at current data volumes; deferred.
6. **`owner`/`created_by` filters are separate free-text inputs**, not validated against known
   actors (no actor directory exists yet).
7. **No client-side task_type-specific dynamic form fields** — the create form is uniform across all
   10 task types; type-specific fields (if any emerge) are future work.
8. **`statusTone()` (shared badge-coloring util) does not have bespoke colors for every new task
   lifecycle status** (e.g. `intake_review`, `submitted` render neutral, not a dedicated tone) — not
   modified in this stage to avoid touching shared behavior for other pages; acceptable default.

## Deferred to 66B.3 / later stages

Agent Workroom (66C), Clarification replies (66C), Delivery Inbox (66D), Accept/Reject/Request
Changes/Re-run QA (66D), Approvals UI (66D/66G), DLQ/Retry UI (66D/66G), lifecycle notifications
(66G), Slack/Discord/Telegram intake (66F), real identity/session model + CSRF (timing TBD).

## Statement

No production action occurred. No workflow dispatch occurred. No external action occurred. Gaps
above are all non-blocking for the 66B.2 PASS criteria.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
