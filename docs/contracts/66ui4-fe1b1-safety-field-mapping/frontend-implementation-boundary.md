# Frontend Implementation Boundary — DESIGN-66UI.4-FE.1B.1 Safety Field Mapping Calibration

> **Boundary document only. No runtime code changed. No backend changed. No frontend implementation
> changed. Codex is NOT authorized to implement anything in this document until the Product Owner
> explicitly authorizes implementation following this planning stage.**

Owner: Claude Code (Lead Engineer / Architecture Owner), written for Codex (Frontend Engineer) per
`docs/process/role-responsibility-matrix.md`. This is the contract boundary for the future FE.1B.1
calibration work defined in
`docs/frontend/66ui4-phase1-product-visual-language/fe1b1-safety-field-mapping-plan.md`.

## 1. No new or changed backend contract is required or permitted

FE.1B.1 is a frontend-only recalibration of which existing `/operations/safety` fields
`CalmSafetyPosture.tsx` reads and how it labels them. The `/operations/safety` response shape must
not change. No new endpoint, response field, or response shape may be requested or added.

## 2. What may proceed, once authorized

- **Remove** `dispatch_enabled` and `resume_dispatch_enabled` from `AUTOMATION_FIELDS` in
  `apps/admin-console/src/components/CalmSafetyPosture.tsx`. Rely on the already-present
  `task_api_workflow_dispatch_enabled` and `task_workroom_resume_dispatch_enabled` as the sole,
  correct, already-global automation-dispatch signals.
- **Remove** the global "Approval requirement" fact and its backing fields (`approval_required`,
  `requires_approval`) from `getCalmSafetyPosture()`'s tone computation and `facts` list. Replace with
  a short, honestly-scoped note (e.g. "Approvals: tracked per task — see Task List") that does not
  claim a global approval state.
- **Update `SAFETY_EVIDENCE_FIELDS`** so the four retired fields are either removed from the raw
  evidence disclosure, or relabeled "Not applicable at this endpoint" (never "not reported," which
  would misleadingly imply a data-availability gap rather than a corrected scope mismatch).
- **Update copy/tests** accordingly, per
  `fe1b1-safety-field-mapping-plan.md` §6–7.
- **(Optional, non-blocking) Add a fourth tone** for a future genuinely-partial-evidence case,
  distinct from today's scope-mismatch bug, if the Product Owner and Claude Code agree it is worth
  the added complexity at implementation time.

## 3. Hard boundary (must not)

```text
- No backend changes.
- No API changes.
- No database changes.
- No workflow changes.
- No change to the /operations/safety response shape.
- No new endpoint.
- No production/external controls of any kind.
- No FE.1C Overview implementation.
- No FE.1D navigation/microcopy implementation.
- No fake "Safe" state -- every fact must trace to a real, correctly-scoped, already-present field.
- No hiding of raw evidence.
- No substituting a field into the mapping based on name-similarity alone -- confirm semantics
  against backend source or a live response first (see plan §4's work_item_dispatch_enabled
  cautionary finding).
```

## 4. Authorization gate

Codex may not implement FE.1B.1 until: (a) this planning stage's recommendation is accepted by the
Product Owner, and (b) an explicit, separate Product Owner authorization names FE.1B.1 implementation
specifically. This document and the planning record together establish that the calibration is safe
to authorize — they do not themselves constitute that authorization.

## 5. Statement

Boundary specification only. No runtime code changed. No frontend implementation changed. No backend
change. No API contract change requested. No workflow dispatch. No workflow resume. No external
action. No production action. Codex implementation not authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
