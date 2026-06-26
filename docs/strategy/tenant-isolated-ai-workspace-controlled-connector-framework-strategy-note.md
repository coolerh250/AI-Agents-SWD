# Tenant-Isolated AI Workspace & Controlled Connector Framework — Strategy Note v1

> **Status: strategy note only.** This is a future design-direction reference. It is
> **not scheduled into the current Roadmap**, it is not an implementation, and it does
> not change any step's scope. The platform is **tenant-ready, not tenant-enabled**.

## 1. Purpose
Record — as a forward-looking design reference — the direction of a tenant-isolated AI
workspace and a controlled connector framework (including future "bring-your-own-repo" /
BYOR-style connectors). This note exists so later design work does not accidentally
harden the platform into a shape that cannot be made tenant-isolated later. It adds no
runtime behaviour.

## 2. Current Decision
- Tenant-isolated workspace and BYOR connectors are a **strategic extension direction**,
  **not a current Roadmap work item**.
- The platform today is **tenant-ready, not tenant-enabled**: models should not be
  written so as to preclude a future tenant boundary, but no tenant boundary is enforced.
- No multi-tenant implementation, no tenant isolation enforcement, and no connector
  runtime are introduced by this note.

## 3. Strategic Concept
A future tenant-isolated workspace would scope projects, work items, dispatch, delivery
packages, audit, secrets, and Admin Console views to a `tenant_id` / `workspace_id` /
`owner_scope` / `isolation_scope`, so multiple owners can use the platform without
sharing data, credentials, or execution context. A Controlled Connector Framework would
let a tenant connect external systems (e.g., their own repository) through a governed,
auditable, approval-gated boundary — never an ungoverned direct integration.

## 4. Why This Matters
Multi-project delivery (Step 57) makes the platform useful for many concurrent projects,
which naturally raises "can different owners / customers use it in isolation?". Designing
project / work-item / delivery / audit / connector / Admin Console models with a latent
scope dimension now keeps that option open at low cost; retrofitting isolation onto a
hard-wired global singleton model later is expensive and error-prone.

## 5. Why Not Now
Tenant isolation and external connectors depend on foundations that are modeled but **not
production-enabled**: production identity / OIDC (Step 52), production secret management
(Step 53), approval + audit governance, and a real tenant boundary. Enabling tenant
isolation or real connectors before those are mature would create a false sense of
isolation and real data-exposure risk. Therefore this stays a strategy note.

## 6. Project Management Position
- **Step 57 remains completed as a multi-project baseline, not multi-tenant.** It must
  not be retroactively reinterpreted or modified into a multi-tenant implementation.
- **Step 58 (Admin Console v2 Operational Metrics) and Step 59 (Sandbox GitHub Draft PR
  Flow) are unchanged** by this note and keep their existing Roadmap scope and order.
- This note introduces no new scheduled work; any tenant-readiness or connector work
  must be scheduled separately, explicitly, later.

## 7. Tenant-ready Design Principles
Future model/design work should avoid hard-wiring an un-tenantable global singleton:
- Prefer models that can later carry `tenant_id` / `workspace_id` / `owner_scope` /
  `isolation_scope` without a destructive rewrite.
- Keep project / work-item / dispatch / delivery-package / audit records attributable to
  an owner scope, even if that scope is a single default scope today.
- Keep secrets, credentials, and connector configuration per-scope-capable.
- Do not assume a single global Admin Console audience; keep views scope-filterable.
- This is a **readiness** principle, not an enablement: no tenant boundary is enforced now.

## 8. Controlled Connector Framework Concept
A future connector framework should begin with **mock connectors, readiness checks,
policy simulation, and an audit model** — exactly the fail-closed, modeled-not-enabled
pattern used by the identity / secret / security baselines. A connector descriptor would
declare capability, required identity, required secret references, approval requirement,
and audit mapping, and would run only in mock / simulation mode until the underlying
foundations are mature.

## 9. Connector Risk Principles
- Real connector **write**, **external send**, **database mutation**, and **storage
  upload** must wait until identity, secret management, approval, audit, and the tenant
  boundary are mature.
- Connectors must be approval-gated, auditable, and scoped; never an ungoverned direct
  integration.
- No connector may bypass the operator-action allowlist, HARD_SAFETY_ACTIONS, or audit
  canonicalization.
- External credentials are never committed; connector secrets follow the Step 53 model.

## 10. Isolation Claim Restrictions
To prevent overstatement, this note explicitly records the following:
- This note does not claim complete isolation is implemented.
- This note does not claim production-grade multi-tenancy is implemented.
- This note does not claim a BYOR connector is implemented.
- The platform is **tenant-ready, not tenant-enabled**; no tenant isolation is enforced
  at runtime today.

## 11. Future Go / No-go Criteria
A future tenant-isolation / connector phase should only be considered **go** when:
- Production identity / OIDC is enabled and verified.
- Production secret management is configured and verified.
- Approval + audit governance covers tenant- and connector-scoped actions.
- A tenant boundary model (scope attribution + access control) is designed and verified.
- A controlled connector framework exists in mock / simulation with passing verifiers.
Otherwise the decision is **no-go** and the work stays modeled, not enabled.

## 12. Future Phase Candidates
Candidate (unscheduled) future phases, in dependency order:
1. Tenant-readiness review of existing models (scope attribution gaps).
2. Tenant boundary model (scope + access control), modeled not enforced.
3. Controlled Connector Framework — mock + readiness + policy simulation + audit.
4. Tenant-scoped Admin Console views (read-only first).
5. Guarded, approval-gated, audited real connector reads (no writes).
6. Tenant isolation enforcement — only after identity/secret/approval maturity.

## 13. Current Roadmap Impact
**None.** This note does not change the Roadmap. Step 58 / Step 59 keep their scope and
order. No step is added, removed, reordered, or marked scheduled because of this note.

## 14. Post-Step-57 Observation
Step 57 delivered real multi-project and work-item dispatch capability, but it is not
multi-tenant isolation. The current implementation should be treated as a multi-project
baseline. A future tenant-readiness review should check whether project, work item,
dispatch, delivery package, audit, and Admin Console models need `tenant_id` /
`workspace_id` / `owner_scope` / `isolation_scope` extension. This review must be
scheduled separately and must not be assumed completed by Step 57.

## 15. Summary
Tenant-isolated workspaces and a controlled connector framework are a recorded **future
design direction**, not current work. The platform is **tenant-ready, not
tenant-enabled**. Step 57 stays a completed multi-project baseline (not multi-tenant), and
Step 58 / Step 59 are unchanged. No runtime, tenant, or connector behaviour is added;
nothing here is production-enabled; `production_executed` stays false. Claude Code does
not decide Production readiness.
