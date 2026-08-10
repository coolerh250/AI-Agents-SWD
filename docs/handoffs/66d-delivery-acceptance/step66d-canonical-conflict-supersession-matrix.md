# Step 66D — Canonical Conflict Supersession Matrix

> **Supersession record only. No contract frozen, no implementation authorized. Historical evidence
> was annotated, never rewritten. `production_executed_true_count: 0`.**

Canonical baseline: main `64467fe`. Binding source:
`docs/contracts/66d-delivery-acceptance/step66d-delivery-decision-model-binding-decisions.md`.

## Summary

| Conflict | Previous statement A | Previous statement B | Binding resolution | Files updated |
| --- | --- | --- | --- | --- |
| 66D-CONFLICT-01 | Six gate actions | Three PO decisions | Layered model (66D-D01) | gates, DoD, milestone manifest, master plan, design spec (annotated), precedence |
| 66D-CONFLICT-02 | Acceptance in the delivery lifecycle | Decision outside the lifecycle | Projection + immutable record (66D-D02) | milestone manifest, DoD, precedence |
| 66D-CONFLICT-03 | Task-tied delivery | Project/work-item/workflow/run lineage | Dual-anchor (66D-D03) | milestone manifest, DoD, design spec (annotated), precedence |
| 66D-CONFLICT-04 | `DeliveryPackage` reused | Distinct new surface required | `DeliverySubmission` + legacy preservation (66D-D04) | milestone manifest, DoD, design spec (annotated), precedence |

---

## 66D-CONFLICT-01 — Decision vocabulary

```text
Statement A
  Path:     docs/alignment/66-project-completion/master/product-and-technical-gates.md
  Section:  "Delivery gate (M2 exit)" -> Security/Governance Gate
  Old effective meaning:
            The delivery decision surface is a 6-action gate
            (Accept/Reject/Request-Changes/Re-run-QA/Escalate/Archive).
  New binding meaning:
            Those six are Review Gate Actions. A separate 3-value Product Owner Final Decision
            contract sits alongside them, with its own enum, schema, API, event, audit action and
            authorization boundary.
  Historical preservation: not applicable -- ACTIVE_CANONICAL, edited in place.

  Path:     docs/alignment/66-project-completion/master/project-definition-of-done.md
  Section:  proof-point 6 (and 7)
  Old effective meaning:
            "the four-action decision gate" is the single measure of accept/reject/request-changes.
  New binding meaning:
            Seven separate sub-criteria (a)-(g): Review Gate Action contract, PO Final Decision
            contract, bounded QA rerun rule, blocking/non-blocking follow-up rule, immutable
            decision history, dual-anchor traceability, legacy/new entity separation.
  Historical preservation: not applicable -- ACTIVE_CANONICAL, edited in place.

Statement B
  Path:     docs/design/ai-agent-team-functional-poc-control-center-spec.md
  Section:  §12 "Delivery package + Product Owner acceptance"
  Old effective meaning:
            "Product Owner decision (only these three)" read as the whole decision surface.
  New binding meaning:
            Correct, but scoped: it describes the Product Owner Final Decision layer only.
  Historical preservation:
            PARTNER_SPECIFICATION. Original text untouched; an append-only
            "Supersession note -- Step 66D-ALIGN1" section was added below a stable marker. The
            pre-marker content is still a byte-exact match of blob 65c93a1, machine-verified.

Binding resolution: 66D-D01. Neither statement was wrong; each described a different layer.
```

## 66D-CONFLICT-02 — Lifecycle versus decision record

