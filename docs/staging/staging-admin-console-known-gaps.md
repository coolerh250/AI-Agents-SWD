# Staging Admin Console Known Gaps (Step 64C)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Known gaps / pending items for the staging Admin Console exposure (Step 64C) on staging target
host `10.0.1.32` (`agentai-swd-stage`). None is a production readiness sign-off; **Claude Code
does not decide production readiness.**

## Operator workstation confirmation — resolved (confirmed)
The port-forward mechanism was validated end-to-end from a client host, and the **operator has
confirmed** they can open the read-only Admin Console page from their own workstation via
`http://localhost:18000/admin`. Overall marker is now full **PASS**. Alternatives (own key /
existing SSH access) remain documented in
[staging-operator-access-validation.md](staging-operator-access-validation.md).

## Per-page endpoints not all individually probed
13 read-only `/operations/*` endpoints were probed (all 200). Some pages (projects, task-graph,
design-review, workspace, mini-delivery, delivery-package, regression, cost-llm, incidents,
multi-project delivery) render the SPA shell but their specific backing endpoints were not each
probed in Step 64C. Deeper per-page data validation is deferred to Step 64D/64E.

## Empty data states
The staging DB is freshly bootstrapped, so data pages show empty states (no projects / work
items / candidates). **Update (Step 64D):** the demo seed + workflow populated Projects /
Work Items / Agent Executions / QA / Audit / Metrics (project=1, work items=1, agent
executions=10, workflows=2). Release Governance remains empty (delivery dispatch gated). See
[staging-demo-admin-console-evidence.md](staging-demo-admin-console-evidence.md).

## Transport / secrets
- **HTTP only** (no TLS) — acceptable for the first staging demo; TLS is a future option.
- Vault runs in **dev mode** with `SECRET_PROVIDER=mock-vault` — not a production secret store.
- `github_has_token=true` is a sandbox/mock token; live GitHub write is disabled.

## Evidence artifacts
- No screenshots were committed (to avoid any accidental secret capture). Page reachability is
  evidenced by host-local `curl` HTTP codes recorded in
  [staging-admin-console-page-inventory.md](staging-admin-console-page-inventory.md). A
  gitignored `runtime_evidence/staging/admin-console/` path is reserved for optional local,
  non-secret screenshots if desired later.

## Not done in this stage
- No demo workflow executed (Step 64D).
- No operator mutation performed (operator actions disabled in staging).
- No public port exposure; no production action / secret / external write.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
