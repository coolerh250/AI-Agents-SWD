# Recommended Merge Plan (M0 Reconciliation Plan) — Step 66M0-SOT-RECONCILE-P v2

> **Planning document only. No merge, cherry-pick, deployment, or runtime modification is performed
> by this document or authorized by it. Execution requires a separate, future, explicit Product
> Owner authorization naming this plan.**

## 1. Recommended FE.1D merge/disposition order

```text
1. design/66ui4-fe1d-navigation-microcopy @ 43269c5   (merge first -- foundational design record)
2. review/66ui4-fe1d-technical-readiness @ 25309ea    (merge second -- reviews the design)
3. review/66ui4-fe1d-boundary @ 9e9a622                (merge third -- consolidates 1+2 into the
                                                         operative contract, needs the Slice-1-
                                                         complete annotation)
```

This preserves the same chronological-order merge pattern this project has used for every prior
multi-branch consolidation (FE.1C-MD, FE.1C.1-MD, FE.1D-S1-MD): each branch's own historical
sequence (design -> review -> consolidation) is reproduced in the merge order, not collapsed or
reordered.

## 2. Exact branches / commits

```text
design/66ui4-fe1d-navigation-microcopy @ 43269c5
review/66ui4-fe1d-technical-readiness @ 25309ea
review/66ui4-fe1d-boundary @ 9e9a622
```

All three confirmed based on `main` @ `707cb8c` (pre-FE.1D-S1). A future execution stage must
re-verify these commits have not drifted before merging (the same Shared Context Preflight
discipline used in every prior merge stage).

## 3. Exact files (per branch — see fe1d-branch-disposition-matrix.md for full detail)

```text
Branch 1 (design): 8 docs under docs/design/66ui4-fe1d-navigation-microcopy/**, 3 files under
  docs/stages/66ui4-fe1d-navigation-microcopy-design/**, scripts/verify_design66ui4_fe1d_
  navigation_microcopy.py, tests/test_design66ui4_fe1d_navigation_microcopy.py,
  source/progress.md.
Branch 2 (technical readiness): docs/design/66ui4-fe1d-navigation-microcopy/claude-code-technical-
  readiness-review.md, docs/test/step66ui4-fe1d-technical-readiness-review-record.md,
  scripts/verify_step66ui4_fe1d_technical_readiness.py, tests/test_step66ui4_fe1d_technical_
  readiness.py, source/progress.md.
Branch 3 (boundary): 3 docs under docs/contracts/66ui4-fe1d-navigation-microcopy/**,
  docs/test/step66ui4-fe1d-boundary-consolidation-record.md, 3 files under
  docs/stages/66ui4-fe1d-boundary/**, scripts/verify_step66ui4_fe1d_boundary.py,
  tests/test_step66ui4_fe1d_boundary.py, source/progress.md.

No file is recommended for exclusion from any of the three branches -- see disposition matrix,
all MERGE_FULL.
```

## 4. Conflict-resolution rules

```text
All three merges are expected to conflict ONLY in source/progress.md (the established pattern).
Resolve by: preserve all existing content on main, insert the incoming branch's own stage section
at the correct chronological position. Verify after each resolution via
`grep -n "^## Stage 66UI.4-FE.1D"` (and `"^## Stage 66UI.4-FE.1D-DESIGN"`,
`"^## Stage 66UI.4-FE.1D-TECH-REVIEW"`, `"^## Stage 66UI.4-FE.1D-BOUNDARY"` as applicable) showing
each section exactly once, in the correct order relative to the already-merged FE.1D-S1 sections
(design/tech-review/boundary chronologically PRECEDE FE.1D-S1's own implementation/review/preview/
validation/merge sections, since Slice 1 authorization and implementation came after the boundary
was consolidated).
```

## 5. Required annotations (exact wording recommended)

