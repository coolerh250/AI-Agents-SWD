# Navigation Polish Spec — Step 66UI.4-FE.1D

> Owner: Claude Design. Label / helper-text / badge / grouping polish for the **existing** 7-group
> nav (`Nav.tsx`). **No route additions, no route-target changes, no IA restructure.**

## Baseline (deployed, `Nav.tsx` @ `707cb8c`)

7 groups: Overview, Team Work, Deliveries, Operator Center, Governance, Platform Ops (20 items,
collapsed by default), Settings. Placeholder destinations exist (Delivery Inbox/Detail, Reminder/
Expiry, Approvals, DLQ/Retry, Settings/*) but the **nav items themselves are not visually marked**
as not-yet-available — the "not yet available" message only appears after navigating.

## 1. Group names — keep

The 7 group names already read as product areas, not engineering layers. **No renames.** Optional:
add a one-line group subtitle/helper on hover or under the header (label text only), e.g.:

| Group | Optional subtitle |
| --- | --- |
| Team Work | "Assign and collaborate with the AI team" |
| Deliveries | "Review and accept delivered work" |
| Operator Center | "Handle operations, approvals, and recovery" |
| Governance | "Safety and audit evidence" |
| Platform Ops | "Platform & DevOps status (read-only)" |
| Settings | "Roles, integrations, and policy" |

## 2. Placeholder nav items — add a "Soon" badge (label/badge only)

Give every nav item whose destination is a `PlaceholderPage` a small muted **"Soon"** (or stage tag)
badge, so its not-yet-available state is legible *in the nav* without navigating. Applies to:
Deliveries → Delivery Inbox, Delivery Detail; Team Work → (Clarifications is a placeholder page —
badge "Soon"); Reminder/Expiry; Operator Center → Approvals, DLQ / Retry; all 5 Settings items;
Overview → Notifications. This is a badge + muted styling only — the route and destination are
unchanged.

> Note: this is a nav-label/badge change, not a route change. The placeholder *pages* already exist
> and already say "Not yet available."

## 3. Page order — minor, within groups only

Operator flow reads top-to-bottom already. One optional within-group reorder (no cross-group moves):
in **Operator Center**, order by daily use — Operator Console, Incidents, Agent Executions, then the
"Soon" Approvals / DLQ-Retry last. No new routes; ordering only.

## 4. Platform Ops — see `platform-ops-density-spec.md`

Platform Ops (20 items) is the main density concern. Handled in its own spec: shorten labels, add
read-only / diagnostic / evidence markers, optional non-structural visual sub-grouping. Minimal
polish, not a reorg.

## 5. Labels to clarify (reduce ambiguity, no route change)

Three delivery-flavored items can read as duplicates; clarify by label/subtitle, **not** by moving
them:

| Current label | Route | Clarified label / subtitle | Reason |
| --- | --- | --- | --- |
| Deliveries (group) → Delivery Inbox / Detail | `/delivery-inbox`, `/delivery-detail` | keep; "Soon" badge | future 66D task-linked acceptance |
| Platform Ops → Delivery Package | `/delivery-package` | subtitle "Delivery evidence / package record" | existing evidence surface, distinct from 66D |
| Platform Ops → Projects / Work Items | `/delivery` | keep label; subtitle "Multi-project delivery (read-only)" | legacy delivery model |

## 6. Demo Evidence — unchanged

Stays out of first-level nav (direct route only). No change.

## Accessibility

- "Soon"/marker badges carry text (not color alone); nav items keep keyboard focus and button/link
  semantics; subtitles are real text, not title-only tooltips where they carry meaning.

## Out of scope (FE.1D)

- No new nav routes; no route-target changes; no cross-group moves; no IA restructure.
- No fix for the SPA deep-link/hard-refresh gap (backend; see design-brief).

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
