# Step 66D-DESIGN — Route Architecture and Existing-Route Drill-down Map

> **Design specification only. No route source modified. No frontend implementation. No merge.
> `production_executed_true_count: 0`.**

```text
CANONICAL_BASELINE:  main 9c5210d190b82b76575ba8d456b5d2005c2867d2
ROUTE INVENTORY:     measured, see docs/handoffs/66d-delivery-acceptance/
                     step66d-design-existing-ui-route-inventory.md
MEASURED ROUTE COUNT: 44   (parser over apps/admin-console/src/App.tsx)
```

## 1. Existing router convention (measured, must be respected)

`apps/admin-console/src/App.tsx` uses React Router v6 with:

```text
flat kebab-case root paths        /agent-executions, /task-graph, /delivery-package, /audit-evidence
colon params, camelCase names     /tasks/:taskId, /tasks/:taskId/workroom, /projects/:projectId
nested static segment under param /tasks/:taskId/workroom   (precedent for a nested child page)
grouped settings prefix           /settings/roles-permissions ... (5 routes)
```

The prompt's suggested semantics used `{brace}` placeholders. **The repository convention is
`:colonCamelCase`.** Per the "follow existing convention" rule, the canonical semantic routes below
are expressed in the repository's convention. No route source is modified by this stage.

## 2. Canonical semantic route contract (frozen; NOT IMPLEMENTED)

| Scope | Semantic route (repo convention) | Status today | Notes |
| --- | --- | --- | --- |
| Cross-project | `/delivery-inbox` | **route EXISTS, renders `PlaceholderPage` ("Requires Step 66D")** | reuse the existing path; replace the placeholder element in FE1 |
| Project-level | `/projects/:projectId/control-center` | **ABSENT** — PLANNED / NOT IMPLEMENTED | nests under the existing `/projects/:projectId`, mirroring the `/tasks/:taskId/workroom` precedent |
| Submission-level | `/delivery-submissions/:deliverySubmissionId/review` | **ABSENT** — PLANNED / NOT IMPLEMENTED | submission-anchored, per 66D-D04 naming (`DeliverySubmission`) |

### 2.1 Disposition of the existing `/delivery-detail` placeholder

`/delivery-detail` exists today as a `PlaceholderPage` and is **not** submission-scoped (it carries
no id parameter), so it cannot address a specific `DeliverySubmission`. Frozen disposition:

```text
/delivery-detail   -> SUPERSEDED BY /delivery-submissions/:deliverySubmissionId/review
                      FE1/FE2 must not build the review workspace on the id-less path.
                      Retire-or-redirect is a Codex implementation decision recorded in the
                      handoff; this design does not modify the route source.
```

### 2.2 Collision check (measured)

```text
grep for 'control-center'      in App.tsx -> 0 matches   (no collision)
grep for 'delivery-submissions' in App.tsx -> 0 matches  (no collision)
/delivery-inbox                 present once             (reuse, no collision)
/projects/:projectId            present once             (parent exists; child segment free)
```

## 3. Deep-link parameter contract (frozen)

Supported context parameters (query string unless noted):

```text
project_id                  (path param on the Control Center route)
primary_work_item_id
workflow_id
run_id
delivery_submission_id      (path param on the review route)
delivery_review_task_id
artifact_id                 (or an equivalent evidence target ref)
return_to                   opaque, app-internal route+fragment token
```

Binding constraints:

```text
No secret, token, credential, secret name/value, or unredacted sensitive evidence in any URL.
No actor identity or capability claim in any URL (request-provided identity is never authoritative).
return_to must be validated against an in-app allow-list of known routes; never an absolute
  external URL (open-redirect prevention).
Unknown or malformed parameters degrade to the surface's default view plus a readable notice --
  never a raw error or a blank screen.
```

## 4. Route responsibility matrix

Legend — Implemented state: `IMPLEMENTED` (real page) · `PLACEHOLDER` (route exists, renders
`PlaceholderPage`) · `PLANNED / NOT IMPLEMENTED` (no route). Source of truth = which record the
surface authoritatively reflects. All 66D write actions are NOT IMPLEMENTED.

