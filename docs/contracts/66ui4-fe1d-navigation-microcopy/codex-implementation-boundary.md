# Codex Implementation Boundary — Step 66UI.4-FE.1D-BOUNDARY

> **Boundary consolidation / implementation readiness packaging only. No runtime code changed by
> this document. No backend/API/database/workflow change. No new endpoint. No deployment. No merge.
> No production/external action. Codex remains unauthorized. FE.1D implementation remains
> unauthorized.**

Executed by: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`).

## 1. Stage purpose

Consolidate the FE.1D design (`design/66ui4-fe1d-navigation-microcopy`, Claude Design), the FE.1D
technical readiness review (`review/66ui4-fe1d-technical-readiness`, Claude Code), and the Product
Owner's decisions on the two open items from that review, into a single, final implementation
boundary document. This boundary is the artifact a future Codex implementation stage must follow if
and when the Product Owner separately authorizes Codex to implement FE.1D. This stage packages
readiness only — it does not itself authorize implementation, merge, or deployment.

## 2. Source documents

```text
Design (Claude Design, PASS): design/66ui4-fe1d-navigation-microcopy, commit 43269c5, Draft PR #12
  - docs/design/66ui4-fe1d-navigation-microcopy/design-brief.md
  - docs/design/66ui4-fe1d-navigation-microcopy/navigation-polish-spec.md
  - docs/design/66ui4-fe1d-navigation-microcopy/microcopy-guide.md
  - docs/design/66ui4-fe1d-navigation-microcopy/field-label-cleanup-map.md
  - docs/design/66ui4-fe1d-navigation-microcopy/engineering-field-exposure-reduction.md
  - docs/design/66ui4-fe1d-navigation-microcopy/platform-ops-density-spec.md
  - docs/design/66ui4-fe1d-navigation-microcopy/product-owner-review-checklist.md
  - docs/design/66ui4-fe1d-navigation-microcopy/codex-implementation-notes.md
  Marker: DESIGN66UI4_FE1D_NAVIGATION_MICROCOPY_VERIFY: PASS

Technical readiness review (Claude Code, PASS_WITH_GAPS): review/66ui4-fe1d-technical-readiness,
  commit 25309ea
  - docs/design/66ui4-fe1d-navigation-microcopy/claude-code-technical-readiness-review.md
  - docs/test/step66ui4-fe1d-technical-readiness-review-record.md
  Marker: STEP66UI4_FE1D_TECHNICAL_READINESS_VERIFY: PASS

Product Owner decisions (this stage, §3 below): "+ Create task" unchanged; delivery_package_ready_
  for_admin_console rename deferred to 66D; TECH-REVIEW PASS_WITH_GAPS accepted; Codex still not
  authorized.
```

Both source branches are based directly on `main` @ `707cb8c`; this boundary is likewise produced
against `main` @ `707cb8c`, with no intervening merge.

## 3. Product Owner decisions

Verbatim authorization:

```text
接受 Step 66UI.4-FE.1D-TECH-REVIEW 判定為 PASS_WITH_GAPS；PO 決策如下：
1. 維持目前 "+ Create task" 文案，不改為 "New task"。
2. 不在 FE.1D 將 delivery_package_ready_for_admin_console 改為 "Ready to publish"，此項 deferred 到
   66D Delivery 階段。
授權 Claude Code 依上述決策整理 FE.1D Codex Implementation Boundary；仍不得授權 Codex 實作，不得修改
frontend/backend/API/DB/workflow，不得新增 endpoint，不得部署。
```

Applied to this boundary as:

```text
1. Step 66UI.4-FE.1D-TECH-REVIEW's PASS_WITH_GAPS verdict is accepted as-is; no re-review requested.
2. "+ Create task" (TaskList.tsx) stays unchanged. Excluded from every slice below.
3. delivery_package_ready_for_admin_console -> "Ready to publish" is excluded from FE.1D entirely
   and deferred to Step 66D (Delivery). Not scheduled by this document.
4. Codex remains unauthorized for FE.1D implementation. This document does not authorize it.
5. No runtime source change is authorized by this document. No deployment is authorized by this
   document.
