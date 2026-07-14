# Codex Readiness Boundary — DESIGN-66UI.4 Phase 1 Product Visual Language

> **Boundary document only. No runtime code changed. No frontend implementation changed. Codex is
> NOT authorized to implement anything in this document until the Product Owner explicitly
> authorizes implementation following this review.**

Owner: Claude Code (Lead Engineer / Architecture Owner), written for Codex (Frontend Engineer) per
`docs/process/role-responsibility-matrix.md`. This is the boundary Codex must observe for the Phase
1 visual-language work defined in `docs/design/66ui4-phase1-product-visual-language/`, subordinate
to and consistent with
`docs/frontend/66ui2-navigation-ia/codex-implementation-plan-boundary.md` and this stage's
`docs/contracts/66ui4-phase1-product-visual-language/frontend-implementation-boundary.md`.

## 1. Can implement after Product Owner authorization

- **Phase 1 visual polish only** — refine `apps/admin-console/src/styles.css` tokens per
  `visual-language-spec.md` (surface elevation, spacing scale, type scale, lifecycle-vs-safety color
  separation). No new palette, no theme system.
- **Global product language** and **microcopy improvements** per `product-microcopy-guide.md`,
  applied to the surfaces Phase 1 touches.
- **Calm safety posture display** — replace `SafetyStatusBar.tsx`'s raw-field render with the calm
  summary + expandable detail per `calm-safety-posture-spec.md`, reading the same server fields.
- **Overview cleanup using existing data only** — restructure `ExecutiveOverview.tsx` to
  attention-first bands per `overview-dashboard-spec.md`, with honest placeholders for 66D-gated
  counts.
- **Navigation visual polish without IA/route changes** — restyle `Nav.tsx` / `NavGroup.tsx` per
  `navigation-visual-polish-spec.md`; group membership, order, and every route stay exactly as
  deployed in Step 66UI.2-FE.1.
- **Field relabel / demotion only where raw evidence remains accessible** — per
  `engineering-field-reduction-map.md`; a "Technical details" disclosure keeps exact field names
  available, never removed.

## 2. What Codex must NOT implement

```text
- Backend changes.
- API changes.
- Database changes.
- New metrics endpoints.
- Workflow dispatch / resume.
- Production / external controls of any kind.
- Delivery (66D) real UI — Delivery Inbox/Detail beyond a compliant placeholder.
- Reminder/Expiry (66C.4) real UI beyond a compliant placeholder.
- Pipeline board (not part of Phase 1; needs its own future contract).
- Drag-and-drop behavior of any kind.
- Client-side-only RBAC (server remains the sole access-control authority).
- Hiding required audit/safety evidence entirely (relocate to expand/hover only; never remove).
```

## 3. Dependency map

| Frontend piece | Blocked on |
| --- | --- |
| Visual-language tokens (Phase 1) | Nothing — ready once Product Owner authorizes |
| Calm safety posture component (Phase 1) | Nothing — ready once authorized |
| Overview attention-first restructure (Phase 1) | Nothing — ready once authorized |
| Navigation visual polish (Phase 1) | Nothing — ready once authorized |
| Engineering-field reduction / microcopy on Phase 1 surfaces | Nothing — ready once authorized |
| Full Task List / Task Detail / Workroom / Audit redesigns | Their own future design brief + Claude Code review |
| Task Workspace tab convergence (Direction B) | Its own implementation-plan review (carried over from 66UI.1 review, still open) |
| Delivery Inbox/Detail, Approvals (real data) | Claude Code's Step 66D contract |
| Reminder/overdue/expiry (real data) | Claude Code's Step 66C.4 contract |
| Lifecycle Pipeline read-only view | A status-to-column mapping frontend-contract from Claude Code (still unmet) |

## 4. Authorization gate

**Codex must not implement until the Product Owner explicitly authorizes implementation after this
review.** This document, the architecture review
(`docs/design/66ui4-phase1-product-visual-language/claude-code-architecture-review.md`), and the
implementation-boundary contract together establish that Phase 1 is *safe* to authorize — they do
not themselves constitute that authorization. Three open questions from
`product-owner-review-checklist.md` remain for the Product Owner to resolve at or before
authorization: muted-text contrast nudge, whether the Overview team-activity strip ships in Phase 1
or defers to Phase 2, and PR shape (one cohesive PR vs. the 4-step sequence in
`codex-implementation-notes.md` §5).

## 5. Recommended first implementation candidate (if/when authorized)

```text
Step 66UI.4-FE.1 — Phase 1 Product Visual Language (tokens + calm safety posture + Overview
attention-first + navigation visual polish)
```

Scope limited to exactly the four buildable items in
`docs/design/66ui4-phase1-product-visual-language/codex-implementation-notes.md` §1, applied only to
`styles.css`, `SafetyStatusBar.tsx`, `ExecutiveOverview.tsx`, `Nav.tsx`/`NavGroup.tsx`, and the
already-shown safety fields on `TaskDetail.tsx`. No IA/route change. No backend change. No workflow
behavior change. Frontend-only, existing-data, fully revertible — same low-risk shape as Step
66UI.2-FE.1.

## Statement

Boundary specification only. No runtime code changed. No frontend implementation changed. No backend
change. No workflow dispatch. No workflow resume. No external action. No production action. Codex
implementation not authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
