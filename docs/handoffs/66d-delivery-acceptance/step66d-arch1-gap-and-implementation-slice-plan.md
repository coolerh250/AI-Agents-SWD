# Step 66D-ARCH1 — Gap Register and Implementation Slice Plan

> **Planning only. Fourteen gaps. **Authorized: 0 of 14. Implemented: 0 of 14.** Eight slices,
> **none authorized**. `production_executed_true_count: 0`.**

## 1. Gap register

Every gap below is `NOT IMPLEMENTED` and `NOT AUTHORIZED`.

---

### ARCH1-G01 — DeliverySubmission persistence

```text
Current state          ABSENT
Required contract      domain-and-state-model.md section 1
Backend dependency     Step 66D-BE1 (schema + migration)
Frontend dependency    none
UX dependency          none
Identity dependency    none
Environment dependency internal test runtime
Risk                   HIGH -- everything else hangs off this aggregate
Owner                  Claude Code
Recommended slice      Step 66D-BE1
Authorization status   NOT AUTHORIZED
```

### ARCH1-G02 — DeliveryReviewTask linkage

```text
Current state          ABSENT; Task exists, no review task concept
Required contract      domain-and-state-model.md section 2
Backend dependency     Step 66D-BE1, Step 66D-BE2
Frontend dependency    Step 66D-FE1
UX dependency          Step 66D-DESIGN
Identity dependency    none
Risk                   HIGH -- without it there is no accountable reviewer
Owner                  Claude Code
Recommended slice      Step 66D-BE2
Authorization status   NOT AUTHORIZED
```

### ARCH1-G03 — ReviewAction API

```text
Current state          ABSENT
Required contract      api-event-audit-contracts.md section 1
Backend dependency     Step 66D-BE3
Frontend dependency    Step 66D-FE2
UX dependency          Step 66D-DESIGN
Identity dependency    partial -- reviewer capability
Risk                   HIGH
Owner                  Claude Code
Recommended slice      Step 66D-BE3
Authorization status   NOT AUTHORIZED
```

### ARCH1-G04 — ProductOwnerDecision API

```text
Current state          ABSENT
Required contract      api-event-audit-contracts.md section 1; ADR-66D-10 atomicity
Backend dependency     Step 66D-BE3
Frontend dependency    Step 66D-FE2
UX dependency          Step 66D-DESIGN
Identity dependency    CRITICAL -- requires a verified human actor
Risk                   CRITICAL
Owner                  Claude Code
Recommended slice      Step 66D-BE3
Authorization status   NOT AUTHORIZED
```

### ARCH1-G05 — Immutable decision supersession

```text
Current state          ABSENT; legacy human_acceptance_status is overwritten in place
Required contract      ADR-66D-02, ADR-66D-03
Backend dependency     Step 66D-BE1, Step 66D-BE3
Risk                   HIGH -- the guarantee 66D-D02 exists to provide
Owner                  Claude Code
Recommended slice      Step 66D-BE3
Authorization status   NOT AUTHORIZED
```

### ARCH1-G06 — Follow-up lifecycle

```text
Current state          ABSENT
Required contract      domain-and-state-model.md section 5
Backend dependency     Step 66D-BE3
Frontend dependency    Step 66D-FE2
UX dependency          Step 66D-DESIGN
Risk                   MEDIUM
Owner                  Claude Code
Recommended slice      Step 66D-BE3
Authorization status   NOT AUTHORIZED
```

### ARCH1-G07 — TASK_ROLES capability mapping

```text
Current state          TASK_ROLES exists with six roles; no delivery review capability mapping
Required contract      contract-freeze.md section 8
Backend dependency     Step 66D-BE2, Step 66D-BE3
Identity dependency    CRITICAL
Risk                   CRITICAL -- an unmapped capability means anyone or no one can decide
Owner                  Claude Code
Recommended slice      Step 66D-BE2
Authorization status   NOT AUTHORIZED
Note                   this stage specifies the mapping; it does NOT modify RBAC code
```