```

The Product Owner's decisions resolve both open items flagged in the technical readiness review
(§6 items 2 and 5 of that review); no other open item from that review required a Product Owner
decision (the remaining items were either already resolved by the review's own default-rule
application, or are genuinely deferred/out-of-scope items requiring no decision here).

## 4. Allowed frontend-only changes

Carried forward, unchanged, from the stage prompt's own required scope (§3.1) and cross-checked
against the technical readiness review's feasibility classification (all Category A, or Category B
items the review confirmed in-scope):

```text
1. Nav.tsx label / subtitle / badge polish (component at apps/admin-console/src/components/Nav.tsx
   -- see note below on path discrepancy).
2. Platform Ops compact density polish (labels, read-only/evidence markers, existing collapsed +
   compact-density treatment). Optional visual sub-headers are NOT included by default -- see §8.
3. Read-only / evidence / Soon badges, where purely presentational (text + muted styling, no route
   change).
4. TaskList and Overview microcopy polish (titles, empty states, filter labels, status label
   display, table column headers, relative-time display), EXCLUDING the "+ Create task" button
   text (§3 item 2).
5. Existing status label display map cleanup -- using the CORRECTED 8-entry missing-status list
   from the technical readiness review (§7.1 of that review): draft, submitted, blocked, failed,
   accepted, rejected, archived, canceled. The design doc's own "missing entries" list (which
   referenced non-existent enum values aborted/completed/devops/requirement_analysis and omitted
   real ones) must NOT be used as-is.
6. Empty state and placeholder wording consistency (standardized three-line PlaceholderPanel
   pattern; Notifications "Planned" wording variant, which needs a small, frontend-only
   PlaceholderPanel prop addition -- confirmed safe by the technical readiness review).
7. Minor safety wording cosmetic consistency only (CalmSafetyPosture.tsx dash/case consistency in
   title-string literals). No change to getCalmSafetyPosture()'s tone/threshold/field-set logic.
8. Relative time display for TaskList's created_at/updated_at, reusing ExecutiveOverview's existing
   relativeTime() helper (or an equivalent frontend-only helper) -- display only, no data change.
9. Task Detail (TaskDetail.tsx) safety-panel relabel to already-shipped SAFETY_EVIDENCE_FIELDS
   wording, and wrapping its raw KeyValueTable object dump in a "Technical details" disclosure --
   both confirmed in scope by the technical readiness review (§7.3 of that review).
```

**Path-accuracy note:** this stage's own prompt listed illustrative frontend source paths (e.g.
`apps/admin-console/src/Nav.tsx`, `apps/admin-console/src/features/tasks/TaskList.tsx`,
`apps/admin-console/src/features/safety/CalmSafetyPosture.tsx`) that do not match the actual
repository structure. Verified via `Glob` against the current checkout: the real paths are
`apps/admin-console/src/components/Nav.tsx`, `apps/admin-console/src/pages/TaskList.tsx`,
`apps/admin-console/src/pages/ExecutiveOverview.tsx`, `apps/admin-console/src/components/
CalmSafetyPosture.tsx`, `apps/admin-console/src/components/SafetyStatusBar.tsx`,
`apps/admin-console/src/pages/SafetyCenter.tsx`, `apps/admin-console/src/components/
PlaceholderPanel.tsx`, `apps/admin-console/src/pages/TaskDetail.tsx`. This boundary document and its
companion `implementation-slicing-plan.md` use the verified real paths throughout; a future Codex
implementation must use these real paths, not the prompt's illustrative ones.

## 5. Forbidden changes

Carried forward unchanged from the stage prompt's §3.2, confirmed consistent with the design docs'
own constraints and the technical readiness review's findings:

```text
1. "+ Create task" rename -- keep current text (Product Owner decision, §3).
2. delivery_package_ready_for_admin_console -> "Ready to publish" rename -- deferred to 66D
   (Product Owner decision, §3).
3. SPA deep-link fallback fix (backend; docs/frontend/admin-console-spa-deep-link-fallback-known-
   gap.md -- remains separately tracked, unaffected by this document).
