# Mini Project Delivery Path — Roadmap

This is the roadmap from the project-planning foundation to an end-to-end mini
project delivery pilot. Each step builds on the previous one.

| Step | Title | Status | What it adds |
|---|---|---|---|
| 43 | Project Planner & Task Graph | **closed** | brief, user stories, acceptance criteria, milestones, work-item graph, dependency validation, planning-only orchestration + operations visibility |
| 44 | Agent Discussion & Design Review Protocol | **closed** | structured multi-role discussion + design review + gates + go/no-go on a project graph, review-only, before any code |
| 45 | Real Repo Workspace Operator v1 | **closed** | a controlled, allowlisted workspace operator that generates a FastAPI Todo project, runs pytest + static checks, and produces diff / artifacts / work-item execution links — no repo write, no PR, no deploy, no real LLM |
| 46 | Mini Project Delivery Pilot | **closed** | chains plan → design review → controlled workspace → test/static evidence → acceptance evaluation → QA summary → safety summary → mini delivery pilot report, controlled-only |
| 47 | Delivery Package & Acceptance Gate | **closed** | assemble a formal delivery package (14 sections + artifacts), gate it (18 acceptance checks), produce handoff summaries + readiness snapshot + operator-review placeholder; `ready_for_operator_review`, human acceptance pending, controlled-only |
| 48 | Admin Console v0 (read-only) | **closed** | read-only browser UI (`/admin`) + 6 aggregate `/operations/admin-console/*` endpoints over projects / reviews / workspaces / pilots / delivery packages / safety / regression / incidents / LLM; no write API, no operator actions, secret/CoT redaction |
| 49 | Backup / DR Gap Closure | **done (this stage)** | close the four backup/DR gaps (encryption_no_key, storage_not_off_host, schedule_dry_run_only, migration_down_gaps) at a controlled test baseline → readiness `passed_with_non_production_limitations`; no production backup/restore, no real cloud, no real schedule |
| 50 | Admin Console v1 (operator actions) | **done (this stage)** | controlled operator actions (accept / reject / request-changes / note / allowlisted verification rerun) gated by test-local auth + RBAC + CSRF + policy + confirmation + idempotency + audit; high-risk actions disabled; acceptance is human-review only (no deploy/PR/prod) |
| 51 | Kubernetes / Helm / ArgoCD Runtime Baseline | **closed — static baseline validated, not deployed** (51.1–51.4) | container runtime + GitOps deployment baseline; validated, NOT deployed (no cluster, no Helm install, no ArgoCD sync, no production readiness) |
| 51.1 | Runtime Inventory & Helm Foundation | **done (this stage)** | evidence-backed runtime inventory + dependency matrix + component catalog; values-driven Helm foundation chart (generic Deployment/Service/ConfigMap/ServiceAccount) across dev/test/staging-placeholder/prod-placeholder; fail-closed non-deployable production placeholder; lint + render verified; no cluster, no deploy |
| 51.2A | Workload Security & RBAC Safety Baseline | **done (this stage)** | restricted SecurityContext baseline (runAsNonRoot, RuntimeDefault seccomp, no privesc, drop ALL, read-only root, size-limited emptyDir writable paths), ServiceAccount token automount off, RBAC safety (no Role/ClusterRole, no Kubernetes API access); static manifest baseline, no cluster |
| 51.2B | NetworkPolicy & Service Connectivity Baseline | **done (this stage)** | revalidated dependency matrix (75 edges; 49 internal + 26 observability-deferred), connectivity catalog, default-deny ingress/egress, scoped DNS, per-target ingress / per-source egress for all 49 internal edges, Postgres/Redis isolation, external egress disabled, fail-closed; no cluster |
| 51.2C1 | Storage Ownership & Data Lifecycle Baseline | **done (this stage)** | evidence-backed storage consumer inventory + data lifecycle; typed store ownership; generated RWO PVCs for in-cluster Postgres/Redis in dev/test only (Deployment volume integration); workspace ephemeral per-pod (no RWX); reports/audit exports unresolved; backup separate + deferred; fail-closed (no StorageClass/PV, no hostPath/NFS, no real storage class/claim); no cluster |
| 51.2C2 | Migration, Backup & Restore Job Baseline | **done (this stage)** | evidence-backed batch operation inventory + risk; fixed shell-free command catalog; controlled migration Job (advisory lock, forward-only), disabled+suspended backup CronJob (Forbid, secretKeyRef-only, disabled target), disabled restore Job scaffold (isolated `aiagents_restore_drill_` target, source≠target); token-off batch ServiceAccounts (no RBAC); minimal DB-only NetworkPolicy; fail-closed staging/production; templates validated, NOT executed; no cluster |
| 51.3 | ArgoCD & Environment GitOps Baseline | **done (this stage)** | ArgoCD AppProject (restricted source/destinations, no cluster-scoped/Secret) + dev/test/staging/production Application manifests (values-pinned) + non-production app-of-apps (dev+test only) + environment catalog + policy summaries; auto-sync/prune/selfHeal/hooks/finalizers/credentials all absent; production disabled placeholder excluded from app-of-apps; validated, NOT applied (no ArgoCD, no sync, no cluster) |
| 51.4 | Runtime Visibility & Integrated Verification | **done (this stage)** | read-only runtime baseline SDK + 12 GET `/operations/runtime/*` endpoints + `/operations/safety` Kubernetes/Helm/GitOps fields + Admin Console read-only Runtime Baseline view (no deploy/sync/apply) + combined Step 51 verification (`KUBERNETES_HELM_ARGOCD_BASELINE_VERIFY`); `runtime_production_ready=false`, `runtime_validated_not_deployed=true`, `production_executed_true_count=0`; no cluster, no sync |
| 52 | Production Identity & OIDC Foundation | **closed — modeled, fail-closed, not enabled** (52.1–52.4) | identity boundary model → OIDC abstraction → session hardening / role mapping → identity visibility + integrated verification; production identity NOT enabled (no real IdP, no production auth, no production login) |
| 52.1 | Identity Inventory & Auth Boundary Model | **done (this stage)** | evidence-backed authentication/session/CSRF/RBAC/operator-action inventories + identity trust boundary model + test-vs-production auth boundary + identity-to-audit mapping + human-acceptance & verification-rerun boundaries + production OIDC prerequisites (unconfigured) + risk register + policy catalog; test-local auth non-production, production auth disabled/fail-closed, platform_admin ≠ infrastructure admin, human acceptance ≠ deployment; no real OIDC, no production auth, no secret committed |
| 52.2 | OIDC Provider Abstraction & Disabled Production Config | **done (this stage)** | model-only OIDC abstraction (`shared/sdk/identity`: provider/config/policy/redaction) + disabled production config + 10 contracts (provider catalog, discovery, JWKS, claim, role-mapping, callback, state/nonce/PKCE, token-validation, safety-policy) + fail-closed loader/validator + 3 verifiers + combined baseline + 15 tests; production OIDC `disabled_unconfigured`, no discovery/JWKS fetch, no callback, no token validation, no real issuer/client ID/secret, unknown user denied, `platform_admin` never auto-granted, token role claim not authoritative; no IdP connection, no production auth, no secret committed |
| 52.3 | Session Hardening & Role Mapping | **done (this stage)** | session hardening catalog + non-destructive cleanup utility (dry-run, never deletes, no raw token; existing schema, no migration) + concurrency/forced-logout/key-rotation models + safe local role mapping engine (`shared/sdk/identity`: role_mapping, session_cleanup, identity_runtime_config) + role-mapping/unknown-user/break-glass/authorization-decision models + audit enrichment plan + 6 verifiers + cleanup verifier + combined baseline + 15 tests (82 cases); unknown user deny, default role none, `platform_admin` explicit-mapping-only, no wildcard groups, no real group IDs, token role claim not authoritative, break-glass disabled, key rotation model-only (production secret store deferred to 53); no real IdP, no production auth, no secret committed, `production_executed=false` |
| 53 | Production Secret Management Foundation | **closed — modeled, fail-closed, not configured** | secret inventory/classification/ownership/usage + reference-only `SecretRef` (no value) + disabled secret-store abstraction (`read_secret_value` raises) + disabled production store config + lifecycle/rotation/access-boundary/audit/redaction models + 4 reference catalogs (all `store=disabled`) + read-only `/operations/secrets/*` (13 GET) + 21 `/operations/safety` secret fields + Admin Console read-only Secret Posture view (no reveal/copy/upload/rotate/configure) + 9 verifiers + combined `SECRET_MANAGEMENT_FOUNDATION_BASELINE_VERIFY` + 23 tests; no real secret store, no secret value, no committed secret, `secrets_production_ready=false`, `production_executed_true_count=0`. Next: Step 54 (Application Security & Supply Chain Baseline), Step 55 (Non-production Kubernetes Runtime Smoke), Step 56 (Real ArgoCD Non-production Manual Sync) — all pending. |
| 52.4 | Identity Visibility & Integrated Verification | **done (this stage — closes Step 52)** | read-only identity posture SDK (`shared/sdk/identity_posture`) + committed anti-drift summary + 13 GET `/operations/identity/*` endpoints + 35 `/operations/safety` identity fields + Admin Console read-only Identity Posture view (no login/connect/configure/toggle/editor/break-glass button) + combined Step 52 verifier (`IDENTITY_FOUNDATION_BASELINE_VERIFY`) + `IDENTITY_OPERATIONS_VISIBILITY_VERIFY`/`ADMIN_CONSOLE_IDENTITY_POSTURE_VERIFY`/`IDENTITY_SAFETY_FIELDS_VERIFY` + 11 tests + full regression; `identity_posture_status=modeled_fail_closed_not_enabled`, `identity_production_ready=false`, OIDC + production auth disabled, `production_executed_true_count=0`; no real IdP, no mutation endpoint/button, no secret committed |