| Surface | Actual route | Implemented state | Source of truth | Control Center summary | Drill-down purpose | Write actions |
| --- | --- | --- | --- | --- | --- | --- |
| Delivery Inbox | `/delivery-inbox` | PLACEHOLDER | `DeliveryReviewTask` queue (NOT IMPLEMENTED) | n/a (Inbox is cross-project, not a CC section) | find the submission needing review | none today; FE1 read-only, FE2 none |
| Unified Control Center | `/projects/:projectId/control-center` | PLANNED / NOT IMPLEMENTED | `project_delivery_control_center` read model (NOT IMPLEMENTED) | — (it *is* the summary surface) | — | none (read-only surface) |
| Delivery Review | `/delivery-submissions/:deliverySubmissionId/review` | PLANNED / NOT IMPLEMENTED | `DeliverySubmission` + `DeliveryReviewAction` + `ProductOwnerDecision` (NOT IMPLEMENTED) | review status, decision readiness, latest action, effective decision, primary CTA | full review workspace; Review Gate Action; PO Final Decision; follow-ups | FE2 only, NOT AUTHORIZED |
| Delivery (multi-project work items) | `/delivery` | IMPLEMENTED | work items / delivery state (Step 57) | work-item rollup line in Lifecycle Progress | work-item and dispatch detail | existing audited mutations (out of 66D scope) |
| Agent Executions | `/agent-executions` | IMPLEMENTED | `agent_executions` rows | runtime agent activity summary (Execution Summary) | per-execution detail/evidence | none |
| Task Graph | `/task-graph` | IMPLEMENTED | latest delivery-state graph (Path A model) | not a CC section; linked from Execution Summary | work decomposition/dependency detail | none |
| QA / Code Evidence | `/qa-code` | IMPLEMENTED | QA runs / code workspaces | QA result summary (Delivery/Acceptance + Evidence Health) | QA and code-workspace evidence | none |
| Audit Evidence | `/audit-evidence` | IMPLEMENTED | audit events (safe metadata) | audit evidence health + Activity Timeline entries | full audit inspection | none |
| Safety Center | `/safety` | IMPLEMENTED | `/operations/safety` posture | Safety Summary | full safety posture + evidence | none |
| Dead Letter / Retry | `/dlq-retry` | PLACEHOLDER | DLQ / retry state (task-scoped read NOT IMPLEMENTED) | failure/retry summary (Execution Summary) | DLQ/retry item detail and recovery | none today |
| Approvals | `/approvals` | PLACEHOLDER | approval queue (NOT IMPLEMENTED for 66D) | approvals line in Attention Strip | approval item detail | none today |
| Metrics / Cost | `/metrics`, `/cost-llm` | IMPLEMENTED | operational metrics; LLM cost | Cost and External Actions summary | full metrics / cost detail | none |
| Project / Project Detail | `/projects`, `/projects/:projectId` | IMPLEMENTED | project rollup | Project Context Header | project detail | none |
| Legacy Delivery Package | `/delivery-package` | IMPLEMENTED | legacy `DeliveryPackage` (Step 47/49) | referenced only as `legacy_delivery_package_refs` in the submission summary | legacy evidence package inspection | existing legacy semantics unchanged (66D-D04) |
| Sandbox GitHub | `/sandbox-github` | IMPLEMENTED | sandbox draft-PR posture | source-control evidence line | branch/commit/Draft PR evidence | none (sandbox, dry-run default) |
| Workspace Execution | `/workspace` | IMPLEMENTED | workspace manifest/tests/diff | latest artifact line | artifact/workspace detail | none |
| Incidents | `/incidents` | IMPLEMENTED | incident summary | failure summary (secondary) | incident detail | none |

**Rule compliance:** every Control Center section above has an explicit source route or a
`PLANNED / NOT IMPLEMENTED` source; no absent route is described as implemented.

## 5. Return behavior (frozen)

Returning from any drill-down to the Control Center must preserve:

```text
project          (never re-select a project)
selected section (restore the anchor the user left from)
filters          (drill-down filters that were seeded from the CC context)
expanded item    where practical (e.g. the expanded evidence row)
```

Mechanism: the Control Center passes `return_to` (validated in-app token encoding route +
fragment + minimal filter state). If `return_to` is missing or invalid, the drill-down's back
affordance falls back to `/projects/:projectId/control-center` with the default `#overview`
section — never to a project picker.

## 6. Missing-route handling

Where a drill-down target is `PLACEHOLDER` or `PLANNED / NOT IMPLEMENTED`, the Control Center
summary card must:

```text
render the summary as UNKNOWN or MISSING (never healthy/zero)
label the target explicitly as not yet available, with the gating stage
disable the deep link (no dead navigation) and explain why
never fabricate a count or a status
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