```text
Statement A
  Path:     docs/alignment/66-project-completion/master/canonical-milestone-manifest.md
  Section:  M2 -> API/data contract dependencies
  Old effective meaning:
            accepted / rejected / changes-requested / qa-rerun-requested are delivery states,
            i.e. acceptance lives inside the delivery lifecycle.
  New binding meaning:
            Delivery review status may carry ACCEPTED and REJECTED, but only as a PROJECTION of the
            current effective decision. The authoritative history is a separate immutable,
            supersedable ProductOwnerDecision record.
  Historical preservation: not applicable -- ACTIVE_CANONICAL, edited in place.

Statement B
  Source:   Step 66D-ARCH1 prompt §11 ("acceptance must not be mixed into the Delivery lifecycle")
  Old effective meaning:
            Acceptance must not appear in the delivery lifecycle at all.
  New binding meaning:
            SUPERSEDED. Projection is permitted; only the authoritative record must be separate.
  Historical preservation:
            The superseded formulation is stated and marked superseded in the binding decision
            record's 66D-D02 section, so the change of position is auditable.

Binding resolution: 66D-D02, requirements D02-R1..D02-R12.
```

## 66D-CONFLICT-03 — Anchor model

```text
Statement A
  Path:     docs/alignment/66-project-completion/master/canonical-milestone-manifest.md
  Section:  M2 -> Architecture / API-data contract dependencies
  Old effective meaning:
            Delivery packages are "tied to real tasks", with TASK_ROLES as the RBAC anchor --
            implying the Task is the delivery anchor generally.
  New binding meaning:
            Dual anchor. Human review and RBAC anchor on `delivery_review_task_id`; execution,
            artifacts and requirement traceability anchor on
            project -> work item -> workflow -> run.
  Historical preservation: not applicable -- ACTIVE_CANONICAL, edited in place.

Statement B
  Path:     docs/handoffs/program-sync/step66sync1-poc-scope-binding-decisions.md
  Section:  D-1 binding requirements D1-R5/D1-R6
  Old effective meaning:
            The Task surface is non-dispatching and is not the Agent execution source of truth.
  New binding meaning:
            UNCHANGED and preserved. 66D-D03 explicitly restates D03-R3 to keep it true.
  Historical preservation:
            Not edited. D-1 remains binding exactly as recorded.

Binding resolution: 66D-D03. The two statements are reconciled by scoping the anchor per concern,
not by weakening D-1.
```

## 66D-CONFLICT-04 — Entity name collision

```text
Statement A
  Paths:    apps/orchestrator/src/delivery_package_api.py
            apps/admin-console/src/pages/DeliveryPackage.tsx
            agents/delivery-package-agent/
            docs/product/delivery-package-acceptance-gate.md
  Section:  Step 47 / Stage 49 Delivery Package and Acceptance Gate
  Old effective meaning:
            `DeliveryPackage` is an implemented Platform Ops evidence object with 14 sections, an
            18-check acceptance gate and `human_acceptance_status`.
  New binding meaning:
            UNCHANGED. Preserved as the legacy object; not renamed, not reshaped, semantics not
            silently changed.
  Historical preservation:
            No source file was modified by this stage.

Statement B
  Path:     docs/alignment/66-project-completion/master/canonical-milestone-manifest.md
  Section:  M2 -> API/data contract dependencies
  Old effective meaning:
            The new acceptance surface must be "not a rename of the existing page", but no name was
            given for the new aggregate -- leaving the collision unresolved.
  New binding meaning:
            The new human-acceptance aggregate is `DeliverySubmission`, with `DeliveryReviewTask`,
            `DeliveryReviewAction`, `ProductOwnerDecision` and `AcceptanceFollowUpItem`. Product
            surfaces: Delivery Inbox and Delivery Review.
  Historical preservation: not applicable -- ACTIVE_CANONICAL, edited in place.

Binding resolution: 66D-D04.
```

## Files updated by this stage

