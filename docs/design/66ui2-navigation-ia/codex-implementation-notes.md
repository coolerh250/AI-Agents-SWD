# Codex Implementation Notes — DESIGN-66UI.2

> Owner: Claude Design, written for Codex (Frontend Engineer). **Codex is NOT authorized to
> implement anything here until the Product Owner explicitly authorizes implementation after Claude
> Code reviews this brief** (`docs/frontend/66ui-full-redesign-options/codex-readiness-boundary.md`
> §4). These notes describe *what* the round-1 nav shell is, not permission to build it.

## Alignment with the existing boundary docs

These notes are consistent with, and subordinate to:
- `docs/contracts/66ui-full-redesign-options/frontend-implementation-boundary.md` (what may proceed
  without a new contract; what needs one).
- `docs/frontend/66ui-full-redesign-options/codex-readiness-boundary.md` (forbidden list;
  dependency map; authorization gate).

If anything here appears to conflict with those, those documents win.

## 1. Scope Codex may implement (once authorized)

- **Grouped, collapsible left-nav shell** — restructure `apps/admin-console/src/components/Nav.tsx`
  from a flat list into the 7 groups in `navigation-map.md` (Overview, Team Work, Deliveries,
  Operator Center, Governance, Platform Ops, Settings), using a `NavGroup` component with
  expand/collapse.
- **Regroup existing routes** under the new groups per `migration-from-current-nav.md` —
  **without changing any route target or page component.** Every existing `to=""` path stays
  exactly as it is today.
- **Default expansion state** per `navigation-map.md` (Team Work expanded; Platform Ops collapsed;
  active-route group auto-expands). Expansion state may be kept in client-side UI state only.
- **Role-based default landing** per `role-based-entry-points.md`, with the documented interim
  fallbacks (e.g. Reviewer/Approver → Overview until 66D). Default route selection is client-side
  and grants no capability.
- **Compliant placeholder routes/panels** for the not-yet-available items, following
  `placeholder-rules.md` exactly (state label + "Not yet available" + specific stage + "No workflow
  action available"; no actionable controls; no fabricated data).
- **Remove `Diagnostics (Demo Evidence)` from the first-level nav** while keeping its `/demo-evidence`
  route reachable by direct URL.
- **Persistent top-bar safety posture** (`dispatch=OFF`, `resume=OFF`, `prod_exec=0`) and
  test-role-simulation indicator on every page — reusing the existing `SafetyBadge` /
  safety-display components; values come from the server, never inferred client-side.

Reuse existing shared components wherever possible: `SafetyBadge`, `StatusBadge`, `EmptyState`,
`ErrorState`, `LoadingState`, `EvidenceTable`, `JsonPanel`, `KeyValueTable`, `Layout`. The only
genuinely new components needed for round 1 are a `NavGroup` (collapsible group) and a
`PlaceholderPanel` (compliant placeholder renderer).

## 2. Scope Codex must NOT touch

- **No route target changes.** Do not re-point, rename the path of, or merge any existing route.
  (Labels in the nav may be refined, e.g. "Executive Overview" → "Dashboard"; the *route* does not
  change.)
- **No page content/behavior changes** to any existing page, including all Platform Ops pages
  (grouping only — no redesign this round).
- **No Task Workspace tab-merge** of `TaskDetail.tsx` + `TaskWorkroom.tsx` (that is Option 2, a
  later stage needing its own implementation-plan review — Claude Code review §6.3).
- **No backend, API client contract, RBAC rule, or safety-computation change.**

## 3. How to reuse existing routes

- Keep the current route table and page components intact. The nav change is purely *which group
  header a given `NavLink` is rendered under*, plus collapse/expand chrome around groups.
- Contextual routes (`/tasks/:id`, `/tasks/:id/workroom`) stay as sub-routes reached from the Task
  List; they are not promoted to standing top-level links.
- Placeholder items get **new** routes that render `PlaceholderPanel` — they must not alias or
  shadow any existing working route.
- All data shown by existing pages continues to come from the existing endpoints
  (`GET /tasks`, `GET /tasks/{id}`, `GET /tasks/{id}/workroom`, `GET /tasks/{id}/audit-evidence`,
  and the three `POST` workroom/clarification endpoints). No new endpoint is needed or permitted for
  round 1.

## 4. Placeholder presentation (must follow `placeholder-rules.md`)

- Every placeholder is a read-only informational panel with the required plain-text messages.
- No Accept / Reject / Approve / Retry / Replay / Send / Dispatch / Resume / drag control anywhere in
  a placeholder.
- No fabricated counts, rows, deliveries, approvals, or queues.
- Integrations placeholder shows every connector as not-connected/disabled with no "Connect" control.

## 5. Hard prohibitions (restated from the boundary docs)

```text
- No workflow state mutation.
- No workflow dispatch.
- No workflow resume.
- No production behavior; production_executed_true_count stays server-computed and displayed as 0.
- No lifecycle drag-and-drop (the deferred pipeline, if ever built, is read-only and needs a
  status-to-column mapping contract from Claude Code first — not in round 1).
- No Delivery (66D) functionality beyond a compliant placeholder (no 66D contract exists yet).
- No Reminder/Expiry (66C.4) functionality beyond a compliant placeholder (no 66C.4 contract yet).
- No Settings/Identity (66S) functionality beyond a compliant placeholder.
- No client-side-only RBAC; server remains the authority.
```

## 6. Dependency map (what unblocks what)

| Frontend piece | Blocked on |
| --- | --- |
| Nav shell / IA regrouping (round 1) | Nothing — ready once Product Owner authorizes |
| Placeholder routes/panels (round 1) | Nothing — ready once authorized |
| Role-based default landing (round 1) | Nothing — ready once authorized |
| Delivery Inbox/Detail, Approvals, DLQ/Retry (real) | Claude Code's 66D contract |
| Reminder/overdue/expiry (real) | Claude Code's 66C.4 contract |
| Unified Operator Action Center | Both 66D and 66C.4 contracts |
| Task Workspace tab shell (Option 2) | Its own implementation-plan review (Claude Code review §6.3) |
| Lifecycle Pipeline read-only view | A status-to-column mapping frontend-contract from Claude Code |

## 7. Suggested first PR (once authorized)

A single, self-contained PR: the `NavGroup` regrouping + `PlaceholderPanel` + placeholder routes +
role-based default landing + removal of Demo Evidence from first-level nav. It touches
`Nav.tsx`, adds two components, and adds placeholder routes — no existing page is modified. This is
the lowest-risk possible first step and is fully revertible. Frontend tests and `npm run build` /
`npm test` would be required for this PR since it changes frontend files.

## Statement

Design specification only. No runtime code. No production action. No Codex implementation authorized
by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