4. Two-way URL sync.
5. Backend changes.
6. API changes.
7. Database changes.
8. Workflow changes.
9. New endpoint.
10. New route.
11. Safety logic changes (CalmSafetyPosture.tsx's getCalmSafetyPosture() function body).
12. RBAC changes.
13. New task status model (the TASK_STATUSES enum itself; only its display-label map may be
    extended per §4 item 5).
14. Real Delivery / Reminder / Notifications / Pipeline functionality.
15. TaskWorkroom.tsx body_hash cleanup (confirmed real by the technical readiness review, but not
    enumerated by any FE.1D design doc with a before/after map -- deferred).
16. Broad Platform Ops / Evidence raw field rename work without mapping (AuditEvidence.tsx,
    DemoEvidence.tsx, and the shared EvidenceTable component's raw snake_case column headers across
    roughly 8 pages -- confirmed real by the technical readiness review, but no before/after map
    exists -- deferred to a future, separately-designed slice).
17. Production/external actions.
```

## 6. Slice 1 scope

```text
Title: Navigation polish
Files: apps/admin-console/src/components/Nav.tsx (single file where possible)
Scope: group subtitles; Soon/read-only/evidence badges on placeholder nav items; shortened
  Platform Ops labels; Platform Ops compact-density treatment (already collapsed by default --
  labels/markers/density class only, no sub-headers by default -- see §8).
Excludes: route changes, any FE.1D functionality beyond label/badge/density, Platform Ops visual
  sub-headers (deferred pending Product Owner input -- see §8).
```

## 7. Slice 2 scope

```text
Title: Microcopy and field labels
Files: apps/admin-console/src/pages/TaskList.tsx, apps/admin-console/src/pages/
  ExecutiveOverview.tsx, apps/admin-console/src/pages/TaskDetail.tsx,
  apps/admin-console/src/components/PlaceholderPanel.tsx, apps/admin-console/src/App.tsx
  (requiredStep prop values only), apps/admin-console/src/components/CalmSafetyPosture.tsx
  (title-string literals only), a new shared status-label module.
Scope: status label map display cleanup (using the corrected 8-entry list, §4 item 5); empty-state
  consistency; relative-time display; production_effect/requires_approval chips-only-when-true;
  Overview metric relabels; placeholder wording standardization incl. Notifications "Planned"
  variant; Task Detail safety-panel relabel + Technical details disclosure wrap; safety wording
  dash/case cosmetic consistency (no logic change).
Excludes: "+ Create task" rename (stays "+ Create task"); delivery_package_ready_for_admin_console
  rename (deferred to 66D); any change to getCalmSafetyPosture()'s logic; any change to
  TaskWorkroom.tsx or the broader evidence-table raw-field surface.
```

## 8. Deferred items

```text
1. Platform Ops optional visual sub-headers (platform-ops-density-spec.md #4) -- ship only if the
   Product Owner explicitly wants it in a future decision; the design's own documented fallback
   (labels + markers + density only, no sub-headers) is what Slice 1 implements by default.
2. TaskWorkroom.tsx body_hash relabel -- no before/after map exists; needs its own design pass.
3. Broad Platform Ops / Audit / Demo-Evidence raw column-header rename work (~8 pages) -- same
   reason; needs its own design pass with an explicit before/after map before any Codex slice
   touches it.
4. SPA deep-link / hard-refresh fallback -- backend change, tracked separately
   (docs/frontend/admin-console-spa-deep-link-fallback-known-gap.md), not part of FE.1D at all.
5. Two-way URL sync -- not part of FE.1D at all.
6. delivery_package_ready_for_admin_console -> "Ready to publish" rename -- explicitly deferred to
   Step 66D (Delivery) per Product Owner decision (§3 item 2).
```

## 9. Required tests for future Codex

```text
1. Frontend unit tests for every changed component (existing project convention: Vitest + React
   Testing Library under apps/admin-console/src/__tests__/).
2. Explicit coverage for: shared status-label map completeness (all 17 TASK_STATUSES values map to
   a label, using the corrected list in §4 item 5); Notifications placeholder renders the "Planned"
   variant without a "Requires Step" line; Task Detail's Technical details disclosure renders the
   full task object and is collapsed by default; safety-panel relabel matches
   SAFETY_EVIDENCE_FIELDS wording exactly; no regression to the FE.1C/FE.1C.1 deep-link /
   query-param behavior (existing tests must still pass unmodified in intent).
3. npm run build (deterministic hash comparison against the pre-change build, or documented new
   hash if intentional visual change).
4. npm run typecheck.
5. npm test -- full suite, not just new tests -- must pass with zero regressions.
6. A safety statement per .agents/skills/frontend-implementation/SKILL.md: workflow dispatch/
   resume "no", external action "no", production action "no", each explicit.
7. Known gaps section listing every item in §8 as explicitly deferred, not silently dropped.
```

## 10. Required Product Owner validation checklist

For the eventual implemented UI (once Codex is authorized, implements, and it is deployed to test
runtime for validation -- none of which this document authorizes):

```text
1. Nav.tsx: group subtitles visible and readable; Soon/read-only/evidence badges visible on the
   correct placeholder/read-only items; Platform Ops labels shortened and legible; no route/
   destination changed by clicking any nav item.
2. TaskList: "+ Create task" text UNCHANGED; status filter dropdown shows product labels while the
   underlying query param/API value is unchanged (spot-check via URL); empty state reads the new
   product-warm copy; created/updated columns show relative time with exact time on hover;
   production-effect/needs-approval chips appear only when true.
3. Overview: demoted metrics show relabeled text; delivery_package_ready_for_admin_console still
   reads its EXISTING label (not "Ready to publish" -- confirm this rename did NOT ship).
4. Task Detail: safety panel shows product labels, not raw snake_case; raw object dump is inside a
   collapsed "Technical details" disclosure, not rendered inline by default.
5. Notifications placeholder: reads the new "Planned" wording, not "Requires Step future
   notifications stage."
6. Safety Center / Overview system posture: tone titles use a consistent em dash; no change to
   which tone (Safe/Attention/Unavailable) is shown for the same underlying data as before this
   change.
7. Confirm no new route is reachable that wasn't reachable before.
8. Confirm the SPA deep-link fallback gap is unchanged (still reproduces the known 404 behavior).
```

## 11. Merge/deploy authorization requirements

```text
This document authorizes none of: Codex implementation, PR merge, or deployment. Per the Merge
Gate and Deployment Gate (.agents/skills/stage-gate/SKILL.md), any future merge or deployment of
FE.1D implementation work requires its own explicit, scoped Product Owner authorization naming the
exact branch/target and environment -- an authorization for this boundary-consolidation stage does
not imply authorization for any later stage. The expected future sequence, unchanged from the
FE.1C/FE.1C.1 precedent, is: Product Owner authorizes Codex -> Codex implements per this boundary
-> Claude Code reviews (Implementation Efficiency Gate) -> Claude Code deploys to test runtime for
Product Owner UI validation (Deployment Gate, with its own explicit authorization) -> Product Owner
validates (Product Owner Validation Gate) -> Product Owner authorizes merge to main (Merge Gate,
with its own explicit authorization) -> Claude Code merges and recalibrates test runtime.
```

## 12. Stop conditions

Per `docs/process/stop-conditions.md` and `.agents/skills/security-governance/SKILL.md`, any future
Codex implementation stage building from this boundary must stop and report (not proceed silently)
if:

```text
1. The stage prompt authorizing implementation conflicts with this boundary document or with the
   Product Owner decisions recorded in §3.
2. A forbidden path (§5, or apps/orchestrator/**, services/**, infra/**, migrations/**,
   database/**, helm/**, k8s/**, .github/workflows/**) needs to be touched to accomplish the
   requested change.
3. A production or external action is requested without explicit, separate Product Owner
   authorization.
4. A workflow dispatch/resume is requested without explicit, separate Product Owner authorization.
5. A secret, token, internal IP, SSH alias, or other internal identifier is found in any file
   touched by the implementation.
6. Any deferred item in §8 is requested without the design pass / Product Owner decision that item
   requires.
```

## Statement

Boundary consolidation / implementation readiness packaging only. No runtime code changed by this
document. No backend/API/database/workflow change. No new endpoint. No deployment. No merge. No
production/external action. Codex remains unauthorized. FE.1D implementation remains unauthorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
