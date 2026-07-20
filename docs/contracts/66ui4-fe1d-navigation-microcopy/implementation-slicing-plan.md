# Implementation Slicing Plan — Step 66UI.4-FE.1D-BOUNDARY

> **Planning document only. No runtime code changed by this document. No production action. No
> Codex implementation authorized by this document.**

## 1. Recommended slicing option

**Option C (from the stage prompt's own menu), refined into exactly the two slices the stage prompt
itself specifies (§3.3).** The technical readiness review (`claude-code-technical-readiness-review.md`
§8) had recommended four narrower slices during its own analysis; this boundary consolidation
adopts the stage prompt's simpler two-slice structure instead, since (a) the Product Owner's two
decisions (§po-decision-record.md) have already removed the two items that most complicated the
original Slice 2 (the "New task" button label and the `delivery_package_ready_for_admin_console`
rename), reducing Slice 2's residual risk, and (b) two clearly-scoped, single-review-pass PRs are
easier for the Product Owner to track through the remaining gates than four. The finer-grained
internal boundaries the technical readiness review identified (Nav.tsx-only; TaskDetail.tsx as its
own concern; safety-wording isolation) are preserved as **file-level scoping within these two
slices**, not as additional top-level slices -- see §2-9 below.

## 2. Slice 1 — title and scope

```text
Title: Navigation polish
Scope: Nav.tsx group subtitles; Soon/read-only/evidence badges on placeholder and read-only nav
  items; shortened Platform Ops labels; Platform Ops compact-density treatment (already collapsed
  by default -- labels/markers/density class only). No optional visual sub-headers (deferred,
  codex-implementation-boundary.md #8). No route or route-target change of any kind.
```

## 3. Slice 1 — allowed files

```text
apps/admin-console/src/components/Nav.tsx
apps/admin-console/src/__tests__/** (new/updated test files only, for Nav.tsx behavior)
docs/frontend/66ui4-fe1d-navigation-microcopy/** (implementation report, once authorized)
docs/test/step66ui4-fe1d-*.md (implementation test report, once authorized)
source/progress.md
```

## 4. Slice 1 — forbidden files

```text
Any apps/admin-console/src/ file other than Nav.tsx and its own tests.
apps/orchestrator/**, services/**, infra/**, migrations/**, database/**, helm/**, k8s/**,
  .github/workflows/**.
Any change to App.tsx's route table.
```

## 5. Slice 1 — tests

```text
1. Vitest/RTL coverage confirming every nav item's `to` value is byte-identical before/after (no
   route drift from a label-only change).
2. Coverage confirming Soon/read-only/evidence badges render as text-plus-styling, not as an
   interactive control (no fake control -- clicking a badge does nothing beyond the existing link
   behavior of its parent nav item).
3. Coverage confirming Platform Ops group remains collapsed by default (defaultExpanded: false
   unchanged).
4. npm run build / npm run typecheck / npm test (full suite) all passing with zero regressions to
   existing Nav.tsx-dependent tests.
```

## 6. Slice 2 — title and scope

```text
Title: Microcopy and field labels
Scope: TaskList / ExecutiveOverview / TaskDetail / PlaceholderPanel microcopy and field-label
  cleanup; shared status-label map extraction and completion (using the corrected 8-entry missing
  list); empty-state consistency; relative-time display; production_effect/requires_approval
  chips-only-when-true; Overview metric relabels (excluding delivery_package_ready_for_admin_
  console); Notifications "Planned" placeholder wording; Task Detail safety-panel relabel + raw
  KeyValueTable "Technical details" disclosure wrap; CalmSafetyPosture.tsx title-string dash/case
  cosmetic consistency (no logic change). Explicitly excludes the "+ Create task" rename and the
  delivery_package_ready_for_admin_console rename (both resolved by Product Owner decision, see
  po-decision-record.md).
```

## 7. Slice 2 — allowed files

```text
apps/admin-console/src/pages/TaskList.tsx
apps/admin-console/src/pages/ExecutiveOverview.tsx
apps/admin-console/src/pages/TaskDetail.tsx
apps/admin-console/src/components/PlaceholderPanel.tsx
apps/admin-console/src/App.tsx (requiredStep prop values only -- no route table change)
apps/admin-console/src/components/CalmSafetyPosture.tsx (title-string literals only -- no change to
  getCalmSafetyPosture() logic, SAFETY_EVIDENCE_FIELDS field set, or tone thresholds)
apps/admin-console/src/tasks/ (a new shared status-label module, e.g. taskStatusLabels.ts, or
  equivalent placement consistent with existing project structure)
apps/admin-console/src/__tests__/** (new/updated test files only)
docs/frontend/66ui4-fe1d-navigation-microcopy/** (implementation report, once authorized)
docs/test/step66ui4-fe1d-*.md (implementation test report, once authorized)
source/progress.md
```

## 8. Slice 2 — forbidden files

```text
apps/admin-console/src/tasks/taskTypes.ts (the TASK_STATUSES enum itself must not change -- only a
  new/updated display-label module may reference it).
apps/admin-console/src/pages/TaskWorkroom.tsx.
apps/admin-console/src/pages/AuditEvidence.tsx, apps/admin-console/src/pages/DemoEvidence.tsx,
  apps/admin-console/src/components/EvidenceTable.tsx, and any other Platform Ops/evidence page.
apps/orchestrator/**, services/**, infra/**, migrations/**, database/**, helm/**, k8s/**,
  .github/workflows/**.
```

## 9. Slice 2 — tests

```text
1. Coverage confirming the shared status-label map has a display label for all 17 TASK_STATUSES
   values (using the corrected 8-entry missing list: draft, submitted, blocked, failed, accepted,
   rejected, archived, canceled, in addition to the 9 already mapped) and that the underlying enum
   value sent to the API/query-param is unchanged for every status.
2. Coverage confirming "+ Create task" text is UNCHANGED (a regression test, given this was an
   explicit Product Owner decision -- this test should fail loudly if a future change accidentally
   reintroduces the rename).
3. Coverage confirming delivery_package_ready_for_admin_console's Overview label is UNCHANGED (same
   regression-test rationale).
4. Coverage confirming Task Detail's Technical details disclosure is collapsed by default and
   contains the full task object; confirming the safety panel's relabeled text matches
   SAFETY_EVIDENCE_FIELDS wording exactly.
5. Coverage confirming Notifications renders the new "Planned" copy without a "Requires Step" line,
   while every other PlaceholderPanel-based route still renders "Requires Step {requiredStep}."
   unchanged.
6. Coverage confirming no regression to FE.1C/FE.1C.1 behavior (Overview attention-tile deep links,
   TaskList query-param initialization, one-way URL sync) -- existing tests for those features must
   still pass unmodified in intent.
7. npm run build / npm run typecheck / npm test (full suite) all passing with zero regressions.
```

## 10. Deferred items

```text
1. Platform Ops optional visual sub-headers -- not part of either slice; ships only on a future,
   explicit Product Owner decision.
2. TaskWorkroom.tsx body_hash relabel -- needs its own design pass with a before/after map.
3. Broad Platform Ops / Audit / Demo-Evidence raw column-header rename work (~8 pages) -- needs its
   own design pass with a before/after map.
4. SPA deep-link / hard-refresh fallback fix -- backend change, tracked separately, not part of
   FE.1D.
5. Two-way URL sync -- not part of FE.1D.
6. delivery_package_ready_for_admin_console -> "Ready to publish" rename -- explicitly deferred to
   Step 66D per Product Owner decision.
```

## 11. Rationale

Two slices (rather than the technical readiness review's originally-suggested four) is appropriate
now that the Product Owner has resolved the two decisions that made the review recommend finer
splitting: with "+ Create task" and the delivery-package rename both settled, Slice 2's remaining
scope is entirely display-string/label work across a bounded, already-enumerated set of files, with
no unresolved semantic question left inside it. Slice 1 remains intentionally single-file
(`Nav.tsx`) and lowest-risk, so it can be reviewed, and if the Product Owner wishes, deployed/
validated independently of Slice 2's larger surface. Both slices exclude every item in
`codex-implementation-boundary.md` §5 (forbidden changes) and §8 (deferred items) -- in particular,
neither slice touches `TaskWorkroom.tsx`, the broader evidence-table raw-field surface, or any
backend/API/database/workflow/route path. Splitting further (e.g. separating the safety-wording
cosmetic change from the rest of Slice 2) was considered, per the technical readiness review's own
risk note about not reopening safety logic; it is not required here because Slice 2's tests (§9
item 4 and the CalmSafetyPosture-specific coverage) already give the Product Owner and Claude Code a
trivially reviewable, logic-untouched diff for that specific file even inside the combined slice.

## Statement

Planning document only. No runtime code changed by this document. No production action. No Codex
implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
