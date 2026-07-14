# Design PR Source-of-Truth Review — DESIGN-66UI.4 Phase 1

> **Review only. No PR merged or closed by this document. Merge/close recommendations only — actual
> merge/close actions require explicit Product Owner authorization and are GitHub actions Claude Code
> did not perform in this stage.**

Owner: Claude Code (Lead Engineer / Architecture Owner). Written because prior stages
(Step 66UI.2-FE.1-R's Delivery Package placement gap, and the 66UI.3 preflight conflict Claude Design
itself flagged in `product-owner-decision-record.md`) showed that design decisions recorded only on
unmerged Draft PRs diverge from what actually ships, creating an avoidable source-of-truth risk.

## 1. Current state of each design PR/branch

| PR | Branch | Commit | State | Content |
| --- | --- | --- | --- | --- |
| #1 | `design/66ui-full-redesign-options` | `00d1191` | open, draft | DESIGN-66UI.1 — three layout options + PO Hybrid direction selection (Option 1 → IA, Option 2 → task workspace, Option 3 → deferred). Reviewed PASS by Claude Code (`docs/design/66ui-full-redesign-options/claude-code-architecture-review.md`, on `main`). |
| #2 | `design/66ui2-navigation-ia` | `edda1b0` | open, draft | DESIGN-66UI.2 detailed nav/IA brief. Reviewed PASS by Claude Code (`docs/design/66ui2-navigation-ia/claude-code-architecture-review.md`, on `main`), but its own "decision #2" (move Delivery Package to Deliveries) was **superseded** — the actual implemented-and-deployed IA (Step 66UI.2-FE.1, merged at `7ae6975`) keeps Delivery Package under Platform Ops, and the 66UI.3 Product Owner decision (below) makes that supersession explicit and binding. |
| #4 | `design/66ui3-product-ux-visual-direction` | `1f1d1d1` | open, draft | DESIGN-66UI.3 — product UX review, three visual directions, and the binding Product Owner decision record: Hybrid (A+B+C), Delivery Package confirmed under Platform Ops, **PR #2 declared superseded and to be closed**, and authorization for Claude Design to write the Phase 1 brief (PR #5). |
| #5 | `design/66ui4-phase1-product-visual-language` | `c37c88d` | open, draft | DESIGN-66UI.4 — the Phase 1 detailed brief reviewed in `claude-code-architecture-review.md` (this stage). Verdict: PASS. |

## 2. Assessment (spec §4 questions)

**1. Which open design PRs are still relevant?**
PR #4 and PR #5 are the current, relevant design record — PR #4 holds the binding Hybrid/Delivery
Package/PR #2-superseded decision; PR #5 is the Phase 1 brief that decision authorized. PR #1 is
relevant only as historical lineage (it is where the original Hybrid direction and Platform Ops
grouping idea originated), not as an active decision source — every decision it recorded has since
been re-confirmed or superseded by the more specific 66UI.2/66UI.3 decisions.

**2. Which open design PRs are superseded?**
PR #2 is explicitly superseded, per the Product Owner's own recorded decision in PR #4
(`product-owner-decision-record.md` §"PR #2 decision": "Close PR #2 ... as superseded by the merged
Navigation / IA implementation now on `main`. `main` / test-runtime state is the source of truth.").

**3. Which should be merged to main after review?**
Recommend PR #4 and PR #5, in that order (see §4 below) — both are documentation-only (no runtime
code), both passed Claude Code review (PR #4's content was reviewed as part of this stage's
preflight and §3 above; PR #5 in `claude-code-architecture-review.md`), and both currently hold
content that is not yet reflected on `main`. Merging them removes the exact "decision stranded on an
unmerged branch" risk that caused the FE.1-R Delivery Package gap.

**4. Which should be closed without merge?**
PR #2 — per the Product Owner's own recorded decision. This is a GitHub action (closing a PR) that
Claude Code did not perform in this review-only stage; it requires either explicit Product Owner
authorization for Claude Code to close it, or the Product Owner/repo admin closing it directly.

**5. Must PR #4 be merged before PR #5?**
Recommend yes, in that order. PR #5's `design-brief.md` directly cites
`docs/design/66ui3-product-ux-visual-direction/product-owner-decision-record.md` as its authorizing
source; merging PR #5 first would leave that citation pointing at a path that does not yet exist on
`main`. Merging PR #4 first keeps the dependency chain intact on `main`.

**6. Is PR #1 still useful as historical context, or should it be closed?**
Useful as historical context — it is the origin of the Hybrid direction and the Platform Ops
grouping, and its `claude-code-architecture-review.md` PASS verdict is already a permanent part of
`main`'s history regardless of the PR's own open/closed state. Recommend the Product Owner decide
between: (a) merge it as an archival record (no runtime risk, doc-only), or (b) close it without
merge now that PR #4/#5 supersede its concrete recommendations with more specific decisions. Either
is safe; this is a low-stakes housekeeping choice, not a blocking one.

**7. Can PR #5 become the primary Phase 1 design source after this review?**
Yes, functionally — this review's verdict is PASS and finds no gap requiring another round. Formally
it remains the primary source once merged to `main`; until then, the authoritative content still
lives on the unmerged branch, which is precisely the divergence risk flagged below.

## 3. `main`-as-source-of-truth risk (spec's stated reason for this task)

**Current risk: unresolved, but bounded.** Neither PR #4 nor PR #5 is merged as of this review.
`main` at commit `51ad83d` does not yet contain the Product Owner's Hybrid decision text, the
Delivery Package/PR #2-superseded ruling, or the Phase 1 brief itself — the actual specification
content still lives only on the two unmerged draft branches. This review's own new docs on `main`
(this file and the three others listed in §5) summarize and cite that content, but do not replace
it: if either branch were deleted or force-changed before merge, the summaries here would become the
only surviving record. Claude Design itself flagged this same systemic pattern in
`product-owner-decision-record.md` §"Process note," recommending PR #1, #4, and the Phase 1 PR be
merged to `main` after Claude Code review. This review concurs and extends the recommendation to
include closing PR #2 per the Product Owner's own decision.

**Recommended resolution:** Product Owner authorizes merging PR #4 then PR #5 (both documentation-
only, zero runtime risk) and decides PR #1's disposition (merge-as-archive or close) and PR #2's
closure. Until authorized, this review's four new `main` docs are the interim, review-confirmed
summary of record.

## 4. Merge order / close recommendation summary

```text
1. Merge PR #4 (design/66ui3-product-ux-visual-direction) — binding decision record.
2. Merge PR #5 (design/66ui4-phase1-product-visual-language) — Phase 1 brief, depends on #4.
3. Close PR #2 (design/66ui2-navigation-ia) without merge — superseded, per PO decision in PR #4.
4. PR #1 (design/66ui-full-redesign-options) — Product Owner's choice: merge as historical archive,
   or close without merge. Not blocking either way.
```

No PR is merged or closed by this document. All four actions above require explicit Product Owner
authorization and are GitHub state changes outside this review-only stage's scope.

## Statement

Review only. No PR merged. No PR closed. No runtime code changed. No backend changed. No frontend
implementation changed. Merge/close recommendations only.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
