# Navigation Map — DESIGN-66UI.2

> Owner: Claude Design. The proposed left-navigation structure for the Admin Console. Structure
> only — no route target changes (see `design-brief.md` "What this stage does NOT change").

## Proposed left navigation structure

```text
┌─ Top bar (persistent, all pages) ───────────────────────────────────────────┐
│ [Role: <simulated role> ▾]   Safety: dispatch=OFF · resume=OFF · prod_exec=0 │
│                              🔔 Notifications      ⚠ test-role simulation     │
└──────────────────────────────────────────────────────────────────────────────┘

Left navigation (grouped, collapsible):

▸ Overview                                   [active]
    Dashboard                                (default landing for most roles)

▸ Team Work                                  [active · expanded by default]
    Tasks                                    → /tasks
    Create Task                              → /tasks/new
    Task Detail                              → /tasks/:id            (contextual)
    Task Workroom                            → /tasks/:id/workroom   (contextual)
      └ Clarifications                       (section within Workroom)
      └ Reminder / Expiry                    [placeholder · Requires Step 66C.4]

▸ Deliveries                                 [placeholder group · Requires Step 66D]
    Delivery Inbox                           [placeholder · Requires Step 66D]
    Delivery Detail                          [placeholder · Requires Step 66D]

▸ Operator Center                            [active]
    Operator Console                         → /operator
    Incidents                                → /incidents
    Agent Executions                         → /agent-executions
    Approvals                                [placeholder · Requires Step 66D]
    DLQ / Retry                              [placeholder · Requires Step 66D]

▸ Governance                                 [active]
    Safety Center                            → /safety
    Audit Evidence                           → /audit-evidence

▸ Platform Ops                               [active · COLLAPSED by default]
    Operational Metrics                      → /metrics
    Projects                                 → /projects
    Projects / Work Items                    → /delivery
    Workflows / Task Graph                   → /task-graph
    QA / Code                                → /qa-code
    Design Review                            → /design-review
    Workspace Execution                      → /workspace
    Mini Delivery Pilot                      → /mini-delivery
    Delivery Package                         → /delivery-package
    Regression                               → /regression
    Cost / LLM                               → /cost-llm
    Runtime Baseline                         → /runtime
    Identity Posture                         → /identity
    Secret Posture                           → /secrets
    Security / Supply Chain                  → /security
    Sandbox GitHub Draft PR                  → /sandbox-github
    Release Governance                       → /release-governance
    Backup / Restore / DR                    → /backup-dr
    Production Readiness Gate                → /production-readiness
    Controlled Rollout Review                → /controlled-rollout-review

▸ Settings                                   [placeholder group]
    Roles & Permissions                      [placeholder · Requires Step 66S]
    Integrations                             [placeholder · Coming later]
    Web Research Sources                     [placeholder · Coming later]
    Approval Policy                          [placeholder · Coming later]
    Identity / Session                       [placeholder · Requires Step 66S; read-only posture
                                              lives under Platform Ops → Identity Posture today]

(not in first-level nav)
    Diagnostics (Demo Evidence)              → /demo-evidence  (direct-route only; dev diagnostic)
```

## Primary nav vs. secondary nav

- **Primary nav** = the 7 group headers, always visible: Overview, Team Work, Deliveries, Operator
  Center, Governance, Platform Ops, Settings. This is the entire top level — 7 items where there
  used to be 28.
- **Secondary nav** = the items inside each expanded group. Contextual items (Task Detail, Task
  Workroom) appear as secondary items only once a task is opened; they are reached by selecting a
  task from `Tasks`, not by a standing top-level link (this matches today's behavior — Workroom is
  already a sub-route of a task, never a standalone nav entry).

## Collapsed group behavior

- Each group header is a disclosure control (expand/collapse), with the current group's expansion
  state preserved within a session (client-side UI state only — not persisted to any backend, no
  credential/session storage; consistent with the localStorage restriction in the original spec).
- **Default expansion state:** `Team Work` expanded; `Platform Ops` collapsed; all other groups
  collapsed except the one containing the active route, which auto-expands. This makes the core
  product surface (Team Work) immediately visible and keeps the 20-item Platform Ops group from
  dominating the viewport.
- A collapsed group still shows its header and any attention indicator (e.g., a count badge) so a
  collapsed group never hides the fact that something inside needs attention. Attention counts that
  depend on 66D/66C.4 data are themselves placeholders until those contracts exist (see
  `placeholder-rules.md`) — no fabricated counts.
- Placeholder groups (`Deliveries`, and the placeholder items within `Settings`) render their header
  in a muted/disabled style with the required placeholder label; selecting them opens the compliant
  placeholder panel rather than a working page.

## Default landing behavior

- Landing is **role-based** (see `role-based-entry-points.md` for the full matrix). The default for
  most roles is `Overview → Dashboard`.
- Where a role's *intended* default is a placeholder area (e.g. Reviewer / Approver → Approvals,
  which is 66D-gated), the interim default falls back to `Overview → Dashboard` until the gating
  stage ships, rather than landing the user on a placeholder. This fallback is documented per-role
  in `role-based-entry-points.md`.
- Landing selection is a client-side default route only; it does not grant any capability and does
  not change server-side RBAC.

## Safety surfaces in the nav frame

The persistent top bar carries the always-visible safety posture (`dispatch=OFF`, `resume=OFF`,
`prod_exec=0`) and the test-role-simulation indicator on every page regardless of group. Detailed
safety/governance placement is in `role-based-entry-points.md` (Governance group) and the
per-page rows in `page-grouping.md`; the values themselves are server-computed and displayed as
returned (`frontend-implementation-boundary.md` §4), never inferred in the nav.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
