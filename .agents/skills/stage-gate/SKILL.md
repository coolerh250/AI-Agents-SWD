# Skill: Stage Gate

> **Process documentation only. No backend/frontend runtime change. No production action.**

Owner: all partners. This skill defines the nine gates every stage in this project passes through
(not every stage exercises every gate — a design-only review stage stops at the Design Review Gate;
a docs-only governance stage like this one stops at the Security/Governance Gate). Each gate names
who owns it, what evidence it requires, how it is scored, and who may or may not approve it.

## The nine gates

### 1. Shared Context Sync Gate

- **Owner:** whichever partner is executing the stage.
- **Required input:** latest `main`, `source/progress.md`, relevant shared docs, related PRs/branches.
- **Required evidence:** a completed Shared Context Preflight / context receipt
  (`docs/stages/context-receipt-template.md`).
- **Pass criteria:** PASS if synced and reviewed with no unresolved conflict; PASS_WITH_GAPS if a
  minor gap is found and documented; FAIL if the partner proceeded without syncing or ignored a
  conflict.
- **Who can approve:** the executing partner self-certifies by producing the context receipt; no
  external approval needed for this gate alone.
- **Who cannot approve:** nobody may skip producing the receipt.

### 2. Architecture Direction Gate

- **Owner:** Claude Code (Lead Engineer / Architecture Owner).
- **Required input:** the stage's design brief or proposed direction, existing contracts, runtime
  reality (verified against actual code, not assumed).
- **Required evidence:** an architecture review doc under `docs/design/<stage>/` or
  `docs/contracts/<stage>/` stating scope, risks, and required boundaries.
- **Pass criteria:** PASS if no runtime/backend/API contradiction found; PASS_WITH_GAPS if minor,
  non-blocking gaps are documented; FAIL if the direction requires backend/API/workflow change not
  yet authorized, or misrepresents current capability.
- **Who can approve:** Claude Code.
- **Who cannot approve:** Claude Design or Codex may not self-approve their own architecture
  soundness; Product Owner may override direction but does not substitute for the technical review.

### 3. Design Review Gate

- **Owner:** Claude Design produces; Claude Code reviews.
- **Required input:** design brief, wireframes/specs, Product Owner direction it is built from.
- **Required evidence:** design docs under `docs/design/<stage>/` plus Claude Code's architecture
  review of them.
- **Pass criteria:** PASS if the design is implementable within existing contracts/data and violates
  none of `security-governance` or `design-collaboration` skill rules; PASS_WITH_GAPS if open
  questions are explicitly flagged for the Product Owner; FAIL if it implies unauthorized backend/
  API/workflow behavior.
- **Who can approve:** Claude Code (technical readiness); Product Owner (direction acceptance).
- **Who cannot approve:** Codex may not authorize its own implementation from a design that hasn't
  passed this gate.

### 4. Implementation Efficiency Gate

- **Owner:** Codex (or whichever partner implements) produces; Claude Code reviews.
- **Required input:** an authorized contract/boundary doc, the design handoff.
- **Required evidence:** implementation report, test results, build result under
  `docs/frontend/<stage>/` and `docs/test/`.
- **Pass criteria:** PASS if implementation matches the contract/boundary with no scope creep and
  tests/build pass; PASS_WITH_GAPS if minor, disclosed gaps remain; FAIL if scope was exceeded,
  forbidden paths were touched, or tests/build fail.
- **Who can approve:** Claude Code (technical PASS/PASS_WITH_GAPS/FAIL only).
- **Who cannot approve:** Codex cannot self-certify its own PR as final; Product Owner acceptance is
  a separate, later gate.

### 5. Security / Governance Gate

- **Owner:** Claude Code.
- **Required input:** the stage's full diff/scope, `.agents/skills/security-governance/SKILL.md`.
- **Required evidence:** secret scan result, forbidden-path check, safety-field statement
  (`production_executed_true_count`, workflow dispatch/resume, external action all as expected).
- **Pass criteria:** PASS if secret scan is clean (or matches an established, already-accepted
  baseline) and no forbidden capability was claimed or exercised; FAIL otherwise — this gate has no
  PASS_WITH_GAPS state, since security findings are binary (found or not found).
- **Who can approve:** Claude Code.
- **Who cannot approve:** no partner may waive a security finding; only the Product Owner may accept
  a documented, non-blocking informational finding as a known baseline.

### 6. Product Owner Validation Gate

- **Owner:** Product Owner (Zachary) only.
- **Required input:** a working, deployed-to-test-runtime feature or a reviewed document/decision to
  validate.
- **Required evidence:** an operator UI-validation record or explicit decision record under
  `docs/decisions/` per `docs/process/operator-validation-standard.md`.
- **Pass criteria:** `VISIBLE` / `NOT_VISIBLE` / `PARTIAL_WITH_GAPS` (UI validation) or a recorded
  Product Owner decision (design/direction acceptance).
- **Who can approve:** Product Owner only.
- **Who cannot approve:** Claude Code, Claude Design, and Codex may report technical readiness but
  **none of them may substitute for or pre-decide this verdict** — see
  `docs/process/role-responsibility-matrix.md` "Cross-cutting rule."

### 7. Merge Gate

- **Owner:** Product Owner authorizes; Claude Code executes.
- **Required input:** explicit Product Owner merge authorization naming the exact branch/target.
- **Required evidence:** the authorization quote in the merge-record doc, pre-merge checklist,
  post-merge verification.
- **Pass criteria:** PASS if merged exactly as authorized with all post-merge checks passing; FAIL if
  merged without authorization, or if merged to an unauthorized target.
- **Who can approve:** Product Owner authorizes the merge; Claude Code executes it.
- **Who cannot approve:** no partner may merge without an explicit, scoped Product Owner
  authorization naming the branch and target.

### 8. Deployment Gate

- **Owner:** Product Owner authorizes; Claude Code executes.
- **Required input:** explicit Product Owner deployment authorization naming the exact environment
  (test runtime only, never production without separate explicit authorization).
- **Required evidence:** pre/post-deployment safety verification
  (`production_executed_true_count` before/after, health checks, rollback status).
- **Pass criteria:** PASS if deployed exactly to the authorized environment with all safety checks
  passing; FAIL if deployed beyond scope or without authorization.
- **Who can approve:** Product Owner authorizes; Claude Code executes.
- **Who cannot approve:** no partner may deploy — to any environment, including test runtime —
  without an explicit Product Owner authorization for that specific deployment.

### 9. Post-deployment Review Gate

- **Owner:** Claude Code records; Product Owner may additionally validate via Gate 6.
- **Required input:** the deployment record from Gate 8.
- **Required evidence:** a post-deployment record documenting UI verification, safety verification,
  and rollback status (required vs. not required, with reasoning).
- **Pass criteria:** PASS if no rollback was required or a required rollback was completed and
  verified; FAIL if a known-broken state was left deployed without rollback or explicit Product
  Owner acceptance of the gap.
- **Who can approve:** Claude Code records the technical result; Product Owner may layer Gate 6 on
  top of it for product acceptance.
- **Who cannot approve:** no partner may declare a deployment "accepted" on the Product Owner's
  behalf.

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
