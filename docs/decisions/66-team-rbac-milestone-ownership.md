# Decision: Team RBAC Milestone Ownership

> **Decision record only. No runtime code changed. No backend changed. No frontend implementation
> changed. No API/database/workflow change. No production/external action.**

Decision status: **APPROVED_BY_PRODUCT_OWNER**

## Context

Step 66ALIGN.1-CC (Claude Code's project-completion alignment analysis) and Step 66ALIGN.1
(Claude Design's `production-trust-and-adoption-ux.md`) reached different conclusions on which
milestone owns Team RBAC-related work: Claude Code's `milestone-dependency-plan.md` placed
product-level role/permission UI at M3 (AI Team Orchestration / Multi-role Control); Claude
Design's report tied "real identity/session/CSRF" to M6/M7 (Production Readiness / Rollout). The
Step 66M0-SOT-RECONCILE-P v2 cross-partner consensus matrix flagged this as the one
`REQUIRES_PO_DECISION` item out of 13 cross-partner topics (0 CONFLICT, 2 MINOR_DIFFERENCE
elsewhere). This record resolves it.

## Decision

```text
M3 owns:
- product-level team/project roles
- role permissions
- task assignment
- team/project visibility
- operator controls
- approval/retry/replay/recovery permissions

M6/M7 own:
- production identity provider integration
- authentication
- session security
- role provisioning
- production access review
- rollout onboarding
```

## Rationale

Product authorization (who can see/assign/act on tasks and teams within the product) and
production authentication (how a real identity is established and kept secure at rollout) are
related but distinct concerns, and the former must not be blocked waiting on the latter. Team/
project-level role and permission control is core product functionality needed for the M3 AI Team
Orchestration / Multi-role Control milestone to function at all (task assignment, operator
controls, and approval/retry/replay/recovery permissions are meaningless without some role model).
Production identity provider integration, real authentication, session security hardening, and
formal access review are properly scoped to M6 (Production Readiness / Platform Hardening) and M7
(Production Rollout / Adoption), where the platform's actual production identity/security posture
is established -- not before.

## Effect on prior reports

This decision resolves the ambiguity both `docs/alignment/66-project-completion/claude-code/
milestone-dependency-plan.md` and `docs/design/66-project-completion-experience-alignment/
production-trust-and-adoption-ux.md` (both still on their own unmerged, advisory-only alignment
branches) had left open. Neither alignment branch is merged or modified by this decision; both
remain available as advisory input for a future Step 66ALIGN.2 consolidation, which may now cite
this decision record directly rather than re-litigating the ambiguity.

## Statement

Decision record only. No runtime code changed. No backend changed. No frontend implementation
changed. No API/database/workflow change. No new endpoint. No new route. No production/external
action. No M3 or M6/M7 implementation authorized by this record -- it resolves milestone ownership
only, not implementation scheduling or authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
