# Step 66SYNC.1 — POC Scope Binding Decisions (D-1 / D-2 / D-3)

> **Product Owner binding decision record. This document records decisions that the Product Owner
> made and formally accepted. It does NOT authorize implementation. No runtime, frontend, backend,
> API, database, workflow, deployment, migration, secret, or feature-gate change was made in the
> stage that created it. `production_executed_true_count: 0`.**

```text
DOCUMENT_STATUS:
CANONICAL / BINDING

DECISION_AUTHORITY:
Product Owner

DECISION_DATE:
2026-08-04

RECORDED_BY:
Claude Code (Step 66SYNC.1-M1), acting as recorder only

CONTEXT_ID:
AIAT-SYNC-20260803-01

CANONICAL_BASELINE:
main c1db4cc

FINAL_RECONCILIATION_COMMIT:
2396c6c

D-1:
RESOLVED / BINDING

D-2:
RESOLVED / BINDING

D-3:
RESOLVED / BINDING

OPEN_PRODUCT_OWNER_DECISIONS_FROM_STEP66SYNC1:
0

POC_SCOPE_DECISION_SET:
COMPLETE

POC_IMPLEMENTATION_AUTHORIZED:
NO
```

## Relationship to the reconciliation evidence

At the time of Step 66SYNC.1-A / A1 / D, D-1, D-2 and D-3 were classified
`OPEN_PRODUCT_OWNER_DECISION`, and every partner artifact recorded
`OPEN_PRODUCT_OWNER_DECISIONS: 3`. That was correct then and those historical documents are
preserved unchanged. The decisions were subsequently resolved by Product Owner authorization on
2026-08-04, which this record — and only this record — makes canonical. Where this record and an
earlier reconciliation artifact disagree about decision status, this record governs; the earlier
artifact remains valid as a record of the state at reconciliation time.

The option analysis that these decisions were made against is
`docs/handoffs/program-sync/step66sync1-poc-scope-decision-package.md` (non-binding proposal,
unchanged).

---

## D-1 — POC entry point

```text
Decision ID:  D-1
Status:       RESOLVED / BINDING
Selected:     Dedicated POC Development Goal
```

The single formal POC entry point is:

```text
Product Owner Development Goal
  -> Durable POC Project
    -> Primary Work Item
      -> Workflow / Run
        -> Existing Intake Pipeline
```

### Binding requirements

```text
D1-R1  The POC entry must create a durable Project identity.
D1-R2  A Primary Work Item identity must be created.
D1-R3  A Workflow / Run identity must be created.
D1-R4  Project -> Work Item -> Workflow/Run traceability must be preserved.
D1-R5  The existing Task API and Task UI remain non-dispatching.
D1-R6  The existing Task surface must not be used as the Agent execution source of truth.
D1-R7  UI wording must not conceal the fact that the Task surface and the Agent pipeline are
       not yet connected.
```

### Consequences for the recorded technical state

`apps/orchestrator/src/task_api.py` continues to return `dispatch_enabled: False` and continues not
to publish to `stream.tasks`. This decision does not change that code; it decides that the POC will
not depend on changing it. The two-disconnected-task-paths finding (Claude Code D-1 discrepancy,
Codex FE-POC-G1, Claude Design UX-POC-B1) is therefore addressed by adding a separate goal path,
not by converting the Task surface.

---

## D-2 — Execution model

```text
Decision ID:  D-2
Status:       RESOLVED / BINDING
Selected:     Hybrid execution model
```

Working partners for the first POC:

```text
Claude Code    -> Backend / Architecture implementation partner
Codex          -> Frontend implementation partner
Claude Design  -> UX / IA / Design partner
```

The platform must in future be able to record, for each unit of partner work:

```text
assigned task
actor type
execution status
artifact
commit
branch
draft PR
test evidence
review evidence
handoff evidence
timestamps
```

### Binding requirements

```text
D2-R1  Claude Code, Codex and Claude Design are external AI partners.
D2-R2  An external AI partner must not be presented or modelled as a runtime Agent service.
D2-R3  agents/backend-agent/ and agents/frontend-agent/ remain classified NOT IMPLEMENTED.
D2-R4  The first POC does not create permanent backend-agent or frontend-agent runtime services.
D2-R5  Whether to create permanent runtime services is deferred to a separate decision after the
       POC retrospective.
```

### Consequences for the recorded technical state

`agents/backend-agent/` and `agents/frontend-agent/` contain `.gitkeep` only, with zero `.py` files.
This decision confirms that state is intentional for the POC and must not be described as
implemented, partially implemented, or planned-for-this-POC. The ten implemented runtime agents are
unaffected.

