# FE.1D Branch Disposition Matrix — Step 66M0-SOT-RECONCILE-P v2

> **Analysis and documentation only. No disposition is executed by this document. Alignment
> branches are assessed separately, below, using the advisory classification scale only — never a
> merge disposition.**

## FE.1D branch assessment

### 1. Design branch — `design/66ui4-fe1d-navigation-microcopy` @ `43269c5` (Draft PR #12)

```text
1. Still-valid formal design decisions: navigation-polish-spec.md, platform-ops-density-spec.md
   (Slice 1 content -- now historical rationale for what shipped, still accurate); microcopy-
   guide.md, field-label-cleanup-map.md, engineering-field-exposure-reduction.md (Slice 2 content
   -- still valid, still pending authorization); design-brief.md, product-owner-review-
   checklist.md, codex-implementation-notes.md (process/context docs -- still accurate).
2. Already implemented by FE.1D-S1: navigation-polish-spec.md's group subtitles/Soon-Read-only-
   Evidence badges/Platform Ops label shortening/compact density; platform-ops-density-spec.md's
   label-shortening table and marker table -- all shipped, confirmed byte-for-byte via the FE.1D-
   S1-R review (docs/frontend/.../slice1-navigation-polish-review.md, already on main).
3. Unauthorized Slice 2 (still pending, not stale): microcopy-guide.md, field-label-cleanup-
   map.md, engineering-field-exposure-reduction.md's TaskList/Overview/TaskDetail/PlaceholderPanel/
   CalmSafetyPosture recommendations.
4. Corrected by technical review: microcopy-guide.md's "missing entries to add" list for the
   shared status-label map (draft/blocked/aborted/canceled/completed/devops/requirement_analysis)
   was found inaccurate against the real TASK_STATUSES enum; the corrected 8-entry list already
   lives in the boundary branch's codex-implementation-boundary.md and does not need to be
   re-derived -- the design branch's own list should be annotated as superseded-by-correction, not
   edited (preserve historical record of what was originally proposed).
5. Inconsistent with the shipped UI (minor, non-blocking): navigation-polish-spec.md's illustrative
   Platform Ops group subtitle text ("Platform & DevOps status (read-only)") differs cosmetically
   from what actually shipped and was Product-Owner-validated ("Platform and DevOps status");
   navigation-polish-spec.md's instruction to "keep label" for the `/delivery` item conflicts with
   platform-ops-density-spec.md's own instruction to shorten it to "Work Items" -- Codex followed
   the density-spec version, which the FE.1D-S1-R review found reasonable. Neither is a blocking
   inconsistency; both are recorded, non-blocking observations already on main from the S1 review.
6. Can it be merged in full? Yes -- no conflict with main or with shipped code content.
7. Superseded annotation needed? Yes, for the Slice-1-covered sections specifically (see
   Recommended Merge Plan for exact wording), so a future reader does not mistake still-open
   Slice-2-only proposals for equally-still-open Slice-1 proposals that have, in fact, already
   shipped.
```

**Disposition: `MERGE_FULL`** (with required superseded-for-Slice-1 annotations; Slice 2 content
merges unchanged as still-valid future design input).

### 2. Technical readiness branch — `review/66ui4-fe1d-technical-readiness` @ `25309ea`

```text
1. Corrections still valid: the corrected TASK_STATUSES 8-entry list, the narrower raw-ID/hash
   page scope (TaskDetail.tsx in scope; TaskWorkroom.tsx/broad evidence-table surface deferred) --
   both remain accurate today; nothing in FE.1D-S1's shipped content or FE.1D-S2's still-pending
   scope has changed either fact.
2. Absorbed into the boundary document: yes, verbatim -- codex-implementation-boundary.md §4 item 5
   and §7.1/§7.2 of the review directly carry these corrections forward. This branch's content is
   the ORIGIN of those corrections, the boundary branch is where they became actionable.
3. Historical review evidence only: the full A-E feasibility classification table (14 review
   areas) is now historical evidence of due diligence performed before Slice 1 was authorized --
   still valuable as a record, no longer actionable since Slice 1 has already shipped exactly along
   the lines that table recommended.
4. Consistent with merged FE.1D-S1? Yes -- every Category-A item this review approved for Slice 1
   matches what actually shipped, confirmed via the FE.1D-S1-R review's independent re-verification
   (already on main).
5. Can it be merged in full? Yes -- no conflict with main; it is a point-in-time review record,
   the same kind of document this project has always merged as historical evidence (matching the
   precedent of every prior FE.1x `-R` review record already on main).
```

