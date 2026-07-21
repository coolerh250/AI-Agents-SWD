# Codex Implementation Notes — Step 66UI.4-FE.1D

> Owner: Claude Design, for Codex (Frontend Engineer). **Codex is NOT authorized by this document.**
> Authorization requires Claude Code technical-readiness review to pass AND an explicit Product Owner
> go-ahead. These notes describe the intended frontend-only FE.1D build for when that happens.

## 1. Frontend-only items FE.1D may implement (once authorized)

- **Nav labels/badges/subtitles** (`Nav.tsx`): "Soon"/stage markers on placeholder items; optional
  group subtitles; shortened Platform Ops labels; read-only/evidence markers; optional Platform Ops
  visual sub-headers; within-group ordering. No route or route-target change.
- **Microcopy** (`TaskList.tsx`, placeholder pages, empty states): product-language titles/notes/
  buttons/empty states; standardized placeholder wording; normalized `requiredStep` prop values.
- **Shared status-label map**: extract + complete `TASK_STATUS_LABELS` (currently partial in
  `ExecutiveOverview.tsx`) into a shared module used by TaskList (dropdown display + badge) and
  Overview. **Option/enum values stay raw**; only display text changes.
- **TaskList table**: relative-time display for `created_at`/`updated_at` (reuse Overview
  `relativeTime`); `production_effect`/`requires_approval` as chips-only-when-true; product column
  headers.
- **Overview demoted metrics labels**: relabel per `field-label-cleanup-map.md` (display only).
- **Move-to-details (category B)**: wrap raw ID/hash/correlation fields (and, if confirmed, Task
  Detail's raw `KeyValueTable`) in a "Technical details" `<details>` disclosure on pages that
  already render them. **[confirm scope with Claude Code first]**
- **Safety wording micro-polish** (`CalmSafetyPosture.tsx`): cosmetic only (dash/case
  consistency) — **no change to tone thresholds, field set, or evidence logic**.

## 2. Forbidden (always)

```text
No backend / API / database / workflow change. No new endpoint. No route additions or route-target
changes. No IA restructure. No two-way URL sync. No SPA deep-link / hard-refresh fallback fix
(that is a BACKEND change — docs/frontend/admin-console-spa-deep-link-fallback-known-gap.md).
No workflow dispatch/resume/state mutation. No production or external action. No real Delivery /
Reminder / Notifications / Pipeline functionality. No change to enum/boolean/timestamp underlying
values or API payloads (display only). No re-rename of FE.1B/FE.1B.1 safety field labels. No change
to safety tone logic. No fabricated fields/values (category D stays out). No client-side-only RBAC.
No deployment. No merge.
```

## 3. Needs Claude Code confirmation before implementing

- Authoritative `TASK_STATUSES` enum list (so the status-label map is exhaustive).
- Which pages actually render raw `task_id`/`work_item_id`/`execution_id`/`event_id`/hashes (for
  the category-B move-to-details).
- Whether wrapping Task Detail's raw `KeyValueTable` in a disclosure is in FE.1D scope or a later
  phase.
- Whether `PlaceholderPanel` may take a non-"Requires Step" line for the Notifications "Planned"
  copy (tiny component tweak) or whether to keep the current sentence shape.
- The `delivery_package_ready_for_admin_console` → "Ready to publish" rename meaning.

## 4. Needs Product Owner decision

- Optional Platform Ops sub-headers (include or not).
- "New task" vs "Create task"; Notifications "Planned" wording.

## 5. Suggested PR shape (once authorized)

Frontend-only, one cohesive PR (or a small sequence): shared status-label module → nav labels/badges/
Platform Ops density → TaskList microcopy/labels/relative-time → Overview metric relabels →
placeholder/empty-state consistency → safety cosmetic polish. All display-only; reuses existing data
and components; revertible. Frontend tests + `npm run build` / `npm test` required.

## Statement

Design specification only. No runtime code. No production action. No Codex implementation authorized
by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
