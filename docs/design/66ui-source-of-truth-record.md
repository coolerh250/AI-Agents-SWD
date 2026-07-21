# UI/UX Design Source-of-Truth Record

> **Merge/disposition record only. No runtime code changed. No backend changed. No frontend
> implementation changed. No API/database/workflow change. No production/external action. No Codex
> implementation authorized by this document.**

Owner: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`), executed per explicit Product Owner authorization:

```text
授權 Claude Code 依序 merge PR #4、PR #5 到 main；關閉 PR #2 不 merge；PR #1 暫時保留；不授權 Codex 實作。
```

This record is the outcome of Step 66UI.4-SOT-M and supersedes the "unresolved" status recorded in
`docs/design/66ui4-phase1-product-visual-language/design-pr-source-of-truth-review.md` (Step
66UI.4-R) — that review recommended exactly the disposition executed here.

## Merge order executed

```text
1. PR #4 -- design/66ui3-product-ux-visual-direction -> main (merge commit a47f205)
2. PR #5 -- design/66ui4-phase1-product-visual-language -> main (merge commit cf6c086)
```

Both merges were fast, clean `git merge --no-ff` with **zero conflicts** (confirmed via
`git status` immediately after each merge showing no `UU` entries). Both merges are documentation-
only: `git diff 62c5852..cf6c086 --name-only` shows every changed path under
`docs/design/66ui3-product-ux-visual-direction/` or `docs/design/66ui4-phase1-product-visual-language/`
— no `apps/`, `shared/`, or `infra/` path touched.

## PR disposition

| PR | Branch | Disposition | Status |
| --- | --- | --- | --- |
| #1 | `design/66ui-full-redesign-options` | **Retained as historical reference.** Not merged, not closed. Its concrete recommendations (Option 1 → IA, Option 2 → task workspace, Option 3 → deferred) have been superseded in specificity by the merged 66UI.2/66UI.3/66UI.4 decisions now on `main`, but the PR itself stays open per explicit Product Owner instruction. | Open, historical reference only — **not** current implementation source. |
| #2 | `design/66ui2-navigation-ia` | **Superseded — closed without merge.** Not merged. | **Closed** (confirmed by Product Owner, see "PR #2 close status" below). |
| #4 | `design/66ui3-product-ux-visual-direction` | **Merged to main** at commit `a47f205`. | Merged — now source of truth. |
| #5 | `design/66ui4-phase1-product-visual-language` | **Merged to main** at commit `cf6c086`. | Merged — now source of truth. |

### PR #2 close status

PR #2 could not be closed via GitHub tooling in this stage: no `gh` CLI is available in this
environment and no GitHub token is present (checked `GITHUB_TOKEN` / `GH_TOKEN` — both unset; no
credential extraction attempted, per the explicit "do not extract credentials, do not use unsafe
token methods" instruction). Manual close was recommended, with the following comment text:

```text
Superseded by:
- the merged Navigation / IA implementation on main (Step 66UI.2-FE.1-M, merge commit 7ae6975)
- the test-runtime deployment record (Step 66UI.2-FE.1-D)
- the PR #4 / PR #5 source-of-truth merge (Step 66UI.4-SOT-M, this record)
Not merged. Branch not deleted pending separate Product Owner authorization.
```

**Update — PR #2 confirmed closed.** The Product Owner manually closed PR #2 via the GitHub UI and
confirmed via screenshot (`design: define navigation / information architecture detailed brief #2`,
red "Closed" badge, closed by `coolerh250`). PR #2 is now closed, not merged, per the original
authorization. The `design/66ui2-navigation-ia` branch was not deleted (no separate authorization
given for branch cleanup).

PR URL: `https://github.com/coolerh250/AI-Agents-SWD/pull/2`

**Important finding from this stage's Shared Context Preflight:** PR #2's branch received a new
commit (`7c95483`, 2026-07-14 09:16, "record PO decisions and sync DeliveryPackage placement")
*before* the 66UI.3 Hybrid decision was recorded (`1f1d1d1`, 15:00 the same day). That PR #2 commit
records an *earlier* Product Owner decision (`product-owner-decision-record.md` on the PR #2
branch) that placed Delivery Package under **Deliveries**, not Platform Ops. This is precisely the
decision the 66UI.3 decision record (merged in this stage) explicitly names and supersedes:

> "The earlier 66UI.2 'decision #2' (move Delivery Package to Deliveries), which lived only on the
> unmerged PR #2, is superseded by this decision." — `docs/design/66ui3-product-ux-visual-direction/product-owner-decision-record.md`

This confirms — it does not contradict — the instruction to close PR #2 without merge: merging PR #2
would reintroduce a decision the Product Owner has already explicitly overridden, and would conflict
with the actual deployed/merged `main` state (Delivery Package under Platform Ops, confirmed in
`apps/admin-console/src/components/Nav.tsx` and the Step 66UI.2-FE.1-M/D records).

## Binding decisions now on `main`

