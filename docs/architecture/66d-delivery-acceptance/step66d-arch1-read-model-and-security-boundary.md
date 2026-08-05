# Step 66D-ARCH1 — Read Model and Security Boundary

> **Specification only. No read model, projector, cache or endpoint is implemented.
> `production_executed_true_count: 0`.**

## 1. POC Control Center unified read model

A project-level read model that answers "what is the state of this project's work, and what is
waiting on me" without the operator visiting six pages.

```text
read_model_id           project_delivery_control_center
Granularity             one document per project_id
Nature                  DERIVED. Never a source of truth. Never written to directly.
```

### Required content

```text
development goal                requirements baseline
project                         acceptance criteria
work items                      workflow / run
runtime agent activities        external AI partner activities
artifacts                       source-control evidence
approvals                       blockers
failures                        retry / DLQ evidence
QA status                       DeliverySubmission
DeliveryReviewTask              Review Gate Action history
Product Owner Decision          follow-up items
cost summary                    external-action summary
safety summary                  legacy DeliveryPackage refs
```

### Semantics

```text
data sources            delivery domain events + existing project/work-item/run/QA/audit sources
refresh semantics       event-driven projection, rebuildable from the event log
consistency             EVENTUALLY CONSISTENT -- explicitly, not incidentally
stale indicator         REQUIRED. Every response carries as_of and is_stale.
missing-data behavior   an absent source renders as UNKNOWN, never as zero, empty or healthy
authorization           per-project; cross-project access denied and masked as 404
redaction               applied at projection time
```

The stale indicator and the `UNKNOWN` rule exist for one reason: a control centre that renders a
missing input as "0 failures" or "no blockers" tells the operator the opposite of the truth.
Absence of data must be visible as absence.

### Not decided here

```text
Information architecture:  Unified Control Center  vs  Coordinated Existing Routes
Status:                    STILL OPEN
Owner:                     Step 67POC.0 / Step 66D-DESIGN
```

This stage specifies **what data the surface must be able to show**. It does not choose the
navigation model, the page structure or the route layout. Choosing one here would pre-empt a
decision that has an explicit owner.

## 2. Security and redaction boundary

### Never persisted, never returned, never logged

```text
private chain of thought        raw model tokens
secrets                         credentials
client secrets                  private keys
actual DSNs                     internal credential identifiers
real account identifiers        unredacted sensitive evidence
```

Secret names may appear as **references only**. Values never appear.

### Identity boundary

```text
Today:   POC sandbox / internal test runtime operator identity
Future:  verified shared-runtime identity, decided by RA-2 (RA2-D01..D12), NOT IMPLEMENTED
```

```text
Request-provided actor_id, role or capability claims are NEVER authoritative.
ACCEPT and REJECT require a verified human actor with Product Owner decision capability.
Until RA-2 identity is implemented, that verified identity does not exist, so a production-grade
acceptance flow cannot be claimed -- only a sandbox one.
```

This is recorded as gap `ARCH1-G08` and is one of the two CRITICAL gaps.

### Authorization posture

```text
Cross-project access        denied, masked as 404 (existence is not leaked)
Cross-team access           denied, masked as 404
Capability check            against TASK_ROLES; specified here, NOT modified here
Two-person control          not required for acceptance; required for production actions,
                            which acceptance does not grant
```

### What acceptance does not authorize

```text
production approval          security approval
identity activation          secret provisioning
deployment                   external provider calls
GitHub writes                notifications
resume / replay execution    feature-gate activation
```

`ACCEPTED` is a statement about delivered work. It is not a permission grant (ADR-66D-07).

## 3. Environment boundary

```text
Target environment       internal test runtime only
Production               NOT TOUCHED, NOT CONFIGURED, NOT REACHABLE from this contract
BE3 resume/replay        DISABLED, all four gates default false
production_executed      false on every audit record
production_executed_true_count   0
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
