# Design Brief — DESIGN-66UI.4 Phase 1: Global Product Visual Language

> Owner: Claude Design. The Phase 1 detailed design brief authorized by the Product Owner's
> DESIGN-66UI.3 decision (`docs/design/66ui3-product-ux-visual-direction/product-owner-decision-record.md`).
> **Design specification only — no runtime code, no Codex implementation authorized, no backend/API
> change requested.**

## Stage

`66ui4-phase1-product-visual-language` (DESIGN-66UI.4, "Phase 1" of the 66UI.3 roadmap)

## Design goal

Make the Admin Console read as a **product**, not as engineering tooling — globally, before any
page-specific redesign — by fixing the signals that appear on *every* page: raw backend fields, a
noisy safety bar, a metrics-first Overview, flat undifferentiated visual hierarchy, and
system-language microcopy. This is the direction-agnostic foundation every later phase builds on.

## Hybrid baseline (from 66UI.3 decision)

- **Direction A** framing for **Dashboard / Overview / cross-task** surfaces.
- **Direction B** framing for **Task Detail / Workroom / Clarification / future Delivery Review**
  (later phases; Phase 1 only prepares the shared visual language they will use).
- **Direction C** *principles* throughout: simplified product language, calmer safety posture,
  better visual hierarchy, reduced engineering-field exposure.

## Phase 1 scope (the six items the Product Owner named)

1. **Global product visual language** — a refined token + hierarchy system (`visual-language-spec.md`).
2. **Calm safety posture** — replace the raw 12-field `SafetyStatusBar` with a calm, plain-language
   posture indicator (`calm-safety-posture-spec.md`).
3. **Overview cleanup** — attention-first Overview dashboard (`overview-dashboard-spec.md`).
4. **Navigation visual polish** — visual refinement of the existing 7-group nav, no IA change
   (`navigation-visual-polish-spec.md`).
5. **Engineering-field reduction** — a concrete field-by-field map from raw backend names to product
   language or expandable detail (`engineering-field-reduction-map.md`).
6. **Product microcopy improvement** — a microcopy guide with before/after strings
   (`product-microcopy-guide.md`).

Plus `codex-implementation-notes.md` (what Codex may build once authorized) and
`product-owner-review-checklist.md`.

## What this stage changes

- Introduces a product-grade visual language (elevation, density, typography scale, semantic-vs-
  lifecycle color separation) layered on the **existing** dark tokens — refinement, not a new
  palette.
- Replaces the raw safety-field bar with a calm posture indicator (same server values, product
  presentation).
- Restructures the Overview to lead with human-action queues, then metrics.
- Polishes the nav's visual rhythm/active-state and keeps Platform Ops visually quiet.
- Reduces engineering-field exposure app-wide and replaces system strings with product microcopy.

## What this stage does NOT change

- **No IA / route changes.** The 7-group nav and every route stay exactly as deployed (66UI.2).
- **No page-specific redesigns** beyond Overview + the global safety indicator + nav polish. Task
  List, Task Detail, Workroom, Clarification, Delivery, Operator, Audit deep-redesigns are **later
  phases** — Phase 1 only gives them the shared visual language and microcopy rules to adopt later.
- **No backend / API / contract change.** All data comes from existing endpoints; safety values stay
  server-computed and displayed-as-returned (never inferred/hardcoded client-side).
- **No new palette invented** — the existing dark tokens are refined and extended, not replaced.
  (A possible light/dual-theme is a Direction-C future question, explicitly out of Phase 1.)
- **No plain-text-rendering change** — user/agent content stays plain text (no markdown-to-HTML,
  no auto-linking, no `dangerouslySetInnerHTML`).
- **No Delivery (66D) / Reminder (66C.4) real UI** — placeholders keep their exact safety semantics.
- **No Codex authorization.** This brief makes Phase 1 *ready* to authorize after Claude Code review.

## Target roles / personas

All six product RBAC roles benefit (the changes are global). The calm safety posture especially
serves non-technical roles (Requester, Reviewer/Approver, Security/Compliance) who currently face
raw field dumps.

## Constraints

- Existing endpoints only (`GET /tasks`, `GET /tasks/{id}`, `GET /tasks/{id}/workroom`,
  `GET /tasks/{id}/audit-evidence`, `/operations/safety`, `/operations/admin-console/overview`,
  etc.). No new endpoint requested.
- Server-side RBAC remains the access-control authority; visual changes never gate access.
- Accessibility: color never the sole state carrier; visible keyboard focus; sufficient contrast in
  the dark theme; respects `prefers-reduced-motion`.
- Masking: no internal IP / SSH alias / hostname / token / secret anywhere.

## Companion documents

`visual-language-spec.md`, `calm-safety-posture-spec.md`, `overview-dashboard-spec.md`,
`navigation-visual-polish-spec.md`, `engineering-field-reduction-map.md`,
`product-microcopy-guide.md`, `codex-implementation-notes.md`, `product-owner-review-checklist.md`.

## Statement

Design specification only. No runtime code. No production action. No API/contract decision. No
Codex implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
