# Demo Evidence Page — Diagnostic-Only Policy (Step 64E.4A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Policy only — no code change, no rebuild, no restart in this stage.**

Governs the Demo Evidence page added in Step 64E.3B (`apps/admin-console/src/pages/DemoEvidence.tsx`,
route `/demo-evidence`).

## Policy
- The Demo Evidence page may remain in the build as a **Developer Diagnostic / Evidence Debug View
  only**.
- It **must not** be used as the primary staging acceptance path.
- It **must not** be referenced as proof that the formal product UI is usable.
- **Operator acceptance must be based on the formal product pages** per
  [formal-admin-console-page-evidence-map.md](formal-admin-console-page-evidence-map.md).

## Required relabeling / placement
If the page remains in the UI, relabel it as one of:
- **Diagnostics**
- **Developer Diagnostics**
- **Evidence Debug View**

And, in staging acceptance mode, **hide it from normal operator navigation** so it is not part of
the operator's acceptance path. (Implementation deferred to Step 64E.4B — not done here.)

## Rationale
The Demo Evidence page was built to diagnose whether the demo data exists and can be fetched. It
does that well, but it is an aggregation view, not the product an operator uses. Treating it as the
acceptance path validates the wrong artifact and masks formal-page gaps. Keeping it as a labeled
diagnostic preserves its debugging value without letting it stand in for the product.

## Verifier consequence
The Step 64E.4A verifier (`scripts/verify_product_ui_remediation_plan.py`) FAILS if any planning
doc treats that diagnostic page as the accepted staging path (i.e. asserts it, rather than the
formal product pages, is the acceptance path).

## Status
- Step 64E: **FAILED_STAGING_REPRESENTATIVENESS**. Step 64F: **BLOCKED**.
- Demo Evidence page: **developer diagnostic only — not staging acceptance**.
- **No production action**; `production_executed_true_count=0`. **No implementation claimed.**

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