---

## D-3 — Delivery generation mode

```text
Decision ID:  D-3
Status:       RESOLVED / BINDING
Selected:     Runtime LLM remains plan-only; Claude Code and Codex generate implementation.
```

### Permitted

```text
Claude Code backend implementation
Codex frontend implementation
isolated sandbox branch
draft PR
deterministic template generation
tests
static analysis
review evidence
```

### Prohibited

```text
runtime LLM direct patch generation
runtime LLM direct test generation
automatic patch application
autonomous merge
direct push to main
```

### Binding requirements

```text
D3-R1  The existing runtime LLM plan-only safety control must not be removed or weakened.
D3-R2  Code may only be produced by a controlled AI partner on a sandbox branch.
D3-R3  All code modification must go through a draft PR.
D3-R4  Autonomous runtime code generation is deferred to a separate high-risk stage.
D3-R5  That future stage requires an independent security review.
D3-R6  Autonomous runtime code generation must not be folded into ordinary POC.0.
```

### Consequences for the recorded technical state

`generate_patch_proposal` and `generate_test_plan` raise `LLMProviderError` by design. This decision
makes that fail-closed behaviour a binding safety control rather than an incidental implementation
detail. Removing it is out of scope for POC.0 and for every stage authorized so far.

---

## Additional binding conditions

```text
B-01  No production repository.
B-02  No production data.
B-03  No production credential.
B-04  No production endpoint call.
B-05  All code modification only on an isolated sandbox branch via draft PR.
B-06  All partner work must produce durable artifacts and audit evidence.
B-07  A chat report alone is never acceptable completion evidence.
B-08  BE3 resume/replay execution remains disabled.
B-09  Unified POC Control Center and Coordinated Existing Routes remain POC.0 non-binding design
      options; neither is selected.
B-10  Step 66D-ARCH must complete before any formal Delivery/Acceptance surface implementation.
B-11  Every implementation stage requires its own separate Product Owner authorization.
B-12  production_executed_true_count must remain 0.
```

## Deferred decisions

```text
Permanent backend-agent / frontend-agent runtime services
  -> deferred by D2-R5 to a post-POC-retrospective decision.

Autonomous runtime LLM patch/test generation
  -> deferred by D3-R4/D3-R5 to a separate high-risk stage with independent security review.

POC.0 information architecture (Unified POC Control Center vs Coordinated Existing Routes)
  -> still an open POC.0 design option under B-09; NOT SELECTED, and NOT one of D-1/D-2/D-3.

Delivery / Acceptance contract
  -> blocked by B-10 on Step 66D-ARCH, which is a separate authorization.
```

## Prohibited implications

These decisions must not be read as any of the following, none of which is true:

```text
POC.0 is authorized                              -- FALSE
POC implementation may begin                     -- FALSE
Step 66D-ARCH is authorized                      -- FALSE
Step 67POC.0 is authorized                       -- FALSE
RA-2M or RA-2 implementation is authorized       -- FALSE
The Task API may now dispatch                    -- FALSE
Runtime agents will be built for the first POC   -- FALSE
The runtime LLM may generate patches or tests    -- FALSE
The POC implementation scope is technically final -- FALSE
```

## Required future stages

```text
Step 66D-ARCH                     NOT STARTED / NOT AUTHORIZED  (required before B-10 surfaces)
POC.0 architecture and read model NOT STARTED / NOT AUTHORIZED
POC.0 environment scope           NOT STARTED / NOT AUTHORIZED
POC.0 IA option selection         NOT MADE     (B-09)
Step 67POC.0                      NOT STARTED / NOT AUTHORIZED
Per-stage implementation auth.    NOT GRANTED  (B-11)
```

## Implementation authorization status

```text
POC_SCOPE_DECISION_SET:              COMPLETE
POC_SCOPE_IMPLEMENTATION_PLAN:       NOT YET FINALIZED
POC_IMPLEMENTATION_AUTHORIZED:       NO
POC_IMPLEMENTATION_STARTED:          NO
STEP66D_ARCH:                        NOT STARTED / NOT AUTHORIZED
STEP67POC0:                          NOT STARTED / NOT AUTHORIZED
RA2M:                                NOT STARTED / NOT AUTHORIZED
BE3_RESUME_REPLAY:                   DISABLED
PRODUCTION_EXECUTED_TRUE_COUNT:      0
```

A complete decision set is not a finalized implementation scope. Scope finalization additionally
requires Step 66D-ARCH, POC.0 architecture/read-model/environment scope, the POC IA option
selection, and per-stage authorization under B-11.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
