# Admin Console v0 — Read-only Visibility (Step 48 / Stage 50)

## Purpose

The first browser UI for the platform: a **read-only** project-delivery
management view for business owners, project managers, platform operators, and
system administrators. It upgrades the operator experience from "API / scripts /
Grafana" to a coherent read-only delivery / governance status console.

It does **not** replace Grafana. Grafana stays for metrics / tracing / infra
observability; Admin Console v0 focuses on business workflow / project delivery /
governance status / operator visibility.

## Scope

Read-only visibility over: platform safety posture, projects, project stage,
task graph / work items, design review findings / gates / go-no-go, workspace
generated code summary / tests / diff, mini delivery pilot status, delivery
package + acceptance gate, human acceptance (pending), regression status, audit
integrity, backup readiness gaps, incidents, and LLM / cost governance.

## Read-only model

The console is strictly read-only (see
[admin-console-read-only-safety.md](admin-console-read-only-safety.md)):

- No approve / reject / request-changes / rerun / pause / resume / edit.
- No trigger workspace execution / delivery package build / deploy / PR.
- No write API calls (GET only), no direct DB / Redis access.
- Operator action affordances are absent or disabled with a tooltip:
  "Operator actions are disabled in Admin Console v0."

## Pages

Executive Overview, Projects, Project Detail, Task Graph, Design Review,
Workspace Execution, Mini Delivery Pilot, Delivery Package / Acceptance Gate,
Safety Center, Regression / Verification, Cost / LLM Governance, Incidents. See
[admin-console-page-map.md](admin-console-page-map.md).

## API sources

Only existing `/operations/*` GET endpoints plus six read-only aggregate
endpoints under `/operations/admin-console/*`
(see [../operations/admin-console-operations.md](../operations/admin-console-operations.md)).
No endpoint has side effects.

## Deployment method

The console is served at **`/admin`** by the orchestrator via a `StaticFiles`
mount. The mount prefers a built Vite bundle (`admin_console_static/dist`) when
present and otherwise serves a committed **zero-build static fallback**
(`apps/admin-console/static/index.html`) — a self-contained read-only page that
calls the aggregate API. This guarantees `/admin` responds even where a Node
toolchain is unavailable. No new docker service and no Node runtime are required.

To build the richer React app (optional, when npm is available):

```bash
cd apps/admin-console
npm install
npm run typecheck && npm run build   # outputs to static/dist (gitignored)
npm test
```

`VITE_OPERATIONS_API_BASE_URL` sets the API base (default same-origin /
`http://localhost:8000`). `node_modules/` and `static/dist/` are gitignored.

## Limitations

- No real authentication / RBAC (placeholder only this stage).
- Task Graph / Design Review / Workspace pages surface the latest pilot context;
  full per-project historical drill-down (and optional React Flow graph) is
  future work — a fallback table is always present.
- Human acceptance is always shown `pending`; the console cannot change it.

## Future v1 operator actions

Step 50 (Admin Console v1) will add real operator actions (accept / reject /
request-changes) gated by auth + approval policy + audit, with operator action
endpoints enabled only behind `ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS=true`.