## Current foundation (Steps 43–44)

* Projects, briefs, user stories, acceptance criteria, milestones, work items,
  dependencies, risks, artifacts, graph snapshots (Step 43).
* Deterministic FastAPI Todo template + dependency graph validation (Step 43).
* Planning-only orchestration: project-scale requests route to the
  project-planner-agent; the workflow stops at `project_planned` (Step 43).
* Multi-role design review: discussion sessions, deterministic role
  contributions (no chain-of-thought), six reviewers, acceptance coverage,
  seven review gates, and a go/no-go decision; review-only — the workflow stops
  at `design_reviewed` / `design_reviewed_with_findings` / `design_review_blocked`
  (Step 44).
* Operations API for project / work item / dependency / graph / acceptance /
  delivery-readiness + discussion / design-review / findings / gates /
  go-no-go / acceptance-coverage visibility.
* Controlled workspace operator: after a non-blocked design review, the
  orchestrator requests a controlled workspace execution that generates a
  deterministic FastAPI Todo project under an allowlisted root, runs pytest +
  static checks, and records diff / artifacts / work-item execution links;
  controlled-only — the workflow stops at `workspace_tests_passed` /
  `workspace_tests_failed` / `workspace_execution_failed` and never deploys or
  opens a PR (Step 45).
* Mini project delivery pilot: one controlled run chains plan → design review →
  workspace execution → test/static evidence → evidence-based acceptance
  evaluation → QA summary → safety summary → a mini delivery pilot report, with
  pilot-level steps, evidence, and artifact links; controlled-only — no PR, no
  deploy, no real LLM, `production_executed=false` (Step 46).
