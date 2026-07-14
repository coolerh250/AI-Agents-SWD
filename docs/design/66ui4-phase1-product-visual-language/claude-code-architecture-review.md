# Claude Code Architecture Review — DESIGN-66UI.4 Phase 1 Product Visual Language

> **Review only. No runtime code changed. No backend changed. No frontend implementation changed.
> No design PR merged. No Codex implementation authorized by this document.**

Reviewer: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`). Reviews branch
`design/66ui4-phase1-product-visual-language` (commit `c37c88d`) and its associated Draft PR
(`github.com/coolerh250/AI-Agents-SWD` PR #5 — "design: phase 1 product visual language"), plus
`design/66ui3-product-ux-visual-direction` (commit `1f1d1d1`, Draft PR #4) for the Product Owner
Hybrid decision that authorizes this brief.

## 1. Scope of this review

This is a design/architecture/source-of-truth review, not an implementation review — there is no
runtime code to test, and none was changed. The question this review answers: *does this Phase 1
brief contradict the platform's actual runtime capabilities, misrepresent what is currently
implemented, imply implementation before contract/authorization, or authorize work it shouldn't?*
It does not evaluate visual design quality, which is Claude Design's and the Product Owner's domain.

## 2. Files confirmed present

All 9 expected files exist in `docs/design/66ui4-phase1-product-visual-language/` on
`origin/design/66ui4-phase1-product-visual-language` at commit `c37c88d`: `design-brief.md`,
`visual-language-spec.md`, `calm-safety-posture-spec.md`, `overview-dashboard-spec.md`,
`navigation-visual-polish-spec.md`, `engineering-field-reduction-map.md`,
`product-microcopy-guide.md`, `codex-implementation-notes.md`, `product-owner-review-checklist.md`.

## 3. Product Owner decision, as recorded

Read from `docs/design/66ui3-product-ux-visual-direction/product-owner-decision-record.md` on the
same PR #4 branch (binding reference this brief is built from):

- **Verdict: Hybrid (A + B + C).** Direction A (AI Team Command Center) for Dashboard / Overview /
  cross-task; Direction B (Agent Workspace) for Task Detail / Workroom / Clarification / future
  Delivery Review; Direction C applied as language/style principles only (no separate structural
  layout).
- **Delivery Package stays under Platform Ops**; Delivery Inbox / Delivery Detail stay under
  Deliveries (placeholders); the two are **not merged** until the Step 66D contract exists. This
  matches the deployed, PO-validated `main` state from Step 66UI.2-FE.1-M/D.
- **PR #2 is closed as superseded** by the merged Navigation/IA implementation now on `main`.
- This decision record **explicitly authorizes** Claude Design to produce the Phase 1 brief under
  review here, and states Codex is **not yet authorized** to implement it.

`design-brief.md` correctly cites this decision record as its authorizing source and restates the
Hybrid baseline, the Delivery Package placement, and the six Phase 1 scope items the Product Owner
named (visual language, calm safety posture, Overview cleanup, navigation visual polish,
engineering-field reduction, product microcopy).

## 4. Required review areas (spec §3)

| # | Check | Result |
| --- | --- | --- |
| 1 | No runtime implementation requested | **Pass** — every file's closing Statement reads "Design specification only. No runtime code."; `codex-implementation-notes.md` opens with "Codex is NOT authorized to implement until Claude Code reviews this brief AND the Product Owner explicitly authorizes Phase 1." |
| 2 | No backend/API/database change required | **Pass** — `design-brief.md` "Constraints": existing endpoints only, no new endpoint requested; verified against the actual orchestrator source (`apps/orchestrator/src/operations.py` defines both `/operations/admin-console/overview` and `/operations/safety`) — the brief's endpoint claims are accurate, not aspirational. |
| 3 | No workflow dispatch/resume implied | **Pass** — `codex-implementation-notes.md` §4 hard prohibitions list "No workflow dispatch / resume / state mutation" explicitly. |
| 4 | No production/external action implied | **Pass** — restated in every file's Statement and in §4's prohibitions; `calm-safety-posture-spec.md` requires the posture indicator to be presentation-only over the same server fields, never a control. |
| 5 | No Delivery real UI implied before 66D contract | **Pass** — `overview-dashboard-spec.md` "Data dependency honesty" requires "Deliveries to review" and "Approvals" tiles to show "—" + "Requires Step 66D" caption, never a fabricated number; `codex-implementation-notes.md` §2 lists "Delivery Review UI — placeholder-only until Step 66D contract" under scope explicitly NOT in Phase 1. |
| 6 | No Reminder/Expiry real UI implied before 66C.4 contract | **Pass** — `codex-implementation-notes.md` §2 lists "Reminder/Expiry real UI — placeholder-only until Step 66C.4 contract" under out-of-scope. |
| 7 | No Pipeline board / drag-and-drop implied | **Pass** — not present anywhere in the Phase 1 scope (6 named items) or in `codex-implementation-notes.md` §1's allowed-scope list; absence confirmed by full-text read of all 9 files. |
| 8 | No client-side-only RBAC implied | **Pass** — `design-brief.md` "Constraints": "Server-side RBAC remains the access-control authority; visual changes never gate access." Repeated in `codex-implementation-notes.md` §4. |
| 9 | Safety posture remains server-data-based | **Pass** — `calm-safety-posture-spec.md`: "Same server values, product presentation... Values stay server-computed and displayed-as-returned — never hardcoded or inferred client-side," with an explicit "not reported" fallback for missing values (never a guessed default). Verified the brief's field list (`production_executed_true_count`, `dispatch_enabled`, `resume_dispatch_enabled`, `task_api_workflow_dispatch_enabled`, `task_workroom_resume_dispatch_enabled`, `github_external_write_enabled`, `discord_external_send_enabled`, `llm_external_call_enabled`, `approval_required`, `requires_approval`, `workflow_production_executed_true_count`) against the actual deployed `SafetyStatusBar.tsx` — every field name matches exactly. |
| 10 | Engineering field reduction does not hide required audit/safety evidence entirely | **Pass** — `engineering-field-reduction-map.md` states the rule directly: "Never hide a safety-relevant signal; only relocate its technical representation while keeping the plain-language statement visible." Every safety-relevant field's disposition is **relabel** or **demote** (moved to expand/hover), never **hide**; the one **hide** disposition in the whole map (`sender_type` in Workroom, "implied by treatment") is a non-safety presentation field, not an audit/safety value. |
| 11 | Microcopy does not overclaim automation or agent capability | **Pass** — `product-microcopy-guide.md` tone rule 3 ("Reassurance-first for safety") and its own examples are consistently under-claiming, not over-claiming: "Nothing runs automatically — you stay in control," "Answering won't automatically restart the AI team. A person still decides the next step." No string implies autonomous action beyond what the platform actually does. |
| 12 | Overview cleanup does not require new backend metrics unless marked placeholder/future | **Pass** — `overview-dashboard-spec.md` "What stays the same": "The `/operations/admin-console/overview` endpoint and its data — no new endpoint;" gated counts (Deliveries to review, Approvals) are explicitly the only ones marked as honest placeholders pending 66D. |
| 13 | Visual language changes are feasible as frontend-only work | **Pass** — every referenced component/token (`styles.css` `--bg`/`--card`/`--fg`/`--muted`/`--line`, `.b-ok`/`.b-warn`/`.b-bad`/`.b-neutral`, `SafetyStatusBar.tsx`, `ExecutiveOverview.tsx`, `Nav.tsx`, `NavGroup.tsx`, `TaskDetail.tsx`, `TaskList.tsx`, `TaskWorkroom.tsx`) was confirmed to exist in `apps/admin-console/src/` with the exact field/token names the brief cites — the brief is grounded in the real codebase, not speculative. |
| 14 | Codex implementation notes narrow enough for staged implementation | **Pass** — `codex-implementation-notes.md` §1 scopes exactly four buildable items (tokens, calm safety posture component, Overview restructure, nav visual polish) plus field-reduction/microcopy applied only to the surfaces those four touch; §2 explicitly defers everything else (full Workroom/Task Detail/List/Audit redesigns, Task Workspace tab convergence, Delivery/Reminder real UI) to later phases with their own review gates; §5 proposes either one cohesive PR or a 4-step sequence, both revertible and frontend-only. |

No gaps found across all 14 required areas — this brief is materially cleaner than the FE.1 design
brief reviewed in Step 66UI.2-FE.1-R (which had one placement gap); no equivalent gap exists here.

## 5. Architecture / safety assessment

- **Runtime code changed:** No. Zero files under `apps/` touched by this review; `git status` /
  `git diff --stat` on this checkout confirm no working-tree changes prior to this stage's own new
  docs.
- **Backend/API/database impact:** None. Existing endpoints only; no new endpoint, field, or shape
  requested.
- **Workflow dispatch/resume:** None implied or performed.
- **Production/external action:** None implied or performed.
- **Safety evidence visibility:** Preserved — the field-reduction map relocates technical detail
  behind expand/hover, it does not remove any safety-relevant field from the UI's reachable surface.
- **Backend data dependency:** Every Phase 1 surface (calm safety posture, Overview, nav) reads data
  the deployed app already fetches; Overview's two 66D-gated tiles use an honest placeholder, not a
  new metric.

## 6. Minor observations (non-blocking)

1. The brief itself already surfaces three open questions for the Product Owner
   (`product-owner-review-checklist.md`): muted-text contrast nudge, whether the Overview
   team-activity strip ships in Phase 1 or defers to Phase 2, and PR shape (one PR vs. a 4-step
   sequence). These are legitimate Product Owner decisions, not review defects — carried forward to
   §9 of this review's completion report.
2. `codex-implementation-notes.md` and `product-owner-review-checklist.md` both correctly restate
   that acceptance of this brief is not implementation authorization, and that the eventual
   *implemented* Phase 1 needs its own separate operator UI-validation verdict after Codex builds and
   Claude Code deploys — consistent with the pattern already used for Step 66UI.2-FE.1-V/D.
3. `SafetyStatusBar.tsx`, `ExecutiveOverview.tsx`, `Nav.tsx`/`NavGroup.tsx` are the only components
   this Phase 1 brief requires Codex to touch; `TaskDetail.tsx`/`TaskList.tsx`/`TaskWorkroom.tsx` are
   referenced only for their *future*-phase field-reduction mapping (defined now, applied later) —
   confirmed the brief does not ask Codex to modify those pages in Phase 1 itself.

## 7. Verdict

**PASS.** The Phase 1 Product Visual Language brief (PR #5) is architecturally sound, safely
scoped, grounded in the real deployed codebase, and does not authorize or imply anything beyond
frontend-only, existing-data, revertible visual/product-language work. It may serve as the Phase 1
design source of truth once merged (see `design-pr-source-of-truth-review.md`). Codex remains **not
authorized** to implement pending explicit Product Owner authorization.

## Statement

Review only. No runtime code changed. No backend changed. No frontend implementation changed. No
design PR merged. No Codex implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
