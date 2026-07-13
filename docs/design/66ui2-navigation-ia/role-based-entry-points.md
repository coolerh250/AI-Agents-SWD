# Role-Based Entry Points — DESIGN-66UI.2

> Owner: Claude Design. Default landing and primary nav items per product RBAC role
> (`docs/product/operator-rbac-model.md`). Nav visibility is a convenience layer only — server-side
> RBAC remains the authority for what each role can actually access.

## Default entry point matrix

| Role | Default landing | Interim fallback (if default is placeholder-gated) | Primary groups surfaced |
| --- | --- | --- | --- |
| Requester | Team Work → Tasks (My Tasks scope) | — | Team Work, Overview |
| PM / Engineering Lead | Overview → Dashboard | — | Overview, Team Work, Deliveries*, Operator Center |
| Reviewer / Approver | Operator Center → Approvals | Overview → Dashboard (until 66D) | Operator Center, Deliveries*, Governance |
| Platform Admin | Overview → Dashboard | — | all 7 groups |
| Agent Operator | Operator Center → Operator Console | — | Operator Center, Governance, Platform Ops |
| Security / Compliance Reviewer | Governance → Safety Center | — | Governance, Platform Ops (security posture) |

\* Deliveries is a placeholder group until Step 66D; it is "surfaced" in the sense of being visible
and clearly marked, not functional.

## Per-role detail

### Requester

- **Default:** `Team Work → Tasks`, scoped to their own tasks. The Requester's whole concern is
  usually one or a few tasks, so landing directly in Team Work (not a cross-task dashboard) is the
  shortest path to "what's happening with my task / what is waiting on me."
- **Primary items:** Tasks, Create Task, Task Detail, Task Workroom (answer Clarifications).
- **Does not need:** Operator Center, Platform Ops (collapsed, rarely relevant).

### PM / Engineering Lead

- **Default:** `Overview → Dashboard`. A PM oversees many tasks; the cross-task summary (open tasks,
  clarifications waiting, deliveries pending once 66D lands) is the right first screen, with Team
  Work one click away for drill-in.
- **Primary items:** Overview, Team Work (team-scoped Tasks), Clarifications, Deliveries (future
  review), Operator Center (awareness).

### Reviewer / Approver

- **Intended default:** `Operator Center → Approvals`. This role's core job is acting on gated
  approvals.
- **Interim fallback:** because `Approvals` is 66D-gated (placeholder), the interim default is
  `Overview → Dashboard` rather than landing the user on a placeholder panel. Once 66D ships and the
  Approvals page becomes active, the default moves to `Operator Center → Approvals`.
- **Primary items:** Approvals (future), Delivery Detail (future review), Governance (evidence).

### Platform Admin

- **Default:** `Overview → Dashboard`. This role legitimately needs everything; the dashboard is the
  neutral cross-cutting entry, and all 7 groups are available. Grouping is what makes the full
  surface navigable (previously 28 flat items).
- **Primary items:** all groups; most frequent are Overview, Team Work, Governance, Settings
  (future), Platform Ops.

### Agent Operator

- **Default:** `Operator Center → Operator Console`. This role handles execution, failures, and
  (once 66D) DLQ/Retry — Operator Center is its home.
- **Primary items:** Operator Console, Incidents, Agent Executions, DLQ/Retry (future), plus Team
  Work Workroom + Governance Audit Evidence when investigating a specific task's failure.

### Security / Compliance Reviewer

- **Default:** `Governance → Safety Center`. This role's material starts with safety posture and
  audit evidence.
- **Primary items:** Safety Center, Audit Evidence, and — because platform security posture lives
  under Platform Ops (Identity/Secret/Security Posture) — those Platform Ops items are a
  documented secondary destination. This cross-group span is an accepted consequence of keeping
  Category H as a grouping-only surface this round (consistent with the 66UI.1 journey-map finding);
  it is flagged in `product-owner-review-checklist.md` as something to revisit if it proves awkward.

## Safety visibility is role-independent

Regardless of role or landing page, the persistent top-bar safety posture (`dispatch=OFF`,
`resume=OFF`, `prod_exec=0`) and the test-role-simulation indicator are shown on every page. RBAC
denial is always a readable message ("Your current role cannot perform this action."), never a
blank screen or a broken section.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