- **Hybrid direction** (`docs/design/66ui3-product-ux-visual-direction/product-owner-decision-record.md`):
  Direction A for Dashboard/Overview/cross-task; Direction B for Task Detail/Workroom/Clarification/
  future Delivery Review; Direction C as language/style principles throughout.
- **Delivery Package placement**: stays under Platform Ops; Delivery Inbox/Detail stay under
  Deliveries; not merged until the Step 66D contract exists. Matches the actual deployed `Nav.tsx`.
- **PR #2 superseded** by the merged Navigation/IA implementation and this source-of-truth merge.
- **Phase 1 Product Visual Language brief** (`docs/design/66ui4-phase1-product-visual-language/`):
  global visual language, calm safety posture, Overview cleanup, navigation visual polish,
  engineering-field reduction, product microcopy — reviewed PASS in
  `docs/design/66ui4-phase1-product-visual-language/claude-code-architecture-review.md` (Step
  66UI.4-R, unchanged by this merge).
- **Codex remains unauthorized** to implement from either PR's content. Nothing in this merge
  changes that — merging design documentation to `main` makes it the source of truth for *reading*,
  not an implementation authorization.

## `main` as source of truth

As of this record, `main` contains the full text of both the DESIGN-66UI.3 decision record and the
DESIGN-66UI.4 Phase 1 brief. The divergence risk flagged in
`docs/design/66ui4-phase1-product-visual-language/design-pr-source-of-truth-review.md` §3 ("neither
PR #4 nor PR #5 is merged...") is now resolved for those two PRs, and PR #2's disposition is now
fully closed out (confirmed closed by the Product Owner). The only remaining open item is PR #1's
continued-open status, which is explicitly authorized and not a gap.

## FE.1D source-of-truth gap — closed (Step 66M0-SOT-RECONCILE-M)

The FE.1D design, technical readiness review, and Codex implementation boundary branches, which
had remained unmerged advisory/contract input while FE.1D-S1 shipped independently, were merged to
`main` per explicit Product Owner authorization in Step 66M0-SOT-RECONCILE-M:

```text
1. design/66ui4-fe1d-navigation-microcopy @ 43269c5 (Draft PR #12) -> main, merge commit 45da561
2. review/66ui4-fe1d-technical-readiness @ 25309ea               -> main, merge commit 03318b7
3. review/66ui4-fe1d-boundary @ 9e9a622                            -> main, merge commit 0414343
```

- **FE.1D design** — merged. Historical design brief for FE.1D Slice 1 (shipped) and Slice 2
  (unauthorized candidate). Its "New task" vs. "Create task" and delivery-package-rename open
  questions are resolved by the Product Owner decisions below.
- **FE.1D technical readiness** — merged. Historical review evidence documenting the corrections
  found in the design (corrected `TASK_STATUSES` list; narrowed raw-ID/hash page scope) and the
  PASS_WITH_GAPS verdict that led to the Product Owner's decisions.
- **FE.1D boundary** — merged. Now the formal, binding `docs/contracts/66ui4-fe1d-navigation-
  microcopy/codex-implementation-boundary.md` contract on `main` for any future FE.1D Slice 2
  authorization decision.
- **FE.1D-S1** — shipped. Already merged and deployed (Step 66UI.4-FE.1D-S1-MD, merge commit
  `513f190`); unaffected by this merge (zero `apps/**` diff introduced by the three branches above).
- **FE.1D-S2** — unauthorized / non-critical. Design and boundary content for Slice 2 is now
  readable on `main`, but remains an unauthorized candidate specification, not an implementation
  authorization. Explicitly not on the M0-M7 critical path (Step 66ALIGN.1-CC).
- **Product Owner decisions preserved.** `"+ Create task"` remains unchanged.
  `delivery_package_ready_for_admin_console` is not renamed to "Ready to publish" in FE.1D; the
  rename remains deferred to Step 66D. Workflow dispatch keeps the shipped FE.1B.1 wording
  ("Workflow dispatch", not "Automation dispatch"). Delivery Package remains under Platform Ops.
  `TaskWorkroom.tsx` `body_hash` and the broader evidence/raw-field relabel remain deferred. SPA
  deep-link fallback and two-way URL sync remain excluded, tracked as separate platform gaps.
- **Team RBAC milestone ownership** resolved separately in
  `docs/decisions/66-team-rbac-milestone-ownership.md` (M3 owns product-level team/role control;
  M6/M7 own production identity/authentication/session security).
- **Alignment branches** (`alignment/66-project-completion-claude-code`,
  `design/66-project-completion-experience-alignment`, `alignment/66-project-completion-codex`)
  remain unmerged — not part of this closure, reserved for a future Step 66ALIGN.2 stage.

See `docs/reconciliation/66m0-fe1d-sot/source-of-truth-closure-record.md` and
`docs/reconciliation/66m0-fe1d-sot/merge-execution-record.md` for the full closure detail.

## Statement

Merge/disposition record only. No runtime code changed. No backend changed. No frontend
implementation changed. No API/database/workflow change. No production/external action. No
deployment performed. No Codex implementation authorized by this document. No FE.1D Slice 2
authorized or implemented by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=true image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