**Disposition: `MERGE_FULL`** (as historical review-evidence record; no annotation strictly
required beyond noting, in the merge record, that its corrections are also captured in the boundary
document being merged in the same operation).

### 3. Boundary branch — `review/66ui4-fe1d-boundary` @ `9e9a622`

```text
1. Product Owner decisions complete and still valid: "+ Create task" stays unchanged (valid,
   confirmed still true in shipped FE.1D-S1 and unchanged since); delivery_package_ready_for_
   admin_console rename deferred to 66D (valid, still deferred -- 66D has not started); both
   decisions in po-decision-record.md remain exactly as authorized.
2. Slice 1 completion should be annotated as completed: YES -- this is the single most important
   update needed. The boundary document as written describes Slice 1 as future work ("Slice 1
   scope," "Recommended Codex implementation slicing"); it must be annotated (not rewritten) to
   state Slice 1 is COMPLETE (implemented, reviewed, preview-deployed, Product-Owner-validated,
   merged, deployed -- Step 66UI.4-FE.1D-S1-MD, main commit 513f190/690b700).
3. Slice 2 boundary still applicable: YES, unchanged. Nothing about Slice 2's scope, forbidden
   items, or required tests has been invalidated by Slice 1 shipping; if anything, Slice 1's
   successful, small-PR execution is a positive precedent for Slice 2 following the same pattern
   when authorized.
4. Content belonging to future feature milestones (per cross-partner-consensus-matrix.md's M2/M4/
   M6 mappings): `TaskWorkroom.tsx` `body_hash` relabel and the broad Platform Ops/Audit/Demo-
   Evidence raw-field rename work, both explicitly deferred in the boundary document itself, align
   with Codex's alignment-branch suggestion to fold safety/evidence-wording polish into M2/M6
   functional work rather than treat it as a standalone future FE.1D slice -- worth cross-
   referencing in the merge annotation, not worth re-litigating the boundary's own scope decision.
5. Should this become the formal main contract? YES -- this matches the established precedent of
   every other FE.1x stage (`docs/contracts/<stage>/` living on main as the operative contract for
   Codex once authorized). It is the correct document to consult before any future FE.1D-S2
   authorization decision.
6. Can it be merged in full? Yes -- no conflict with main; requires the Slice-1-complete annotation
   described in item 2.
```

**Disposition: `MERGE_FULL`** (with a required "Slice 1 status: COMPLETE" annotation added; Slice 2
boundary content merges unchanged as the still-operative contract for any future authorization).

## Summary table

| Branch | Disposition | Files to include | Files to exclude | Required annotation | Conflict risk | Runtime impact | Source-of-truth impact | Required PO authorization |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `design/66ui4-fe1d-navigation-microcopy` @ `43269c5` | `MERGE_FULL` | All 11 files (8 design docs + 3 stage artifacts + its own verifier/test) | None | "Slice 1 content superseded-by-shipped-code (see FE.1D-S1-MD); Slice 2 content remains pending authorization" note at the top of each Slice-1-covered doc | Low (source/progress.md only, resolved chronologically) | None | Consolidates design rationale onto main | Merge authorization (documentation-only; no runtime/Codex authorization implied) |
| `review/66ui4-fe1d-technical-readiness` @ `25309ea` | `MERGE_FULL` | All files (review doc + record + verifier/test) | None | Cross-reference note: "corrections captured verbatim in codex-implementation-boundary.md, merged in the same operation" | Low (source/progress.md only) | None | Consolidates review evidence onto main | Merge authorization |
| `review/66ui4-fe1d-boundary` @ `9e9a622` | `MERGE_FULL` | All files (3 contracts + record + 3 stage artifacts + verifier/test) | None | "Slice 1 status: COMPLETE (Step 66UI.4-FE.1D-S1-MD, commit 513f190/690b700). Slice 2 boundary remains the operative, unchanged contract, still requiring separate Product Owner authorization before Codex may implement it." | Low (source/progress.md only) | None | Establishes the formal main contract for any future Slice 2 decision | Merge authorization |

## Statement

Analysis and documentation only. No disposition is executed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
