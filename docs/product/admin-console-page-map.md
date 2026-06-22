# Admin Console v0 — Page Map (Stage 50)

| Route | Page | Purpose | Data source | Empty state |
|---|---|---|---|---|
| `/` | Executive Overview | platform + delivery status at a glance | `GET /operations/admin-console/overview` | always renders cards |
| `/projects` | Projects | all projects with rollup | `GET /operations/admin-console/projects` | "No projects yet" |
| `/projects/:id` | Project Detail | single project full view | `GET /operations/admin-console/projects/{id}` | 404 → "Not available" |
| `/task-graph` | Task Graph | work items / dependencies (latest context; fallback table) | `GET /operations/admin-console/latest-delivery-state` | "No project graph available yet" |
| `/design-review` | Design Review | findings / gates / go-no-go (latest context) | `GET /operations/admin-console/latest-delivery-state` | "No design review available yet" |
| `/workspace` | Workspace Execution | generated file manifest / tests / diff summary | `GET /operations/admin-console/latest-delivery-state` | "No workspace execution available yet" |
| `/mini-delivery` | Mini Delivery Pilot | pilot status / evidence | `GET /operations/admin-console/latest-delivery-state` | "No mini delivery pilot yet" |
| `/delivery-package` | Delivery Package / Acceptance Gate | package + gate + readiness + human acceptance | `GET /operations/admin-console/latest-delivery-state` | "No delivery package yet" |
| `/safety` | Safety Center | read-only safety posture | `GET /operations/admin-console/safety-summary` | renders KV table |
| `/regression` | Regression / Verification | latest regression status + gaps | `GET /operations/admin-console/regression-summary` | renders KV table |
| `/cost-llm` | Cost / LLM Governance | LLM routing / usage / budget | `GET /operations/admin-console/overview` (llm_summary) | "No usage data available" |
| `/incidents` | Incidents | incident counts / lifecycle | `GET /operations/admin-console/overview` (incidents_summary) | "No incidents" |

## Empty / error behaviour

- **Loading:** every page shows "Loading…" while its read-only request is in
  flight.
- **404 / missing endpoint:** "Not available in this environment".
- **Other API error:** "Unable to load data (…)" — the app never crashes.
- **Empty data:** a dedicated EmptyState message per page (above).

## Routing

The built React app uses client-side routing under `basename="/admin"`. The
zero-build static fallback uses an in-page page switcher with a fixed subset of
pages (Overview, Projects, Delivery Package, Safety, Regression, Cost/LLM,
Incidents) calling the same aggregate endpoints.

## Read-only baseline pages (Step 51.4 / Step 52.4)

* **Runtime Baseline** (`/runtime`) — read-only Kubernetes/Helm/GitOps baseline
  (`/operations/runtime/report`); no deploy/sync/apply/install control.
* **Identity Posture** (`/identity`) — read-only Step 52 identity foundation
  (`/operations/identity/report`); production identity NOT enabled, no OIDC
  login/connect/configure button, no production auth toggle, no role-mapping
  editor, no break-glass button, no token/secret display.

Both pages are GET-only and present in the React app and the static fallback.
