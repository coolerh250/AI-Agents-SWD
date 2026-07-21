# Design Brief — Step 66UI.4-FE.1D Navigation Polish + Microcopy / Field Label Cleanup

> Owner: Claude Design. Frontend-only polish design spec for the next sub-stage, to be reviewed by
> Claude Code and then implemented (once authorized) by Codex. **Design/documentation only — no
> runtime code, no backend/API/DB/workflow change, no new endpoint, no Codex authorization, no
> deployment, no merge.**

## Stage

`66UI.4-FE.1D-DESIGN` (design for the FE.1D sub-stage). Source of truth: `main` @ `707cb8c`.

## Goal

After FE.1A (visual tokens), FE.1B/FE.1B.1 (calm safety posture + safety field mapping), FE.1C
(attention-first Overview), and FE.1C.1 (task-list deep-link filter), the Admin Console reads much
more like a product. FE.1D is a **final language/label polish pass** over what remains
engineering-flavored, changing only **labels, microcopy, helper text, badges, and section grouping/
ordering** — never data, routes, endpoints, or behavior.

Make the console read as an **AI team command center / operator workspace / product console**, not
an **API inspector / debug console / raw backend viewer / engineering dashboard**.

## Scope (frontend-only, label/microcopy)

1. Navigation polish — labels, helper text/subtitles, placeholder badges, Platform Ops density.
2. Page / section title polish.
3. Product microcopy cleanup (titles, empty states, placeholders, buttons, filters, status labels).
4. Engineering-field exposure reduction (relabel / move-to-details), categorized A–D.
5. Field label rename map (before → after).
6. Platform Ops density / grouping polish (minimal, non-structural).
7. Empty-state & placeholder wording consistency.
8. Safety / system-posture wording consistency (micro-polish only; FE.1B/FE.1B.1 already did the
   substance — do not re-open or change safety logic).

## Hard constraints (this stage does NOT do, and FE.1D implementation must NOT do)

```text
No frontend code change (this stage). No backend/API/database/workflow change. No new endpoint.
No deployment. No merge. No production action. No external action.
No real Delivery / Reminder / Notifications / Pipeline functionality.
No fix of the Admin Console SPA deep-link / hard-refresh fallback gap
  (docs/frontend/admin-console-spa-deep-link-fallback-known-gap.md) — that is a BACKEND change and
  is explicitly OUT OF FE.1D scope.
No two-way URL sync.
No route additions or route-target changes.
No Codex authorization.
```

Future suggestions are allowed but must be labelled:

- **現在可做 (FE.1D frontend-only polish):** relabels, helper text, badges, section grouping/ordering
  within an existing group, display formatting (e.g. relative time), moving raw fields into a
  "Technical details" disclosure on a page that already renders them.
- **未來才做 (needs backend/API/routing/workflow):** SPA deep-link fallback, real Delivery/Reminder/
  Notifications/Pipeline, any new field/endpoint, two-way URL sync.

## Current state reviewed (for grounding)

- `apps/admin-console/src/components/Nav.tsx` — 7 groups (Overview, Team Work, Deliveries, Operator
  Center, Governance, Platform Ops [20 items, collapsed], Settings); Delivery Package under Platform
  Ops (matches merged decision). **Unchanged since 66UI.2** (not in the FE.1B–FE.1C.1 diff).
- `apps/admin-console/src/App.tsx` — routes incl. placeholder routes (`PlaceholderPage`) for
  Notifications, Clarifications, Reminder/Expiry, Delivery Inbox/Detail, Approvals, DLQ/Retry, and 5
  Settings pages.
- `apps/admin-console/src/pages/ExecutiveOverview.tsx` — FE.1C attention-first Overview (product
  microcopy already strong; demoted metrics still use some engineering labels).
- `apps/admin-console/src/pages/TaskList.tsx` — still shows raw status enums in the filter dropdown
  and badges, raw timestamps, always-on boolean columns, and a "Step 66B" engineering note.
- `apps/admin-console/src/components/CalmSafetyPosture.tsx` + `SafetyStatusBar.tsx` — FE.1B/FE.1B.1
  safety wording is already product-grade and consistent; FE.1D leaves the substance and proposes
  only tiny cosmetic polish.
- `apps/admin-console/src/components/PlaceholderPanel.tsx` / `pages/PlaceholderPage.tsx` — one shared
  placeholder pattern; `requiredStep` values are slightly inconsistent (`"66D"`, `"66S"`, `"66S or
  later"`, `"future notifications stage"`).

## Companion documents

`navigation-polish-spec.md`, `microcopy-guide.md`, `field-label-cleanup-map.md`,
`engineering-field-exposure-reduction.md`, `platform-ops-density-spec.md`,
`product-owner-review-checklist.md`, `codex-implementation-notes.md`; stage artifacts under
`docs/stages/66ui4-fe1d-navigation-microcopy-design/`.

## Statement

Design specification only. No runtime code. No production action. No API/contract decision. No
Codex implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