```text
In design branch's navigation-polish-spec.md and platform-ops-density-spec.md (top of file, added
  as a new callout, not a rewrite of existing content):
  "Slice 1 status: IMPLEMENTED AND SHIPPED (Step 66UI.4-FE.1D-S1-MD, main commit 513f190/690b700).
  The recommendations in this document describing Slice 1 scope are historical design rationale for
  what shipped, not an open proposal."

In boundary branch's codex-implementation-boundary.md (top of file, added as a new callout):
  "Slice 1 status: COMPLETE (Step 66UI.4-FE.1D-S1-MD, main commit 513f190/690b700) -- implemented,
  reviewed, preview-deployed, Product-Owner-validated, merged, and deployed. Slice 2 boundary below
  remains the operative, unchanged contract and still requires a separate, explicit Product Owner
  authorization before Codex may implement it."

In technical-readiness branch's claude-code-technical-readiness-review.md (top of file, added as a
  new callout):
  "Corrections in this review (corrected TASK_STATUSES list, narrowed raw-ID/hash scope) are also
  captured in docs/contracts/66ui4-fe1d-navigation-microcopy/codex-implementation-boundary.md,
  merged in the same reconciliation operation. Slice 1 has since shipped consistent with this
  review's Category-A/B classifications (Step 66UI.4-FE.1D-S1-MD)."
```

## 6. PR #12 disposition

```text
PR #12 (Draft, design: fe1d navigation polish + microcopy) corresponds to the design branch.
Recommended: once design/66ui4-fe1d-navigation-microcopy is merged per this plan, PR #12 should be
CLOSED (not left open indefinitely) with a comment noting it was consolidated via this
reconciliation plan's merge commit(s), following the same precedent as every prior FE.1x design
PR in this project. This action itself requires the same merge authorization as the merge, since
closing a PR after merge is a routine consequence of merging, not a separate risk.
```

## 7. Superseded-document handling

```text
No document is recommended for deletion or full supersession -- all three branches are MERGE_FULL.
"Superseded" here means annotated-as-historical-for-Slice-1-content only (see §5), never removed.
This matches this project's own established preference (Feedback memory: "surgical changes,"
"don't remove pre-existing dead code unless asked") -- historical design/review records remain
readable, just clearly marked as to what has since shipped vs. what remains pending.
```

## 8. source/progress.md update plan

```text
After merging all three branches (in the order in §1), append a single consolidated summary
section to source/progress.md, e.g. "## Stage 66UI.4-FE.1D-DESIGN-TECH-BOUNDARY-CONSOLIDATION"
(exact stage name to be finalized by the executing stage), stating: the three branches merged,
their commits, the annotation additions, and the fact that this consolidation does not itself
authorize FE.1D Slice 2 or change any Slice 1 shipped behavior. This mirrors the existing pattern
where each merge stage's OWN new content (not just the conflict-resolved carried-forward content)
gets its own dedicated summary section.
```

## 9. Source-of-truth record update plan

```text
docs/design/66ui-source-of-truth-record.md should be updated (by the executing stage, not this
one) to note that the FE.1D design/technical-readiness/boundary chain is now fully consolidated on
main, alongside the already-consolidated FE.1D-S1 implementation chain -- closing the "advisory-
only, unmerged" status these three branches have carried throughout this reconciliation stage.
```

## 10. Post-merge verification plan

See `post-merge-verification-plan.md` (separate required deliverable) for the full checklist.

## 11. Test runtime impact

```text
NONE. All three branches are documentation/contract-only (confirmed zero apps/**, services/**,
infra/**, migrations/**, database/** files in any of the three branches' diffs against main). No
redeployment, no rebuild, no test-runtime change is required or recommended as a consequence of
executing this merge plan.
```

## 12. Rollback plan

```text
Standard git revert of the merge commits, in reverse order, if a defect is found post-merge. Since
no runtime file changes, rollback carries zero test-runtime risk -- it is purely a documentation-
state rollback. No rollback backup beyond git history itself is required (contrast with FE.1D-S1-MD,
which required an in-container bundle backup because it touched deployed runtime files; this plan
touches none).
```

## 13. Alignment advisory handoff to Step 66ALIGN.2

See `align2-advisory-handoff.md` (separate required deliverable).

## Explicit non-execution statement

This plan is a recommendation only. **No branch is merged, no PR is closed, and no annotation is
added to any branch by this document or by this stage.** Execution requires a future, separate,
explicit Product Owner authorization naming this plan (or a successor stage prompt) and the exact
branches/commits to merge.

## Statement

Planning document only. No merge, cherry-pick, deployment, or runtime modification performed or
authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
