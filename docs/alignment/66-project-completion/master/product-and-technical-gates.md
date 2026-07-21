# Product and Technical Gates — Project Completion Master Plan

> **Consolidated planning document only. No runtime code, no backend, no API, no database, no
> workflow, no new endpoint/route, no merge of any alignment branch, no deployment performed by
> this document.**

Applies the nine gates from `.agents/skills/stage-gate/SKILL.md` and the hard restrictions in
`.agents/skills/security-governance/SKILL.md` to each milestone-level product/technical gate,
consolidating Claude Code's `security-runtime-gates.md`, Claude Design's per-milestone Product Owner
validation checklists, and Codex's per-milestone test-strategy/risk entries.

## Core loop gate (M1 exit)

```text
Architecture Direction Gate: Claude Code confirms the reminder/expiry scheduler mechanism (poller
  vs. Redis-Streams delayed message) before Codex implementation begins; confirms no new task-
  status value is needed (clarification_expired already exists).
Security/Governance Gate: any real agent-work trigger from the scheduler requires its own explicit
  workflow-dispatch-adjacent authorization; no external notification send without the same
  explicit-authorization pattern already used for Discord.
Product Owner Validation Gate: VISIBLE/NOT_VISIBLE/PARTIAL_WITH_GAPS pattern, same as FE.1C/FE.1D,
  applied to a real /clarification-reminders page and the full assign/converse/clarify/wait loop.
Pass condition: a human can assign, converse, clarify/answer, and see the 24h/72h reminder/expiry
  transition for real, with no implied auto-dispatch/resume anywhere in the flow.
```

## Delivery gate (M2 exit)

```text
Architecture Direction Gate: the delivery/acceptance data model and 6-action endpoint contract
  (Step 66D-ARCH) must be reviewed and frozen by Claude Code BEFORE Codex builds any UI against it
  — this is the single highest-severity gate in the entire Master Plan (unanimous across all three
  partners).
Security/Governance Gate: the 6-action gate (Accept/Reject/Request-Changes/Re-run-QA/Escalate/
  Archive) must enforce server-side RBAC using the existing TASK_ROLES model — no client-side-only
  gating (non-negotiable, security-governance/SKILL.md item 5).
Product Owner Validation Gate: required per new page/flow; must confirm Request-Changes vs.
  Re-run-QA reads as unambiguously different decisions.
Merge/Deployment Gates: unchanged — Product Owner authorizes each merge and each deployment
  individually; no blanket authorization inherited from M1.
Pass condition: a reviewer can see, open (without raw JSON), and decide on a real delivery record
  with an unambiguous, server-enforced, audited consequence.
```

## Team control gate (M3 exit)

```text
Security/Governance Gate: Team RBAC UI must present server-enforced roles only, never a
  client-side-only permissions display; M3 agent activity must remain read-only until its own
  control contract (pause/reassign/retry) is complete; the fixed-team routing logic must not
  introduce any new external-action or production-action capability without its own explicit gate.
Product Owner Validation Gate: required; must independently verify server-side enforcement, not
  just that a control is hidden/shown correctly in the UI.
Pass condition: a multi-role user sees real, server-enforced cross-task team activity and role
  permissions matching the locked 6-role matrix, with server-side enforcement independently
  verified.
```

## Notification/channel gate (M4 exit)

```text
Security/Governance Gate: the highest-risk milestone before M6 — the first milestone necessarily
  involving REAL external sends. Every external-send capability ships OFF by default; explicit,
  scoped Product Owner authorization required before each channel's first real send, not just
  before the feature is merged.
Product Owner Validation Gate: must explicitly re-confirm external-send posture is OFF each time
  new channel code lands — never assumed to still hold from a prior stage.
Pass condition: a real, non-fabricated notification feed and action queue exist; any channel shown
  "connected" is genuinely connected under an explicit, scoped authorization.
```

## Pilot gate (M5 exit)

```text
Security/Governance Gate: production_executed_true_count monitored continuously before/during/
  after the pilot run; any anomaly halts the pilot rather than being logged and continued past.
Product Owner Validation Gate: the highest-stakes validation before M6 — structured as a
  multi-session validation, not a single checklist pass, given the pilot spans the full M1-M4 loop.
Pass condition: a real operator completes the full assign->execute->clarify->deliver->accept->
  notify loop in a controlled, non-production environment with no unresolved P0/P1 gap.
```

## Production readiness gate (M6 exit)

```text
Architecture Direction Gate: a real (not "kind") Kubernetes cluster, real ArgoCD instance, and real
  secret store must be designed and reviewed before any production-facing manifest is applied;
  the Stage 60-63A dry-run models are a starting point, re-validated against the real substrate,
  not re-invented, and not treated as already-sufficient.
Security/Governance Gate: THIS is where allowArgoCDProductionSync/allowKubernetesProductionMutation
  -style flags move from documented-false to a real, deliberate, Product-Owner-authorized true for
  the first time in this project's history. Every Backup/DR gap closed here, not carried forward.
  Postgres moved off `trust`. Vault moved off ephemeral dev mode.
Product Owner Validation Gate + Merge/Deployment Gates: production authorization is categorically
  different from every test-runtime authorization issued so far; requires its own explicit, named
  "production" authorization.
Pass condition: all nine production-ready conditions in project-definition-of-done.md are
  simultaneously true — no partial "mostly ready" declaration permitted.
```

## Adoption gate (M7 exit)

```text
Security/Governance Gate: production_executed_true_count is EXPECTED to become nonzero here for
  the first time — the one milestone where that is the intended, authorized outcome. Every
  external-send capability individually authorized for production use.
Product Owner Validation Gate: the final go-live decision, categorically the Product Owner's alone
  — no partner may substitute for or pre-decide this verdict.
Pass condition: real production traffic flowing under real user adoption, every rollout decision
  explicitly Product-Owner-authorized.
```

## Standing rule across every gate

No gate may be marked passed on the basis of: a dry-run rehearsal, seeded/demo evidence, a
placeholder page (however well-labeled), or a test-runtime deployment record alone. Every gate
requires the specific evidence named above, in addition to (not instead of) passing verifiers/
tests.

## Statement

Consolidated planning document only. No runtime code, no backend, no API, no database, no workflow,
no new endpoint/route, no merge of any alignment branch, no deployment performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
