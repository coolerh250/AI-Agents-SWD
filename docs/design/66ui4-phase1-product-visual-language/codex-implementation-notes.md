# Codex Implementation Notes — DESIGN-66UI.4 Phase 1

> Owner: Claude Design, for Codex (Frontend Engineer). **Codex is NOT authorized to implement until
> Claude Code reviews this brief AND the Product Owner explicitly authorizes Phase 1.** These notes
> describe the intended Phase 1 build; they are not permission to start.

## Subordinate to the boundary docs

Consistent with `docs/frontend/66ui2-navigation-ia/codex-implementation-plan-boundary.md` and the
role-responsibility matrix. Where anything here appears to conflict with a Claude Code contract or
boundary doc, those win.

## 1. Scope Codex may implement in Phase 1 (once authorized)

- **Visual-language tokens** per `visual-language-spec.md`: add `--surface-raised/base/quiet`,
  spacing scale, type scale, and lifecycle-vs-safety color separation to `styles.css`. Refinement of
  existing tokens — no new palette, no theme system.
- **Calm safety posture component** per `calm-safety-posture-spec.md`: replace the raw-field render
  in `SafetyStatusBar.tsx` with the calm summary + expandable human-labeled detail. **Keep reading
  the same server field(s) it reads today**; only the presentation changes.
- **Overview dashboard** per `overview-dashboard-spec.md`: restructure `ExecutiveOverview.tsx` to
  attention-first bands over the **existing** `/operations/admin-console/overview` data, with honest
  placeholders ("Requires Step 66D") for gated counts.
- **Navigation visual polish** per `navigation-visual-polish-spec.md`: restyle `NavGroup`/`.side-nav`
  (rhythm, active state, quiet Platform Ops). **No IA/route change.**
- **Engineering-field reduction + microcopy** per `engineering-field-reduction-map.md` and
  `product-microcopy-guide.md`, applied to the surfaces Phase 1 touches (safety posture, Overview,
  nav, and the safety fields already shown on Task Detail). A shared "Technical details" disclosure
  pattern for demoted fields.

New components likely needed: a `SafetyPosture` component (replacing the bar's internals), Overview
attention-tile + team-activity-strip components, a small "TechnicalDetails" disclosure. Reuse
existing `StatusBadge`, `EmptyState`, `ErrorState`, `LoadingState`, `Layout`, `NavGroup`.

## 2. Scope NOT in Phase 1 (later phases)

- Full Workroom / Task Detail / Task List / Clarification / Audit redesigns — later phases; Phase 1
  only defines their shared language and applies it where safety fields already appear.
- Task Workspace tab convergence (Direction B) — its own future stage + implementation-plan review.
- Delivery Review UI — placeholder-only until Step 66D contract.
- Reminder/Expiry real UI — placeholder-only until Step 66C.4 contract.

## 3. Reuse & data rules

- **Existing endpoints only.** No new/changed endpoint. Overview uses the existing overview
  endpoint; safety posture uses the existing safety source.
- **Safety values stay server-computed and displayed-as-returned.** The calm summary maps values →
  plain language for *display*; it must not hardcode or infer the values. Missing value → "not
  reported," never a guessed default.
- **Agent identity/activity** (Overview team strip) must come from real server data; where none is
  available, show a calm "No active agent runs," not invented activity.
- **Plain-text rendering unchanged** for any user/agent content.

## 4. Hard prohibitions (restated)

```text
- No IA / route change.
- No backend / API / contract change.
- No workflow dispatch / resume / state mutation.
- No production or external action; production_executed stays server-computed and shown as 0/None.
- No client-side inference or hardcoding of safety values.
- No fabricated counts, deliveries, approvals, or agent activity.
- No client-side-only RBAC.
- No removal of any safety signal (relocate technical detail only).
- No Delivery (66D) / Reminder (66C.4) real UI beyond compliant placeholders.
```

## 5. Suggested Phase 1 PR shape (once authorized)

Because this touches global styling + three surfaces, it can ship as one cohesive PR or a small
sequence: (a) tokens + microcopy/util scaffolding, (b) calm safety posture, (c) Overview
attention-first, (d) nav polish. All are frontend-only, use existing data, and are revertible.
Frontend tests + `npm run build` / `npm test` required (frontend files change).

## Statement

Design specification only. No runtime code. No production action. No Codex implementation authorized
by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
