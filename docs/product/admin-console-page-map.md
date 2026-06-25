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

## Read-only baseline pages (Step 51.4 / Step 52.4 / Step 53 / Step 54.1)

* **Runtime Baseline** (`/runtime`) — read-only Kubernetes/Helm/GitOps baseline
  (`/operations/runtime/report`); no deploy/sync/apply/install control. Includes the
  Step 55 read-only **Non-production Runtime Smoke** section
  (`/operations/runtime/nonprod-smoke/readiness`, `/preflight`, `/report`); framework
  ready, BLOCKED when no safe non-production cluster exists; no deploy / helm-install /
  cleanup / kubectl-exec / ArgoCD-sync control, no namespace/secret input, no
  production-ready toggle.
* **Identity Posture** (`/identity`) — read-only Step 52 identity foundation
  (`/operations/identity/report`); production identity NOT enabled, no OIDC
  login/connect/configure button, no production auth toggle, no role-mapping
  editor, no break-glass button, no token/secret display.
* **Secret Posture** (`/secrets`) — read-only Step 53 secret management foundation
  (`/operations/secrets/report`); production secret management NOT configured, no
  reveal/copy/upload/rotate/configure control, no secret value displayed.
* **Security / Supply Chain** (`/security`) — read-only Step 54.1 application
  security & supply chain baseline (`/operations/security/report`); modeled, NOT
  enforced for production, no run-scan/upload-source/connect-scanner/configure-
  scanner/create-PR/push-image/production-gate control. Includes the Step 54.2
  read-only **Local Scan Toolchain Baseline** section
  (`/operations/security/scans/status`); local-only, no run-scan control, scan
  status degrades to not_run when no local scan has run in this environment. Also
  includes the Step 54.3 read-only **SBOM / Image Digest / Container Security**
  section (`/operations/security/sbom/status`, `/operations/security/images/readiness`);
  no generate-SBOM / pull / scan / login / push / sign / attest control. Also
  includes the Step 54.4 read-only **Threat Model / Release Risk / Evidence**
  section (`/operations/security/step54/status`, `/release-risk/summary`,
  `/evidence/package`, `/readiness/report`); a release risk summary is NOT an
  approval; no generate-evidence / approve-release / enable-gate / deploy /
  create-PR / sync-ArgoCD control. Runtime evidence/risk/readiness artifacts are
  never committed (status not_run here).

All pages are GET-only and present in the React app and the static fallback.
