# Security / Governance / Runtime Gates Per Milestone — Step 66ALIGN.1-CC

> **Analysis and documentation only. No implementation, merge, deployment, or runtime modification
> performed by this document.**

This document applies the nine gates from `.agents/skills/stage-gate/SKILL.md` and the hard
restrictions in `.agents/skills/security-governance/SKILL.md` to each canonical milestone,
identifying what must be true before that milestone can be considered complete.

## M0 — Source of Truth and Runtime Reconciliation

```text
Security/Governance Gate: no new surface -- verify secret scan stays at the current baseline
  (critical=0, high=0, informational=100) and no internal IP/SSH-alias/hostname is newly exposed.
Runtime/Deployment: confirm main == test-runtime-deployed-commit's build output (already true);
  no staging runtime to reconcile (intentionally decommissioned).
Product Owner Validation Gate: not required for M0 -- it is a housekeeping/documentation milestone.
```

## M1 — Core Human–Agent Interaction Loop (66C.4 remainder)

```text
Architecture Direction Gate: Claude Code must confirm the reminder/expiry scheduler mechanism
  (poller vs. Redis-Streams delayed-message) before Codex implementation begins, and must confirm
  it introduces no new task-status value (clarification_expired already exists).
Security/Governance Gate: no workflow dispatch/resume without explicit authorization (the
  scheduler firing a status transition is not itself a "workflow dispatch" in the sense this
  project restricts, but any stage building it must state explicitly whether it triggers agent
  work -- if it does, that is a workflow-dispatch-adjacent action requiring its own authorization
  gate); no external notification send without the same explicit-authorization pattern already
  used for Discord in this project.
Runtime/Deployment: test-runtime-only, same disposable-clone-build pattern already established;
  no production action.
Product Owner Validation Gate: required -- the same VISIBLE/NOT_VISIBLE/PARTIAL_WITH_GAPS pattern
  used for FE.1C/FE.1D stages should be reused for the Reminder/Expiry page.
```

## M2 — Delivery and Acceptance Loop (66D)

```text
Architecture Direction Gate: the delivery/acceptance data model must be reviewed and frozen by
  Claude Code BEFORE Codex builds any UI against it (see the explicit answer to "should the
  delivery data model/API be frozen before UI design" in alignment-statement.md).
Security/Governance Gate: the 6-action acceptance gate (Accept/Reject/Request-Changes/Re-run-QA/
  Escalate/Archive) must enforce server-side RBAC using the existing TASK_ROLES model -- no
  client-side-only gating of who may Accept/Reject (this is an explicit, non-negotiable rule in
  security-governance/SKILL.md item 5).
Runtime/Deployment: still test-runtime-only. No production deployment authorized by reaching M2.
Product Owner Validation Gate: required per new page/flow, following the established pattern.
Merge/Deployment Gates: unchanged process -- Product Owner authorizes each merge and each
  deployment individually; no blanket authorization.
```

## M3 — AI Team Orchestration and Multi-role Control (66E, Team RBAC)

```text
Security/Governance Gate: Team RBAC UI must be a presentation of server-side-enforced roles, never
  a client-side-only permissions display; the fixed-team routing logic (66E) must not introduce any
  new external-action or production-action capability without its own explicit gate.
Runtime/Deployment: test-runtime-only.
Product Owner Validation Gate: required.
```

## M4 — Notifications, Action Center and Channels (66F, 66G)

```text
Security/Governance Gate: this is the highest-risk milestone from a security-governance
  perspective before M6, because it is the first milestone that necessarily involves REAL external
  sends (Slack/Telegram messages, notification delivery) rather than read-only/internal state.
  Every external-send capability must ship OFF by default (matching the existing Discord pattern:
  github_external_write_enabled=false, discord_external_send_enabled=false style flags) and require
  explicit, scoped Product Owner authorization before any real external message is sent -- not just
  before the feature is merged, but before each authorized "go live" moment for that channel.
Runtime/Deployment: test-runtime-only until explicitly authorized otherwise; if any real external
  send is authorized for testing, it must be to a controlled test channel/recipient, exactly
  following this project's already-established "real_github_test_enabled"-style pattern (a
  narrowly-scoped, explicitly authorized real-integration test, not a silent default-on).
Product Owner Validation Gate: required, and should explicitly re-confirm external-send posture
  each time, not assume a prior "off" default still holds after new channel code lands.
```

## M5 — Controlled End-to-End Pilot (66H)

```text
Security/Governance Gate: this is a full-loop exercise with a real operator -- it must run with
  production_executed_true_count monitored continuously (before/during/after), exactly like every
  deployment stage in this project already does, and any anomaly must halt the pilot rather than be
  logged and continued past.
Runtime/Deployment: test-runtime-only (or, if a new pilot-specific environment is stood up, it must
  carry the same non-production posture and safety statements as every environment this project has
  used so far).
Product Owner Validation Gate: this is the highest-stakes Product Owner validation before M6 --
  recommend it be structured as a multi-session validation (not a single checklist pass) given the
  pilot spans the full M1-M4 loop.
```

## M6 — Production Readiness and Platform Hardening

```text
Architecture Direction Gate: a real (not "kind") Kubernetes cluster, real ArgoCD instance, and real
  secret store must be designed and reviewed BEFORE any production-facing manifest is applied --
  the Stage 60-63A dry-run models (deployment-authorization-boundary-model.yaml, production-
  credential-readiness-model.yaml, production-gitops-readiness-model.yaml) are a strong starting
  point and should be reused/extended rather than re-invented, but they were explicitly built and
  validated in a non-production sandbox and must be re-validated against the real substrate before
  being trusted for it.
Security/Governance Gate: THIS is where allowArgoCDProductionSync / allowKubernetesProductionMutation
  / allow_production_failover-style flags move from documented-false to a real, deliberate,
  Product-Owner-authorized true for the first time in this project's history. Every one of the
  Backup/DR gaps (encryption_no_key, storage_not_off_host, schedule_dry_run_only,
  migration_down_gaps) must be closed here, not carried forward again. Postgres must move off
  `trust` auth. Vault must move off ephemeral dev mode.
Runtime/Deployment: this is the first milestone where a genuinely new, separate production
  environment is provisioned. It must not reuse the test runtime's host/credentials/data.
Product Owner Validation Gate + Merge/Deployment Gates: production authorization is categorically
  different from every authorization this project has issued so far (test-runtime deployment
  authorizations) -- it requires its own explicit, named "production" authorization, per
  security-governance/SKILL.md's own framing ("An authorization for one action does not imply
  authorization for another").
```

## M7 — Production Rollout and Adoption

```text
Security/Governance Gate: production_executed_true_count is EXPECTED to become nonzero here for
  the first time in the project's history -- this is the one milestone where that is the intended,
  authorized outcome rather than a violation. Every prior stage's "production_executed_true_count
  remains 0" statement was correctly scoped to say "not yet", not "never".
Runtime/Deployment: production environment, real traffic, real operator adoption.
Product Owner Validation Gate: final go-live decision, categorically the Product Owner's alone
  (per role-responsibility-matrix.md's cross-cutting rule -- no partner may substitute for or
  pre-decide this verdict).
```

## Statement

Analysis and documentation only. No implementation, merge, deployment, or runtime modification
performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