### ARCH1-G08 — Verified human identity

```text
Current state          ABSENT; only sandbox/test operator identity exists
Required contract      read-model-and-security-boundary.md section 2
Backend dependency     none in 66D
Identity dependency    RA-2 (RA2-D01..D12 decided, RA-2I0 onward NOT AUTHORIZED)
Risk                   CRITICAL -- ACCEPT/REJECT require a verified human actor
Owner                  RA-2 track
Recommended slice      RA-2I0 onward, outside Step 66D
Authorization status   NOT AUTHORIZED
```

### ARCH1-G09 — Transactional outbox for delivery events

```text
Current state          outbox pattern exists for clarification; no delivery outbox
Required contract      ADR-66D-08
Backend dependency     Step 66D-BE4
Risk                   MEDIUM
Owner                  Claude Code
Recommended slice      Step 66D-BE4
Authorization status   NOT AUTHORIZED
```

### ARCH1-G10 — Unified read model

```text
Current state          ABSENT
Required contract      read-model-and-security-boundary.md section 1
Backend dependency     Step 66D-BE4
Frontend dependency    Step 66D-FE1
UX dependency          Step 66D-DESIGN
POC.0 dependency       YES -- IA option still unselected
Risk                   HIGH
Owner                  Claude Code
Recommended slice      Step 66D-BE4
Authorization status   NOT AUTHORIZED
```

### ARCH1-G11 — Legacy DeliveryPackage references

```text
Current state          legacy object implemented; no reference field on any new aggregate
Required contract      ADR-66D-05; legacy_delivery_package_refs
Backend dependency     Step 66D-BE1
Risk                   LOW
Owner                  Claude Code
Recommended slice      Step 66D-BE1
Authorization status   NOT AUTHORIZED
```

### ARCH1-G12 — Cost and external-action accounting

```text
Current state          llm_budget exists; no per-submission summary
Required contract      api-event-audit-contracts.md section 6
Backend dependency     Step 66D-BE4
Risk                   MEDIUM
Owner                  Claude Code
Recommended slice      Step 66D-BE4
Authorization status   NOT AUTHORIZED
```

### ARCH1-G13 — DLQ evidence integration

```text
Current state          retry-scheduler and outbox relay exist; not surfaced in review
Required contract      read-model-and-security-boundary.md section 1
Backend dependency     Step 66D-BE4
Risk                   MEDIUM -- absent DLQ evidence must render UNKNOWN, never "healthy"
Owner                  Claude Code
Recommended slice      Step 66D-BE4
Authorization status   NOT AUTHORIZED
```

### ARCH1-G14 — Frontend interaction

```text
Current state          ABSENT; only the legacy DeliveryPackage page exists
Required contract      Delivery Inbox and Delivery Review surfaces
Backend dependency     Step 66D-BE2, BE3, BE4
Frontend dependency    Step 66D-FE1, Step 66D-FE2
UX dependency          Step 66D-DESIGN
POC.0 dependency       YES -- IA option still unselected
Risk                   HIGH
Owner                  Codex / Claude Design
Recommended slice      Step 66D-FE1, Step 66D-FE2
Authorization status   NOT AUTHORIZED
```

---

## 2. Gap tally

```text
Total gaps                14
Authorized                 0
Implemented                0
CRITICAL                   3   (G04, G07, G08)
HIGH                       5   (G01, G02, G03, G05, G10, G14 -- G14 counted HIGH)
MEDIUM                     4   (G06, G09, G12, G13)
LOW                        1   (G11)
Identity-dependent         3   (G04, G07, G08)
POC.0-dependent            2   (G10, G14)
```

## 3. Implementation slice plan

No slice below is authorized. Each requires its own explicit Product Owner authorization.

### Step 66D-DESIGN