* Delivery package & acceptance gate: a completed mini pilot is assembled into a
  formal delivery package (14 sections, linked artifacts, acceptance checklist),
  evaluated by an 18-check acceptance gate, and accompanied by business /
  technical / operator handoff summaries plus a delivery readiness snapshot and a
  pending operator-review placeholder. The gate resolves to
  `ready_for_operator_review`; human acceptance stays `pending` and operator
  action endpoints are disabled by default; controlled-only — no PR, no deploy,
  no real LLM, no external delivery, `production_executed=false` (Step 47).

* Admin Console v0: a read-only browser UI served at `/admin` (zero-build static
  fallback + optional React/Vite bundle) backed by six read-only aggregate
  `/operations/admin-console/*` endpoints, surfacing platform safety, projects,
  task graph, design review, workspace execution, mini delivery pilot, delivery
  package + acceptance gate, human acceptance (pending), regression, backup gaps,
  incidents, and LLM/cost. No write API, no operator actions, secret /
  chain-of-thought redaction; `production_executed=false` (Step 48).

* Backup / DR Gap Closure: closes the four long-standing backup/DR gaps at a
  controlled test baseline — test-only encrypted backup + manifest, mock
  off-host transfer with readback verification, dry-run-validated schedule
  specs, dry-run retention, and a complete migration rollback catalog (no
  `unknown`). Backup readiness advances to
  `passed_with_non_production_limitations`. No production backup/restore, no real
  cloud write, no real schedule, no raw key persisted; `production_executed=false`
  (Step 49). See `docs/operations/backup-dr-gap-closure.md`.

* Admin Console v1 Operator Actions: a controlled Operator Console at `/operator`
  with test-local signed-session auth, RBAC (viewer/reviewer/operator/
  platform_admin), CSRF, policy-engine gate, one-time confirmation, idempotency,
  and audit. Enabled actions: add note, request changes, accept, reject, and
  allowlisted verification rerun. Delivery acceptance is a human-review
  acceptance only — it never triggers GitHub / PR / merge / deploy / external
  delivery / production. High-risk actions are disabled-only catalog entries;
  `production_executed=false` (Step 50). See
  `docs/product/admin-console-v1-operator-actions.md`.

## Still out of scope (carry-forward)

* Kubernetes / Helm / ArgoCD runtime baseline (Step 51); production OIDC /
  external IdP integration.
* Work-item dispatch to a real implementing agent.
* Real LLM, real GitHub production write, real deploy, real escalation.
* Real production secret store, real off-host cloud backup target, real
  production backup schedule, real production restore, real pager.
