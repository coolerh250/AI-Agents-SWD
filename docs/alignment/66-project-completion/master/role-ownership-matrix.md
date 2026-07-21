# Role Ownership Matrix — Project Completion Master Plan

> **Consolidated planning document only. No runtime code, no backend, no API, no database, no
> workflow, no new endpoint/route, no merge of any alignment branch, no deployment performed by
> this document.**

Consolidates `docs/process/role-responsibility-matrix.md` with the milestone-specific ownership
implied by all three Step 66ALIGN.1 reports, plus the Team RBAC decision
(`docs/decisions/66-team-rbac-milestone-ownership.md`).

## Roles

```text
Product Owner (Zachary) — Owns product direction and priority. Owns final validation of every
  stage (VISIBLE/NOT_VISIBLE/PARTIAL_WITH_GAPS or PASS/PASS_WITH_GAPS/FAIL). No other role may
  substitute for or pre-decide this verdict. Sole authority for merge, deployment, and production
  authorization.
ChatGPT Project Architect / PM Coordinator — Translates Product Owner direction into stage specs;
  writes the prompts executed by Claude Code, Codex, and Claude Design; reviews completion reports;
  maps known gaps to future stages. Does not decide final product acceptance.
Claude Code — Lead Engineer / Architecture Owner. Owns architecture, backend, API, database,
  integration, safety/governance/deployment posture, and every API contract Codex implements
  against. Reviews Codex's frontend PRs. Integrates, tests, deploys to test runtime. Cannot decide
  product acceptance — reports technical PASS/PASS_WITH_GAPS/FAIL only.
Claude Design — UI/UX Designer. Owns information architecture, wireframes, user flows, component
  specs, microcopy. Does not modify runtime code, decide backend behavior, RBAC, production safety,
  or deployment.
Codex — Frontend Engineer. Owns Admin Console frontend implementation (React components, routes,
  API clients, frontend tests) only when explicitly authorized for that specific stage. Does not
  modify backend, database, workflow, policy, or infrastructure unless explicitly authorized by
  both Claude Code and the Product Owner.
GitHub — Hosting/version-control substrate. Not a decision-making role; branch/PR state is
  discussion material until merged to main or explicitly cited as accepted (source-of-truth-
  policy.md).
Admin Console — The product surface itself (frontend application). Not a decision-making role;
  the object all other roles act upon/through.
Operator — Product RBAC role (see `shared/sdk/tasks/rbac.py`), distinct from any of the
  above development-team roles. Uses the shipped product; does not have merge/deploy/production
  authorization.
Admin — Product RBAC role. Highest in-product privilege tier for platform/settings/RBAC management
  within the product itself; still subordinate to the Product Owner's authorization authority over
  merge/deploy/production.
Member — Product RBAC role. Standard in-product user; assigns/works tasks, reviews deliveries per
  the 6-role matrix's scoping.
```

**Important distinction restated from `docs/process/role-responsibility-matrix.md`:** Claude
Design and Codex are members of this project's *development team* — they are not Agents inside the
AI Agent Team Work product itself, and "Agent Operator" (a product RBAC role) must never be
confused with either of them.

## Authority matrix

| Milestone activity | Design authority | Technical implementation owner | Review owner | PO validation owner | Merge authorization owner | Deployment authorization owner | Production approval owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M0 reconciliation | — | Claude Code | Claude Code (self-certifies via context receipt) | N/A (housekeeping) | Product Owner | N/A | N/A |
| M1 (66C.4) | Claude Design (decision-request UX, participates only if new UX states require clarification) | Claude Code (primary — scheduler, reminder/expiry transitions, controlled resume, backend/API/DB/workflow, audit/safety, notification production, integration review, preview deploy/runtime validation) + Codex (explicitly authorized frontend slice only) | Claude Code | Product Owner | Product Owner | Product Owner | N/A |
| M2 (66D) | Claude Design (Delivery UX, gated on contract) | Claude Code (66D-ARCH contract) + Codex (implementation) | Claude Code | Product Owner | Product Owner | Product Owner | N/A |
| M3 (66E, Team RBAC) | Claude Design (team visibility model) | Claude Code (RBAC/assignment contract) + Codex (implementation) | Claude Code | Product Owner | Product Owner | Product Owner | N/A |
| M4 (66F/66G) | Claude Design (Action/Notification Center UX) | Claude Code (unified action-item contract, channel gateways) + Codex (implementation) | Claude Code | Product Owner | Product Owner | Product Owner | Product Owner (per-channel external-send) |
| M5 (66H pilot) | Claude Design (guided checklist UX) | Claude Code (pilot safety architecture) + Codex (implementation) | Claude Code | Product Owner (multi-session) | Product Owner | Product Owner | N/A (non-production) |
| M6 (production hardening) | Claude Design (readiness/trust UX) | Claude Code (real substrate, security hardening) + Codex (implementation) | Claude Code | Product Owner (named "production" authorization) | Product Owner | Product Owner | Product Owner (first-ever) |
| M7 (rollout/adoption) | Claude Design (onboarding/trust UX) | Claude Code (rollout architecture) + Codex (implementation) | Claude Code | Product Owner (final go-live) | Product Owner | Product Owner | Product Owner (sole, per cross-cutting rule) |

## Step 66C.4 ownership (canonical, corrected in Step 66ALIGN.2-R1)

```text
Claude Code owns: the reminder scheduler, reminder and expiry state transitions, controlled
  resume, any backend/API/DB/workflow change, audit and safety enforcement, notification event
  production, integration review, and preview deployment/runtime validation. Claude Code is the
  primary implementation owner of Step 66C.4 as a whole.

Codex owns only: explicitly authorized frontend slice(s), user-visible reminder/expiry/waiting
  states, frontend interaction changes built against Claude Code's frozen contract, and frontend
  tests. Codex does not own or implement Step 66C.4's backend/scheduler/workflow behavior.

Claude Design participates only if new UX states or decision surfaces require design
  clarification beyond what core-loop-experience-definition.md already defines.

Canonical stage sequence (exact future stage names may be refined during 66C.4-P, but this
  ownership boundary is binding): 66C.4-P (Claude Code planning) -> 66C.4-BE (Claude Code backend/
  workflow implementation) -> 66C.4-BE-R (Claude Code technical review/gate) -> 66C.4-FE (Codex
  frontend slice, only if explicitly authorized) -> 66C.4-VP (test-runtime preview) -> 66C.4-POV
  (Product Owner validation) -> 66C.4-MD (merge/deploy merged main).
```

## Team RBAC milestone ownership (canonical, per docs/decisions/66-team-rbac-milestone-ownership.md)

```text
M3 owns: product-level team/project roles, role permissions, task assignment permissions,
  team/project visibility, operator controls, approval permissions, retry/replay/recovery
  permissions.

M6/M7 own: production identity provider integration, authentication, session security, role
  provisioning, production access review, rollout onboarding.
```

This is now a settled, non-unresolved decision — it must not be re-flagged as an open cross-partner
question in any future alignment stage (this was the sole `REQUIRES_PO_DECISION` item from Step
66M0-SOT-RECONCILE-P v2's consensus matrix, now resolved).

## Cross-cutting rule (restated verbatim from role-responsibility-matrix.md)

Claude Code, Codex, and Claude Design may each report a technical outcome (implementation PASS,
design ready, frontend build pass) but **none of them decides final product acceptance**. Only the
Product Owner gives that verdict.

## Statement

Consolidated planning document only. No runtime code, no backend, no API, no database, no workflow,
no new endpoint/route, no merge of any alignment branch, no deployment performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
