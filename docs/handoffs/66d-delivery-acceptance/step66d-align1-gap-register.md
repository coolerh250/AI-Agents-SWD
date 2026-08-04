# Step 66D-ALIGN1 — Alignment Gap Register

> **Gap register only. Every item below is NOT IMPLEMENTED and NOT AUTHORIZED. Resolving a
> vocabulary conflict closes no implementation gap. `production_executed_true_count: 0`.**

Ten gaps. **Authorized: 0 of 10. Implemented: 0 of 10.**

---

## ALIGN1-G01 — Bounded QA rerun count

```text
Gap ID:               ALIGN1-G01
Conflict ID:          66D-CONFLICT-01
Previous documents:   project-definition-of-done.md proof-point 7 ("limit defined during 66D-ARCH")
Binding resolution:   66D-D01 confirms RERUN_QA is a Review Gate Action, never a PO Final Decision.
                      §14 of this stage explicitly forbids deciding the numeric bound here.
Remaining architecture work: freeze maximum rerun count, cooldown, timeout, escalation threshold
Remaining design work:       consequence copy for an exhausted rerun budget
Remaining backend work:      counter, enforcement, audit record
Remaining frontend work:     remaining-rerun affordance and disabled state
Risk:                 MEDIUM -- an unbounded rerun loop is a real cost and audit hazard
Owner:                Claude Code (Step 66D-ARCH)
Authorization status: NOT IMPLEMENTED / NOT AUTHORIZED
```

## ALIGN1-G02 — DeliverySubmission schema

```text
Gap ID:               ALIGN1-G02
Conflict ID:          66D-CONFLICT-04
Previous documents:   canonical-milestone-manifest.md M2 (new surface required, unnamed)
Binding resolution:   66D-D04 names the aggregate DeliverySubmission
Remaining architecture work: fields, identifiers, immutability, retention, redaction, versioning
Remaining design work:       none until the schema is frozen
Remaining backend work:      persistence model
Remaining frontend work:     none until the contract is frozen
Risk:                 HIGH -- everything else in Step 66D depends on this shape
Owner:                Claude Code (Step 66D-ARCH)
Authorization status: NOT IMPLEMENTED / NOT AUTHORIZED
```

## ALIGN1-G03 — Review action API

```text
Gap ID:               ALIGN1-G03
Conflict ID:          66D-CONFLICT-01
Previous documents:   product-and-technical-gates.md (6-action endpoint contract)
Binding resolution:   66D-D01 fixes the six actions and separates them from the decision contract
Remaining architecture work: request/response schemas, idempotency, concurrency, error codes, audit
Remaining design work:       action affordances and consequence previews
Remaining backend work:      endpoints and RBAC enforcement
Remaining frontend work:     Delivery Review action surface
Risk:                 HIGH
Owner:                Claude Code (contract) -> Codex (frontend)
Authorization status: NOT IMPLEMENTED / NOT AUTHORIZED
```

## ALIGN1-G04 — Product Owner decision API

```text
Gap ID:               ALIGN1-G04
Conflict ID:          66D-CONFLICT-01, 66D-CONFLICT-02
Previous documents:   ai-agent-team-functional-poc-control-center-spec.md §12
Binding resolution:   66D-D01 and 66D-D02 -- a separate contract from the review action API
Remaining architecture work: decision schema, evidence-reviewed references, versioning
Remaining design work:       Final Acceptance surface (spec screen 7.12)
Remaining backend work:      endpoints, authorization, audit
Remaining frontend work:     acceptance surface
Risk:                 HIGH
Owner:                Claude Code (contract) -> Codex (frontend)
Authorization status: NOT IMPLEMENTED / NOT AUTHORIZED
```

## ALIGN1-G05 — Immutable supersession persistence

```text
Gap ID:               ALIGN1-G05
Conflict ID:          66D-CONFLICT-02
Previous documents:   none -- this requirement did not exist in canonical form before
Binding resolution:   66D-D02 D02-R1..R3 (never overwritten, never deleted, supersedes_decision_id)
Remaining architecture work: supersession chain model and query semantics
Remaining design work:       decision-history presentation
Remaining backend work:      append-only persistence and constraints
Remaining frontend work:     history view
Risk:                 HIGH -- an in-place overwrite would destroy the audit property
Owner:                Claude Code (Step 66D-ARCH)
Authorization status: NOT IMPLEMENTED / NOT AUTHORIZED
```

## ALIGN1-G06 — DeliveryReviewTask linkage