```text
executor              Claude Design
scope                 UX/IA and interaction specification for Delivery Inbox and Delivery Review
dependency            this contract freeze merged; POC.0 IA option selected
risk                  MEDIUM -- IA choice is still open and owned elsewhere
review level          design review
acceptance evidence   interaction spec covering all six actions, three decisions and follow-ups
authorization status  NOT AUTHORIZED
```

### Step 66D-BE1 — Persistence and domain models

```text
executor              Claude Code
scope                 DeliverySubmission, DeliveryReviewTask, DeliveryReviewAction,
                      ProductOwnerDecision, AcceptanceFollowUpItem schemas and migrations
dependency            contract freeze merged
risk                  HIGH -- first migration in this domain; immutability must be structural
review level          technical + security review
acceptance evidence   migration up/down, model tests, immutability tests, CAS tests
authorization status  NOT AUTHORIZED
```

### Step 66D-BE2 — Submission and review task APIs

```text
executor              Claude Code
scope                 submission lifecycle endpoints, review task assignment, TASK_ROLES mapping
dependency            Step 66D-BE1
risk                  HIGH -- capability mapping touches RBAC
review level          technical + security review
acceptance evidence   endpoint tests, RBAC denial tests, cross-project 404 masking tests
authorization status  NOT AUTHORIZED
```

### Step 66D-BE3 — Review action, decision and follow-up APIs

```text
executor              Claude Code
scope                 the six Review Gate Actions, the three final decisions, supersession,
                      follow-ups, bounded QA rerun enforcement
dependency            Step 66D-BE1, Step 66D-BE2
risk                  CRITICAL -- ADR-66D-10 atomicity and ADR-66D-09 bound live here
review level          technical + security review + independent review
acceptance evidence   atomicity tests, idempotency tests, 409 QA_RERUN_LIMIT_REACHED test,
                      blocking follow-up rejection test, supersession test
authorization status  NOT AUTHORIZED
```

### Step 66D-BE4 — Events, outbox, audit and read model

```text
executor              Claude Code
scope                 durable events, transactional outbox, audit actions, unified read model
dependency            Step 66D-BE1..BE3
risk                  HIGH
review level          technical review
acceptance evidence   outbox tests, event envelope tests, stale-indicator and UNKNOWN tests
authorization status  NOT AUTHORIZED
```

### Step 66D-FE1 — Delivery Inbox and Delivery Review observation

```text
executor              Codex
scope                 read-only surfaces
dependency            Step 66D-BE2, Step 66D-DESIGN, POC.0 IA selection
risk                  MEDIUM
review level          UI review
acceptance evidence   observation-only tests; no action affordances
authorization status  NOT AUTHORIZED
```

### Step 66D-FE2 — Review actions, decisions and follow-up interaction

```text
executor              Codex
scope                 action and decision affordances, follow-up management
dependency            Step 66D-BE3, Step 66D-FE1
risk                  HIGH -- this is where an operator can accept work
review level          UI review + security review
acceptance evidence   capability-gated affordance tests; no client-side rerun counter
authorization status  NOT AUTHORIZED
```

### Step 66D-QA — Combined verification

```text
executor              Claude Code
scope                 contract/runtime/UI/security verification across the whole slice set
dependency            all preceding slices
risk                  MEDIUM
review level          independent review
acceptance evidence   end-to-end acceptance flow on the internal test runtime
authorization status  NOT AUTHORIZED
```

## 4. Naming reconciliation

`main` already uses `Step 66D-BE*` / `Step 66D-FE*` naming in the master plan family. The slice
names above adopt that existing convention rather than introducing a parallel scheme. No duplicate
stage is created. Where a future canonical name differs, the mapping is: this document's
`Step 66D-BE1..BE4` and `Step 66D-FE1..FE2` are the delivery-acceptance slices, distinct from the
Step 66C.4 `BE1..BE3` reminder/expiry slices, which are unrelated and already merged.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
