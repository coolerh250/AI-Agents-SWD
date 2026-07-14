# Navigation Visual Polish Spec — DESIGN-66UI.4 Phase 1

> Owner: Claude Design. Visual refinement of the **existing** deployed 7-group side nav
> (`Nav.tsx` / `NavGroup.tsx` / `.side-nav` in `styles.css`). **No IA change, no route change** —
> the 66UI.2 structure is correct and stays.

## Baseline (deployed today)

`.side-nav` renders 7 groups (Overview, Team Work, Deliveries, Operator Center, Governance, Platform
Ops collapsed, Settings); each item is a `--card` chip with `--line` border; active item gets
`#388bfd` border + faint accent background. Structurally good; visually flat — every item is the
same weight, group headers are quiet, and the 20-item Platform Ops group can still visually dominate
when expanded.

## Polish (visual only)

### 1. Group rhythm & hierarchy

- Increase separation between groups (spacing scale `16`), reduce per-item chrome so items read as a
  list, not 27 equal buttons. Group titles use the `label` type style (uppercase, `--muted`).
- Give the two daily-driver groups (Team Work, Operator Center — per Direction A/B) slightly stronger
  presence; keep Governance/Settings calm; keep Platform Ops **quiet** (`--surface-quiet`) and
  collapsed by default (already the case).

### 2. Active & current-context state

- Strengthen the active item (clear filled state on `--surface-raised`, not just a border) so "where
  am I" is unmistakable.
- Auto-expand the group containing the active route (already implemented); ensure the active item is
  scrolled into view within a long nav.

### 3. Item treatment

- Items become quieter by default (less card-like), with hover/active doing the visual work — this
  reduces the "wall of identical chips" feel. Placeholder items (Delivery Inbox/Detail, Reminder,
  Settings items) keep their muted + stage-tag treatment from 66UI.2 (`Requires 66D` etc.),
  restyled to the refined chip.

### 4. Platform Ops stays subordinate

- Collapsed by default (unchanged). When expanded, render its 20 items in the **compact** density on
  `--surface-quiet` so it reads clearly as "advanced / platform maintenance," never competing with
  the core product groups. This directly serves the PO principle that Platform Ops must exist but not
  dominate the product feel.

### 5. Top-bar relationship

- The persistent top bar now carries the **calm safety posture** (from `calm-safety-posture-spec.md`)
  instead of the raw field bar; the nav and top bar should read as one calm frame around the content,
  not two noisy strips.

## Explicitly unchanged

- Group membership, order, and every route (66UI.2, deployed + PO-validated). Delivery Package stays
  under Platform Ops (66UI.3 decision).
- Collapse/expand behavior and the role-based landing routes.
- Placeholder semantics and tags.

## Accessibility

- Group toggles and nav items keyboard-navigable with visible focus (existing `NavGroup` toggle
  keeps its button semantics); active state not conveyed by color alone (add weight/fill).

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
