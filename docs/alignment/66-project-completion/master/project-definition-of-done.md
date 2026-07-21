# Project Definition of Done — AI Agent Team Work

> **Consolidated planning document only. No runtime code, no backend, no API, no database, no
> workflow, no new endpoint/route, no merge of any alignment branch, no deployment performed by
> this document.**

Measurable completion criteria for the whole project, consolidating the 14 required proof-points
from the Step 66ALIGN.2-CONSOLIDATE prompt with Claude Code's 9-point concrete "production-ready"
definition from `alignment-statement.md`.

## 14 measurable proof-points

```text
1. Multi-role users can create and assign tasks.
   Measured by: a real task created and assigned via the product UI by a user under a real (not
   test-header-simulated) role, on a real test-runtime (pre-M6) or production (post-M6) record —
   Product Owner UI-validated.

2. The AI Agent Team can raise a clarification.
   Measured by: a real clarification raised against a real task, presented as a decision request
   (per core-loop-experience-definition.md), Product Owner UI-validated.

3. The system can wait, remind, transition blocked/expired, and resume in a controlled way.
   Measured by: a real 24h reminder fired and a real 72h blocked/expired transition observed on a
   real task (Step 66C.4), with resume remaining an explicit, gated human action never an implicit
   side effect — Product Owner UI-validated.

4. Agents can perform real, controlled work.
   Measured by: agent execution evidence tied to a real task, visible as task-scoped team state
   (M1) and cross-task team activity (M3), with no orchestration control exposed beyond what a
   backend contract explicitly authorizes.

5. Users can review Delivery, QA, and evidence.
   Measured by: a real Delivery Inbox/Detail (M2, built only after the 66D-ARCH contract freeze)
   showing a real delivery record, evidence as expandable secondary detail, never a raw JSON
   headline — Product Owner UI-validated.

6. Users can accept/reject/request changes.
   Measured by: the four-action decision gate (Accept/Reject/Request-Changes/Re-run-QA) exercised
   on a real delivery with server-enforced RBAC and an audited, unambiguous consequence — Product
   Owner UI-validated, with the Request-Changes-vs-Re-run-QA distinction confirmed unambiguous.

7. QA rerun count is limited and auditable.
   Measured by: a real, bounded QA-rerun mechanism (limit defined during 66D-ARCH) with every
   rerun recorded in audit evidence — no unbounded rerun loop possible.

8. Retry/DLQ/replay/recovery are operable.
   Measured by: a real Approvals P0 / DLQ-Retry P0 product UI (M2) reading from the already-running
   approval-engine/retry-scheduler backend services, with real retry/replay/recovery actions
   exercised and audited — Product Owner UI-validated.

9. Production actions require approval.
   Measured by: every production-affecting/external action gated behind an explicit human-approval
   UX with a consequence preview (per production-trust-and-adoption-ux.md), verified server-side,
   not merely UI-hidden.

10. Audit integrity, secrets, cost, and RBAC are governed.
    Measured by: audit-chain integrity continuously monitored (no repeat of the Stage 42 tamper-
    artifact class of incident); a real secret store (Vault HA/auto-unseal or cloud KMS) replacing
    ephemeral dev-mode Vault; a real, server-enforced RBAC system (not test-header simulation)
    matching the locked 6-role matrix; cost visibility per the existing cost-tracking mechanisms
    extended to any new M2-M4 backend services.

11. Backup/restore/rollback have been actually rehearsed.
    Measured by: all four Backup/DR gaps (encryption_no_key, storage_not_off_host,
    schedule_dry_run_only, migration_down_gaps) closed with a real, verified remediation — not a
    re-stated "still open" note — and at least one real restore/rollback rehearsal performed and
    recorded against the real (M6) substrate, not the "kind" dry-run sandbox.

12. A controlled pilot has been completed.
    Measured by: the M5 pilot's evidence package and multi-session Product Owner validation record
    showing a real operator completed the full loop end-to-end with no unresolved P0/P1 gap.

13. The production-readiness gate has been completed.
    Measured by: all nine "production-ready" conditions below are simultaneously true, confirmed by
    an explicit, named Product Owner "production" authorization (categorically distinct from every
    test-runtime authorization issued to date).

14. Production rollout and adoption acceptance have been completed.
    Measured by: real production traffic under real user adoption, a completed onboarding/first-run
    experience, and the Product Owner's final go-live acceptance recorded — the one milestone where
    production_executed_true_count becoming nonzero is the intended, authorized outcome.
```

## The nine simultaneous conditions for "production-ready" (M6 exit gate, verbatim from Claude
Code's alignment-statement.md, adopted as canonical)

```text
1. M1-M5 complete and validated by a real controlled pilot (66H) with a real operator exercising
   the full assign -> execute -> clarify -> deliver -> accept -> notify loop, with no unresolved
   P0/P1 gap discovered during that pilot.
2. A real (non-"kind") Kubernetes cluster and real ArgoCD instance exist, governed by the
   already-designed (Stage 60-63A) authorization-boundary models re-validated against the real
   substrate, with allowArgoCDProductionSync/allowKubernetesProductionMutation deliberately,
   explicitly authorized by the Product Owner for the first time.
3. A real secret store is in place (Vault HA + auto-unseal, or an equivalent cloud KMS-backed
   store) — ephemeral dev-mode Vault is retired from any environment claiming production status.
4. Postgres authentication is hardened away from `trust`.
5. All four Backup/DR gaps (encryption_no_key, storage_not_off_host, schedule_dry_run_only,
   migration_down_gaps) are closed with real, verified remediation.
6. The Admin Console SPA deep-link/hard-refresh fallback gap is fixed.
7. Team RBAC's production identity/session layer is hardened and verified — real identity provider
   integration, authentication, session security, production role provisioning, and production
   access review replace the test-only header simulation (the M6/M7-owned pieces per
   `docs/decisions/66-team-rbac-milestone-ownership.md`). Team RBAC's product capability itself
   (team/project roles, role permissions, task assignment permissions, team/project visibility,
   operator controls, approval/retry/replay/recovery permissions, matching the 6-role matrix
   already locked in the 66A.3 blueprint) is implemented and validated in M3, not deferred to M6 —
   this condition is about production-hardening and verifying that already-built capability under
   real production identity/session conditions, not about building it for the first time.
8. Every external-send capability (Discord, Slack, Telegram, GitHub, LLM providers) has been
   explicitly, individually authorized for production use by the Product Owner.
9. production_executed_true_count is expected and intended to become nonzero at M7, with a
   documented, explicit Product Owner authorization as the trigger for the first real production
   action — not an implicit transition. Its value at M6 completion must still be 0.
```

If even one of these nine is not true, the system is **not yet production-ready**, regardless of
how much frontend polish or how many successful test-runtime deployments have accumulated. This
statement is adopted verbatim as the Master Plan's own standard, not merely cited.

## Business acceptance

Final business/product acceptance is the Product Owner's alone (role-responsibility-matrix.md
cross-cutting rule). This Master Plan defines measurable technical/product completion criteria; it
does not substitute for, and cannot pre-decide, that acceptance.

## Statement

Consolidated planning document only. No runtime code, no backend, no API, no database, no workflow,
no new endpoint/route, no merge of any alignment branch, no deployment performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
