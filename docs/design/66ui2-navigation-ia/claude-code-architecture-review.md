# Claude Code Architecture Review — DESIGN-66UI.2 Navigation / IA Detailed Design

> **Review only. No runtime code changed. No backend changed. No frontend implementation changed.
> No design PR merged. No Codex implementation authorized by this document.**

Reviewer: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`). Reviews branch `design/66ui2-navigation-ia`
(commit `edda1b0`) and its associated Draft PR (`github.com/coolerh250/AI-Agents-SWD` PR #2, state
`open`, `draft: true`, 1 commit, 8 files changed, +898/-0, no non-doc files touched).

## 1. Scope of this review

This is an architecture/design review of the implementation-stage Navigation/IA brief that
`docs/frontend/66ui-full-redesign-options/codex-readiness-boundary.md` §4 named as the required
next step after the 66UI.1 review (PASS, commit `3105372`). The question this review answers: *does
this brief's proposed nav restructure preserve every existing route/behavior, correctly defer every
not-yet-built area, and avoid authorizing or misrepresenting any capability?* It does not evaluate
visual/IA design quality, which is Claude Design's and the Product Owner's domain.

## 2. Files confirmed present

All 8 expected files exist in `docs/design/66ui2-navigation-ia/`: `design-brief.md`,
`navigation-map.md`, `page-grouping.md`, `role-based-entry-points.md`, `placeholder-rules.md`,
`migration-from-current-nav.md`, `codex-implementation-notes.md`,
`product-owner-review-checklist.md`.

## 3. Product Owner decision, as recorded

- **Result: `READY_FOR_CODE_REVIEW`.**
- **Dashboard / Operational Metrics do not merge this round.** `Dashboard` (Overview) stays the
  landing page; `Operational Metrics` stays separate under Platform Ops / Metrics. Recorded
  consistently in `design-brief.md` §"Decisions folded in" and `page-grouping.md` (Overview table),
  and left as an explicit open question in `product-owner-review-checklist.md` for a later round —
  it does not block this nav shell.
- **DeliveryPackage stays under Platform Ops**, unchanged, as the existing delivery evidence/package
  record; it is not merged with the Deliveries group. Deliveries/Delivery Inbox remain deferred until
  the Step 66D API/data contract exists — `page-grouping.md` states this explicitly ("DeliveryPackage
  is intentionally NOT in this group").
- **Deliveries group is visible in the first nav shell but placeholder-only.** Delivery Inbox and
  Delivery Detail render as compliant placeholders ("Not yet available. Requires Step 66D." + "No
  workflow action available.") per `placeholder-rules.md`.
- **Security/Compliance cross-group access is acceptable where server-side RBAC allows.**
  `role-based-entry-points.md` documents the Security/Compliance Reviewer's material spanning
  Governance and Platform Ops, and is explicit that "nav visibility is a convenience layer only —
  server-side RBAC remains the authority."
- **Notifications are in-app only in the first version.** `page-grouping.md` and
  `placeholder-rules.md` both state external channels (Slack/Discord/Telegram) are "Coming later"
  and that no external send is implied or active.

## 4. Architecture-safety findings

| Check | Finding |
| --- | --- |
| Does any doc assert workflow dispatch as an active/enabled capability? | Not found. The only "dispatch" mentions restate the persistent safety posture `dispatch=OFF` or explicitly prohibit dispatch from a placeholder. |
| Does any doc assert workflow resume as an active/enabled capability? | Not found. Same pattern — `resume=OFF` restated; never asserted as active. |
| Does any doc assert that a production-affecting action occurs? | Not found. `prod_exec=0` is restated as always-visible; `codex-implementation-notes.md` §5 states `production_executed_true_count` "stays server-computed and displayed as 0." |
| Does any doc assert that an external integration is turned on? | Not found. `placeholder-rules.md` requires every connector be shown "not connected / disabled," with no "Connect" control implying live authentication. |
| Does any doc assert that dragging a card / lifecycle-stage change currently works? | Not found. `placeholder-rules.md` §7 and `codex-implementation-notes.md` §5 both state the deferred pipeline, if ever built, is read-only with "no drag handles"; the round-1 nav shell excludes it entirely. |
| Does any sentence read as an un-negated claim that a forbidden capability is currently switched on? | Not found. `design-brief.md`'s constraints section states "No nav item, badge, or placeholder may imply that workflow dispatch, workflow resume, or any external/production action is enabled" — the governing word is the leading "No," making this a prohibition, not a claim; confirmed by manual reading of the full sentence. |
| Runtime code changed | **No.** `git diff origin/main...origin/design/66ui2-navigation-ia --stat` shows only the 8 new files under `docs/design/66ui2-navigation-ia/`; zero files under `apps/`, `shared/`, `migrations/`, or any other runtime path. |
| Backend code changed | **No.** Same diff-stat confirms zero backend files touched. |
| Frontend implementation changed | **No.** Same diff-stat confirms zero `apps/admin-console/src/**` files touched — `codex-implementation-notes.md` describes a plan referencing real component names (`Nav.tsx`, `SafetyBadge`, etc.), not an edit to them. |
| API contract change requested | **No.** `design-brief.md` §"Constraints" lists the existing endpoint set as sufficient; `product-owner-review-checklist.md` "Contract reference: None." confirms no new/changed endpoint or data shape is requested. |
| Codex implementation authorized | **No.** Every one of the 8 files' footer/statement states no Codex implementation is authorized by that document; `product-owner-review-checklist.md` restates "not authorization to implement." |
| Internal IP / SSH alias / hostname / token / secret present | **No.** `grep -rniE` for the project's known infra-identifier patterns and common secret shapes across all 8 files returned zero matches. |

## 5. Route and content preservation

- `migration-from-current-nav.md` accounts for all 28 current flat nav items; every one keeps its
  existing route target, confirmed against `navigation-map.md`'s proposed structure and
  `page-grouping.md`'s per-page table (routes column marked "existing, unchanged" throughout).
- `page-grouping.md`'s rollup independently totals 31 active existing route targets (Dashboard + 5
  Team Work + 3 Operator Center + 2 Governance + 20 Platform Ops) — consistent with the migration
  table, no route omitted or altered.
- The one item removed from first-level nav, `Diagnostics (Demo Evidence)`, is documented as
  direct-route-only, consistent with its pre-existing "NOT a staging acceptance path" annotation in
  the current `Nav.tsx` — this is a nav-visibility change, not a route removal (`/demo-evidence`
  stays reachable).
- Platform Ops's 20 pages are explicitly "grouping only — no page redesign this round"
  (`page-grouping.md` section header), consistent with the 66UI.1 decision this brief builds on.

## 6. Non-blocking architecture concerns and recommendations

1. **Dashboard/Operational Metrics merge question** remains open for the Product Owner
   (`product-owner-review-checklist.md` Q1) — correctly deferred, does not block the round-1 nav
   shell, consistent with Claude Code's 66UI.1 review §6.1 which first raised it.
2. **DeliveryPackage placement question** (stay under Platform Ops vs. move inside Deliveries as a
   distinct item) is correctly left open (`product-owner-review-checklist.md` Q2) rather than
   silently decided by the design brief.
3. **Security/Compliance cross-group span** (Governance + Platform Ops) is flagged by
   `role-based-entry-points.md` itself as "an accepted consequence... to revisit if it proves
   awkward" — agreed this is a reasonable round-1 tradeoff, not an architecture defect.
4. **`OperatorConsole` vs. Approvals/DLQ resolution** (separate pages under Operator Center, not
   same-page tabs) matches the intended backend/page structure — this correctly closes the open item
   Claude Code's 66UI.1 review §6.2 asked to be settled in this brief, and settling it here (rather
   than deferring again) was the correct call.
5. **No contract change is currently required.** Confirmed independently — the existing endpoint set
   listed in `design-brief.md` §"Constraints" is sufficient for every round-1 nav-shell item; the one
   piece that will eventually need a contract (a read-only Lifecycle Pipeline view) is correctly kept
   out of round 1 and flagged as blocked on a future `frontend-contract.md`
   (`frontend-implementation-boundary.md` §3 in this stage's contract, mirroring the 66UI.1 pattern).

## 7. Verdict

**Technical review result: PASS.** The brief preserves every existing route and page behavior,
resolves the two open items Claude Code's 66UI.1 review asked to be settled, defers every
not-yet-built area behind a compliant placeholder, requests no backend/API/contract change, and
contains no sensitive identifiers or forbidden capability claims. It is safe to proceed to the
Codex-readiness boundary (see `docs/contracts/66ui2-navigation-ia/frontend-implementation-boundary.md`
and `docs/frontend/66ui2-navigation-ia/codex-implementation-plan-boundary.md`), which still requires
explicit Product Owner authorization before Codex begins any implementation — this review does not
grant that authorization; it only confirms the design is safe to authorize.

## Statement

Review only. No runtime code changed. No backend changed. No frontend implementation changed. No
design PR merged. No workflow dispatch. No workflow resume. No external action. No production
action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