```text
Gap ID:               ALIGN1-G06
Conflict ID:          66D-CONFLICT-03
Previous documents:   canonical-milestone-manifest.md M2 ("tied to real tasks")
Binding resolution:   66D-D03 dual-anchor
Remaining architecture work: linkage contract between review task and execution lineage
Remaining design work:       how the two anchors are shown without implying dispatch
Remaining backend work:      linkage persistence and read path
Remaining frontend work:     Delivery Inbox queue
Risk:                 HIGH -- getting this wrong re-creates the two-disconnected-paths problem
Owner:                Claude Code (Step 66D-ARCH)
Authorization status: NOT IMPLEMENTED / NOT AUTHORIZED
```

## ALIGN1-G07 — TASK_ROLES authorization mapping

```text
Gap ID:               ALIGN1-G07
Conflict ID:          66D-CONFLICT-03
Previous documents:   product-and-technical-gates.md (server-side RBAC, non-negotiable)
Binding resolution:   66D-D03 -- TASK_ROLES anchors on delivery_review_task_id
Remaining architecture work: which role may take which of the six actions and the three decisions
Remaining design work:       permission-disabled affordances
Remaining backend work:      server-side enforcement
Remaining frontend work:     role-aware rendering, never client-side-only gating
Risk:                 CRITICAL -- and additionally identity-dependent, see ALIGN1-G10
Owner:                Claude Code (Step 66D-ARCH)
Authorization status: NOT IMPLEMENTED / NOT AUTHORIZED
```

## ALIGN1-G08 — Delivery Inbox read model

```text
Gap ID:               ALIGN1-G08
Conflict ID:          66D-CONFLICT-03
Previous documents:   step66sync1-poc0-consolidated-gap-register.md POC0-BACKEND-G2, POC0-FRONTEND-G4
Binding resolution:   none -- 66D-D01..D04 do not define a read model
Remaining architecture work: unified project-level read model, refresh and staleness semantics
Remaining design work:       queue presentation; still gated on the unselected POC.0 IA option
Remaining backend work:      read model and API
Remaining frontend work:     Delivery Inbox
Risk:                 HIGH; also POC.0-dependent
Owner:                Claude Code (read model) -> Claude Design (spec) -> Codex (frontend)
Authorization status: NOT IMPLEMENTED / NOT AUTHORIZED
```

## ALIGN1-G09 — Legacy DeliveryPackage reference contract

```text
Gap ID:               ALIGN1-G09
Conflict ID:          66D-CONFLICT-04
Previous documents:   docs/product/delivery-package-acceptance-gate.md (Step 47/49)
Binding resolution:   66D-D04 D04-R5 -- reference via legacy_delivery_package_refs only
Remaining architecture work: reference shape, and the rule that referencing never mutates the legacy
                             object
Remaining design work:       how legacy evidence appears inside a review without implying ownership
Remaining backend work:      reference resolution
Remaining frontend work:     evidence links
Risk:                 MEDIUM -- the main risk is silent semantic drift of the legacy API
Owner:                Claude Code (Step 66D-ARCH)
Authorization status: NOT IMPLEMENTED / NOT AUTHORIZED
```

## ALIGN1-G10 — Follow-up lifecycle and verified human identity

```text
Gap ID:               ALIGN1-G10
Conflict ID:          66D-CONFLICT-02
Previous documents:   step66c4-be3-ra2-binding-decisions.md RA2-D01/D02/D03;
                      step66sync1-poc0-consolidated-gap-register.md POC0-SAFETY-G2
Binding resolution:   66D-D02 D02-R6/R7 define blocking vs non-blocking follow-ups
Remaining architecture work: follow-up lifecycle states, ownership, due dates, closure rules
Remaining design work:       follow-up surfaces
Remaining backend work:      follow-up persistence and APIs
Remaining frontend work:     follow-up list and closure actions
Identity dependency:  A Product Owner Final Decision must be attributable to a VERIFIED human
                      identity. Today `task_api.py::_authenticate` takes actor and role verbatim
                      from client headers, and RA2-D01/D02/D03 are decided but NOT IMPLEMENTED
                      (RA-2I0 and RA-2I1 are NOT AUTHORIZED). Until then, any decision recorded in
                      a test/sandbox environment must be labelled with that environment limitation.
Risk:                 CRITICAL
Owner:                Claude Code (Step 66D-ARCH contract; RA-2I1 identity)
Authorization status: NOT IMPLEMENTED / NOT AUTHORIZED
```

---

## Summary

```text
Total gaps:            10
Implemented:           0
Authorized:            0
Critical:              2   (ALIGN1-G07, ALIGN1-G10)
High:                  5   (G02, G03, G04, G05, G06, G08 -- see per-item risk)
Medium:                2   (G01, G09)
Identity-dependent:    2   (G07, G10)
POC.0-dependent:       1   (G08)
```

Nothing in this register is closed, and nothing in it is authorized. Step 66D-ARCH, Step 66D-DESIGN
and every Step 66D implementation slice remain NOT AUTHORIZED.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