```text
ACTIVE_CANONICAL -- edited in place (contradiction removed):
  docs/alignment/66-project-completion/master/product-and-technical-gates.md
  docs/alignment/66-project-completion/master/project-definition-of-done.md
  docs/alignment/66-project-completion/master/canonical-milestone-manifest.md
  docs/alignment/66-project-completion/master/project-completion-master-plan.md
  docs/alignment/66-project-completion/master/canonical-source-of-truth-precedence.md

PARTNER_SPECIFICATION / HISTORICAL_EVIDENCE -- append-only annotation, original text untouched:
  docs/design/ai-agent-team-functional-poc-control-center-spec.md
  docs/handoffs/program-sync/step66sync1-claude-design-ux-gap-register.md
  docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md

NEW canonical records:
  docs/contracts/66d-delivery-acceptance/step66d-delivery-decision-model-binding-decisions.md
  docs/contracts/66d-delivery-acceptance/step66d-canonical-terminology-registry.md
  docs/handoffs/66d-delivery-acceptance/step66d-canonical-conflict-supersession-matrix.md
  docs/handoffs/66d-delivery-acceptance/step66d-align1-gap-register.md
  docs/handoffs/66d-delivery-acceptance/step66d-arch1-retry-readiness.md
  docs/test/step66d-align1-canonical-alignment-evidence.md

NOT edited (deliberately):
  docs/alignment/66-project-completion/master/next-executable-stage-sequence.md
    Its "6-action acceptance-gate endpoint contract" wording is CORRECT under 66D-D01 -- there are
    exactly six Review Gate Actions -- so no contradiction exists and no edit was needed. The file
    is also byte-locked by the RA-2M1/RA-2M2 verifiers as imported planning evidence.
  docs/alignment/66-project-completion/master/critical-path-and-dependency-map.md
    "new 6-action endpoints" is likewise still correct.
  Any file under apps/, agents/, services/, shared/, migrations/, infra/.
```

## Step 66D-BE1-CR1 addendum — 66D-D05 DeliveryReviewTask active state

> Appended by Step 66D-BE1-CR1. It records one further canonical resolution and does not alter any
> conflict, resolution or annotation above.

```text
Conflict:
  ARCH1 step66d-arch1-domain-and-state-model.md section 2 stated
    "review_status mirrors submission review state for the assignee's view"
    -- quoted as the SUPERSEDED prior statement; WITHDRAWN as authority by 66D-D05 and NOT
       AUTHORITATIVE for BE1 persistence --
  while DESIGN step66d-design-delivery-inbox-spec.md section 3 stated that
    DeliveryReviewTask.status is an independent review-task lifecycle whose enum is NOT
    IMPLEMENTED, that it is NOT interchangeable with DeliverySubmission.status, and that a closed
    review task against an EXPIRED submission must remain expressible.

Discovered by:
  Step 66D-BE1, which stopped at its canonical contract gate before creating a branch, because
  "exactly one active review task per submission version" could not be implemented deterministically
  without inventing a lifecycle enum.

Resolution:
  66D-D05 (BINDING, Product Owner)
  docs/contracts/66d-delivery-acceptance/step66d-d05-review-task-active-state-amendment.md

Winner:
  neither literal prior representation

Canonical replacement:
  a structural active predicate that needs no enum
    active  :=  closed_at IS NULL
    closed  :=  closed_at IS NOT NULL
  persistence invariant: AT MOST ONE structurally active DeliveryReviewTask per
  delivery_submission_id (partial unique index WHERE closed_at IS NULL)

Superseded:
  the ARCH1 mirroring sentence, as lifecycle and storage authority for BE1 persistence.
  The original sentence is annotated in place and is not deleted.

Preserved:
  the DESIGN requirement that review-task status and submission status are NOT interchangeable.

Lifecycle enum:
  deferred -- NOT DEFINED. DESIGN did not define review-task lifecycle values and this addendum
  does not claim otherwise. delivery_review_task_status remains PLANNED / NOT IMPLEMENTED.

Deferred by this resolution:
  when an active review task must exist; reopen; close action; reopen-after-close; automatic
  closure; closure caused by a Product Owner decision; closure caused by expiry.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
